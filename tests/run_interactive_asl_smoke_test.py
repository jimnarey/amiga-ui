#!/usr/bin/env python3
"""Xvfb-backed end-to-end test: the ASL directory requester, interactively.

The interactive counterpart of the Qt-free round-trip test
(``tests/test_asl_library.py``) and the widget-level dialog test
(``tests/test_qt_asl_dialog.py``) for the *real* call site: iTidy's Browse
button (``amiga_apps/itidy1classic/source/src/GUI/main_window.c``, the
``GID_BROWSE`` handler calling ``request_directory``). The whole point of a
genuinely *blocking* ``AslRequest`` is that the emulated call parks the
target, opens a real host ``QFileDialog``, waits for the user's actual
choice, and writes the user's actual selection into ``fr_Drawer`` for the app
to branch on — not a fabricated path or default answer. This test proves that
end to end, on a single active context (the GUI thread), with the target
alive and parked while the dialog is up::

    user clicks the projected "Browse..." button (GID_BROWSE)
       -> bridge posts a real IDCMP_GADGETUP IntuiMessage by the gadget's
          real address -> WaitPort resumes -> the app's own handler calls
          request_directory() -> AllocAslRequest (LVO -48) + AslRequestTags
          (the inline wrapper for AslRequest, LVO -60)
       -> the ASL library decodes the app's real tag list (title,
          DrawersOnly, InitialDrawer, DoPatterns) and the projection opens a
          real non-native QFileDialog (Directory mode; unparented, because
          the app passes no ASLFR_Window) blocking in exec() while the
          target waits
    user points the dialog at a real directory and clicks its own Choose
    (accept) or Cancel button
       -> exec() returns the real choice; on accept the library writes the
          chosen path into fr_Drawer (ASL-owned memory) and returns TRUE
       -> iTidy branches on that result *itself*:
            accept -> strncpy(freq->rf_Dir, ...) + draw_folder_path_box ->
               the chosen path is Text()-drawn on the main window (observable
               in the live RastPort op registry)
            cancel -> AslRequest returned FALSE: the handler does not redraw,
               the folder box text never changes
       -> the app's own branch is observed from the live registry, not invented

Which button is pressed is test selection (``--branch {accept,cancel}``);
the translation of the click into the struct write-back and the app's
downstream redraw is entirely address/structure-based, done by the app.

The things this proves (asserted, not assumed):
1. the Browse route was genuinely reached — a real host QFileDialog with the
   app's own title ("Select Folder to Process") and Directory file-mode
   opened, unparented (the app passes no ASLFR_Window);
2. a real host click on the dialog's own button decided the outcome (no
   fabricated default answer);
3. on accept the app drew the *chosen* path into its folder box (RastPort
   Text op contains the tmp directory); on cancel it never did;
4. target + host finished cleanly.

Run as a module (needs the ``tests`` package for the launcher fixture)::

    uv run python -m tests.run_interactive_asl_smoke_test --branch accept
    uv run python -m tests.run_interactive_asl_smoke_test --branch cancel
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
# The whole sequence (browse -> dialog -> choice -> branch) completes well
# under this, so it only guards against a target that parks and never
# satisfies the wait (it times out, it never fabricates a message).
_WAIT_BOUND_SECONDS = 25.0

# The app's own on-screen gadget label (main_window.c: ng_GadgetText of
# GID_BROWSE). Test selection only — the production translation is
# address-based, done by the widget + bridge + app.
_BROWSE_BUTTON_LABEL = "Browse..."

# The requester's own title (main_window.c, request_directory()) — carried by
# ASLFR_TitleText through the library to the real dialog.
_ASL_DIALOG_TITLE = "Select Folder to Process"


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
        choices=("accept", "cancel"),
        default="accept",
        help="which dialog button to press (default: accept)",
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
    from PySide6.QtWidgets import QApplication, QDialogButtonBox, QFileDialog

    from amiga_ui.host.qt_projection import QtGadgetButton, QtHostWindowProjection
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

    # Test selection only: press the projected Browse button, then decide the
    # dialog (point it at a real short tmp directory, click its own
    # accept/reject-role button). The production translation (host click ->
    # tag decode -> struct write-back -> returned BOOL -> app branch) is
    # address/structure-based, done by the widget + bridge + library + app.
    # The tmp directory is deliberately short (mkdtemp under /tmp is
    # /tmp/XXXXXXXX): the app's folder-path box truncates wide text with
    # "...", and an un-observable truncated observation would be a false
    # negative, not a failure of the route.
    tmp_dir = tempfile.mkdtemp(prefix="", dir="/tmp")
    triggered: dict = {
        "done": False,
        "main_win_addr": None,
        "dialog_seen": False,
        "dialog_title": None,
        "dialog_file_mode": None,
        "dialog_parent": "unset",
        "clicked_button": None,
        "folder_text_seen": False,
    }
    state: dict = {"n": 0, "attempts": 0}
    max_attempts = 400  # 400 * 25ms = 10s per step, comfortably under the wait bound
    probe_log: list[str] = []  # diagnostics: what each probe attempt saw

    def _button_by_label(window, label: str) -> QtGadgetButton | None:
        for widget in window.gadget_widgets:
            if isinstance(widget, QtGadgetButton) and widget.text() == label:
                return widget
        return None

    def _find_asl_dialog():
        # Only *visible* file dialogs count: a finished exec() hides its
        # dialog but the top-level object lives on.
        for widget in app.topLevelWidgets():
            if isinstance(widget, QFileDialog) and widget.isVisible():
                return widget
        return None

    def _role_button(dialog, role):
        box = dialog.findChild(QDialogButtonBox)
        if box is None:
            return None
        for button in box.buttons():
            if box.buttonRole(button) == role:
                return button
        return None

    def _folder_path_drawn() -> bool:
        """True if the app Text()-drew our chosen path (its own redraw branch).

        Reads the live shared RastPort op registry (the same registry the
        drawing libraries record into): ``draw_folder_path_box`` Text()-draws
        ``folder_path_buffer``, so the chosen path appearing as an op's text
        is the app's own branch, taken after the real returned TRUE — the
        release binary has no CONSOLE_STATUS, so this is the observable.
        """
        ctx = bridge._ctx
        registry = getattr(ctx, "rastports", None) if ctx is not None else None
        if registry is None:
            return False
        for st in registry.all_states():
            for op in st.ops:
                if op.get("op") == "Text" and tmp_dir in (op.get("text") or ""):
                    return True
        return False

    def advance() -> None:
        if triggered["done"]:
            return
        # The _ProjectedWindow (not the AmigaHostWindow) carries gadget_widgets.
        pw = projection.windows.get(triggered["main_win_addr"]) if triggered["main_win_addr"] else None
        if state["n"] == 0:
            # Press the projected Browse button.
            if pw is None:
                if _retry(advance):
                    return
            else:
                browse_btn = _button_by_label(pw, _BROWSE_BUTTON_LABEL)
                if browse_btn is None:
                    if _retry(advance):
                        return
                else:
                    # A real host press: posts the real IDCMP_GADGETUP by the
                    # gadget's real address; the app's handler then blocks in
                    # AslRequest's exec() loop (a nested Qt loop keeps running).
                    browse_btn.click()
                    _to(advance, 1)
        elif state["n"] == 1:
            # The ASL requester should be up (the target is blocked in the
            # QFileDialog's exec() loop): capture its intent, point it at the
            # real tmp directory, click its own branch button.
            dialog = _find_asl_dialog()
            if dialog is None:
                if _retry(advance):
                    return
            else:
                triggered["dialog_seen"] = True
                triggered["dialog_title"] = dialog.windowTitle()
                triggered["dialog_file_mode"] = dialog.fileMode()
                triggered["dialog_parent"] = dialog.parentWidget()
                role = (
                    QDialogButtonBox.ButtonRole.AcceptRole
                    if branch == "accept"
                    else QDialogButtonBox.ButtonRole.RejectRole
                )
                button = _role_button(dialog, role)
                if button is None:
                    if _retry(advance):
                        return
                else:
                    if branch == "accept":
                        # Open the view where the user would pick: the tmp dir
                        # (Directory mode returns the viewed directory).
                        dialog.setDirectory(tmp_dir)
                    triggered["clicked_button"] = button.text().replace("&", "")
                    # A real host click: exec() returns the real choice; the
                    # library writes the real selection into fr_Drawer (or
                    # leaves the struct untouched on cancel) and the unblocked
                    # app branches on the returned BOOL itself.
                    button.click()
                    _to(advance, 2)
        elif state["n"] == 2:
            # Observe *the app's own branch* in the live RastPort op registry:
            # accept -> the chosen path is drawn into the folder box; cancel
            # -> it never appears. Accept retries until drawn (the redraw runs
            # after WaitPort resumes); cancel waits out a bounded quiet
            # window before declaring "not drawn".
            drawn = _folder_path_drawn()
            if branch == "accept":
                if drawn:
                    triggered["folder_text_seen"] = True
                    triggered["done"] = True
                    close_loop()
                    return
                if _retry(advance):
                    return
                # Budget exhausted: record the absence; let the checks report it.
                triggered["done"] = True
                close_loop()
            else:
                if drawn:
                    triggered["folder_text_seen"] = True  # wrong branch taken!
                    triggered["done"] = True
                    close_loop()
                    return
                if state["attempts"] < 40:  # ~1s quiet window for a late redraw
                    if _retry(advance):
                        return
                triggered["done"] = True
                close_loop()

    def close_loop() -> None:
        # End the run: close the open window(s). The close is a *request* the
        # app owns — ``close()`` posts a real IDCMP_CLOSEWINDOW, the app runs
        # its own close path and exits; retry until every window is gone.
        for addr in list(projection.windows):
            w = projection.host_window(addr)
            if w is not None and w.isVisible():
                w.close()
        if any((w := projection.host_window(addr)) is not None and w.isVisible() for addr in list(projection.windows)):
            QTimer.singleShot(100, close_loop)

    def _retry(func) -> bool:
        # Reschedule the same step shortly (the nested Qt loop is still
        # running). True while retrying, False when the budget is exhausted.
        if state["attempts"] >= max_attempts:
            return False
        state["attempts"] += 1
        QTimer.singleShot(25, func)
        return True

    def _to(func, next_state: int) -> None:
        # Let the target process the just-pressed gadget / click (it parks in
        # WaitPort between presses; a generous beat covers wake + handler).
        state["n"] = next_state
        state["attempts"] = 0
        QTimer.singleShot(200, func)

    def on_window_projected(window_addr: int) -> None:
        # The main window's gadgets are projected in a later refresh, so probe
        # until its Browse button exists. Only the window that carries Browse
        # starts the sequence (iTidy projects a helper window first).
        def probe(attempts: int = 0) -> None:
            if triggered["main_win_addr"] is not None:
                return
            pw = projection.windows.get(window_addr)
            btn = None
            if pw is not None:
                btn = _button_by_label(pw, _BROWSE_BUTTON_LABEL)
                if attempts <= 3 or attempts % 20 == 0:
                    probe_log.append(
                        f"probe win={window_addr:#06x} attempt={attempts} "
                        f"n_gadgets={len(pw.gadget_widgets)} found={btn is not None}"
                    )
            if pw is not None and btn is not None:
                triggered["main_win_addr"] = window_addr
                advance()
                return
            if attempts >= max_attempts:
                return
            QTimer.singleShot(50, lambda: probe(attempts + 1))

        QTimer.singleShot(0, lambda: probe(0))

    projection = QtHostWindowProjection(app, event_source=bridge, window_projected_hook=on_window_projected)

    try:
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
    finally:
        # The chosen tmp dir belongs to the test, not the runtime.
        try:
            os.rmdir(tmp_dir)
        except OSError:
            pass

    app.processEvents()
    failures = _check(
        projection=projection,
        scheduler=scheduler,
        triggered=triggered,
        exit_code=exit_code,
        log_text=log_text,
        branch=branch,
        tmp_dir=tmp_dir,
    )
    for addr in list(projection.windows):
        projection.close_window(addr)
    app.processEvents()

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        print(f"(diagnostics) exit_code={exit_code} last_outcome={scheduler.last_outcome}", file=sys.stderr)
        print(
            f"(diagnostics) triggered={ {k: v for k, v in triggered.items() if k != 'dialog_parent'} }", file=sys.stderr
        )
        print(f"(diagnostics) posted={bridge.posted}", file=sys.stderr)
        print(f"(diagnostics) probe_log ({len(probe_log)} entries):", file=sys.stderr)
        for line in probe_log[-15:]:
            print(f"  {line}", file=sys.stderr)
        return 1
    print(
        f"PASS: Browse -> real ASL QFileDialog ({_ASL_DIALOG_TITLE!r}, Directory mode) -> clicked "
        f"{('Choose/accept' if branch == 'accept' else 'Cancel')} -> app's own branch "
        f"(folder path drawn={triggered['folder_text_seen']}) -> clean exit",
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
    tmp_dir: str,
) -> list[str]:
    """Assert the milestone conditions. Returns failure reasons (empty = pass)."""

    from PySide6.QtWidgets import QFileDialog

    failures: list[str] = []
    expected_button = "accept" if branch == "accept" else "cancel"

    def _hex(value) -> str:
        return f"{value:#06x}" if value else "none"

    # (0) The full interactive sequence completed (press + dialog + click).
    if not triggered["done"]:
        failures.append(
            f"the interactive sequence did not complete "
            f"(win={_hex(triggered['main_win_addr'])} dialog_seen={triggered['dialog_seen']} "
            f"clicked={triggered['clicked_button']!r})"
        )
        return failures  # nothing further to assert without the sequence

    # (1) The ASL route was genuinely reached: the host QFileDialog with the
    # app's own title opened, in Directory file-mode, *unparented* (the app
    # passes no ASLFR_Window — the classic requester then stands on its own).
    if not triggered["dialog_seen"]:
        failures.append("the ASL QFileDialog never opened (Browse route not reached)")
    if triggered["dialog_title"] != _ASL_DIALOG_TITLE:
        failures.append(f"dialog title {triggered['dialog_title']!r} is not the app's own {_ASL_DIALOG_TITLE!r}")
    if triggered["dialog_file_mode"] != QFileDialog.FileMode.Directory:
        failures.append(f"dialog file mode {triggered['dialog_file_mode']!r} is not Directory (DrawersOnly was lost)")
    if triggered["dialog_parent"] != None:  # noqa: E711 — None is the required state
        failures.append(f"dialog parent is {triggered['dialog_parent']!r}, expected None (app passes no ASLFR_Window)")

    # (2) A real host click on the dialog's own role button decided the outcome.
    clicked = (triggered["clicked_button"] or "").lower()
    hit = (
        ("choose" in clicked or "open" in clicked or "save" in clicked or "ok" in clicked)
        if branch == "accept"
        else "cancel" in clicked
    )
    if not hit:
        failures.append(
            f"the dialog's own {expected_button}-role button was not the one pressed (clicked {triggered['clicked_button']!r})"
        )

    # (3) iTidy branched on the returned BOOL *itself*, observed live: accept
    # -> draw_folder_path_box Text()-drew the chosen tmp path; cancel -> the
    # folder box never received it (no fabricated selection).
    if branch == "accept":
        if not triggered["folder_text_seen"]:
            failures.append(f"accept branch: the app never drew the chosen path {tmp_dir!r} into its folder box")
    else:
        if triggered["folder_text_seen"]:
            failures.append(
                f"cancel branch: the app drew {tmp_dir!r} although the user cancelled (a selection was fabricated)"
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
