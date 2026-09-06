"""Tests for the repo ``intuition.library`` IntuiText pair.

Covers, without depending on the iTidy binary, the two Intuition text APIs the
target drives to draw group-box / requester titles:

- ``IntuiTextLength`` measures the IntuiText's string (reading the string
  pointer from the classic pre-2.0 field layout the target builds — GCC-aligned
  on m68k, string pointer at 0x0C) and returns ``count * font width``;
- ``PrintIText`` records the draw at the explicit ``(left, top)`` in the
  IntuiText's own front pen on the host-side RastPort op log (the same shared
  registry graphics.library's ``Text`` uses), without moving the RastPort origin;
- a scanner regression guard: both methods must be valid ``.fd`` traps
  (``ctx`` first, exact arg count) so vamos wires them instead of silently
  dropping them as ``UNKNOWN`` traps.

The 0x0C string-pointer offset is the ABI crux: it was confirmed from the
running target (the three group-box titles "Folder", "Tidy options", "Tools"
decode correctly only at 0x0C, not the packed 0x0B). See
``docs/apps/itidy/compatibility-notes.md``.
"""

import unittest
from types import SimpleNamespace

from amiga_ui.vamos.intuition_library import IntuitionLibrary


def _ctx() -> SimpleNamespace:
    """A minimal call context with no 68k memory (the read helpers must be safe)."""
    return SimpleNamespace()


class _FakeMem:
    """A minimal big-endian 68k memory model (unwritten bytes are 0).

    Byte-backed so ``r8``/``w8`` (string content, pens), ``r16``/``w16``
    (``RastPort.TxWidth``), and ``r32``/``w32`` (IntuiText pointer fields) all
    work over the same storage.
    """

    def __init__(self) -> None:
        self._bytes: dict[int, int] = {}

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

    def r32(self, addr: int) -> int:
        return (self.r8(addr) << 24) | (self.r8(addr + 1) << 16) | (self.r8(addr + 2) << 8) | self.r8(addr + 3)

    def w32(self, addr: int, value: int) -> None:
        value &= 0xFFFFFFFF
        self.w8(addr, (value >> 24) & 0xFF)
        self.w8(addr + 1, (value >> 16) & 0xFF)
        self.w8(addr + 2, (value >> 8) & 0xFF)
        self.w8(addr + 3, value & 0xFF)


def _write_itext(mem: _FakeMem, itext: int, text_addr: int, front_pen: int = 0) -> None:
    """Write a GCC-aligned classic ``struct IntuiText`` into ``mem``.

    The target's ``vc +aos68k`` compiler aligns members to their natural
    alignment (no packing), so the string pointer ``IText`` sits at 0x0C — NOT
    the packed 0x0B. This is the layout the running target actually uses.
    """
    mem.w8(itext + 0x00, front_pen)  # UBYTE FrontPen
    mem.w8(itext + 0x01, 0)  # UBYTE BackPen
    mem.w8(itext + 0x02, 0x8C)  # UBYTE DrawMode (JAM2)
    # 0x03 is alignment padding
    mem.w16(itext + 0x04, 0)  # WORD LeftEdge
    mem.w16(itext + 0x06, 0)  # WORD TopEdge
    # 0x08 is alignment padding before the pointer members
    mem.w32(itext + 0x08, 0)  # APTR TextAttr *ITextFont (NULL)
    mem.w32(itext + 0x0C, text_addr)  # STRPTR IText (the string pointer)
    mem.w32(itext + 0x10, 0)  # APTR IntuiText *NextText (NULL)


def _write_string(mem: _FakeMem, addr: int, text: bytes) -> None:
    for i, ch in enumerate(text):
        mem.w8(addr + i, ch)
    mem.w8(addr + len(text), 0)  # NUL terminator


class IntuitionIntuiTextLengthTest(unittest.TestCase):
    """``IntuiTextLength`` measures the IntuiText's string — not a fake zero."""

    def setUp(self) -> None:
        self.lib = IntuitionLibrary()
        self.itext = 0x00064E4C  # the app's IntuiText address (probe log)
        self.str_addr = 0x00025E14  # the "Folder" string address (probe log)

    def _ctx_with(self, text: bytes) -> SimpleNamespace:
        mem = _FakeMem()
        _write_itext(mem, self.itext, self.str_addr)
        _write_string(mem, self.str_addr, text)
        return SimpleNamespace(mem=mem)

    def test_measures_folder_title(self) -> None:
        # "Folder" is 6 chars; with no screen allocated the width is the Topaz
        # baseline (6), so 6 * 6 = 36.
        ctx = self._ctx_with(b"Folder")
        self.assertEqual(self.lib.IntuiTextLength(ctx, self.itext), 36)

    def test_measures_tidy_options_title(self) -> None:
        # "Tidy options" is 12 chars -> 12 * 6 = 72.
        ctx = self._ctx_with(b"Tidy options")
        self.assertEqual(self.lib.IntuiTextLength(ctx, self.itext), 72)

    def test_reads_string_from_aligned_offset_0c(self) -> None:
        # The ABI crux: the string pointer is at 0x0C (GCC-aligned). A wrong
        # offset (the packed 0x0B) would read a short pointer and measure 0
        # characters, so a positive width proves the 0x0C layout is honoured.
        ctx = self._ctx_with(b"Folder")
        self.assertGreater(self.lib.IntuiTextLength(ctx, self.itext), 0)

    def test_records_measurement_with_decoded_text(self) -> None:
        ctx = self._ctx_with(b"Tools")
        self.lib.IntuiTextLength(ctx, self.itext)

        m = self.lib.itext_measures[-1]
        self.assertEqual(m["itext"], self.itext)
        self.assertEqual(m["string"], self.str_addr)
        self.assertEqual(m["count"], 5)
        self.assertEqual(m["width"], 30)  # 5 * Topaz width 6
        self.assertEqual(m["text"], "Tools")

    def test_no_mem_returns_zero(self) -> None:
        # No 68k memory -> no string to read -> width 0 (honest, not a fake).
        self.assertEqual(self.lib.IntuiTextLength(_ctx(), self.itext), 0)


class IntuitionPrintITextTest(unittest.TestCase):
    """``PrintIText`` records a draw at the explicit position in the IntuiText pen."""

    def setUp(self) -> None:
        self.lib = IntuitionLibrary()
        self.rp = 0x0006A868  # the window RPort the app draws into (probe log)
        self.itext = 0x00064E4C
        self.str_addr = 0x00025E14

    def _ctx_with(self, text: bytes, txwidth: int | None = 6) -> SimpleNamespace:
        mem = _FakeMem()
        if txwidth is not None:
            mem.w16(self.rp + 0x3C, txwidth)  # RastPort.TxWidth
        _write_itext(mem, self.itext, self.str_addr, front_pen=1)
        _write_string(mem, self.str_addr, text)
        return SimpleNamespace(mem=mem)

    def _state(self):
        st = self.lib.rastports.state(self.rp)
        if st is None:
            self.fail(f"no RastPort state tracked for {self.rp:#x}")
        return st

    def test_records_draw_at_explicit_position(self) -> None:
        ctx = self._ctx_with(b"Folder")
        self.lib.PrintIText(ctx, self.rp, self.itext, 42, 3)

        op = self._state().ops[-1]
        self.assertEqual(op["op"], "PrintIText")
        self.assertEqual(op["string"], self.str_addr)
        self.assertEqual(op["count"], 6)
        self.assertEqual(op["width"], 36)  # 6 * Topaz width 6
        self.assertEqual((op["x"], op["y"]), (42, 3))
        self.assertEqual(op["front_pen"], 1)

    def test_uses_rastport_font_width(self) -> None:
        ctx = self._ctx_with(b"Tools", txwidth=8)  # a wider fixed-pitch font
        self.lib.PrintIText(ctx, self.rp, self.itext, 0, 0)

        self.assertEqual(self._state().ops[-1]["width"], 40)  # 5 * 8

    def test_does_not_move_pen_origin(self) -> None:
        # Unlike graphics Text (which advances the origin), PrintIText draws at
        # the explicit (left, top) and must leave the RastPort origin untouched.
        ctx = self._ctx_with(b"Folder")
        self.lib.PrintIText(ctx, self.rp, self.itext, 42, 3)

        self.assertEqual((self._state().x, self._state().y), (0, 0))

    def test_records_decoded_text(self) -> None:
        ctx = self._ctx_with(b"Folder")
        self.lib.PrintIText(ctx, self.rp, self.itext, 42, 3)

        self.assertEqual(self._state().ops[-1]["text"], "Folder")

    def test_falls_back_when_rastport_unpopulated(self) -> None:
        ctx = self._ctx_with(b"Folder", txwidth=None)  # TxWidth never written
        self.lib.PrintIText(ctx, self.rp, self.itext, 0, 0)

        self.assertEqual(self._state().ops[-1]["width"], 36)  # 6 * 6 fallback


class IntuitionSharedRegistryTest(unittest.TestCase):
    """PrintIText draws into the launcher's shared RastPort registry when present."""

    def test_print_itext_uses_shared_registry_on_context(self) -> None:
        # The launcher installs one run-wide registry on ctx.rastports so
        # graphics (Text) and intuition (PrintIText) share a per-RastPort op
        # log. When it is present, PrintIText must record into IT, not into the
        # library's private fallback.
        from amiga_ui.vamos.rastport_state import RastPortRegistry

        lib = IntuitionLibrary()
        shared = RastPortRegistry()
        mem = _FakeMem()
        rp, itext, str_addr = 0x0006A868, 0x00064E4C, 0x00025E14
        _write_itext(mem, itext, str_addr, front_pen=2)
        _write_string(mem, str_addr, b"Folder")
        ctx = SimpleNamespace(mem=mem, rastports=shared)

        lib.PrintIText(ctx, rp, itext, 10, 5)

        shared_state = shared.state(rp)
        if shared_state is None:
            self.fail("no RastPort state tracked in the shared registry")
        shared_op = shared_state.ops[-1]
        self.assertEqual(shared_op["op"], "PrintIText")
        self.assertEqual(shared_op["front_pen"], 2)
        # And it must NOT have leaked into the library's private fallback.
        self.assertIsNone(lib.rastports.state(rp))


class IntuitionScannerTest(unittest.TestCase):
    """Regression guard: both IntuiText methods must be valid .fd traps."""

    def _scan(self):
        from amitools.fd import read_lib_fd
        from amitools.vamos.libcore.impl import LibImplScanner

        impl = IntuitionLibrary()
        fd = read_lib_fd("intuition.library")
        return LibImplScanner().scan("intuition.library", impl, fd, True)

    def test_no_scanner_errors(self) -> None:
        scan = self._scan()
        self.assertEqual(scan.get_num_error_funcs(), 0, scan.get_error_func_names())
        self.assertEqual(scan.get_num_invalid_funcs(), 0, scan.get_invalid_func_names())
        self.assertGreater(scan.get_num_valid_funcs(), 0)

    def test_intuitext_length_is_a_wired_trap(self) -> None:
        scan = self._scan()
        self.assertIn("IntuiTextLength", set(scan.get_valid_func_names()))

    def test_print_itext_is_a_wired_trap(self) -> None:
        scan = self._scan()
        self.assertIn("PrintIText", set(scan.get_valid_func_names()))


if __name__ == "__main__":
    unittest.main()
