#!/usr/bin/env python3
"""Xvfb-backed end-to-end test: the host **menu strip**, interactively.

The menu counterpart of ``run_interactive_close_smoke_test.py``: instead of the
window's close control, the host control this test exercises is a projected
menu entry — iTidy's real ``Project`` → ``Close``. It proves the whole
``SetMenuStrip`` → ``IDCMP_MENUPICK`` route end to end on a single active
context (the GUI thread), with the target alive and parked in ``WaitPort``
while the pick is in flight::

    Qt QAction for the projected Project→Close entry (built from the decoded
    menu strip the app published through ``SetMenuStrip``)
      -> the projection hands the bridge the *real* ``struct Window *`` and the
         packed ``MenuNumber`` recorded for that very ``struct MenuItem``
      -> bridge posts a real ``struct IntuiMessage`` on the window's real
         ``UserPort``: Class = ``IDCMP_MENUPICK``, Code = packed MenuNumber,
         IAddress = NULL (classic semantics)
      -> real Window.UserPort queue
      -> WaitPort resumes (the scheduler parks the target in a nested Qt loop)
      -> GT_GetIMsg removes it
      -> iTidy resolves the Code *itself*: ``ItemAddress(strip, Code)`` then
         ``GTMENUITEM_USERDATA(item)`` == its own ``MENU_PROJECT_CLOSE`` id, then
         advances its selection walk with ``menu_number = item->NextSelect`` until
         that UWORD reads ``MENUNULL`` (so a created item must terminate its own
         chain: ``menu_state.NEXTSELECT_NULL``)
      -> iTidy runs its own Project→Close path and calls CloseWindow *itself*
      -> GT_ReplyIMsg releases the message
      -> projection releases the host window; target + host exit cleanly

Which menu entry gets picked is test selection (the host widget located
through the projection's own address map, the entry located by its on-screen
text). Everything from the pick onward is the production route, keyed by the
addresses and the packed selector the app itself created: the message, the port
queue, the resume, the app's own ``ItemAddress`` walk and the window release.
Nothing is fabricated — in particular no ``IDCMP_CLOSEWINDOW`` is posted, so the
app's decision to close can only have come from the menu pick.

The eight things this proves (asserted, not assumed):
1. the app's real menu strip became a real host menu bar — non-native, a child
   of *that* window, above its drawing surface, with the app's own titles;
2. the pick was made by triggering the real ``QAction`` for that menu item
   (which carries the real window address and packed ``MenuNumber``);
3. exactly one ``IntuiMessage`` was posted, class ``IDCMP_MENUPICK``, Code equal
   to that packed selector (a genuine item selector, not ``MENUNULL``),
   ``IAddress`` NULL, on that window's real ``UserPort`` — and *no* close event;
4. ``WaitPort`` participated and was genuinely satisfied, and
   ``GT_GetIMsg``/``GT_ReplyIMsg`` both took part;
5. the app resolved the Code through its own ``ItemAddress`` walk to the item it
   created: it ran its Project→Close path and never reported an unknown item id;
6. the app closed its window itself — the projection record and the host widget
   are gone through the app's release path;
7. the target exited cleanly;
8. no part of the round trip was simulated.

Run as a module (needs the ``tests`` package for the launcher fixture)::

    uv run python -m tests.run_interactive_menu_smoke_test
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
# The pick happens in well under a second, so this only guards against a target
# that parks and never satisfies the wait (it times out, it never fabricates a
# message).
_WAIT_BOUND_SECONDS = 15.0

# How long to wait for the app to finish attaching its menu strip before giving
# up honestly (the strip is attached after OpenWindow, so the projected window
# can exist a moment before its bar does).
_PICK_INTERVAL_MS = 50
_PICK_ATTEMPTS = 60


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


def _host_text(label: str) -> str:
    """A projected menu text as plain text (undo the ``&`` doubling, strip padding)."""

    return label.replace("&&", "&").strip().lower()


def _close_menu_action(widget) -> tuple | None:
    """The host ``QAction`` of the app's ``Project`` → ``Close`` item, or None.

    Test selection only, and it selects by *on-screen text* — the production
    translation is address/code-based, so nothing here identifies the item to
    the compatibility layer.
    """

    from amiga_ui.host.qt_projection import QtMenuAction

    bar = getattr(widget, "menu_bar", None)
    if bar is None:
        return None
    for title_action in bar.actions():
        if not title_action.menu():
            continue
        if _host_text(title_action.text()) != "project":
            continue
        for action in title_action.menu().actions():
            if isinstance(action, QtMenuAction) and _host_text(action.text()) == "close":
                return (action, _host_text(title_action.text()))
    return None


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

    # Test selection only: activate the host menu entry of the first app-facing
    # projected window that has one (for this target: iTidy's main window).
    triggered: dict = {"done": False, "attempts": 0, "gave_up": False}

    def on_window_projected(window_addr: int) -> None:
        def do_pick() -> None:
            if triggered["done"] or triggered["gave_up"]:
                return
            widget = projection.host_window(window_addr)
            if widget is None:
                return
            target = _close_menu_action(widget)
            if target is None:
                # The menu strip may be attached a moment after OpenWindow; retry
                # while the target runs, then give up honestly (the wait below
                # simply times out — nothing is posted by hand).
                triggered["attempts"] += 1
                if triggered["attempts"] < _PICK_ATTEMPTS:
                    QTimer.singleShot(_PICK_INTERVAL_MS, do_pick)
                else:
                    triggered["gave_up"] = True
                return
            action, title = target
            bar = widget.menu_bar
            layout = widget.layout()
            bar_index = -1
            if layout is not None:
                for position in range(layout.count()):
                    item = layout.itemAt(position)
                    if item is not None and item.widget() is bar:
                        bar_index = position
                        break
            triggered["done"] = True
            triggered["win_addr"] = widget.amiga_window_addr
            triggered["widget"] = widget
            triggered["title"] = title
            triggered["label"] = action.text()
            triggered["code"] = action.amiga_menu_code
            triggered["item_addr"] = action.amiga_item_addr
            # Structural facts about the projected strip, read *now*: the app may
            # close its window (and with it the bar) before the checks run.
            triggered["bar_exists"] = bar is not None
            triggered["native"] = bar is not None and bar.isNativeMenuBar()
            triggered["bar_is_child_of_window"] = bar is not None and bar.parent() is widget
            triggered["bar_index"] = bar_index
            triggered["titles"] = [] if bar is None else [a.text() for a in bar.actions() if a.menu()]
            # The real host activation: the same ``triggered`` signal a mouse
            # click on the projected menu entry delivers.
            action.trigger()

        # Processed by the nested Qt loop once the target has parked in WaitPort.
        QTimer.singleShot(0, do_pick)

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
        print(
            f"(diagnostics) exit_code={exit_code} last_outcome={scheduler.last_outcome} "
            f"attempts={triggered['attempts']} gave_up={triggered['gave_up']}",
            file=sys.stderr,
        )
        print(
            f"(diagnostics) triggered={ {k: v for k, v in triggered.items() if k not in ('widget',)} }", file=sys.stderr
        )
        print(f"(diagnostics) posted={bridge.posted}", file=sys.stderr)
        print(f"(diagnostics) released={bridge.released}", file=sys.stderr)
        print(f"(diagnostics) skipped={bridge.skipped}", file=sys.stderr)
        print(f"(diagnostics) stdout tail: {stdout_text.strip().splitlines()[-12:]}", file=sys.stderr)
        return 1
    print(
        "PASS: host menu entry -> real IDCMP_MENUPICK(Code) -> WaitPort resume -> app's own "
        "ItemAddress walk + CloseWindow -> host window closed -> clean exit",
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
    from amiga_ui.vamos import menu_state
    from amiga_ui.vamos.event_bridge import IDCMP_CLOSEWINDOW, IDCMP_MENUPICK

    failures: list[str] = []

    # (a) The app's menu strip was projected and its Close entry was activated.
    if not triggered["done"]:
        if triggered["gave_up"]:
            failures.append(
                "no host Project→Close menu entry was ever projected (the app's SetMenuStrip "
                "produced no usable host menu bar)"
            )
        else:
            failures.append("the host menu entry was never exercised (no pick occurred)")
        return failures  # nothing further to assert without the pick

    # (1) A real host menu bar: non-native, a child of *that* Amiga window, above
    # its drawing surface, carrying the app's own menu title.  Read from the
    # pick-time snapshot — the app closes its window afterwards, which (correctly)
    # takes the projected bar with it.
    widget = triggered["widget"]
    if not triggered["bar_exists"]:
        failures.append("the picked menu entry has no host menu bar (widget-level projection missing)")
    if triggered["native"]:
        failures.append("the host menu bar is a native app menu; the strip belongs to the Amiga window")
    if not triggered["bar_is_child_of_window"]:
        failures.append("the host menu bar is not a child of the Amiga window that owns the strip")
    if triggered["bar_index"] != 0:
        failures.append(
            f"the host menu bar sits at layout index {triggered['bar_index']}, not above the drawing surface"
        )
    if "project" not in [title.lower() for title in triggered["titles"]]:
        failures.append(f"the host menu bar does not carry the app's own 'Project' title: {triggered['titles']}")

    # (2)+(3) Exactly one posted message: the real pick class, carrying the
    # packed MenuNumber of that item, IAddress NULL, on that window's real
    # UserPort — and no close event, so the app's close can only come from the
    # menu pick.
    if len(bridge.posted) != 1:
        failures.append(f"expected exactly one posted IntuiMessage, got {len(bridge.posted)}: {bridge.posted}")
        return failures
    post = bridge.posted[0]
    if post["idcmp_class"] != IDCMP_MENUPICK:
        failures.append(
            f"posted message class {post['idcmp_class']:#06x} is not IDCMP_MENUPICK"
            f"{' (a fabricated close event instead)' if post['idcmp_class'] == IDCMP_CLOSEWINDOW else ''}"
        )
    if post["window"] != triggered["win_addr"]:
        failures.append(
            f"posted message targets window {post['window']:#06x}, not the picked entry's window "
            f"{triggered['win_addr']:#06x} (not address-based)"
        )
    if post["code"] != triggered["code"]:
        failures.append(f"posted Code {post['code']:#06x} is not the item's packed MenuNumber {triggered['code']:#06x}")
    if menu_state.decode_menu_number(post["code"]) is None:
        failures.append(f"Code {post['code']:#06x} addresses no menu item (MENUNULL-like): the app cannot resolve it")
    if post["iaddress"] != 0:
        failures.append(f"IAddress {post['iaddress']:#010x} must be NULL for a classic MENUPICK")
    if not post["port"]:
        failures.append("posted message has no real UserPort")

    # (4a) WaitPort participated and was genuinely satisfied (not the honest
    # headless boundary, not a timeout/shutdown).
    if scheduler.last_outcome is not WaitOutcome.SATISFIED:
        failures.append(f"WaitPort outcome is {scheduler.last_outcome!r}, expected SATISFIED")
    if "cooperative wait finished with outcome satisfied" not in log_text:
        failures.append("vamos log does not record a satisfied cooperative WaitPort")

    # (4b)+(5) The app drained the message (GT_GetIMsg) and resolved the Code
    # through its own ItemAddress walk: it ran its Project→Close path, and never
    # reported an unknown item id — which is what it prints when the Code does
    # not address the item whose GTMenuItem userdata it reads.
    if "unknown menu item id" in stdout_text.lower():
        failures.append(
            "the app resolved the pick to an unknown item id: its ItemAddress/UserData walk "
            "did not find the item this Code addresses"
        )
    if "Closing iTidy main window" not in stdout_text:
        failures.append("app did not run its Project→Close path (no menu-driven close observed in stdout)")

    # (4c) GT_ReplyIMsg participated: the bridge released the posted message.
    if post["imsg"] not in bridge.released:
        failures.append("GT_ReplyIMsg did not release the posted IntuiMessage")

    # (6) The app closed the window itself: the projection record and the host
    # widget (menu bar included) are gone through the release path.
    if projection.windows:
        failures.append(f"host projection still has windows after the menu-driven close: {list(projection.windows)}")
    if _isValid(widget):
        # Let the release path's deferred teardown settle (``close_window`` uses
        # ``deleteLater``) before reading the widgets it owned.
        QCoreApplication.sendPostedEvents(widget, _deferred_delete_event())
    if _isValid(widget) and widget.isVisible():
        failures.append("the host widget is still visible although the app closed its window")
    if _isValid(widget) and widget.menu_bar is not None and _isValid(widget.menu_bar) and widget.menu_bar.isVisible():
        failures.append("the projected menu bar is still visible although the app closed its window")

    # (7) Target + host finished cleanly, with no fabricated event.
    if exit_code != 0:
        failures.append(f"target did not exit cleanly (exit_code={exit_code})")

    return failures


def _deferred_delete_event():
    from PySide6.QtCore import QEvent

    return QEvent.Type.DeferredDelete


if __name__ == "__main__":
    raise SystemExit(main())
