"""Tests for the repo ``graphics.library`` and its host-side RastPort model.

Covers, without depending on the iTidy binary:

- the ``RastPortState`` / ``RastPortRegistry`` model directly (state updates and
  the ordered op log);
- the ``GraphicsLibrary`` entry points against a fake 68k context, asserting the
  six drawing calls the target app actually issues (``SetAPen``/``SetBPen``/
  ``SetDrMd``/``Move``/``Draw``/``RectFill``) record real state instead of
  no-op'ing, that the classic return contracts hold (``SetFont``/``SetMaxPen``/
  ``SetOutlinePen`` return the *previous* value), and that ``TextLength``
  measures / ``Text`` draws from the RastPort font (recording position, content,
  and the pen advance) rather than returning a fake result;
- a scanner regression guard: every ``GraphicsLibrary`` method must be a *valid*
  ``.fd`` trap (``ctx`` first, exact arg count). Before the dispatch fix the six
  drawing methods lacked ``ctx`` and were scanner errors, so vamos dropped them
  as ``UNKNOWN`` traps and the app's drawing was silently lost.
"""

import unittest
from types import SimpleNamespace

from amiga_ui.vamos.graphics_library import GraphicsLibrary
from amiga_ui.vamos.rastport_state import RastPortRegistry, RastPortState


def _ctx() -> SimpleNamespace:
    """A minimal call context; the RastPort drawing methods never dereference it."""
    return SimpleNamespace()


class _FakeMem:
    """A minimal big-endian 68k memory model (unwritten bytes are 0).

    Byte-backed so both ``r8``/``w8`` (text content) and ``r16``/``w16``
    (``RastPort.TxWidth``) work over the same storage. The constructor takes a
    dict of 16-bit words (address -> word) to match the text-metrics fixtures.
    """

    def __init__(self, words: dict[int, int] | None = None) -> None:
        self._bytes: dict[int, int] = {}
        if words:
            for addr, value in words.items():
                self.w16(addr, value)

    def r8(self, addr: int) -> int:
        return self._bytes.get(addr, 0) & 0xFF

    def w8(self, addr: int, value: int) -> None:
        self._bytes[addr] = value & 0xFF

    def r16(self, addr: int) -> int:
        return (self.r8(addr) << 8) | self.r8(addr + 1)

    def w16(self, addr: int, value: int) -> None:
        value &= 0xFFFF
        self.w8(addr, (value >> 8) & 0xFF)
        self.w8(addr + 1, value & 0xFF)


def _ctx_with_mem(words: dict[int, int] | None = None) -> SimpleNamespace:
    """A call context with a fake 68k memory (for text-metrics reads)."""
    return SimpleNamespace(mem=_FakeMem(words))


class RastPortStateTest(unittest.TestCase):
    def test_set_pen_and_draw_mode_record_state(self) -> None:
        st = RastPortState(rp=0x1000)
        st.set_apen(7)
        st.set_bpen(12)
        st.set_dr_md(0xC0)

        self.assertEqual(st.apen, 7)
        self.assertEqual(st.bpen, 12)
        self.assertEqual(st.draw_mode, 0xC0)
        self.assertEqual([op["op"] for op in st.ops], ["SetAPen", "SetBPen", "SetDrMd"])
        # Each op carries the pen/draw-mode state in effect when it ran.
        self.assertEqual(st.ops[0]["apen"], 7)
        self.assertEqual(st.ops[2]["draw_mode"], 0xC0)

    def test_move_then_draw_records_line_from_and_to(self) -> None:
        st = RastPortState()
        st.move(4, 9)
        st.draw(20, 30)

        self.assertEqual((st.x, st.y), (20, 30))
        draw = st.ops[-1]
        self.assertEqual(draw["op"], "Draw")
        self.assertEqual((draw["from_x"], draw["from_y"]), (4, 9))
        self.assertEqual((draw["x"], draw["y"]), (20, 30))

    def test_rect_fill_records_bounds(self) -> None:
        st = RastPortState()
        st.rect_fill(1, 2, 100, 50)

        fill = st.ops[-1]
        self.assertEqual(fill["op"], "RectFill")
        self.assertEqual((fill["x_min"], fill["y_min"], fill["x_max"], fill["y_max"]), (1, 2, 100, 50))

    def test_set_max_pen_returns_previous(self) -> None:
        st = RastPortState()
        self.assertEqual(st.set_max_pen(15), 0)  # previous default
        self.assertEqual(st.maxpen, 15)
        self.assertEqual(st.set_max_pen(31), 15)  # previous value
        self.assertEqual(st.maxpen, 31)

    def test_set_font_returns_previous(self) -> None:
        st = RastPortState()
        self.assertEqual(st.set_font(0x0A0000), 0)
        self.assertEqual(st.font, 0x0A0000)
        self.assertEqual(st.set_font(0x0B0000), 0x0A0000)

    def test_init_resets_state_and_clears_ops(self) -> None:
        st = RastPortState()
        st.set_apen(7)
        st.move(5, 5)
        st.init()

        self.assertEqual(st.apen, 0)
        self.assertEqual((st.x, st.y), (0, 0))
        self.assertEqual([op["op"] for op in st.ops], ["InitRastPort"])


class RastPortRegistryTest(unittest.TestCase):
    def test_get_or_create_is_idempotent_per_pointer(self) -> None:
        reg = RastPortRegistry()
        a1 = reg.get_or_create(0x06A000)
        a2 = reg.get_or_create(0x06A000)
        b = reg.get_or_create(0x06B000)

        self.assertIs(a1, a2)
        self.assertIsNot(a1, b)
        self.assertIs(reg.state(0x06A000), a1)
        self.assertIsNone(reg.state(0x06C000))
        self.assertEqual(len(reg.all_states()), 2)

    def test_total_ops_sums_across_rastports(self) -> None:
        reg = RastPortRegistry()
        reg.get_or_create(0x1).set_apen(1)
        reg.get_or_create(0x2).set_apen(2)
        reg.get_or_create(0x2).set_bpen(3)

        self.assertEqual(reg.total_ops(), 3)


class GraphicsLibraryDispatchTest(unittest.TestCase):
    """The six drawing calls the target app issues must record real state."""

    def setUp(self) -> None:
        self.lib = GraphicsLibrary()
        self.ctx = _ctx()
        self.rp = 0x06A868  # the window RPort the app draws into (from the probe log)

    def _state(self, rp: int):
        """The tracked RastPort state for ``rp``; fails the test if absent."""
        st = self.lib.rastports.state(rp)
        if st is None:
            self.fail(f"no RastPort state tracked for {rp:#x}")
        return st

    def test_set_apen_bp_en_dr_md_record(self) -> None:
        self.lib.SetAPen(self.ctx, self.rp, 7)
        self.lib.SetBPen(self.ctx, self.rp, 12)
        self.lib.SetDrMd(self.ctx, self.rp, 0xC0)

        st = self._state(self.rp)
        self.assertEqual(st.apen, 7)
        self.assertEqual(st.bpen, 12)
        self.assertEqual(st.draw_mode, 0xC0)
        self.assertEqual([op["op"] for op in st.ops], ["SetAPen", "SetBPen", "SetDrMd"])

    def test_move_draw_rectfill_record(self) -> None:
        self.lib.Move(self.ctx, self.rp, 0, 0)
        self.lib.Draw(self.ctx, self.rp, 319, 0)
        self.lib.RectFill(self.ctx, self.rp, 0, 0, 319, 199)

        st = self._state(self.rp)
        ops = [op["op"] for op in st.ops]
        self.assertEqual(ops, ["Move", "Draw", "RectFill"])
        self.assertEqual((st.x, st.y), (319, 0))
        self.assertEqual(st.ops[1]["from_x"], 0)
        self.assertEqual(st.ops[1]["x"], 319)
        self.assertEqual(st.ops[2]["y_max"], 199)

    def test_setfont_records_and_returns_previous(self) -> None:
        first = self.lib.SetFont(self.ctx, self.rp, 0x06AA48)
        second = self.lib.SetFont(self.ctx, self.rp, 0x06BB00)

        self.assertEqual(first, 0)
        self.assertEqual(second, 0x06AA48)
        self.assertEqual(self._state(self.rp).font, 0x06BB00)

    def test_set_max_pen_and_outline_pen_return_previous(self) -> None:
        self.assertEqual(self.lib.SetMaxPen(self.ctx, self.rp, 15), 0)
        self.assertEqual(self.lib.SetMaxPen(self.ctx, self.rp, 31), 15)
        self.assertEqual(self.lib.SetOutlinePen(self.ctx, self.rp, 9), 0)
        self.assertEqual(self.lib.SetOutlinePen(self.ctx, self.rp, 10), 9)

    def test_set_ab_pen_dr_md_updates_all_three(self) -> None:
        self.lib.SetABPenDrMd(self.ctx, self.rp, 3, 4, 0x8C)

        st = self._state(self.rp)
        self.assertEqual((st.apen, st.bpen, st.draw_mode), (3, 4, 0x8C))
        self.assertEqual(st.ops[-1]["op"], "SetABPenDrMd")

    def test_area_move_draw_record(self) -> None:
        self.lib.AreaMove(self.ctx, self.rp, 10, 20)
        self.lib.AreaDraw(self.ctx, self.rp, 30, 40)

        st = self._state(self.rp)
        self.assertEqual([op["op"] for op in st.ops], ["AreaMove", "AreaDraw"])
        self.assertEqual((st.x, st.y), (30, 40))
        self.assertEqual(st.ops[1]["from_x"], 10)

    def test_init_rast_port_resets(self) -> None:
        self.lib.SetAPen(self.ctx, self.rp, 7)
        self.lib.InitRastPort(self.ctx, self.rp)

        st = self._state(self.rp)
        self.assertEqual(st.apen, 0)
        self.assertEqual([op["op"] for op in st.ops], ["InitRastPort"])

    def test_frontier_functions_record_in_call_log_not_rastport(self) -> None:
        self.lib.SetRGB32(self.ctx, 0x060000, 5, 255, 128, 0)
        self.lib.AllocBitMap(self.ctx, 320, 200, 1, 0, 0)

        self.assertEqual(len(self.lib.call_log), 2)
        self.assertEqual(self.lib.call_log[0]["func"], "SetRGB32")
        self.assertEqual(self.lib.call_log[0]["args"]["n"], 5)
        self.assertEqual(self.lib.call_log[1]["func"], "AllocBitMap")
        # Frontier calls must not leak into the RastPort drawing model.
        self.assertEqual(self.lib.rastports.total_ops(), 0)


class GraphicsLibraryTextLengthTest(unittest.TestCase):
    """``TextLength`` measures from the RastPort font — not a fake zero."""

    def setUp(self) -> None:
        self.lib = GraphicsLibrary()
        self.rp = 0x06A868  # the window RPort the app measures against (probe log)

    def _state(self, rp: int):
        st = self.lib.rastports.state(rp)
        if st is None:
            self.fail(f"no RastPort state tracked for {rp:#x}")
        return st

    def test_uses_rastport_font_width(self) -> None:
        ctx = _ctx_with_mem({self.rp + 0x3C: 6})  # Topaz fixed width
        # "Order:" — 6 chars measured by the app in main_window.c
        self.assertEqual(self.lib.TextLength(ctx, self.rp, 0x00025194, 6), 36)
        self.assertEqual(self.lib.TextLength(ctx, self.rp, 0x0002519C, 3), 18)
        self.assertEqual(self.lib.TextLength(ctx, self.rp, 0x000251A0, 9), 54)

    def test_uses_a_different_font_width(self) -> None:
        ctx = _ctx_with_mem({self.rp + 0x3C: 8})  # a wider fixed-pitch font
        self.assertEqual(self.lib.TextLength(ctx, self.rp, 0x00020000, 5), 40)

    def test_falls_back_when_rastport_unpopulated(self) -> None:
        ctx = _ctx_with_mem({})  # TxWidth never written -> r16 returns 0
        self.assertEqual(self.lib.TextLength(ctx, self.rp, 0x00020000, 4), 24)  # 4 * 6

    def test_falls_back_on_implausible_width(self) -> None:
        ctx = _ctx_with_mem({self.rp + 0x3C: 0x0006AA48})  # a pointer, not a width
        self.assertEqual(self.lib.TextLength(ctx, self.rp, 0x00020000, 4), 24)  # 4 * 6

    def test_zero_count_is_zero_width(self) -> None:
        ctx = _ctx_with_mem({self.rp + 0x3C: 6})
        self.assertEqual(self.lib.TextLength(ctx, self.rp, 0x00020000, 0), 0)

    def test_no_mem_context_falls_back(self) -> None:
        # The drawing-only _ctx() has no .mem; TextLength must still be sane.
        self.assertEqual(self.lib.TextLength(_ctx(), self.rp, 0x00020000, 6), 36)

    def test_records_measurement_on_rastport(self) -> None:
        ctx = _ctx_with_mem({self.rp + 0x3C: 6})
        self.lib.TextLength(ctx, self.rp, 0x00025194, 6)

        op = self._state(self.rp).ops[-1]
        self.assertEqual(op["op"], "TextLength")
        self.assertEqual(op["string"], 0x00025194)
        self.assertEqual(op["count"], 6)
        self.assertEqual(op["length"], 36)


class GraphicsLibraryTextTest(unittest.TestCase):
    """``Text`` records a text-draw op at the pen position and advances the pen."""

    def setUp(self) -> None:
        self.lib = GraphicsLibrary()
        self.ctx = _ctx()
        self.rp = 0x06A868  # the window RPort the app draws into (from the probe log)

    def _state(self, rp: int):
        st = self.lib.rastports.state(rp)
        if st is None:
            self.fail(f"no RastPort state tracked for {rp:#x}")
        return st

    def test_records_draw_at_pen_position(self) -> None:
        ctx = _ctx_with_mem({self.rp + 0x3C: 6})
        self.lib.Move(self.ctx, self.rp, 19, 21)
        self.lib.Text(ctx, self.rp, 0x00065140, 4)

        st = self._state(self.rp)
        op = st.ops[-1]
        self.assertEqual(op["op"], "Text")
        self.assertEqual(op["string"], 0x00065140)
        self.assertEqual(op["count"], 4)
        self.assertEqual(op["width"], 24)  # 4 * Topaz width 6
        self.assertEqual((op["x"], op["y"]), (19, 21))

    def test_advances_pen_by_drawn_width(self) -> None:
        ctx = _ctx_with_mem({self.rp + 0x3C: 6})
        self.lib.Move(self.ctx, self.rp, 19, 21)
        self.lib.Text(ctx, self.rp, 0x00065140, 4)

        self.assertEqual((self._state(self.rp).x, self._state(self.rp).y), (19 + 24, 21))

    def test_uses_rastport_font_width_for_advance(self) -> None:
        ctx = _ctx_with_mem({self.rp + 0x3C: 8})  # a wider fixed-pitch font
        self.lib.Move(self.ctx, self.rp, 0, 0)
        self.lib.Text(ctx, self.rp, 0x00020000, 5)

        self.assertEqual(self._state(self.rp).x, 40)  # 5 * 8
        self.assertEqual(self._state(self.rp).ops[-1]["width"], 40)

    def test_records_decoded_string_content(self) -> None:
        # "Max:" at the emulated string pointer (the app's actual label).
        ctx = _ctx_with_mem({self.rp + 0x3C: 6})
        ptr = 0x00065140
        for i, ch in enumerate(b"Max:"):
            ctx.mem.w8(ptr + i, ch)
        ctx.mem.w8(ptr + 4, 0)  # NUL terminator

        self.lib.Move(self.ctx, self.rp, 19, 21)
        self.lib.Text(ctx, self.rp, ptr, 4)

        self.assertEqual(self._state(self.rp).ops[-1]["text"], "Max:")

    def test_zero_count_does_not_move_pen(self) -> None:
        ctx = _ctx_with_mem({self.rp + 0x3C: 6})
        self.lib.Move(self.ctx, self.rp, 7, 8)
        self.lib.Text(ctx, self.rp, 0x00020000, 0)

        st = self._state(self.rp)
        self.assertEqual((st.x, st.y), (7, 8))
        self.assertEqual(st.ops[-1]["width"], 0)

    def test_no_mem_context_still_records(self) -> None:
        # The drawing-only _ctx() has no .mem; Text must still record the draw.
        self.lib.Move(self.ctx, self.rp, 3, 4)
        self.lib.Text(_ctx(), self.rp, 0x00020000, 4)

        st = self._state(self.rp)
        self.assertEqual(st.ops[-1]["op"], "Text")
        self.assertEqual(st.ops[-1]["text"], "")
        self.assertEqual(st.x, 3 + 24)  # falls back to Topaz width 6


class GraphicsLibraryScannerTest(unittest.TestCase):
    """Regression guard: every method must be a valid .fd trap (ctx + arg count)."""

    def _scan(self):
        from amitools.fd import read_lib_fd
        from amitools.vamos.libcore.impl import LibImplScanner

        impl = GraphicsLibrary()
        fd = read_lib_fd("graphics.library")
        return LibImplScanner().scan("graphics.library", impl, fd, True)

    def test_no_scanner_errors(self) -> None:
        scan = self._scan()
        self.assertEqual(scan.get_num_error_funcs(), 0, scan.get_error_func_names())
        self.assertEqual(scan.get_num_invalid_funcs(), 0, scan.get_invalid_func_names())
        self.assertGreater(scan.get_num_valid_funcs(), 0)

    def test_six_named_drawing_functions_are_wired(self) -> None:
        scan = self._scan()
        valid = set(scan.get_valid_func_names())
        for name in ("SetAPen", "SetBPen", "SetDrMd", "Move", "Draw", "RectFill"):
            self.assertIn(name, valid)

    def test_text_length_is_a_wired_trap(self) -> None:
        scan = self._scan()
        self.assertIn("TextLength", set(scan.get_valid_func_names()))

    def test_text_is_a_wired_trap(self) -> None:
        scan = self._scan()
        self.assertIn("Text", set(scan.get_valid_func_names()))


if __name__ == "__main__":
    unittest.main()
