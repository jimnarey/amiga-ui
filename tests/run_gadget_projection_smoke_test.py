#!/usr/bin/env python3
"""Xvfb-backed smoke test: the real iTidy main window projects its GadTools.

End-to-end under a real X display, this proves the GadTools-to-Qt projection
slice: an in-process iTidy run drives the compatibility layer, which decodes the
main window's real GadTools gadgets (via the ``CreateContext`` / ``CreateGadgetA``
chain) and the host projection renders them as positioned Qt widgets *over* the
RastPort-replayed background.

The assertion is app-level (this is the one place real iTidy values may be
checked): the main projected window contains the expected supported widget
types (``QPushButton`` / ``QComboBox`` / ``QCheckBox`` / ``QLabel``) with
meaningful labels/geometry, and the RastPort background is still visible. The
projection *code* itself is generic (no hard-coded count or iTidy labels).

The target binary still ends at the honest ``WaitPort``-on-empty-queue boundary,
so this asserts the projected window's contents — not a clean app exit.

Run as a module (needs the ``tests`` package for the launcher fixture)::

    uv run python -m tests.run_gadget_projection_smoke_test
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
    from PySide6.QtWidgets import QApplication

    from amiga_ui.host.qt_projection import QtHostWindowProjection
    from amiga_ui.vamos.launcher import run_vamos_in_process
    from tests.test_vamos_launcher import _LauncherRuntimeFixture

    instance = QApplication.instance()
    app = instance if isinstance(instance, QApplication) else QApplication([])
    projection = QtHostWindowProjection(app)

    exit_code = -1
    with tempfile.TemporaryDirectory() as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        runtime = _LauncherRuntimeFixture.create(temp_dir)
        vamos_log_path = temp_dir / "vamos.log"
        with tempfile.NamedTemporaryFile("w+", encoding="utf-8") as stdout_file:
            with contextlib.redirect_stdout(stdout_file), contextlib.redirect_stderr(io.StringIO()):
                exit_code = run_vamos_in_process(
                    args=runtime.build_itidy_args(app_dir=app_dir, vamos_log_path=vamos_log_path),
                    host_projection=projection,
                )

    app.processEvents()
    failures = _check(projection, app, exit_code)
    for addr in list(projection.windows):
        projection.close_window(addr)
    app.processEvents()

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1
    print("PASS: real iTidy main window projected its GadTools over the RastPort background", file=sys.stderr)
    return 0


def _check(projection, app, exit_code: int) -> list[str]:
    """Assert the main window projected all supported widget types meaningfully.

    Returns a list of failure reasons (empty means success).
    """

    from PySide6.QtGui import QImage
    from PySide6.QtWidgets import QCheckBox, QComboBox, QLabel, QPushButton

    failures: list[str] = []

    # Select the main (titled, app-facing) projected window — the largest one.
    projected = {addr: pw for addr, pw in projection.windows.items() if pw.host_window is not None}
    titled = {addr: pw for addr, pw in projected.items() if pw.intent.title}
    print(f"projected host windows: {len(projected)}; titled/app-facing: {len(titled)}", file=sys.stderr)
    if not titled:
        return ["no app-facing (titled) host window was created"]
    addr, pw = max(titled.items(), key=lambda kv: kv[1].intent.width * kv[1].intent.height)
    window = pw.host_window
    if window is None:
        return ["selected app-facing projection has no host window"]
    print(f"main host window: title={window.windowTitle()!r} size={window.width()}x{window.height()}", file=sys.stderr)
    if not window.windowTitle() or "iTidy" not in window.windowTitle():
        failures.append(f"main window title not iTidy-like: {window.windowTitle()!r}")

    # The expected supported widget types, each with meaningful content/geometry.
    buttons = window.findChildren(QPushButton)
    combos = window.findChildren(QComboBox)
    checkboxes = window.findChildren(QCheckBox)
    labels = window.findChildren(QLabel)
    print(
        f"projected gadget widgets: buttons={len(buttons)} combos={len(combos)} "
        f"checkboxes={len(checkboxes)} labels={len(labels)}",
        file=sys.stderr,
    )
    # All four supported kinds must be present (iTidy's main window has each).
    if not buttons:
        failures.append("no QPushButton (BUTTON_KIND) projected")
    if not combos:
        failures.append("no QComboBox (CYCLE_KIND) projected")
    if not checkboxes:
        failures.append("no QCheckBox (CHECKBOX_KIND) projected")
    if not labels:
        failures.append("no QLabel (TEXT_KIND / cycle caption) projected")

    # Every projected gadget widget must have meaningful (non-degenerate) geometry.
    for widget in buttons + combos + checkboxes + labels:
        if widget.width() <= 0 or widget.height() <= 0:
            failures.append(f"gadget widget {type(widget).__name__} has degenerate geometry {widget.geometry()}")
            break

    # Meaningful content: text-bearing widgets are non-empty; combos have items.
    if buttons and all(not b.text().strip() for b in buttons):
        failures.append("all projected buttons have empty text")
    if checkboxes and all(not c.text().strip() for c in checkboxes):
        failures.append("all projected checkboxes have empty text")
    if combos and all(c.count() == 0 for c in combos):
        failures.append("all projected combos have no items (cycle labels not decoded)")
    if labels and all(not lbl.text().strip() for lbl in labels):
        failures.append("all projected labels have empty text")

    # A combo should be showing a real active option (index within range, set).
    for combo in combos:
        if combo.count() > 0 and not (0 <= combo.currentIndex() < combo.count()):
            failures.append(f"combo active index {combo.currentIndex()} out of range for {combo.count()} items")

    # The RastPort background must still be visible (the widgets overlay it,
    # they do not replace the group-box / folder-box rendering).
    surface = window.surface
    state = surface.state()
    ops = getattr(state, "ops", None)
    if state is None or not ops:
        failures.append("drawing surface did not replay a recorded RastPort op stream")
    else:
        img = QImage(surface.width(), surface.height(), QImage.Format.Format_RGB32)
        img.fill(0xFFFFFFFF)
        surface.render(img)
        non_bg = sum(1 for y in range(img.height()) for x in range(img.width()) if img.pixel(x, y) != 0xFFFFFFFF)
        print(f"replayed ops: {len(ops)}; non-background surface pixels: {non_bg}", file=sys.stderr)
        if non_bg <= 0:
            failures.append("RastPort background is not visible (gadget projection removed the replayed surface)")

    # Honest boundary: the target binary must NOT have exited cleanly.
    if exit_code == 0:
        failures.append("app exited cleanly (expected the honest WaitPort-on-empty-queue boundary)")

    return failures


if __name__ == "__main__":
    raise SystemExit(main())
