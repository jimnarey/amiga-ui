"""User-invokable GUI launch path: run an Amiga app interactively, projected.

This backs the ``amiga-ui run`` command — the Qt-backed, user-facing
counterpart of ``amiga-ui probe``:

- it reuses the probe's target resolution and prepared runtime setup (the CLI
  builds the same ``-V``/``-a``/``--cwd`` vamos arguments a probe uses; nothing
  here re-implements that preparation),
- it installs a real :class:`~amiga_ui.host.qt_projection.QtHostWindowProjection`
  on the in-process vamos run, so each app-facing Amiga window appears as an
  independent host top-level window (hosted application mode: no desktop
  canvas, no Workbench backdrop),
- it installs the **cooperative host scheduler** (Qt event-loop backend) so a
  supported blocking OS call — today, ``WaitPort`` on an empty ``UserPort`` —
  parks the target's call stack in a nested Qt loop instead of failing. The
  target *stays alive* and Qt *stays responsive* while it waits; a projected
  gadget activation (a real ``IntuiMessage`` on the real ``UserPort``) wakes
  the wait, the target resumes, and only then may the run complete.

The interactive lifecycle has one model (no separate post-target shell loop):
the run phase *is* the interactive session. The target opens its window (the
host window appears, responsive), parks in ``WaitPort`` (the nested loop), and
the run returns when the target exits — either application-driven (the app
handled a genuine event and returned, e.g. the iTidy ``Exit`` gadget) or via an
automation timeout (``--auto-close-after`` / ``--timeout`` bound the wait
honestly; it never fabricates a message). The distinct outcomes
(application-driven completion, host shutdown, automation timeout,
target-phase failure) are reported from the scheduler's terminal outcome plus
the target return code. If the target exits with projected windows still open
(e.g. an automation timeout), a minimal inspection shell is kept.

Threading: the vamos run executes synchronously on the main (GUI) thread; the
nested Qt loop it parks in is that same thread's event service — no
``QThread``/workers are introduced.

Qt-only module: imported lazily by the CLI ``run`` command. The ``probe``
command never imports it, so plain probes stay Qt-free.
"""

from __future__ import annotations

import contextlib
import os
import sys
import tempfile
import traceback
from typing import Any

# The documented target boundary: for the current iTidy increment an
# *uninteractive* run ends here (the app's main loop blocks on an empty
# UserPort). With the interactive scheduler installed this marker is no longer
# the terminal event (the wait is serviced instead), but it is still useful in
# diagnostics to see whether the target actually reached the wait.
_WAITPORT_BOUNDARY_MARKER = "WaitPort on empty message queue"

# --- Interactive-run terminal outcomes (reported, distinct) -------------------
# A single coherent interactive lifecycle: the target parks in WaitPort and the
# run returns when the target exits or the automation bound fires. These are
# the four documented terminal states, kept distinct (the scheduler's terminal
# outcome plus the target return code decide which one).
OUTCOME_APPLICATION_EXITED = 0  # the app handled a real event and returned cleanly
OUTCOME_TARGET_FAILURE = 1  # the target failed (no window, or failed around a wait)
OUTCOME_NO_DISPLAY = 2  # no usable host display
OUTCOME_TIMEOUT = 3  # the automation wait bound expired (honest, no fabricated input)
OUTCOME_HOST_SHUTDOWN = 4  # the host shell is shutting down


def _vamos_log_path(vamos_args: list[str]) -> str | None:
    """Extract the ``-L`` vamos log path from the prepared argument list."""

    for index, arg in enumerate(vamos_args):
        if arg == "-L" and index + 1 < len(vamos_args):
            return vamos_args[index + 1]
    return None


# Qt platforms that render without an external X11/Wayland display.
_SELF_CONTAINED_QT_PLATFORMS = frozenset({"offscreen", "minimal", "minimalegl", "linuxfb", "eglfs", "vnc"})


def _no_display_reason() -> str | None:
    """Return a human reason when no host display is usable, else ``None``.

    Constructing a ``QApplication`` on a platform that needs a display, when
    none is reachable, aborts the whole process (SIGABRT, exit 134) rather
    than raising — so the "fail clearly" requirement can only be met by
    detecting the condition *before* the ``QApplication`` constructor runs.

    We are deliberately conservative: this only reports "no display" when we
    are certain (the requested platform needs an external display and neither
    ``DISPLAY`` nor ``WAYLAND_DISPLAY`` is set). Any uncertainty defers to Qt
    (and the ``RuntimeError`` fallback), so we never block a real display.
    """

    platform = os.environ.get("QT_QPA_PLATFORM", "").strip().lower()
    if platform in _SELF_CONTAINED_QT_PLATFORMS:
        return None  # renders without an external display
    if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
        return None  # a display may exist; let Qt decide
    return (
        "no usable host display: set DISPLAY (X11) or WAYLAND_DISPLAY, or run "
        "with QT_QPA_PLATFORM=offscreen for a headless check"
    )


def run_gui_launch(
    *,
    vamos_args: list[str],
    timeout: int | None = None,
    auto_close_after: float | None = None,
    projection: Any = None,
    event_bridge: Any = None,
    host_scheduler: Any = None,
    window_projected_hook: Any = None,
) -> int:
    """Run the target interactively with a live Qt projection; report its outcome.

    The cooperative host scheduler (Qt event-loop backend) is installed so an
    empty ``WaitPort`` parks the target in a nested Qt loop — the target stays
    alive and Qt stays responsive — until a real event satisfies the wait or the
    automation bound fires. The four distinct terminal outcomes are reported
    (see the ``OUTCOME_*`` constants): application-driven completion, target-phase
    failure, automation timeout, host shutdown (plus ``OUTCOME_NO_DISPLAY``).

    ``projection`` / ``event_bridge`` / ``host_scheduler`` may be pre-created
    (the interactive test drives the production path this way); otherwise they
    are created here (a fresh bridge, a Qt event-loop backend + scheduler, and a
    Qt projection wired to the bridge). When the projection is created here,
    ``window_projected_hook`` is attached to it.
    """

    from PySide6.QtCore import QTimer

    from ..vamos.event_bridge import IntuitionEventBridge
    from .qt_projection import QtHostWindowProjection
    from .qt_scheduler_backend import QtEventLoopBackend
    from .scheduler import CooperativeHostScheduler

    app = _ensure_qapplication()
    if app is None:
        return OUTCOME_NO_DISPLAY

    if event_bridge is None:
        event_bridge = IntuitionEventBridge()
    if host_scheduler is None:
        host_scheduler = CooperativeHostScheduler(QtEventLoopBackend(app))
    if projection is None:
        projection = QtHostWindowProjection(app, event_source=event_bridge, window_projected_hook=window_projected_hook)

    # The automation wait bound: ``--auto-close-after`` (when set) overrides
    # ``--timeout``. Both are honest automation bounds — they terminate the
    # interactive wait (a TIMEOUT), they never fabricate a message. ``None`` /
    # non-positive means "no bound" (purely interactive, no automation timer).
    wait_bound = auto_close_after if auto_close_after else timeout
    if wait_bound and wait_bound > 0:
        host_scheduler.set_wait_bound(float(wait_bound))

    returncode = _run_interactive_target(
        vamos_args=vamos_args,
        event_bridge=event_bridge,
        host_scheduler=host_scheduler,
        projection=projection,
    )
    outcome = _report_outcome(returncode, host_scheduler, projection)

    # The application-driven Exit path closes the target's own window, so no
    # projection remains and the run ends. If the target exited with projected
    # windows still open (e.g. an automation timeout froze a window mid-wait),
    # keep a *minimal* inspection shell (this is not the interactive nested
    # loop — the target is already gone).
    if _describe_projected_windows(projection):
        print("amiga-ui run: projected window(s) remain — close them to exit")
        if auto_close_after:
            QTimer.singleShot(int(auto_close_after * 1000), app.quit)
        app.exec()
        _release_projection(projection)
        print("amiga-ui run: host shell exited; projected windows closed")

    return outcome


def _ensure_qapplication() -> Any | None:
    """Return a live :class:`QApplication`, or ``None`` when no display is usable.

    Constructing a ``QApplication`` on a display-requiring platform with none
    reachable aborts the whole process (SIGABRT) rather than raising, so the
    "fail clearly" path is taken by detecting the condition first (see
    :func:`_no_display_reason`).
    """

    from PySide6.QtWidgets import QApplication

    existing = QApplication.instance()
    if isinstance(existing, QApplication):
        return existing
    reason = _no_display_reason()
    if reason is not None:
        print(f"amiga-ui run: {reason}", file=sys.stderr)
        print("amiga-ui run: run on a graphical desktop, or use an Xvfb display", file=sys.stderr)
        return None
    try:
        return QApplication(sys.argv)
    except RuntimeError as exc:
        # Fallback for builds/configs where Qt raises instead of aborting.
        print(f"amiga-ui run: no usable host display ({exc})", file=sys.stderr)
        print("amiga-ui run: run on a graphical desktop, or use an Xvfb display", file=sys.stderr)
        return None


def _run_interactive_target(
    *,
    vamos_args: list[str],
    event_bridge: Any,
    host_scheduler: Any,
    projection: Any,
) -> int:
    """Execute the in-process vamos run interactively; return the target code.

    The run installs the event bridge, the cooperative host scheduler and the
    projection on the vamos context (via the ``event_bridge`` / ``scheduler`` /
    ``host_projection`` context attributes). The target opens its window (the
    host window appears), parks in ``WaitPort`` (the nested Qt loop — Qt stays
    responsive and the target stays alive), and the run returns when the target
    exits (application-driven) or the automation wait bound fires.

    The interactive wait is bounded by the scheduler's wait bound (a one-shot
    QTimer in the Qt backend), **not** a SIGALRM: a SIGALRM would fire inside
    the nested loop, during a Qt event dispatch, and corrupt the Qt state. A
    target that never reaches a supported wait (fails during startup) is not
    separately bounded here (fast for the current target; documented limit).
    Output is captured to files (vamos needs a real stdout buffer).
    """

    from ..vamos.launcher import run_vamos_in_process

    returncode = 1
    with (
        tempfile.NamedTemporaryFile("w+", encoding="utf-8") as stdout_file,
        tempfile.NamedTemporaryFile("w+", encoding="utf-8") as stderr_file,
    ):
        try:
            with (
                contextlib.redirect_stdout(stdout_file),
                contextlib.redirect_stderr(stderr_file),
            ):
                returncode = run_vamos_in_process(
                    args=vamos_args,
                    event_bridge=event_bridge,
                    host_projection=projection,
                    host_scheduler=host_scheduler,
                )
        except Exception:
            traceback.print_exc()
    return returncode


def _report_outcome(returncode: int, host_scheduler: Any, projection: Any) -> int:
    """Map (target return code, scheduler terminal outcome) to a distinct outcome.

    The scheduler's terminal outcome (:attr:`CooperativeHostScheduler.last_outcome`)
    is the authority on *how the interactive wait ended*; the target return code
    says *whether the target survived*. Only a genuinely satisfied wait plus a
    clean target return is an application-driven completion. The four states:

    - application-driven completion (target returned 0): the app handled a real
      event and exited;
    - automation timeout (the wait bound expired): honest, no fabricated input;
    - host shutdown (the host shell is shutting down);
    - target-phase failure (the target returned non-zero, with or without having
      reached an interactive wait).
    """

    from .scheduler import WaitOutcome

    outcome = getattr(host_scheduler, "last_outcome", None)

    if returncode == 0:
        if outcome is WaitOutcome.SATISFIED:
            print("amiga-ui run: target exited cleanly after a satisfied wait (application-driven)")
        elif outcome is None:
            print("amiga-ui run: target exited cleanly (no interactive wait was reached)")
        else:
            # A wait ended non-satisfied yet the target still returned 0: the
            # target's own exit code is the authority for completion, but report
            # the wait's outcome for diagnostics.
            print(f"amiga-ui run: target exited cleanly (last interactive wait outcome: {outcome.value})")
        return OUTCOME_APPLICATION_EXITED

    if outcome is WaitOutcome.TIMEOUT:
        print(
            "amiga-ui run: the interactive wait timed out (automation bound); no message was fabricated",
            file=sys.stderr,
        )
        return OUTCOME_TIMEOUT
    if outcome is WaitOutcome.SHUTDOWN:
        print("amiga-ui run: the host shell is shutting down", file=sys.stderr)
        return OUTCOME_HOST_SHUTDOWN

    # Target-phase failure: the target returned non-zero. Distinguish the
    # sub-cases for diagnostics (no window projected, failed before any wait, or
    # failed after a satisfied wait).
    if not _has_projected_windows(projection):
        print("amiga-ui run: target failed and no app-facing window was projected", file=sys.stderr)
    elif outcome is None:
        print(
            f"amiga-ui run: target failed (code {returncode}) before reaching an interactive wait",
            file=sys.stderr,
        )
    elif outcome is WaitOutcome.SATISFIED:
        print(
            f"amiga-ui run: target failed (code {returncode}) after a satisfied wait "
            "(the real event was delivered; the target then failed)",
            file=sys.stderr,
        )
    else:
        print(
            f"amiga-ui run: target failed (code {returncode}); last interactive wait outcome: {outcome.value}",
            file=sys.stderr,
        )
    return OUTCOME_TARGET_FAILURE


def _has_projected_windows(projection: Any) -> bool:
    """Whether the projection still owns at least one live host window."""

    windows = getattr(projection, "windows", None) or {}
    return any(getattr(projected, "host_window", None) is not None for projected in windows.values())


def _describe_projected_windows(projection: Any) -> bool:
    """Print one line per projected app-facing window; return whether any exist."""

    windows = getattr(projection, "windows", None) or {}
    if not windows:
        return False
    for window_addr, projected in windows.items():
        host_window = getattr(projected, "host_window", None)
        if host_window is None:
            continue
        intent = getattr(projected, "intent", None)
        title = getattr(intent, "title", "") or "(untitled)"
        print(
            f"amiga-ui run: projected window {window_addr:06x}: "
            f"title={title!r} size={host_window.width()}x{host_window.height()}"
        )
    return _has_projected_windows(projection)


def _release_projection(projection: Any) -> None:
    """Close every remaining projected window and drop the projection's state."""

    windows = dict(getattr(projection, "windows", None) or {})
    for window_addr in list(windows):
        projection.close_window(window_addr)


def _read_text(path: str) -> str:
    with open(path, encoding="utf-8", errors="replace") as handle:
        return handle.read()
