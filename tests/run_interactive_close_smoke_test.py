#!/usr/bin/env python3
"""Xvfb-backed end-to-end test: the host window **close control**, interactively.

The counterpart of ``run_interactive_exit_smoke_test.py`` for the *other* way
an app window ends: not the projected Exit gadget, but the host window
manager's close request. The whole point of "Window Close Semantics"
(``docs/architecture/cooperative-host-scheduler.md``) is that the host close
control is a *request* the app owns — this test proves the real route end to
end, on a single active context (the GUI thread), with the target alive and
parked in ``WaitPort`` while the request is in flight::

    Qt host close request (``AmigaHostWindow.close()`` — the spontaneous
    ``QCloseEvent`` a window manager's close gadget delivers)
      -> closeEvent refuses to destroy the widget (the app owns the lifetime)
      -> projection forwards the request by the widget's real ``struct Window *``
      -> bridge posts a real ``IDCMP_CLOSEWINDOW`` ``IntuiMessage``
      -> real Window.UserPort queue
      -> WaitPort resumes (the scheduler parks the target in a nested Qt loop;
         Qt stays responsive, the target stays alive)
      -> GT_GetIMsg removes it
      -> iTidy dispatches the real Class (``IDCMP_CLOSEWINDOW``) itself
      -> GT_ReplyIMsg releases it
      -> iTidy exits its event loop and calls CloseWindow *itself*
      -> projection releases the host window (the only destruction path)
      -> target + host exit cleanly

Which window gets the close request is test selection (the projected host
window located through the projection's own address map); the translation of
the request into an Amiga message is entirely address-based, keyed by the real
``struct Window *`` the widget carries. Under Xvfb there is no title bar to
click, so the test issues the request with ``QWidget.close()`` — the same
spontaneous ``QCloseEvent`` entry point the widget-level deferral tests in
``tests/test_qt_window_close.py`` pin down. Nothing else about the route is
simulated: the message, the port queue, the resume and the window release all
happen because the app did them.

The seven things this proves (asserted, not assumed):
1. the close request was *deferred*, not self-destroyed: at request time the
   host widget stayed open and the request left through the bridge;
2. the real message appears on the real ``UserPort``, class
   ``IDCMP_CLOSEWINDOW``, targeting exactly the window whose close control was
   pressed (and nothing else was posted — no fabricated gadget event instead);
3. ``WaitPort``, ``GT_GetIMsg`` and ``GT_ReplyIMsg`` all participate;
4. the app handled the genuine ``IDCMP_CLOSEWINDOW`` class itself (its own
   shutdown banner, then its own window-close path in stdout);
5. ``CloseWindow`` removed the host projection *and* the host widget went away
   — through the app's release path, not the request;
6. target + host finished cleanly, with no fabricated event.

Run as a module (needs the ``tests`` package for the launcher fixture)::

    uv run python -m tests.run_interactive_close_smoke_test
"""

from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

from amiga_ui.config import PROJECT_ROOT
from amiga_ui.host.xvfb import XvfbError, start_xvfb

_ITIDY_APP_DIR = PROJECT_ROOT / "amiga_apps/itidy1classic/binary/extracted"

# Automation wait bound (seconds): honest termination of the interactive wait.
# The close request happens in well under a second, so this only guards
# against a target that parks and never satisfies the wait (it times out, it
# never fabricates a message).
_WAIT_BOUND_SECONDS = 15.0


@contextmanager
def _apply_session_environment(session):
    """Point ``DISPLAY``/``QT_QPA_PLATFORM`` at the Xvfb session for this block."""

    tracked_keys = ("DISPLAY", "QT_QPA_PLATFORM")
    previous = {key: os.environ.get(key) for key in tracked_keys}
    env = session.build_env()
    try:
        os.environ["DISPLAY"] = env["DISPLAY"]
        os.environ["QT_QPA_PLATFORM"] = env["QT_QPA_PLATFORM"]
        yield
    finally:
        for key, previous_value in previous.items():
            if previous_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = previous_value


def main() -> int:
    import faulthandler

    faulthandler.enable()
    if not (_ITIDY_APP_DIR / "iTidy").is_file():
        print("SKIP: iTidy binary not present in the working tree", file=sys.stderr)
        return 0
    try:
        session = start_xvfb()
    except XvfbError as exc:
        print(f"SKIP: Xvfb unavailable ({exc})", file=sys.stderr)
        return 0

    with session, _apply_session_environment(session):
        return _run(_ITIDY_APP_DIR)


def _run(app_dir: Path) -> int:
    # Import Qt only after the environment is configured (xcb display, not offscreen).
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from amiga_ui.host.qt_projection import QtHostWindowProjection
    from amiga_ui.host.qt_scheduler_backend import QtEventLoopBackend
    from amiga_ui.host.scheduler import CooperativeHostScheduler
    from amiga_ui.vamos.event_bridge import IntuitionEventBridge
    from amiga_ui.vamos.launcher import run_vamos_in_process
    from tests.test_vamos_launcher import _LauncherRuntimeFixture

    existing_app = QApplication.instance()
    app = existing_app if isinstance(existing_app, QApplication) else QApplication([])
    bridge = IntuitionEventBridge()
    scheduler = CooperativeHostScheduler(QtEventLoopBackend(app))
    scheduler.set_wait_bound(_WAIT_BOUND_SECONDS)

    # Test selection only: press the close control of the projected host
    # window (the first app-facing window the projection shows — for this
    # target that is iTidy's main window). The production translation (close
    # request -> real IntuiMessage) is address-based, done by the widget +
    # projection + bridge.
    triggered: dict = {"done": False}

    def on_window_projected(window_addr: int) -> None:
        def do_close() -> None:
            if triggered["done"]:
                return
            widget = projection.host_window(window_addr)
            if widget is None:
                return
            triggered["done"] = True
            triggered["win_addr"] = widget.amiga_window_addr
            triggered["widget"] = widget
            # A real host close request: the spontaneous QCloseEvent a window
            # manager's close gadget delivers. With the bridge wired, the
            # widget must *refuse* it (defer to the app) and forward the
            # request by address — a close() that destroys the widget here
            # would be the host fabricating the app's close decision.
            triggered["deferred"] = not widget.close()
            triggered["visible_after_request"] = widget.isVisible()

        # A one-shot timer, processed by the nested Qt loop once the target
        # has parked in WaitPort (the window exists by then).
        QTimer.singleShot(0, do_close)

    projection = QtHostWindowProjection(app, event_source=bridge, window_projected_hook=on_window_projected)

    with tempfile.TemporaryDirectory() as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        runtime = _LauncherRuntimeFixture.create(temp_dir)
        vamos_log_path = temp_dir / "vamos.log"
        exit_code = -1
        with tempfile.NamedTemporaryFile("w+", encoding="utf-8") as app_stdout_file:
            # A real file (with ``.buffer``) for stdout — vamos's dos FileManager
            # wraps ``sys.stdout.buffer``; a StringIO would break it.
            with contextlib.redirect_stdout(app_stdout_file), contextlib.redirect_stderr(io.StringIO()):
                exit_code = run_vamos_in_process(
                    args=runtime.build_itidy_args(app_dir=app_dir, vamos_log_path=vamos_log_path),
                    event_bridge=bridge,
                    host_projection=projection,
                    host_scheduler=scheduler,
                )
            app_stdout_file.flush()
            app_stdout_file.seek(0)
            stdout_text = app_stdout_file.read()
        log_text = vamos_log_path.read_text(encoding="utf-8") if vamos_log_path.is_file() else ""
    app.processEvents()
    failures = _check(
        projection=projection,
        bridge=bridge,
        scheduler=scheduler,
        triggered=triggered,
        exit_code=exit_code,
        log_text=log_text,
        stdout_text=stdout_text,
    )
    for addr in list(projection.windows):
        projection.close_window(addr)
    app.processEvents()

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        print(f"(diagnostics) exit_code={exit_code} last_outcome={scheduler.last_outcome}", file=sys.stderr)
        print(f"(diagnostics) posted={bridge.posted}", file=sys.stderr)
        print(f"(diagnostics) released={bridge.released}", file=sys.stderr)
        print(f"(diagnostics) skipped={bridge.skipped}", file=sys.stderr)
        if "Close gadget clicked" in stdout_text:
            print("(diagnostics) app printed: Close gadget clicked - shutting down", file=sys.stderr)
        return 1
    print(
        "PASS: host window close control -> real IDCMP_CLOSEWINDOW -> WaitPort resume "
        "-> app's own CloseWindow -> host window closed -> clean exit",
        file=sys.stderr,
    )
    return 0


def _check(
    *,
    projection,
    bridge,
    scheduler,
    triggered: dict,
    exit_code: int,
    log_text: str,
    stdout_text: str,
) -> list[str]:
    """Assert the milestone conditions. Returns failure reasons (empty = pass)."""

    from PySide6.QtCore import QCoreApplication
    from shiboken6 import isValid as _isValid

    from amiga_ui.host.scheduler import WaitOutcome
    from amiga_ui.vamos.event_bridge import IDCMP_CLOSEWINDOW

    failures: list[str] = []

    # (a) The projected host window's close control was actually pressed.
    if not triggered["done"]:
        failures.append("the host window close control was never exercised (no close request occurred)")
        return failures  # nothing further to assert without the request

    # (1) The request was deferred, not self-destroyed: the widget refused the
    # close (app owns the lifetime) and was still open right after it.
    if not triggered["deferred"]:
        failures.append("the host window destroyed itself on the close request instead of deferring to the app")
    if not triggered["visible_after_request"]:
        failures.append("the host widget was not visible anymore right after the close request (it must stay open)")

    # (2) Exactly one posted message, of the real close class, on the real
    # UserPort, for exactly the window whose close control was pressed.
    if len(bridge.posted) != 1:
        failures.append(f"expected exactly one posted IntuiMessage, got {len(bridge.posted)}: {bridge.posted}")
    else:
        post = bridge.posted[0]
        if post["idcmp_class"] != IDCMP_CLOSEWINDOW:
            failures.append(f"posted message class {post['idcmp_class']:#06x} is not IDCMP_CLOSEWINDOW")
        if post["port"] is None or post["port"] == 0:
            failures.append("posted message has no real UserPort")
        if post["window"] != triggered["win_addr"]:
            failures.append(
                f"posted message targets window {post['window']:#06x}, not the closed "
                f"host window {triggered['win_addr']:#06x} (not address-based)"
            )

    # (3a) WaitPort participated and was genuinely satisfied (not the honest
    # headless boundary, not a timeout/shutdown).
    if scheduler.last_outcome is not WaitOutcome.SATISFIED:
        failures.append(f"WaitPort outcome is {scheduler.last_outcome!r}, expected SATISFIED")
    if "cooperative wait finished with outcome satisfied" not in log_text:
        failures.append("vamos log does not record a satisfied cooperative WaitPort")

    # (3b) GT_GetIMsg participated: the app drained the message and ran its own
    # IDCMP_CLOSEWINDOW handler (the repo target prints this on a close request).
    if "Close gadget clicked - shutting down" not in stdout_text:
        failures.append("app did not run its IDCMP_CLOSEWINDOW handler (GT_GetIMsg drain not observed)")

    # (3c) GT_ReplyIMsg participated: the bridge released the posted message.
    if len(bridge.posted) == 1 and bridge.posted[0]["imsg"] not in bridge.released:
        failures.append("GT_ReplyIMsg did not release the posted IntuiMessage")

    # (4) The app closed the window itself: its own CloseWindow path ran
    # (stdout), the projection record is gone, and the host widget went away —
    # through the release path, not the request (checked by (1) above).
    if "Closing iTidy main window" not in stdout_text:
        failures.append("app never reached its own CloseWindow path (close_itidy_main_window banner not printed)")
    if projection.windows:
        failures.append(f"host projection still has windows after close: {list(projection.windows)}")
    widget = triggered["widget"]
    if _isValid(widget):
        # Let the release path's deferred teardown settle before reading
        # visibility (``close_window`` calls ``deleteLater``).
        QCoreApplication.sendPostedEvents(widget, _deferred_delete_event())
    if _isValid(widget) and widget.isVisible():
        failures.append("the host widget is still visible although the app closed its window")

    # (5) Target + host finished cleanly, with no fabricated event.
    if exit_code != 0:
        failures.append(f"target did not exit cleanly (exit_code={exit_code})")

    return failures


def _deferred_delete_event():
    from PySide6.QtCore import QEvent

    return QEvent.Type.DeferredDelete


if __name__ == "__main__":
    raise SystemExit(main())
