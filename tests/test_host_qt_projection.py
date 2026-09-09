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

# Default surface background: the classic Workbench window light grey (pen 15).
_BG = 0xFFC0C0C0

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


class TextAndClearSemanticsTest(unittest.TestCase):
    """Draw-mode semantics for text foreground and background clears.

    These pin the distinction the audit requires: vector/fill ops (Draw/RectFill)
    pick their *source* pen from the draw mode (JAM1→FgPen, JAM2→BgPen), while
    Text glyphs always use the FgPen foreground and the JAM1/JAM2 treatment
    applies to the *background* behind the glyphs. The corrected rules must NOT
    re-encode "JAM2 universally = draw using BPen".

    Pen values are host palette indices: 0=black (TEXTPEN/SHADOWPEN),
    15=light grey (BACKGROUNDPEN, the window background = ``_BG``).
    """

    def setUp(self) -> None:
        _ensure_app()

    @staticmethod
    def _dark(img: QImage, x0: int, x1: int, y0: int, y1: int) -> int:
        """Count pixels darker than the background (anti-aliased text is not
        pure black, so test on luminance, not exact colour)."""
        return sum(1 for y in range(y0, y1) for x in range(x0, x1) if ((img.pixel(x, y) >> 16) & 0xFF) < 128)

    def test_set_apen_background_rectfill_jam1_clears_to_background(self) -> None:
        """The group-box title clear: JAM1 RectFill with FgPen=BACKGROUNDPEN.

        JAM1 jams the FgPen, so the cleared region is the FgPen = the window
        background. This is the "black bar" fix: the clear must be the window
        light grey, not black.
        """
        st = RastPortState(rp=0x1)
        st.set_apen(15)  # BACKGROUNDPEN -> window light grey
        st.set_dr_md(JAM1)
        st.rect_fill(293, 23, 332, 33)  # the "Folder" title clear region
        img = _render(_surface_with(st, w=640, h=200))
        self.assertEqual(img.pixel(300, 28), _BG)
        self.assertNotEqual(img.pixel(300, 28), 0xFF000000, "the clear must not be black")

    def test_set_apen_background_rectfill_jam2_clears_to_bg_pen(self) -> None:
        """The folder-path clear: JAM2 RectFill with BgPen=BACKGROUNDPEN.

        JAM2 jams the BgPen, so the cleared region is the BgPen = the window
        background. The folder-path box sets the BgPen explicitly before fill.
        """
        st = RastPortState(rp=0x1)
        st.set_apen(0)  # TEXTPEN -> black
        st.set_bpen(15)  # BACKGROUNDPEN -> window light grey
        st.set_dr_md(JAM2)
        st.rect_fill(97, 36, 487, 45)  # the folder-path clear region
        img = _render(_surface_with(st, w=640, h=200))
        self.assertEqual(img.pixel(200, 40), _BG)
        self.assertNotEqual(img.pixel(200, 40), 0xFF000000, "the clear must not be black")

    def test_text_under_jam2_uses_fg_pen_not_bg_pen(self) -> None:
        """Text glyphs use the FgPen foreground, even under JAM2.

        The folder-path box sets FgPen=TEXTPEN (black), BgPen=BACKGROUNDPEN
        (light grey), JAM2, then draws Text. If the old "JAM2 -> BgPen" rule
        were applied to Text, the glyphs would be light grey (the BgPen) and
        invisible on the light grey background. They must be the FgPen (black).
        """
        st = RastPortState(rp=0x1)
        st.set_apen(0)  # TEXTPEN -> black
        st.set_bpen(15)  # BACKGROUNDPEN -> light grey
        st.set_dr_md(JAM2)
        st.move(10, 20)
        st.record_text(string=0x9000, count=4, width=24, text="SYS:")
        img = _render(_surface_with(st, w=200, h=60))
        dark = self._dark(img, 5, 70, 12, 40)
        self.assertGreater(dark, 5, "text glyphs must be the FgPen (black), not the BgPen")

    def test_rectfill_jam2_uses_bg_pen_but_text_jam2_uses_fg_pen(self) -> None:
        """The corrected rules distinguish fill source from text foreground.

        Under the same JAM2 state, a RectFill uses the BgPen (the fill source),
        while a Text uses the FgPen (the text foreground). This is the explicit
        guard against re-encoding "JAM2 universally = draw using BPen".
        """
        st = RastPortState(rp=0x1)
        st.set_apen(0)  # FgPen = black
        st.set_bpen(15)  # BgPen = light grey
        st.set_dr_md(JAM2)
        # A JAM2 RectFill uses the BgPen (light grey) as its source.
        st.rect_fill(5, 5, 20, 20)
        # A JAM2 Text uses the FgPen (black) as its foreground.
        st.move(30, 12)
        st.record_text(string=0x9000, count=4, width=24, text="SYS:")
        img = _render(_surface_with(st, w=200, h=60))
        # The filled region is the BgPen (light grey = the window background).
        self.assertEqual(img.pixel(10, 10), _BG)
        # The text region has dark (FgPen) pixels — the glyphs are distinguishable.
        dark = self._dark(img, 28, 75, 5, 30)
        self.assertGreater(dark, 5, "JAM2 Text must use the FgPen, not the BgPen")

    def test_group_title_clear_region_matches_background_not_black(self) -> None:
        """Pixel-semantic: the group-title clear region IS the background.

        Not a "count non-background pixels" check: every pixel in the cleared
        title band must equal the window background (light grey), proving the
        "black bar" is gone.
        """
        st = RastPortState(rp=0x1)
        st.set_apen(15)  # BACKGROUNDPEN -> window light grey
        st.set_dr_md(JAM1)
        st.rect_fill(293, 23, 332, 33)
        img = _render(_surface_with(st, w=640, h=200))
        bg_count = 0
        total = 0
        for y in range(23, 34):
            for x in range(293, 333):
                total += 1
                if img.pixel(x, y) == _BG:
                    bg_count += 1
        self.assertGreater(total, 0)
        self.assertEqual(bg_count, total, "every pixel in the title clear must be the background")


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
