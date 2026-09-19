#!/usr/bin/env python3
"""Xvfb-backed end-to-end test: the second window, interactively — "Restore Backups...".

The interactive counterpart of the probe-level coverage for iTidy's *second*
real window: the "Restore Backups..." button (``GID_RESTORE`` in
``amiga_apps/itidy1classic/source/src/GUI/main_window.c``) opens
``open_restore_window`` (``source/src/GUI/RestoreBackups/restore_window.c``),
which is a genuinely new case for the hosted application model: a *second*
Amiga window with its own RastPort op stream, its own projected host
top-level window, its own gadget set, and its own event loop (the app parks
in ``WaitPort`` on the restore window's ``UserPort`` while it is up).

The whole point is that the second window is real, not a no-op: the app
calls ``OpenWindowTags`` with its own title and GadTools list, the projection
projects *that window* as its own host top-level with *its own* gadgets, the
app then parks in its own restore-window event loop, and a real host click on
one of its own gadgets is posted as a real ``IDCMP_GADGETUP`` on *that*
window's ``UserPort`` and consumed by *that* window's handler::

    user clicks the projected "Restore Backups..." button (GID_RESTORE)
        -> bridge posts a real IDCMP_GADGETUP on the main window's UserPort
        -> WaitPort resumes -> the app's own handler calls
           open_restore_window() (LockPubScreen, GetScreenDrawInfo, OpenFont,
           InitRastPort, GetVisualInfo, CreateContext, CreateGadgetA x7,
           OpenWindowTags)
        -> the projection opens a second host top-level window titled with
           the app's own RESTORE_WINDOW_TITLE ("iTidy - Restore Backups")
           carrying the app's own projectable gadgets (Restore Run,
           Restore window positions, Delete Run, View Folders..., Cancel)
        -> the app parks in its own restore-window event loop
           (WaitPort on the restore window's UserPort)
    user clicks the projected "Cancel" button of the restore window
        -> bridge posts a real IDCMP_GADGETUP on the *restore* window's
           UserPort -> WaitPort resumes -> the app's own handler branches on
           the result itself: continue_running = FALSE
        -> the app's own close path (close_restore_window -> CloseWindow)
           runs, and the restore host window disappears from the projection
        -> the app returns to its main loop and the run ends cleanly

Which buttons are pressed is test selection; the translation of every click
into a real ``IntuiMessage`` and the app's downstream branch is entirely
address/structure-based, done by the widgets + bridge + libraries + app.

The things this proves (asserted, not assumed):
1. the second window genuinely opened — a host top-level with the app's own
   title "iTidy - Restore Backups" and its own real projectable gadget set
   (the two GadTools LISTVIEWs are decoded but not projectable, the settled
   boundary for that gadget kind);
2. a real host click on the restore window's own "Cancel" button posted a
   real IDCMP_GADGETUP on the restore window's own UserPort, and the app
   consumed that message (GT_GetIMsg/GT_ReplyIMsg release);
3. the app branched on that result *itself*: its own close path ran and the
   restore host window disappeared from the projection (not process-alive,
   not a described expectation);
4. target + host finished cleanly (satisfied cooperative wait, exit 0).

The run also writes a probe-shaped artifact
(``artifacts/runs/<ts>-interactive-restore-iTidy/``) so
``uv run python tools/analyze_target_failure.py --latest`` can analyze this
exact run.

Run as a module (needs the ``tests`` package for the launcher fixture)::

    uv run python -m tests.run_interactive_restore_backups_smoke_test
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
# The whole sequence (restore -> second window -> cancel -> close -> exit)
# completes well under this, so it only guards against a target that parks
# and never satisfies the wait (it times out, it never fabricates a message).
_WAIT_BOUND_SECONDS = 25.0

# The app's own on-screen gadget labels (main_window.c: ng_GadgetText of
# GID_RESTORE; restore_window.c: ng_GadgetText of the restore gadgets). Test
# selection only — the production translation is address-based.
_RESTORE_BUTTON_LABEL = "Restore Backups..."
_CANCEL_BUTTON_LABEL = "Cancel"

# The app's own second-window title (restore_window.c: RESTORE_WINDOW_TITLE),
# carried through OpenWindowTags' WA_Title to the host window title.
_RESTORE_WINDOW_TITLE = "iTidy - Restore Backups"

# The app's own projectable restore-window gadget labels (restore_window.c
# ng_GadgetText strings). The two GadTools LISTVIEWs (run list, details) are
# decoded but not projectable — the settled boundary for that gadget kind —
# so the projected set is exactly these five.
_RESTORE_GADGET_LABELS = frozenset(
    {
        "Restore Run",
        "Restore window positions",
        "Delete Run",
        "View Folders...",
        "Cancel",
    }
)


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
    if argv is None:
        argv = sys.argv[1:]

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


def _gadget_labels(window) -> list[str]:
    return [getattr(widget, "text", lambda: None)() or "" for widget in window.gadget_widgets]


def _run(app_dir: Path) -> int:
    # Import Qt only after the environment is configured (xcb display, not offscreen).
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

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

    triggered: dict = {
        "done": False,
        "main_win_addr": None,
        "restore_win_addr": None,
        "restore_title": None,
        "restore_gadgets": None,
        "cancel_posted": False,
        "cancel_consumed": False,
        "restore_closed": False,
    }
    state: dict = {"n": 0, "attempts": 0}
    max_attempts = 400  # 400 * 25ms = 10s per step, comfortably under the wait bound
    probe_log: list[str] = []  # diagnostics: what each probe attempt saw

    def _button_by_label(window, label: str) -> QtGadgetButton | None:
        for widget in window.gadget_widgets:
            if isinstance(widget, QtGadgetButton) and widget.text() == label:
                return widget
        return None

    def advance() -> None:
        if triggered["done"]:
            return
        if state["n"] == 0:
            # Press the projected "Restore Backups..." button.
            pw = projection.windows.get(triggered["main_win_addr"]) if triggered["main_win_addr"] else None
            if pw is None:
                if _retry(advance):
                    return
            else:
                restore_btn = _button_by_label(pw, _RESTORE_BUTTON_LABEL)
                if restore_btn is None:
                    if _retry(advance):
                        return
                else:
                    # A real host press: posts the real IDCMP_GADGETUP by the
                    # gadget's real address; the app's own GID_RESTORE handler
                    # then opens the second window and parks in its event loop.
                    restore_btn.click()
                    _to(advance, 1)
        elif state["n"] == 1:
            # The second window should be up with its own gadgets; capture the
            # app's own projected gadget set, then press its own "Cancel".
            # The second window is found by the app's own title carried
            # through WA_Title — never by position, never by "the other
            # window".
            found = next(
                ((addr, pw) for addr, pw in projection.windows.items() if pw.intent.title == _RESTORE_WINDOW_TITLE),
                None,
            )
            if found is None:
                if _retry(advance):
                    return
            else:
                addr, pw = found
                triggered["restore_win_addr"] = addr
                triggered["restore_title"] = pw.intent.title
                triggered["restore_gadgets"] = sorted(set(_gadget_labels(pw)))
                cancel_btn = _button_by_label(pw, _CANCEL_BUTTON_LABEL)
                if cancel_btn is None:
                    if _retry(advance):
                        return
                else:
                    # A real host press on the *second* window's own gadget:
                    # posts the real IDCMP_GADGETUP on the *restore* window's
                    # UserPort; the app's own handler branches on the result.
                    cancel_btn.click()
                    _to(advance, 2)
        elif state["n"] == 2:
            # Observe *the app's own branch*: its own close path
            # (close_restore_window -> CloseWindow) removes the restore host
            # window from the projection. Not process-alive, not an expected
            # description — the window the app opened is the window the app
            # closes.
            if triggered["restore_win_addr"] not in projection.windows:
                triggered["restore_closed"] = True
                triggered["done"] = True
                close_loop()
                return
            if _retry(advance):
                return

    def close_loop() -> None:
        # End the run: close the remaining open window(s). The close is a
        # *request* the app owns — ``close()`` posts a real
        # IDCMP_CLOSEWINDOW, the app runs its own close path and exits;
        # retry until every window is gone.
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
        # Let the target process the just-pressed gadget (it parks in
        # WaitPort between presses; a generous beat covers wake + handler).
        state["n"] = next_state
        state["attempts"] = 0
        QTimer.singleShot(200, func)

    def on_window_projected(window_addr: int) -> None:
        # The main window's gadgets are projected in a later refresh, so probe
        # until its Restore button exists. Only the window that carries the
        # button starts the sequence (iTidy projects a helper window first).
        def probe(attempts: int = 0) -> None:
            if triggered["main_win_addr"] is not None:
                return
            pw = projection.windows.get(window_addr)
            btn = None
            if pw is not None:
                btn = _button_by_label(pw, _RESTORE_BUTTON_LABEL)
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

    exit_code = -1
    log_text = ""
    stderr_text = ""
    try:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            runtime = _LauncherRuntimeFixture.create(temp_dir)
            vamos_log_path = temp_dir / "vamos.log"
            with tempfile.NamedTemporaryFile("w+", encoding="utf-8") as app_stdout_file:
                # A real file (with ``.buffer``) for stdout — vamos's dos FileManager
                # wraps ``sys.stdout.buffer``; a StringIO would break it.
                with (
                    contextlib.redirect_stdout(app_stdout_file),
                    contextlib.redirect_stderr(io.StringIO()) as stderr_buf,
                ):
                    exit_code = run_vamos_in_process(
                        args=runtime.build_itidy_args(app_dir=app_dir, vamos_log_path=vamos_log_path),
                        event_bridge=bridge,
                        host_projection=projection,
                        host_scheduler=scheduler,
                    )
                stderr_text = stderr_buf.getvalue()
                app_stdout_file.seek(0)
                stdout_text = app_stdout_file.read()
            log_text = vamos_log_path.read_text(encoding="utf-8") if vamos_log_path.is_file() else ""
            _write_run_artifacts(
                app_dir=app_dir,
                exit_code=exit_code,
                vamos_log_text=log_text,
                stdout_text=stdout_text,
                stderr_text=stderr_text,
            )
    finally:
        app.processEvents()

    failures = _check(
        projection=projection,
        scheduler=scheduler,
        bridge=bridge,
        triggered=triggered,
        exit_code=exit_code,
        log_text=log_text,
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
        print(f"(diagnostics) skipped={bridge.skipped}", file=sys.stderr)
        print(f"(diagnostics) released={bridge.released}", file=sys.stderr)
        print(f"(diagnostics) probe_log ({len(probe_log)} entries):", file=sys.stderr)
        for line in probe_log[-15:]:
            print(f"  {line}", file=sys.stderr)
        print(f"(diagnostics) stderr tail:\n{stderr_text[-4000:]}", file=sys.stderr)
        return 1
    print(
        f"PASS: 'Restore Backups...' -> real second window ({_RESTORE_WINDOW_TITLE!r} with its own "
        f"gadgets {triggered['restore_gadgets']}) -> clicked its own Cancel -> the app's own branch "
        f"closed the restore window (its CloseWindow ran) -> clean exit",
        file=sys.stderr,
    )
    return 0


def _write_run_artifacts(
    *, app_dir: Path, exit_code: int, vamos_log_text: str, stdout_text: str, stderr_text: str
) -> None:
    """Write this run as a probe-shaped artifact so the failure analyzer can
    consume it: ``uv run python tools/analyze_target_failure.py --latest``."""

    from amiga_ui.run_artifacts import create_run_artifacts, write_json

    artifacts = create_run_artifacts("interactive-restore", "iTidy")
    artifacts.stdout_path.write_text(stdout_text, encoding="utf-8", errors="replace")
    artifacts.stderr_path.write_text(stderr_text, encoding="utf-8", errors="replace")
    artifacts.vamos_log_path.write_text(vamos_log_text, encoding="utf-8", errors="replace")
    try:
        artifact_root = str(artifacts.root.relative_to(PROJECT_ROOT))
    except ValueError:
        artifact_root = str(artifacts.root)
    write_json(
        artifacts.result_path,
        {
            "artifact_root": artifact_root,
            "ok": exit_code == 0,
            "returncode": exit_code,
            "status": "ok" if exit_code == 0 else "app_failed",
            "stderr_path": f"{artifact_root}/stderr.txt",
            "stdout_path": f"{artifact_root}/stdout.txt",
            "target": "iTidy",
            "vamos_log_path": f"{artifact_root}/vamos.log",
        },
    )
    # The launcher fixture's runtime tree is a temp dir; the app's own logs
    # (PROGDIR:logs/) live under the app dir, so copy the freshest ones for
    # offline inspection of this exact run.
    logs_dir = app_dir / "logs"
    if logs_dir.is_dir():
        newest = sorted(logs_dir.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)[:4]
        for path in newest:
            (artifacts.runtime_root / path.name).write_bytes(path.read_bytes())


def _check(*, projection, scheduler, bridge, triggered: dict, exit_code: int, log_text: str) -> list[str]:
    """Assert the milestone conditions. Returns failure reasons (empty = pass)."""

    from amiga_ui.host.scheduler import WaitOutcome
    from amiga_ui.vamos.event_bridge import IDCMP_GADGETUP

    failures: list[str] = []
    _hex = lambda value: f"{value:#010x}" if value else "none"  # noqa: E731

    # (0) The full interactive sequence completed (restore + cancel + close).
    if not triggered["done"]:
        failures.append(
            "the interactive sequence did not complete "
            f"(main={_hex(triggered['main_win_addr'])} restore={_hex(triggered['restore_win_addr'])} "
            f"title={triggered['restore_title']!r} closed={triggered['restore_closed']})"
        )
        return failures  # nothing further to assert without the sequence

    # (1) The second window genuinely opened with the app's own title and its
    # own real projectable gadget set (the two LISTVIEWs are decoded but not
    # projectable — the settled boundary for that gadget kind).
    if triggered["restore_title"] != _RESTORE_WINDOW_TITLE:
        failures.append(
            f"second window title {triggered['restore_title']!r} is not the app's own {_RESTORE_WINDOW_TITLE!r}"
        )
    gadgets = set(triggered["restore_gadgets"] or [])
    missing = _RESTORE_GADGET_LABELS - gadgets
    if missing:
        failures.append(f"second window is missing its own real gadgets: {sorted(missing)} (got {sorted(gadgets)})")

    # (2) A real host click on the restore window's own Cancel button posted a
    # real IDCMP_GADGETUP on the *restore* window's UserPort, and the app
    # consumed that message (GT_GetIMsg -> GT_ReplyIMsg release).
    restore_addr = triggered["restore_win_addr"]
    cancel_post = next(
        (p for p in bridge.posted if p["window"] == restore_addr and p["idcmp_class"] == IDCMP_GADGETUP),
        None,
    )
    if cancel_post is None:
        failures.append(
            "no real IDCMP_GADGETUP was posted on the restore window's UserPort (Cancel never reached the app)"
        )
    else:
        if cancel_post["imsg"] not in bridge.released:
            failures.append("the app never consumed the Cancel message (GT_GetIMsg/GT_ReplyIMsg never ran on it)")
        triggered["cancel_posted"] = cancel_post is not None
        triggered["cancel_consumed"] = cancel_post["imsg"] in bridge.released

    # (3) The app branched on the result *itself*: its own close path ran and
    # the restore host window disappeared from the projection.
    if not triggered["restore_closed"]:
        failures.append("the app's own close branch never ran: the restore host window is still projected")

    # (4) Target + host finished cleanly, with a satisfied cooperative wait (the
    # route parked and resumed for real, it did not time out or fabricate).
    if scheduler.last_outcome is not WaitOutcome.SATISFIED:
        failures.append(f"WaitPort outcome is {scheduler.last_outcome!r}, expected SATISFIED")
    if "cooperative wait finished with outcome satisfied" not in log_text:
        failures.append("vamos log does not record a satisfied cooperative WaitPort")
    if exit_code != 0:
        failures.append(f"target did not exit cleanly (exit_code={exit_code})")

    return failures


if __name__ == "__main__":
    raise SystemExit(main())
