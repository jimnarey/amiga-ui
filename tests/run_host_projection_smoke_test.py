#!/usr/bin/env python3
"""Narrow Xvfb-backed smoke test: real iTidy drives a real host window.

Proves the first host-rendering increment end-to-end under a real X display:
an in-process iTidy run drives the compatibility layer, which opens the app's
main window through the projection boundary. A real host top-level Qt window is
created using the Amiga window's title and initial geometry, and its RastPort op
stream is replayed onto the drawing surface on the app's first
``GT_RefreshWindow``.

The target *binary* still ends at the honest ``WaitPort``-on-empty-queue
boundary (a documented target limitation), so this asserts the host window was
created, titled, correctly sized, and actually painted — not a clean app exit.

Run as a module so the ``tests`` package (for the launcher fixture) and the
installed ``amiga_ui`` are importable::

    uv run python -m tests.run_host_projection_smoke_test
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
    # Import Qt only after the environment is configured, so the QApplication
    # uses the Xvfb ``xcb`` display (not an offscreen fallback).
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
        # A real file for stdout (vamos wraps sys.stdout.buffer); stderr may be
        # a StringIO.
        with tempfile.NamedTemporaryFile("w+", encoding="utf-8") as stdout_file:
            with contextlib.redirect_stdout(stdout_file), contextlib.redirect_stderr(io.StringIO()):
                exit_code = run_vamos_in_process(
                    args=runtime.build_itidy_args(app_dir=app_dir, vamos_log_path=vamos_log_path),
                    host_projection=projection,
                )

    app.processEvents()
    _failures = _check(projection, app, exit_code)
    for addr in list(projection.windows):
        projection.close_window(addr)
    app.processEvents()

    if _failures:
        for failure in _failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1
    print("PASS: host projection created and replayed a real iTidy window", file=sys.stderr)
    return 0


def _check(projection, app, exit_code: int) -> list[str]:
    """Assert the host window was created, titled, sized, and actually painted.

    Returns a list of failure reasons (empty means success).
    """

    from PySide6.QtGui import QImage
    from PySide6.QtWidgets import QMenuBar

    failures: list[str] = []

    # The backdrop 1x1 utility window is tracked but NOT projected; the main
    # window (titled, IDCMP set) IS projected as a real host top-level window.
    projected = {addr: pw for addr, pw in projection.windows.items() if pw.host_window is not None}
    titled = {addr: pw for addr, pw in projected.items() if pw.intent.title}
    print(f"projected host windows: {len(projected)}; titled/app-facing: {len(titled)}", file=sys.stderr)
    if not titled:
        return ["no app-facing (titled) host window was created"]

    # The main window is the largest titled projection.
    addr, pw = max(titled.items(), key=lambda kv: kv[1].intent.width * kv[1].intent.height)
    window = pw.host_window
    if window is None:  # narrowed for pyright; impossible given the filters above
        return ["selected app-facing projection has no host window"]
    intent = pw.intent
    print(f"main host window: title={window.windowTitle()!r} size={window.width()}x{window.height()}", file=sys.stderr)

    if not window.windowTitle():
        failures.append("host window has an empty title")
    elif "iTidy" not in window.windowTitle():
        failures.append(f"host window title is not iTidy-like: {window.windowTitle()!r}")

    if window.width() != intent.width or window.height() != intent.height:
        failures.append(
            f"host window geometry {window.width()}x{window.height()} != Amiga window {intent.width}x{intent.height}"
        )

    if window.findChildren(QMenuBar):
        failures.append("host window unexpectedly has a menu bar (should be menu-bar-free)")

    # The surface must hold a replayed RastPort op stream and actually paint it.
    surface = window.surface
    state = surface.state()
    ops = getattr(state, "ops", None)
    if state is None or not ops:
        failures.append("drawing surface did not replay a recorded RastPort op stream")
        return failures

    img = QImage(surface.width(), surface.height(), QImage.Format.Format_RGB32)
    img.fill(0xFFFFFFFF)
    surface.render(img)
    non_bg = sum(1 for y in range(img.height()) for x in range(img.width()) if img.pixel(x, y) != 0xFFFFFFFF)
    print(f"replayed ops: {len(ops)}; non-background surface pixels: {non_bg}", file=sys.stderr)
    if non_bg <= 0:
        failures.append("replayed op stream produced no visible painting")

    # Honest boundary: the target binary must NOT have exited cleanly.
    if exit_code == 0:
        failures.append("app exited cleanly (expected the honest WaitPort-on-empty-queue boundary)")

    return failures


if __name__ == "__main__":
    raise SystemExit(main())
