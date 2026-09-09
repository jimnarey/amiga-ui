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

from amiga_ui.vamos.exec_library import PeekPortManager
from amiga_ui.vamos.intuition_library import IntuitionLibrary
from amiga_ui.vamos.rastport_state import JAM2, RastPortRegistry


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
    # UBYTE DrawMode: the classic IntuiText DrawMode is a *different* value set
    # from the RastPort DrMd (the local NDK 3.2 subset does not define its bit
    # values), and the repo's PrintIText does not decode it (documented
    # deferral). Written 0 — an honest uninitialised value, not a RastPort mode.
    mem.w8(itext + 0x02, 0)
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


# Intuition window tags (WA_*): the target's NDK defines TAG_USER as the high
# bit (1 << 31), so WA_Dummy = (1 << 31) + 99 and WA_BusyPointer = WA_Dummy + 0x35.
_WA_DUMMY = (1 << 31) + 99
_WA_LEFT = _WA_DUMMY + 0x01
_WA_TOP = _WA_DUMMY + 0x02
_WA_BUSY_POINTER = _WA_DUMMY + 0x35
_TAG_END = 0


def _write_pointer_taglist(mem: _FakeMem, taglist: int, busy: bool | None, left: int | None, top: int | None) -> None:
    """Write a ``SetWindowPointerA`` tag list ending in ``TAG_END``."""
    offset = 0
    if busy is not None:
        mem.w32(taglist + offset, _WA_BUSY_POINTER)
        mem.w32(taglist + offset + 4, 1 if busy else 0)
        offset += 8
    if left is not None:
        mem.w32(taglist + offset, _WA_LEFT)
        mem.w32(taglist + offset + 4, left)
        offset += 8
    if top is not None:
        mem.w32(taglist + offset, _WA_TOP)
        mem.w32(taglist + offset + 4, top)
        offset += 8
    mem.w32(taglist + offset, _TAG_END)


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


# --- window-owned RastPort fakes ----------------------------------------------
class _FakeBlock:
    def __init__(self, addr: int, size: int) -> None:
        self.addr = addr
        self.size = size


class _FakeAlloc:
    """Minimal MemoryAlloc stand-in: a bump allocator that tracks live/freed blocks."""

    def __init__(self, mem: _FakeMem, base: int = 0x080000) -> None:
        self.mem = mem
        self.next_addr = base
        self.freed: list[int] = []
        self.live: dict[int, _FakeBlock] = {}

    def alloc_memory(self, size: int, label: str | None = None) -> _FakeBlock:
        addr = self.next_addr
        self.next_addr += (size + 3) & ~3
        block = _FakeBlock(addr, size)
        self.live[addr] = block
        return block

    def alloc_cstr(self, text: str, label: str | None = None) -> _FakeBlock:
        encoded = text.encode("latin-1") + b"\x00"
        block = self.alloc_memory(len(encoded), label=label)
        for i, ch in enumerate(encoded):
            self.mem.w8(block.addr + i, ch)
        return block

    def free_memory(self, block: _FakeBlock) -> None:
        self.freed.append(block.addr)
        self.live.pop(block.addr, None)


class _FakeVLib:
    def __init__(self, impl) -> None:
        self.impl = impl


class _FakeVLibMgr:
    def __init__(self, exec_impl) -> None:
        self._exec = _FakeVLib(exec_impl)

    def get_vlib_by_name(self, name: str):
        return self._exec if name == "exec.library" else None


# struct Window offsets (mirrors intuition_library.py) for reading the result.
_W_OFF_WIDTH = 0x08
_W_OFF_HEIGHT = 0x0A
_W_OFF_TITLE = 0x20
_W_OFF_WSCREEN = 0x2E
_W_OFF_RPORT = 0x32
# struct RastPort offsets (NDK 3.2 graphics/rastport.h).
_RP_OFF_MASK = 0x18
_RP_OFF_FGPEN = 0x19
_RP_OFF_BGPEN = 0x1A
_RP_OFF_AOLPEN = 0x1B
_RP_OFF_DRMODE = 0x1C
_RP_OFF_FONT = 0x34
_RP_OFF_TXHEIGHT = 0x3A
_RP_OFF_TXWIDTH = 0x3C
# struct Screen offsets (mirrors intuition_library.py).
_S_OFF_RASTPORT = 0x54
_S_OFF_RP_FONT = 0x54 + 0x34
_S_OFF_RP_TXHEIGHT = 0x54 + 0x3A
_S_OFF_RP_TXWIDTH = 0x54 + 0x3C
# Classic WA_ tags for OpenWindowTagList (WA_Dummy = 0x80000063).
_OWA_LEFT = 0x80000064
_OWA_TOP = 0x80000065
_OWA_WIDTH = 0x80000066
_OWA_HEIGHT = 0x80000067
_OWA_TITLE = 0x8000006E


class IntuitionWindowRPortTest(unittest.TestCase):
    """Each opened window gets its own RastPort drawing target (not the screen's)."""

    def setUp(self) -> None:
        self.lib = IntuitionLibrary()
        self.mem = _FakeMem()
        self.alloc = _FakeAlloc(self.mem)
        self.registry = RastPortRegistry()
        exec_impl = SimpleNamespace(port_mgr=PeekPortManager(self.alloc))
        self.ctx = SimpleNamespace(mem=self.mem, alloc=self.alloc, vlib_mgr=_FakeVLibMgr(exec_impl), rastports=self.registry)

    def _write_open_tags(self, taglist: int, *, left, top, width, height, title=0) -> None:
        mem = self.mem
        offset = 0
        for tag, data in ((_OWA_LEFT, left), (_OWA_TOP, top), (_OWA_WIDTH, width), (_OWA_HEIGHT, height), (_OWA_TITLE, title)):
            mem.w32(taglist + offset, tag)
            mem.w32(taglist + offset + 4, data)
            offset += 8
        mem.w32(taglist + offset, 0)  # TAG_END

    def _open_window(self, taglist: int, **kwargs) -> int:
        self._write_open_tags(taglist, **kwargs)
        return self.lib.OpenWindowTagList(self.ctx, 0, taglist)

    def test_window_rport_is_not_the_screen_rport(self) -> None:
        screen = self.lib.LockPubScreen(self.ctx, 0)
        win = self._open_window(0x00065000, left=10, top=20, width=100, height=50)

        win_rp = self.mem.r32(win + _W_OFF_RPORT)
        screen_rp = screen + _S_OFF_RASTPORT
        self.assertNotEqual(win_rp, screen_rp)
        # The public screen's embedded RPort stays a valid drawing target for
        # screen-level APIs — it is just no longer handed out as a window RPort.
        self.assertNotEqual(self.mem.r32(screen_rp + _RP_OFF_FONT), 0)
        self.assertNotEqual(self.mem.r16(screen_rp + _RP_OFF_TXWIDTH), 0)

    def test_window_rport_has_standard_values_and_inherited_font_metrics(self) -> None:
        screen = self.lib.LockPubScreen(self.ctx, 0)
        win = self._open_window(0x00065000, left=10, top=20, width=100, height=50)
        win_rp = self.mem.r32(win + _W_OFF_RPORT)

        # Documented standard RastPort values (NDK AutoDocs InitRastPort).
        self.assertEqual(self.mem.r8(win_rp + _RP_OFF_MASK), 0xFF)
        self.assertEqual(self.mem.r8(win_rp + _RP_OFF_FGPEN), 0xFF)
        self.assertEqual(self.mem.r8(win_rp + _RP_OFF_BGPEN), 0)
        self.assertEqual(self.mem.r8(win_rp + _RP_OFF_AOLPEN), 0xFF)
        self.assertEqual(self.mem.r8(win_rp + _RP_OFF_DRMODE), JAM2)
        # Font pointer + text metrics inherited explicitly from the screen RPort.
        self.assertEqual(self.mem.r32(win_rp + _RP_OFF_FONT), self.mem.r32(screen + _S_OFF_RP_FONT))
        self.assertEqual(self.mem.r16(win_rp + _RP_OFF_TXHEIGHT), self.mem.r16(screen + _S_OFF_RP_TXHEIGHT))
        self.assertEqual(self.mem.r16(win_rp + _RP_OFF_TXWIDTH), self.mem.r16(screen + _S_OFF_RP_TXWIDTH))

    def test_window_rport_state_registered_in_shared_registry(self) -> None:
        win = self._open_window(0x00065000, left=10, top=20, width=100, height=50)
        win_rp = self.mem.r32(win + _W_OFF_RPORT)

        st = self.registry.state(win_rp)
        if st is None:
            self.fail("the window RPort state must be registered up front")
        # Registered up front with the standard values, before any app drawing.
        self.assertEqual(st.apen, 0xFF)
        self.assertEqual(st.bpen, 0)
        self.assertEqual(st.draw_mode, JAM2)

    def test_two_windows_have_isolated_op_streams(self) -> None:
        win_a = self._open_window(0x00065000, left=10, top=20, width=100, height=50)
        win_b = self._open_window(0x00066000, left=10, top=20, width=100, height=50)
        rp_a = self.mem.r32(win_a + _W_OFF_RPORT)
        rp_b = self.mem.r32(win_b + _W_OFF_RPORT)
        self.assertNotEqual(rp_a, rp_b)

        # Draw into each window's own RPort; the streams must not mix.
        self.registry.get_or_create(rp_a).set_apen(0)
        self.registry.get_or_create(rp_a).rect_fill(1, 2, 3, 4)
        self.registry.get_or_create(rp_b).set_bpen(5)

        st_a = self.registry.state(rp_a)
        st_b = self.registry.state(rp_b)
        if st_a is None or st_b is None:
            self.fail("both window RPort states must be registered")
        ops_a = [op["op"] for op in st_a.ops]
        ops_b = [op["op"] for op in st_b.ops]
        self.assertEqual(ops_a, ["SetAPen", "RectFill"])
        self.assertEqual(ops_b, ["SetBPen"])
        # Window B's fill must not appear in A's stream (and vice versa).
        self.assertNotIn("RectFill", ops_b)
        self.assertNotIn("SetBPen", ops_a)

    def test_close_window_releases_only_its_own_rport(self) -> None:
        win_a = self._open_window(0x00065000, left=10, top=20, width=100, height=50)
        win_b = self._open_window(0x00066000, left=10, top=20, width=100, height=50)
        rp_a = self.mem.r32(win_a + _W_OFF_RPORT)
        rp_b = self.mem.r32(win_b + _W_OFF_RPORT)
        self.registry.get_or_create(rp_a).set_apen(1)
        self.registry.get_or_create(rp_b).set_apen(2)

        self.lib.CloseWindow(self.ctx, win_a)

        # Window A's drawing state is gone; window B's is untouched.
        self.assertIsNone(self.registry.state(rp_a))
        st_b = self.registry.state(rp_b)
        if st_b is None:
            self.fail("window B's RPort state must survive closing window A")
        self.assertEqual(st_b.apen, 2)
        # Window A's RPort block (and the window) were freed; B's blocks are live.
        self.assertIn(rp_a, self.alloc.freed)
        self.assertIn(win_a, self.alloc.freed)
        self.assertNotIn(rp_b, self.alloc.freed)
        self.assertIn(rp_b, self.alloc.live)

    def test_close_window_notifies_projection(self) -> None:
        closed: list[int] = []
        opened: list[int] = []

        class _Probe:
            def open_window(self, intent):
                opened.append(intent.window_addr)

            def refresh_window(self, intent, ops):
                pass

            def close_window(self, window_addr):
                closed.append(window_addr)

        self.ctx.host_projection = _Probe()
        win = self._open_window(0x00065000, left=10, top=20, width=100, height=50)

        self.assertEqual(opened, [win])
        # The projection saw the window's *own* RPort (not the screen RPort).
        self.lib.CloseWindow(self.ctx, win)
        self.assertEqual(closed, [win])


class IntuitionSetWindowPointerATest(unittest.TestCase):
    """``SetWindowPointerA`` records the request — not a silent no-op."""

    def setUp(self) -> None:
        self.lib = IntuitionLibrary()
        self.win = 0x0006B2C8  # the app's window address (probe log)
        self.taglist = 0x00064C00

    def _ctx_with(self, busy: bool | None, left: int | None = None, top: int | None = None) -> SimpleNamespace:
        mem = _FakeMem()
        _write_pointer_taglist(mem, self.taglist, busy, left, top)
        return SimpleNamespace(mem=mem)

    def test_records_busy_pointer_true(self) -> None:
        ctx = self._ctx_with(True)
        self.lib.SetWindowPointerA(ctx, self.win, self.taglist)

        op = self.lib.set_window_pointer_ops[-1]
        self.assertEqual(op["win"], self.win)
        self.assertTrue(op["busy_pointer"])
        self.assertIsNone(op["new_pos"])

    def test_records_busy_pointer_false(self) -> None:
        ctx = self._ctx_with(False)
        self.lib.SetWindowPointerA(ctx, self.win, self.taglist)

        self.assertFalse(self.lib.set_window_pointer_ops[-1]["busy_pointer"])

    def test_records_new_position(self) -> None:
        ctx = self._ctx_with(None, left=10, top=20)
        self.lib.SetWindowPointerA(ctx, self.win, self.taglist)

        op = self.lib.set_window_pointer_ops[-1]
        self.assertIsNone(op["busy_pointer"])
        self.assertEqual(op["new_pos"], (10, 20))

    def test_no_mem_records_defaults(self) -> None:
        # No 68k memory -> no tag list to read -> defaults (the request is still
        # recorded, not dropped).
        self.lib.SetWindowPointerA(_ctx(), self.win, self.taglist)

        op = self.lib.set_window_pointer_ops[-1]
        self.assertEqual(op["win"], self.win)
        self.assertIsNone(op["busy_pointer"])
        self.assertIsNone(op["new_pos"])

    def test_multiple_calls_accumulate(self) -> None:
        self.lib.SetWindowPointerA(self._ctx_with(True), self.win, self.taglist)
        self.lib.SetWindowPointerA(self._ctx_with(False), self.win, self.taglist)

        self.assertEqual(len(self.lib.set_window_pointer_ops), 2)
        self.assertFalse(self.lib.set_window_pointer_ops[-1]["busy_pointer"])


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

    def test_set_window_pointer_a_is_a_wired_trap(self) -> None:
        scan = self._scan()
        self.assertIn("SetWindowPointerA", set(scan.get_valid_func_names()))


if __name__ == "__main__":
    unittest.main()
