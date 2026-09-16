#!/usr/bin/env python3
"""Xvfb-backed end-to-end test: the LHA-not-found ``EasyRequestArgs`` dialog, interactively.

The interactive counterpart of the Qt-free round-trip tests
(``tests/test_easy_request_args.py`` and ``tests/test_qt_easy_request_dialog.py``)
for the *real* call site: iTidy's LHA-not-found "Continue without backups?"
dialog (``amiga_apps/itidy1classic/source/src/GUI/main_window.c``, the
``GID_APPLY`` handler). The whole point of a genuinely *blocking*
``EasyRequestArgs`` is that the emulated call parks the target, opens a real
host ``QMessageBox`` parented to the app's own window, waits for the user's
actual button choice, and returns the real classic result code (nonzero for the
positive gadget, 0 for the negative/cancel) back into the call — not a
fabricated default. This test proves that end to end, on a single active
context (the GUI thread), with the target alive and parked while the dialog is
up::

    user clicks the projected "Backup icons using LhA" checkbox
      -> bridge toggles the host-side checked state (registry) and posts a real
         IDCMP_GADGETUP IntuiMessage by the gadget's real address
      -> WaitPort resumes -> iTidy's GID_BACKUP handler reads the state back via
         GT_GetGadgetAttrs(GTCB_Checked) and sets enable_backup = TRUE
    user clicks the projected "Start" (GID_APPLY) button
      -> GID_APPLY syncs prefs->enable_backup = TRUE, sees LHA missing in the
         prepared runtime (no LHA in C:/SYS:)
      -> ShowEasyRequest -> __EasyRequestArgs LVO 588
      -> projection opens a real QMessageBox parented to iTidy's host window
         and blocks in exec() (a nested Qt loop) while the target is parked
    user clicks the dialog's own "Continue" or "Cancel" button
      -> exec() returns the clicked gadget's real classic code
      -> iTidy branches on that returned LONG *itself*:
           Continue (nonzero) -> disables backup and unchecks the checkbox via
              GT_SetGadgetAttrs(GTCB_Checked, FALSE)
           Cancel (0)         -> aborts the operation (break), checkbox stays on
      -> the app's own branch is observable in the live registry, not fabricated

Which button is pressed is test selection (``--branch {continue,cancel}``);
the translation of the press into the returned classic code and the app's
downstream branch are entirely address/structure-based and done by the app.

The things this proves (asserted, not assumed):
1. the LHA route was genuinely reached — the host QMessageBox with the app's
   own title ("LHA Not Found") and its own "Continue"/"Cancel" buttons opened,
   parented to iTidy's real host window;
2. a real host click on the dialog's own button dismissed it (no fabricated
   default answer);
3. iTidy branched on the returned LONG *itself*: Continue unchecks the backup
   checkbox (registry checked goes TRUE->FALSE via its own GT_SetGadgetAttrs
   call); Cancel leaves it checked (TRUE) and aborts — the branch is read from
   the live registry, not invented by the test;
4. target + host finished cleanly.

Run as a module (needs the ``tests`` package for the launcher fixture)::

    uv run python -m tests.run_interactive_lha_smoke_test --branch continue
    uv run python -m tests.run_interactive_lha_smoke_test --branch cancel
"""

from __future__ import annotations

import argparse
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
# The whole sequence (enable backup -> Start -> dialog -> branch) completes in
# well under two seconds, so this only guards against a target that parks and
# never satisfies the wait (it times out, it never fabricates a message).
_WAIT_BOUND_SECONDS = 25.0

# The app's own on-screen gadget labels (main_window.c): the backup checkbox
# and the GID_APPLY "Start" button. Test selection only — the production
# translation is address-based, done by the widget + bridge + app.
_BACKUP_CHECKBOX_LABEL = "Backup icons using LhA"
_APPLY_BUTTON_LABEL = "Start"

# The LHA dialog's own title and buttons (main_window.c, GID_APPLY handler).
_LHA_DIALOG_TITLE = "LHA Not Found"
_CONTINUE_LABEL = "Continue"
_CANCEL_LABEL = "Cancel"


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


def main(argv: list[str] | None = None) -> int:
    import faulthandler

    faulthandler.enable()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--branch",
        choices=("continue", "cancel"),
        default="continue",
        help="which dialog button to press (default: continue)",
    )
    args = parser.parse_args(argv)

    if not (_ITIDY_APP_DIR / "iTidy").is_file():
        print("SKIP: iTidy binary not present in the working tree", file=sys.stderr)
        return 0
    try:
        session = start_xvfb()
    except XvfbError as exc:
        print(f"SKIP: Xvfb unavailable ({exc})", file=sys.stderr)
        return 0

    with session, _apply_session_environment(session):
        return _run(_ITIDY_APP_DIR, branch=args.branch)


def _run(app_dir: Path, *, branch: str) -> int:
    # Import Qt only after the environment is configured (xcb display, not offscreen).
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QMessageBox

    from amiga_ui.host.qt_projection import (
        QtGadgetButton,
        QtGadgetCheckbox,
        QtHostWindowProjection,
    )
    from amiga_ui.host.qt_scheduler_backend import QtEventLoopBackend
    from amiga_ui.host.scheduler import CooperativeHostScheduler
    from amiga_ui.vamos.event_bridge import IntuitionEventBridge
    from amiga_ui.vamos.gadget_state import gadget_registry_from_ctx
    from amiga_ui.vamos.launcher import run_vamos_in_process
    from tests.test_vamos_launcher import _LauncherRuntimeFixture

    existing_app = QApplication.instance()
    app = existing_app if isinstance(existing_app, QApplication) else QApplication([])
    bridge = IntuitionEventBridge()
    scheduler = CooperativeHostScheduler(QtEventLoopBackend(app))
    scheduler.set_wait_bound(_WAIT_BOUND_SECONDS)

    # Test selection only: press the projected backup checkbox, then the
    # projected Start button, then the dialog's own branch button. The
    # production translation (host press -> real IntuiMessage / real returned
    # code -> app branch) is address/structure-based, done by the widget +
    # bridge + projection + app. The state machine below sequences the three
    # presses across the nested Qt loops (the target parks in WaitPort between
    # presses and blocks in the QMessageBox's exec() loop while the dialog is
    # up), each step retried until its target widget exists.
    triggered: dict = {
        "done": False,
        "main_win_addr": None,
        "checkbox_addr": None,
        "checkbox_before": None,
        "dialog_seen": False,
        "dialog_title": None,
        "dialog_parented": None,
        "clicked_button": None,
        "checkbox_after": None,
    }
    # Retry budget per step: each fire is one attempt; a step that cannot find
    # its widget yet reschedules (the nested loop is still running). A step
    # that exhausts its budget is recorded as a failure (the route did not
    # reach that widget) instead of retrying forever.
    state: dict = {"n": 0, "attempts": 0}
    max_attempts = 400  # 400 * 25ms = 10s per step, comfortably under the wait bound
    probe_log: list[str] = []  # diagnostics: what each probe attempt saw

    def _registry():
        return gadget_registry_from_ctx(bridge._ctx) if bridge._ctx is not None else None

    def _checked(gadget_addr: int):
        registry = _registry()
        if registry is None or not gadget_addr:
            return None
        desc = registry.get(gadget_addr)
        return desc.checked if desc is not None else None

    def _checkbox_by_label(window, label: str) -> QtGadgetCheckbox | None:
        # The projected CHECKBOX is a QtGadgetCheckbox (it records the real
        # Amiga addresses); match by visible text. QComboBox (cycle gadgets) has
        # no ``text()`` and is a different type, so the isinstance filter skips it.
        for widget in window.gadget_widgets:
            if isinstance(widget, QtGadgetCheckbox) and widget.text() == label:
                return widget
        return None

    def _button_by_label(window, label: str) -> QtGadgetButton | None:
        # The projected BUTTON is a QtGadgetButton (it records the real Amiga
        # addresses); match by visible text.
        for widget in window.gadget_widgets:
            if isinstance(widget, QtGadgetButton) and widget.text() == label:
                return widget
        return None

    def _find_lha_box():
        for widget in app.topLevelWidgets():
            if isinstance(widget, QMessageBox) and widget.windowTitle() == _LHA_DIALOG_TITLE:
                return widget
        return None

    def _button_text(box: QMessageBox, label: str):
        for button in box.buttons():
            if button.text() == label:
                return button
        return None

    def advance() -> None:
        if triggered["done"]:
            return
        # The _ProjectedWindow (not the AmigaHostWindow) carries gadget_widgets.
        pw = projection.windows.get(triggered["main_win_addr"]) if triggered["main_win_addr"] else None
        if state["n"] == 0:
            # Enable backup: press the projected backup checkbox.
            if pw is None:
                if _retry(advance):
                    return
            else:
                checkbox = _checkbox_by_label(pw, _BACKUP_CHECKBOX_LABEL)
                if checkbox is None:
                    if _retry(advance):
                        return
                else:
                    triggered["checkbox_addr"] = checkbox.amiga_gadget_addr
                    # A real host press: toggles the QCheckBox, which fires
                    # ``toggled`` -> bridge.gadget_up (toggles the registry
                    # checked state, posts the real IDCMP_GADGETUP).
                    checkbox.click()
                    triggered["checkbox_before"] = _checked(triggered["checkbox_addr"])
                    _to(advance, 1)
        elif state["n"] == 1:
            # Trigger the LHA path: press the projected Start (GID_APPLY) button.
            if pw is None:
                if _retry(advance):
                    return
            else:
                apply_btn = _button_by_label(pw, _APPLY_BUTTON_LABEL)
                if apply_btn is None:
                    if _retry(advance):
                        return
                else:
                    apply_btn.click()
                    _to(advance, 2)
        elif state["n"] == 2:
            # The LHA dialog should be up now (the target is blocked in the
            # QMessageBox's exec() loop); press its own branch button.
            box = _find_lha_box()
            if box is None:
                if _retry(advance):
                    return
            else:
                triggered["dialog_seen"] = True
                triggered["dialog_title"] = box.windowTitle()
                parent = box.parentWidget()
                triggered["dialog_parented"] = parent is not None and parent is not app and parent.isVisible()
                label = _CONTINUE_LABEL if branch == "continue" else _CANCEL_LABEL
                button = _button_text(box, label)
                if button is None:
                    if _retry(advance):
                        return
                else:
                    # A real host click on the dialog's own button: exec()
                    # returns the clicked gadget's real classic code, and the
                    # target (unblocked) branches on that LONG itself.
                    triggered["clicked_button"] = label
                    button.click()
                    _to(advance, 3)
        elif state["n"] == 3:
            # The target is back in WaitPort (its GID_APPLY handler finished);
            # read the live registry to observe *its own* branch. The sequence
            # is now complete (the observable is captured); end the run by
            # closing the window(s) in a separate loop (the app may exit before
            # a further state-machine tick would mark done).
            triggered["checkbox_after"] = _checked(triggered["checkbox_addr"])
            triggered["done"] = True
            close_loop()

    def close_loop() -> None:
        # End the run: close the open window(s). The close is a *request* the
        # app owns — ``close()`` defers to the app (it posts a real
        # IDCMP_CLOSEWINDOW), the app runs its own close path and exits. For the
        # Cancel branch only the main window is open; for Continue the app also
        # opened a progress window, so close every open one.
        for addr in list(projection.windows):
            w = projection.host_window(addr)
            if w is not None and w.isVisible():
                w.close()
        # Let the app's close path run (it parks in WaitPort to process the
        # IDCMP_CLOSEWINDOW, then exits); retry until every window is gone.
        if any((w := projection.host_window(addr)) is not None and w.isVisible() for addr in list(projection.windows)):
            QTimer.singleShot(100, close_loop)

    def _retry(func) -> bool:
        # Reschedule the same step shortly (the nested Qt loop is still
        # running). Returns True while retrying, False when the budget is
        # exhausted (the step is recorded as not completed).
        if state["attempts"] >= max_attempts:
            return False
        state["attempts"] += 1
        QTimer.singleShot(25, func)
        return True

    def _to(func, next_state: int) -> None:
        # Let the target process the just-pressed gadget (it parks in WaitPort
        # between presses; a generous beat covers the wake + handler + re-park).
        state["n"] = next_state
        state["attempts"] = 0
        QTimer.singleShot(200, func)

    def on_window_projected(window_addr: int) -> None:
        # The main window's gadgets are projected in a later refresh (well after
        # the window first appears), so probe (retry) until its backup checkbox
        # exists rather than assuming it is present at projection time. Only the
        # window that carries the checkbox starts the sequence; iTidy projects a
        # helper window first, so keying on "the first projected window" would
        # target the wrong one. Once any window starts the sequence, the others
        # stop probing (main_win_addr is set).
        def probe(attempts: int = 0) -> None:
            if triggered["main_win_addr"] is not None:
                return  # the sequence is already running
            pw = projection.windows.get(window_addr)
            cb = None
            if pw is not None:
                cb = _checkbox_by_label(pw, _BACKUP_CHECKBOX_LABEL)
                if attempts <= 3 or attempts % 20 == 0:
                    probe_log.append(
                        f"probe win={window_addr:#06x} attempt={attempts} "
                        f"n_gadgets={len(pw.gadget_widgets)} "
                        f"found={cb is not None}"
                    )
            if pw is not None and cb is not None:
                triggered["main_win_addr"] = window_addr
                advance()
                return
            if attempts >= max_attempts:
                return  # this window never carried the checkbox
            QTimer.singleShot(50, lambda: probe(attempts + 1))

        # A one-shot timer, processed by the nested Qt loop once the target has
        # parked in WaitPort.
        QTimer.singleShot(0, lambda: probe(0))

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
        log_text = vamos_log_path.read_text(encoding="utf-8") if vamos_log_path.is_file() else ""
    app.processEvents()
    failures = _check(
        projection=projection,
        scheduler=scheduler,
        triggered=triggered,
        exit_code=exit_code,
        log_text=log_text,
        branch=branch,
    )
    for addr in list(projection.windows):
        projection.close_window(addr)
    app.processEvents()

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        print(f"(diagnostics) exit_code={exit_code} last_outcome={scheduler.last_outcome}", file=sys.stderr)
        print(f"(diagnostics) triggered={triggered}", file=sys.stderr)
        print(f"(diagnostics) posted={bridge.posted}", file=sys.stderr)
        print(f"(diagnostics) probe_log ({len(probe_log)} entries):", file=sys.stderr)
        for line in probe_log[-15:]:
            print(f"  {line}", file=sys.stderr)
        return 1
    print(
        f"PASS: LHA-not-found EasyRequestArgs -> real QMessageBox -> clicked "
        f"{('Continue' if branch == 'continue' else 'Cancel')} -> app's own branch "
        f"(checkbox after={triggered['checkbox_after']}) -> clean exit",
        file=sys.stderr,
    )
    return 0


def _check(
    *,
    projection,
    scheduler,
    triggered: dict,
    exit_code: int,
    log_text: str,
    branch: str,
) -> list[str]:
    """Assert the milestone conditions. Returns failure reasons (empty = pass)."""

    failures: list[str] = []
    expected_button = _CONTINUE_LABEL if branch == "continue" else _CANCEL_LABEL

    # (0) The full interactive sequence completed (all three presses happened).
    def _hex(value) -> str:
        return f"{value:#06x}" if value else "none"

    if not triggered["done"]:
        failures.append(
            f"the interactive sequence did not complete "
            f"(win={_hex(triggered['main_win_addr'])} checkbox={_hex(triggered['checkbox_addr'])} "
            f"dialog_seen={triggered['dialog_seen']} clicked={triggered['clicked_button']!r})"
        )
        return failures  # nothing further to assert without the sequence

    # (1) The LHA route was genuinely reached: the host QMessageBox with the
    # app's own title opened, parented to iTidy's real host window.
    if not triggered["dialog_seen"]:
        failures.append("the LHA-not-found QMessageBox never opened (route not reached)")
    if triggered["dialog_title"] != _LHA_DIALOG_TITLE:
        failures.append(f"dialog title {triggered['dialog_title']!r} is not the app's own {_LHA_DIALOG_TITLE!r}")
    if not triggered["dialog_parented"]:
        failures.append("the LHA QMessageBox was not parented to iTidy's real host window")

    # (2) A real host click on the dialog's own branch button dismissed it.
    if triggered["clicked_button"] != expected_button:
        failures.append(
            f"the dialog's own {expected_button!r} button was not the one pressed "
            f"(clicked {triggered['clicked_button']!r})"
        )

    # (3) iTidy branched on the returned LONG itself, observable in the live
    # registry: the backup checkbox must have been enabled (before) and the
    # branch must have left it in the branch-specific state (after) —
    # Continue unchecks it (via the app's own GT_SetGadgetAttrs), Cancel
    # leaves it checked.
    if triggered["checkbox_before"] is not True:
        failures.append(
            f"the backup checkbox was not enabled before Apply "
            f"(checkbox_before={triggered['checkbox_before']!r}, expected True)"
        )
    if branch == "continue":
        if triggered["checkbox_after"] is not False:
            failures.append(
                "Continue branch: the app did not uncheck the backup checkbox "
                f"(checkbox_after={triggered['checkbox_after']!r}, expected False)"
            )
    else:
        if triggered["checkbox_after"] is not True:
            failures.append(
                "Cancel branch: the app must leave the backup checkbox checked "
                f"(checkbox_after={triggered['checkbox_after']!r}, expected True)"
            )

    # (4) Target + host finished cleanly, with a satisfied cooperative wait (the
    # route parked and resumed for real, it did not time out or fabricate).
    from amiga_ui.host.scheduler import WaitOutcome

    if scheduler.last_outcome is not WaitOutcome.SATISFIED:
        failures.append(f"WaitPort outcome is {scheduler.last_outcome!r}, expected SATISFIED")
    if "cooperative wait finished with outcome satisfied" not in log_text:
        failures.append("vamos log does not record a satisfied cooperative WaitPort")
    if exit_code != 0:
        failures.append(f"target did not exit cleanly (exit_code={exit_code})")

    return failures


if __name__ == "__main__":
    raise SystemExit(main())
