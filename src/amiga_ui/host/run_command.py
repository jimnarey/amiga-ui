"""User-invokable GUI launch path: run an Amiga app and keep its projected windows.

This backs the ``amiga-ui run`` command — the Qt-backed, user-facing
counterpart of ``amiga-ui probe``:

- it reuses the probe's target resolution and prepared runtime setup (the CLI
  builds the same ``-V``/``-a``/``--cwd`` vamos arguments a probe uses; nothing
  here re-implements that preparation),
- it installs a real :class:`~amiga_ui.host.qt_projection.QtHostWindowProjection`
  on the in-process vamos run, so each app-facing Amiga window appears as an
  independent host top-level window (hosted application mode: no desktop
  canvas, no Workbench backdrop),
- after the target run ends it keeps the host shell (the Qt event loop) alive
  so the developer can inspect the projected windows. The shell exits when the
  last projected window is closed (default) or after ``auto_close_after``
  seconds (automation), then releases every projected window.

The target reaching its ``WaitPort`` boundary and the host shell exiting are
distinct, reported events: the run phase ends when the in-process vamos run
returns (for the current target, the documented WaitPort-on-empty-queue
boundary), and the shell only exits afterwards when the user (or the
automation timer) closes the windows.

Threading: the vamos run executes synchronously on the main (GUI) thread and
the Qt event loop only starts after it returns — no ``QThread``/workers are
introduced.

Qt-only module: imported lazily by the CLI ``run`` command. The ``probe``
command never imports it, so plain probes stay Qt-free.
"""

from __future__ import annotations

import contextlib
import os
import signal
import sys
import tempfile
import traceback
from typing import Any

# The documented target boundary: for the current iTidy increment the run ends
# here (the app's main loop blocks on an empty UserPort). Detecting the marker
# in the vamos log is how the command distinguishes "honest boundary" from
# "target exited cleanly" from "target failed elsewhere".
_WAITPORT_BOUNDARY_MARKER = "WaitPort on empty message queue"


class RunTimeoutError(Exception):
    """Raised when the target run phase exceeds its time limit."""


@contextlib.contextmanager
def _run_timeout(timeout_seconds: int | None):
    """Bound the target run phase with SIGALRM (cleared before the Qt loop)."""

    if not timeout_seconds:
        yield
        return

    def handle_timeout(signum, frame):
        raise RunTimeoutError()

    previous_handler = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, handle_timeout)
    signal.setitimer(signal.ITIMER_REAL, timeout_seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)


def _vamos_log_path(vamos_args: list[str]) -> str | None:
    """Extract the ``-L`` vamos log path from the prepared argument list."""

    for index, arg in enumerate(vamos_args):
        if arg == "-L" and index + 1 < len(vamos_args):
            return vamos_args[index + 1]
    return None


# Qt platforms that render without an external X11/Wayland display.
_SELF_CONTAINED_QT_PLATFORMS = frozenset(
    {"offscreen", "minimal", "minimalegl", "linuxfb", "eglfs", "vnc"}
)


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
) -> int:
    """Run the target with a live Qt projection and keep the shell until closed.

    Returns 0 when the projected shell entered and exited cleanly, 1 when the
    target run produced no app-facing window (or failed before one opened),
    and 2 when no usable host display is available. ``projection`` may be a
    pre-created :class:`QtHostWindowProjection` (tests); otherwise one is
    created here.
    """

    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from .qt_projection import QtHostWindowProjection

    existing = QApplication.instance()
    if isinstance(existing, QApplication):
        app = existing
    else:
        reason = _no_display_reason()
        if reason is not None:
            print(f"amiga-ui run: {reason}", file=sys.stderr)
            print("amiga-ui run: run on a graphical desktop, or use an Xvfb display", file=sys.stderr)
            return 2
        try:
            app = QApplication(sys.argv)
        except RuntimeError as exc:
            # Fallback for builds/configs where Qt raises instead of aborting.
            print(f"amiga-ui run: no usable host display ({exc})", file=sys.stderr)
            print("amiga-ui run: run on a graphical desktop, or use an Xvfb display", file=sys.stderr)
            return 2

    if projection is None:
        projection = QtHostWindowProjection(app)

    exit_code = _run_target_phase(vamos_args=vamos_args, timeout=timeout, projection=projection)
    if exit_code is None:
        return 2

    if not _describe_projected_windows(projection):
        print("amiga-ui run: no app-facing window was projected; nothing to inspect", file=sys.stderr)
        return 1

    print("amiga-ui run: host shell active — close the window(s) to exit")
    if auto_close_after:
        QTimer.singleShot(int(auto_close_after * 1000), app.quit)
    app.exec()

    _release_projection(projection)
    print("amiga-ui run: host shell exited; projected windows closed")
    return 0


def _run_target_phase(
    *,
    vamos_args: list[str],
    timeout: int | None,
    projection: Any,
) -> int | None:
    """Execute the in-process vamos run (with the projection) and report its end.

    Returns the target return code, or ``None`` when the run could not even
    start. Output is captured to files (vamos needs a real stdout buffer) and
    the run is bounded by ``timeout``.
    """

    from ..vamos.launcher import run_vamos_in_process

    with (
        tempfile.NamedTemporaryFile("w+", encoding="utf-8") as stdout_file,
        tempfile.NamedTemporaryFile("w+", encoding="utf-8") as stderr_file,
    ):
        returncode = 1
        try:
            with (
                contextlib.redirect_stdout(stdout_file),
                contextlib.redirect_stderr(stderr_file),
                _run_timeout(timeout),
            ):
                returncode = run_vamos_in_process(args=vamos_args, host_projection=projection)
        except RunTimeoutError:
            print(
                f"amiga-ui run: target run exceeded the {timeout}s timeout; "
                "the host shell is not started",
                file=sys.stderr,
            )
            return returncode
        except Exception:
            traceback.print_exc()
            return returncode

        stdout_file.flush()
        stderr_file.flush()
        stdout_file.seek(0)
        stderr_file.seek(0)
        stdout_text = stdout_file.read()
        stderr_text = stderr_file.read()

    log_text = ""
    log_path = _vamos_log_path(vamos_args)
    if log_path:
        with contextlib.suppress(OSError):
            log_text = _read_text(log_path)

    if returncode == 0:
        print("amiga-ui run: target exited cleanly (no WaitPort boundary)")
    elif _WAITPORT_BOUNDARY_MARKER in log_text or _WAITPORT_BOUNDARY_MARKER in stdout_text:
        print(
            "amiga-ui run: target reached its documented WaitPort-on-empty-queue "
            "boundary; the run phase ended, the host shell stays open"
        )
    else:
        print(
            f"amiga-ui run: target run ended with code {returncode} "
            "(not the documented WaitPort boundary); see the run output above"
        )
        if stderr_text.strip():
            print(stderr_text.strip(), file=sys.stderr)
    return returncode


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
    return True


def _release_projection(projection: Any) -> None:
    """Close every remaining projected window and drop the projection's state."""

    windows = dict(getattr(projection, "windows", None) or {})
    for window_addr in list(windows):
        projection.close_window(window_addr)


def _read_text(path: str) -> str:
    with open(path, encoding="utf-8", errors="replace") as handle:
        return handle.read()
