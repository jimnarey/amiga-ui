"""Unit tests for the PySide6 host window projection.

Covers host-window construction (title, geometry, no menu bar by default, the
drawing surface child), the custom replay surface driven by a *synthetic*
:class:`~amiga_ui.vamos.rastport_state.RastPortState` (so these tests do not
depend on iTidy or a display), and the projection's window-address association,
refresh-replay, and close behaviour.

Qt runs on the offscreen platform (``QT_QPA_PLATFORM=offscreen``) so no X server
is required; a single small pixel assertion is used to prove the paint path
actually draws, per ``docs/host-gui/testing-host-ui.md``.
"""

import os
import unittest
from dataclasses import replace

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication, QMenuBar

from amiga_ui.host.projection import OpenWindowIntent
from amiga_ui.host.qt_projection import (
    AmigaHostWindow,
    QtHostWindowProjection,
    RastPortReplaySurface,
)
from amiga_ui.vamos.rastport_state import COMPLEMENT, INVERSVID, JAM1, JAM2, RastPortRegistry, RastPortState

_BG = 0xFFFFFFFF  # default surface background is white

_QAPP: QApplication | None = None


def _ensure_app() -> QApplication:
    """Return a shared offscreen QApplication, pinning the platform only for the
    moment of construction.

    ``QT_QPA_PLATFORM`` is set for the ``QApplication`` construction (the value is
    captured then) and restored immediately after, so this module does not leak
    ``offscreen`` into the ambient environment for other tests (e.g.
    ``test_xvfb``'s ``build_env`` defaulting to ``xcb``).
    """

    global _QAPP
    if _QAPP is not None:
        return _QAPP
    previous = os.environ.get("QT_QPA_PLATFORM")
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    instance = QApplication.instance()
    app = instance if isinstance(instance, QApplication) else QApplication([])
    try:
        _QAPP = app
    finally:
        if previous is None:
            os.environ.pop("QT_QPA_PLATFORM", None)
        else:
            os.environ["QT_QPA_PLATFORM"] = previous
    return app


def _app() -> QApplication:
    return _ensure_app()


# Construct at import so every widget test can build widgets without an X server.
_ensure_app()


def _render(surface: RastPortReplaySurface) -> QImage:
    """Render the surface into a matching QImage and return it."""

    img = QImage(surface.width(), surface.height(), QImage.Format.Format_RGB32)
    img.fill(_BG)
    surface.render(img)
    return img


def _non_bg(img: QImage) -> int:
    return sum(1 for y in range(img.height()) for x in range(img.width()) if img.pixel(x, y) != _BG)


def _surface_with(state: RastPortState, w: int = 200, h: int = 120) -> RastPortReplaySurface:
    surface = RastPortReplaySurface()
    surface.resize(w, h)
    surface.replay(state)
    return surface


def _app_facing_intent(**overrides: int | str | bool) -> OpenWindowIntent:
    base = OpenWindowIntent(
        window_addr=0x1000,
        title="iTidy",
        left=50,
        top=30,
        width=180,
        height=120,
        rport_addr=0x2000,
    )
    return replace(base, **overrides)


class AmigaHostWindowTest(unittest.TestCase):
    def test_title_is_applied(self) -> None:
        window = AmigaHostWindow("iTidy", 180, 120)
        self.assertEqual(window.windowTitle(), "iTidy")

    def test_initial_geometry(self) -> None:
        window = AmigaHostWindow("iTidy", 180, 120, left=50, top=30)
        self.assertEqual(window.width(), 180)
        self.assertEqual(window.height(), 120)

    def test_no_menu_bar_by_default(self) -> None:
        window = AmigaHostWindow("iTidy", 180, 120)
        self.assertIsNone(window.menu_bar)
        self.assertFalse(window.findChildren(QMenuBar))
        self.assertFalse(window.has_menu_strip)

    def test_has_drawing_surface_child(self) -> None:
        window = AmigaHostWindow("iTidy", 180, 120)
        self.assertIsInstance(window.surface, RastPortReplaySurface)
        self.assertIs(window.surface.parent(), window)


class RastPortReplaySurfaceTest(unittest.TestCase):
    def test_line_draw_paints(self) -> None:
        st = RastPortState(rp=0x1)
        st.set_apen(0)
        st.move(10, 20)
        st.draw(150, 20)
        img = _render(_surface_with(st))
        self.assertGreater(_non_bg(img), 0)
        self.assertEqual(img.pixel(80, 20), 0xFF000000)  # black line at y=20

    def test_rect_fill_paints(self) -> None:
        st = RastPortState(rp=0x1)
        st.set_bpen(2)  # red
        st.rect_fill(20, 20, 80, 60)
        img = _render(_surface_with(st))
        self.assertEqual(img.pixel(50, 40), 0xFFFF0000)  # red fill

    def test_text_paints(self) -> None:
        st = RastPortState(rp=0x1)
        st.set_apen(0)
        st.move(10, 10)
        st.record_text(string=0x9000, count=5, width=40, text="Hello")
        img = _render(_surface_with(st))
        self.assertGreater(_non_bg(img), 0)

    def test_print_itext_paints(self) -> None:
        st = RastPortState(rp=0x1)
        st.print_itext(string=0x9100, count=3, width=24, x=20, y=40, front_pen=0, text="ABC")
        img = _render(_surface_with(st))
        self.assertGreater(_non_bg(img), 0)

    def test_bevel_box_paints(self) -> None:
        st = RastPortState(rp=0x1)
        st.draw_bevel_box(left=30, top=20, width=80, height=50)
        img = _render(_surface_with(st))
        self.assertGreater(_non_bg(img), 0)

    def test_text_length_does_not_paint(self) -> None:
        st = RastPortState(rp=0x1)
        st.set_font(0x2000)  # state only
        st.record_text_length(string=0x9200, count=3, length=24)  # measurement only
        img = _render(_surface_with(st))
        self.assertEqual(_non_bg(img), 0)

    def test_replay_is_ordered_and_overdraws(self) -> None:
        # A black line is drawn first, then a white rect over it: the region
        # covered by the rect must be white again (later op wins).
        st = RastPortState(rp=0x1)
        st.set_apen(0)
        st.move(10, 20)
        st.draw(150, 20)
        st.set_bpen(1)  # white
        st.rect_fill(60, 10, 100, 30)
        img = _render(_surface_with(st))
        self.assertEqual(img.pixel(80, 20), 0xFFFFFFFF)  # overdrawn by the white rect


class DrawModeSemanticsTest(unittest.TestCase):
    """Classic RastPort draw-mode semantics (NDK 3.2 ``graphics/rastport.h``).

    JAM1 (0) draws with the FgPen (APen), JAM2 (1) with the BgPen (BPen),
    COMPLEMENT (2) XORs the raster, and INVERSVID (4) swaps the fg/bg pen
    roles. These are NOT blitter minterms. The default DrawMode is JAM2.
    """

    RED = 0xFFFF0000  # pen 2
    BLUE = 0xFF0000FF  # pen 4
    MAGENTA = 0xFFFF00FF  # red XOR blue
    GREEN = 0xFF00FF00  # pen 3

    def _fill_img(self, st: RastPortState) -> "QImage":
        return _render(_surface_with(st))

    def test_rect_fill_default_mode_uses_bg_pen(self) -> None:
        # Default DrawMode is JAM2 -> BgPen. (NDK AutoDocs RectFill: the fill
        # takes the drawing mode into account; JAM2 jams the BgPen.)
        st = RastPortState(rp=0x1)
        st.set_apen(2)  # red (must NOT be used)
        st.set_bpen(4)  # blue
        st.rect_fill(20, 20, 80, 60)
        img = self._fill_img(st)
        self.assertEqual(img.pixel(50, 40), self.BLUE)

    def test_rect_fill_jam1_uses_fg_pen(self) -> None:
        st = RastPortState(rp=0x1)
        st.set_apen(2)  # red
        st.set_bpen(4)  # blue (must NOT be used)
        st.set_dr_md(JAM1)
        st.rect_fill(20, 20, 80, 60)
        img = self._fill_img(st)
        self.assertEqual(img.pixel(50, 40), self.RED)

    def test_inversvid_swaps_pen_roles(self) -> None:
        # JAM1 | INVERSVID: the FgPen role is swapped, so the BgPen is drawn.
        st = RastPortState(rp=0x1)
        st.set_apen(2)  # red
        st.set_bpen(4)  # blue
        st.set_dr_md(JAM1 | INVERSVID)
        st.rect_fill(20, 20, 80, 60)
        img = self._fill_img(st)
        self.assertEqual(img.pixel(50, 40), self.BLUE)

    def test_complement_is_genuine_xor(self) -> None:
        # Fill red (JAM2, BgPen), then XOR-fill blue (COMPLEMENT, FgPen). The
        # overlap must be red XOR blue = magenta — a real raster XOR, not a
        # plain copy that would leave it blue.
        st = RastPortState(rp=0x1)
        st.set_apen(4)  # blue
        st.set_bpen(2)  # red
        st.set_dr_md(JAM2)
        st.rect_fill(20, 20, 80, 60)
        st.set_dr_md(COMPLEMENT)
        st.rect_fill(40, 30, 60, 50)
        img = self._fill_img(st)
        self.assertEqual(img.pixel(50, 40), self.MAGENTA)  # red ^ blue
        self.assertEqual(img.pixel(25, 25), self.RED)  # first fill, untouched by XOR

    def test_draw_line_respects_draw_mode_pen(self) -> None:
        # A line in JAM1 uses the FgPen; the same line in JAM2 uses the BgPen.
        st = RastPortState(rp=0x1)
        st.set_apen(2)  # red
        st.set_bpen(4)  # blue
        st.set_dr_md(JAM1)
        st.move(10, 20)
        st.draw(150, 20)
        img = self._fill_img(st)
        self.assertEqual(img.pixel(80, 20), self.RED)

        st2 = RastPortState(rp=0x1)
        st2.set_apen(2)
        st2.set_bpen(4)
        st2.set_dr_md(JAM2)
        st2.move(10, 20)
        st2.draw(150, 20)
        img2 = self._fill_img(st2)
        self.assertEqual(img2.pixel(80, 20), self.BLUE)


class QtHostWindowProjectionTest(unittest.TestCase):
    def test_open_app_facing_creates_host_window(self) -> None:
        app = _app()
        projection = QtHostWindowProjection(app)
        intent = _app_facing_intent()
        projection.open_window(intent)
        window = projection.host_window(intent.window_addr)
        assert window is not None
        self.assertEqual(window.windowTitle(), "iTidy")
        self.assertEqual(len(projection.windows), 1)

    def test_open_helper_window_is_not_projected(self) -> None:
        app = _app()
        projection = QtHostWindowProjection(app)
        intent = _app_facing_intent(title="", idcmp=0, width=1, height=1)  # backdrop window
        projection.open_window(intent)
        self.assertIsNone(projection.host_window(intent.window_addr))
        self.assertIn(intent.window_addr, projection.windows)  # tracked, not shown

    def test_refresh_replays_recorded_ops(self) -> None:
        app = _app()
        registry = RastPortRegistry()
        rp = 0x2000
        registry.get_or_create(rp).set_apen(0)
        registry.get_or_create(rp).move(10, 10)
        registry.get_or_create(rp).draw(150, 10)
        projection = QtHostWindowProjection(app)
        projection.bind_registry(registry)
        intent = _app_facing_intent(rport_addr=rp)
        projection.open_window(intent)
        projection.refresh_window(intent.window_addr)
        window = projection.host_window(intent.window_addr)
        assert window is not None
        surface = window.surface
        self.assertIs(surface.state(), registry.state(rp))
        self.assertGreater(_non_bg(_render(surface)), 0)

    def test_close_removes_and_closes(self) -> None:
        app = _app()
        projection = QtHostWindowProjection(app)
        intent = _app_facing_intent()
        projection.open_window(intent)
        self.assertIn(intent.window_addr, projection.windows)
        projection.close_window(intent.window_addr)
        self.assertNotIn(intent.window_addr, projection.windows)
        self.assertIsNone(projection.host_window(intent.window_addr))
        # A second close is an idempotent no-op (no exception).
        projection.close_window(intent.window_addr)


if __name__ == "__main__":
    unittest.main()
