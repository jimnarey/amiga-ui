#!/usr/bin/env python3
"""Xvfb-backed end-to-end test: the projected iTidy **Exit** gadget, interactively.

This is the milestone the cooperative host scheduler exists for: one real
end-to-end interaction driven *through the host GUI*, on a single active
context (the GUI thread), with the target staying alive while it waits::

    Qt gadget activation (a real click on the projected Exit button)
      -> semantic gadget event (the bridge's address-based ``gadget_up``)
      -> real IntuiMessage allocation
      -> real Window.UserPort queue
      -> WaitPort resumes (the interactive scheduler parks the target in a
         nested Qt loop; Qt stays responsive, the target stays alive)
      -> GT_GetIMsg removes it
      -> iTidy dispatches the real GadgetID (GID_CANCEL)
      -> GT_ReplyIMsg releases it
      -> iTidy CloseWindow
      -> host projection closes
      -> target + host exit cleanly

The click is located by the widget's *visible text* ("Exit") — that is test
selection only. The translation of the click into an Amiga message is entirely
address-based (the button's recorded real emulated window/gadget addresses); no
``"Exit"`` literal, hard-coded ``GadgetID``, or window title ever appears in the
production path.

The eight things this proves (asserted, not assumed):
1. the real message appears on the real ``UserPort`` (not a fabricated WaitPort
   success);
2. ``WaitPort``, ``GT_GetIMsg`` and ``GT_ReplyIMsg`` all participate;
3. the app handled the genuine ``GadgetID`` (``GID_CANCEL``), not a substitute;
4. ``CloseWindow`` removed the host projection;
5. target + host finished cleanly, with no fabricated event.

Run as a module (needs the ``tests`` package for the launcher fixture)::

    uv run python -m tests.run_interactive_exit_smoke_test
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
# The click happens in well under a second, so this only guards against a
# target that parks and never satisfies the wait (it times out, it never
# fabricates a message).
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

    from amiga_ui.host.qt_projection import QtGadgetButton, QtHostWindowProjection
    from amiga_ui.host.qt_scheduler_backend import QtEventLoopBackend
    from amiga_ui.host.scheduler import CooperativeHostScheduler, WaitOutcome
    from amiga_ui.vamos.event_bridge import IDCMP_GADGETUP
    from amiga_ui.vamos.event_bridge import IntuitionEventBridge
    from amiga_ui.vamos.launcher import run_vamos_in_process
    from tests.test_vamos_launcher import _LauncherRuntimeFixture

    existing_app = QApplication.instance()
    app = existing_app if isinstance(existing_app, QApplication) else QApplication([])
    bridge = IntuitionEventBridge()
    scheduler = CooperativeHostScheduler(QtEventLoopBackend(app))
    scheduler.set_wait_bound(_WAIT_BOUND_SECONDS)

    # Test selection only: locate iTidy's Exit widget by its visible text and
    # click it. The production translation (click -> real IntuiMessage) is
    # address-based, done by the projection + bridge.
    clicked = {"done": False, "gadget_addr": 0}

    def on_window_projected(window_addr: int) -> None:
        def do_click() -> None:
            if clicked["done"]:
                return
            for top in app.topLevelWidgets():
                for button in top.findChildren(QtGadgetButton):
                    if button.text() == "Exit":
                        clicked["gadget_addr"] = button.amiga_gadget_addr
                        clicked["win_addr"] = button.amiga_window_addr
                        clicked["done"] = True
                        # A real Qt click: emits ``clicked`` -> projection wires it
                        # (address-based) to the bridge's ``gadget_up`` -> a real
                        # IntuiMessage is posted on the window's real UserPort.
                        button.click()
                        return

        # A one-shot timer, processed by the nested Qt loop once the target has
        # parked in WaitPort (the window + its buttons exist by then).
        QTimer.singleShot(0, do_click)

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
        clicked=clicked,
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
        if "Cancel button clicked" in stdout_text:
            print("(diagnostics) app printed: Cancel button clicked - closing window", file=sys.stderr)
        return 1
    print("PASS: projected iTidy Exit gadget -> real IntuiMessage -> WaitPort resume -> clean exit", file=sys.stderr)
    return 0


def _check(
    *,
    projection,
    bridge,
    scheduler,
    clicked: dict,
    exit_code: int,
    log_text: str,
    stdout_text: str,
) -> list[str]:
    """Assert the eight milestone conditions. Returns failure reasons (empty = pass)."""

    from amiga_ui.host.scheduler import WaitOutcome
    from amiga_ui.vamos.event_bridge import IDCMP_GADGETUP

    failures: list[str] = []

    # (a) The projected Exit button was actually activated by the test.
    if not clicked["done"]:
        failures.append("the projected Exit button was never activated (no real click occurred)")
        return failures  # nothing further to assert without a click

    # (1) The real message appears on the real UserPort.
    if len(bridge.posted) != 1:
        failures.append(f"expected exactly one posted IntuiMessage, got {len(bridge.posted)}: {bridge.posted}")
    else:
        post = bridge.posted[0]
        if post["idcmp_class"] != IDCMP_GADGETUP:
            failures.append(f"posted message class {post['idcmp_class']:#06x} is not IDCMP_GADGETUP")
        if post["port"] is None or post["port"] == 0:
            failures.append("posted message has no real UserPort")
        # (3) genuine GadgetID: the posted IAddress is the real Exit gadget's
        # address (the one the test located and clicked), not a substitute.
        if post["iaddress"] != clicked["gadget_addr"]:
            failures.append(
                f"posted IAddress {post['iaddress']:#06x} != clicked Exit gadget "
                f"{clicked['gadget_addr']:#06x} (not the real gadget)"
            )

    # (2a) WaitPort participated and was genuinely satisfied (not the honest
    # headless boundary, not a timeout/shutdown).
    if scheduler.last_outcome is not WaitOutcome.SATISFIED:
        failures.append(f"WaitPort outcome is {scheduler.last_outcome!r}, expected SATISFIED")
    if "cooperative wait finished with outcome satisfied" not in log_text:
        failures.append("vamos log does not record a satisfied cooperative WaitPort")

    # (2b) GT_GetIMsg participated: the app drained the message and ran its
    # GID_CANCEL handler (the repo target prints this when the Exit button fires).
    if "Cancel button clicked" not in stdout_text:
        failures.append("app did not run the GID_CANCEL (Exit) handler (GT_GetIMsg drain not observed)")

    # (2c) GT_ReplyIMsg participated: the bridge released the posted message.
    if len(bridge.posted) == 1 and bridge.posted[0]["imsg"] not in bridge.released:
        failures.append("GT_ReplyIMsg did not release the posted IntuiMessage")

    # (4) CloseWindow removed the host projection.
    if projection.windows:
        failures.append(f"host projection still has windows after close: {list(projection.windows)}")

    # (5) Target + host finished cleanly, with no fabricated event.
    if exit_code != 0:
        failures.append(f"target did not exit cleanly (exit_code={exit_code})")

    return failures


if __name__ == "__main__":
    raise SystemExit(main())
