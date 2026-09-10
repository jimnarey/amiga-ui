"""Tests for the repo ``gadtools.library`` bevel-box / refresh pair.

Covers, without depending on the iTidy binary, the two GadTools APIs the
target drives to draw the group-box frames:

- ``DrawBevelBoxA(rport, left, top, width, height, taglist)`` records a
  bevel-box op (the group-box / frame bevel) on the host-side RastPort op log,
  reading the ``GT_VisualInfo`` / ``GTBB_Recessed`` tags from the app's tag
  list. It draws at the explicit ``(left, top)`` bounds and does not move the
  RastPort origin;
- ``GT_RefreshWindow(win, req)`` records the refresh request as a host-side
  repaint signal for the future renderer (there is no host window yet);
- a scanner regression guard: both methods must be valid ``.fd`` traps
  (``ctx`` first, exact arg count) so vamos wires them instead of silently
  dropping them as ``UNKNOWN`` traps.

The bevel-box args used here are the real values from the target's probe log
(the group-box frame at ``(0x5f, 0x22)`` size ``(0x18b, 0x0e)``).
"""

import unittest
from types import SimpleNamespace

from amiga_ui.vamos.gadtools_library import (
    _GT_VISUALINFO,
    _GTBB_RECESSED,
    GadToolsLibrary,
)


def _ctx() -> SimpleNamespace:
    """A minimal call context with no 68k memory (the tag parser must be safe)."""
    return SimpleNamespace()


class _FakeMem:
    """A minimal big-endian 68k memory model (unwritten bytes are 0)."""

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


# GTBB_Recessed / GT_VisualInfo are imported from the library above so the
# test's taglist can never drift from the base the library decodes (the classic
# GT_TagBase is TAG_USER (1<<31) + 0x80000 = 0x80080000, matching the binary).
_TAG_END = 0


def _write_bevel_taglist(mem: _FakeMem, taglist: int, vi_ptr: int, recessed: bool) -> None:
    """Write the app's group-box tag list::

    {GT_VisualInfo, vi_ptr, GTBB_Recessed, recessed, TAG_END}
    """
    mem.w32(taglist + 0, _GT_VISUALINFO)
    mem.w32(taglist + 4, vi_ptr)
    mem.w32(taglist + 8, _GTBB_RECESSED)
    mem.w32(taglist + 12, 1 if recessed else 0)
    mem.w32(taglist + 16, _TAG_END)


class GadToolsDrawBevelBoxATest(unittest.TestCase):
    """``DrawBevelBoxA`` records a bevel-box op — not a silent no-op."""

    def setUp(self) -> None:
        self.lib = GadToolsLibrary()
        self.rp = 0x0006A868  # the window RPort the app draws into (probe log)
        self.taglist = 0x00064BD4  # the group-box tag list address (probe log)
        self.vi = 0x0006C100  # a VisualInfo block address

    def _state(self):
        st = self.lib.rastports.state(self.rp)
        if st is None:
            self.fail(f"no RastPort state tracked for {self.rp:#x}")
        return st

    def _ctx_with_tags(self, vi_ptr: int, recessed: bool) -> SimpleNamespace:
        mem = _FakeMem()
        _write_bevel_taglist(mem, self.taglist, vi_ptr, recessed)
        return SimpleNamespace(mem=mem)

    def test_records_bevel_box_at_explicit_bounds(self) -> None:
        ctx = self._ctx_with_tags(self.vi, True)
        # The real group-box frame from the probe: (left, top, width, height).
        self.lib.DrawBevelBoxA(ctx, self.rp, 0x5F, 0x22, 0x18B, 0x0E, self.taglist)

        op = self._state().ops[-1]
        self.assertEqual(op["op"], "DrawBevelBox")
        self.assertEqual((op["left"], op["top"]), (0x5F, 0x22))
        self.assertEqual((op["width"], op["height"]), (0x18B, 0x0E))

    def test_parses_recessed_tag(self) -> None:
        ctx = self._ctx_with_tags(self.vi, True)
        self.lib.DrawBevelBoxA(ctx, self.rp, 0, 0, 10, 10, self.taglist)

        self.assertTrue(self._state().ops[-1]["recessed"])

    def test_parses_visual_info_tag(self) -> None:
        ctx = self._ctx_with_tags(self.vi, True)
        self.lib.DrawBevelBoxA(ctx, self.rp, 0, 0, 10, 10, self.taglist)

        self.assertEqual(self._state().ops[-1]["visual_info"], self.vi)

    def test_no_mem_records_defaults(self) -> None:
        # No 68k memory -> no tag list to read -> defaults (not a fake success,
        # the bevel box is still recorded at its explicit bounds).
        self.lib.DrawBevelBoxA(_ctx(), self.rp, 5, 6, 7, 8, self.taglist)

        op = self._state().ops[-1]
        self.assertEqual(op["op"], "DrawBevelBox")
        self.assertEqual((op["left"], op["top"], op["width"], op["height"]), (5, 6, 7, 8))
        self.assertFalse(op["recessed"])
        self.assertEqual(op["visual_info"], 0)

    def test_does_not_move_pen_origin(self) -> None:
        # The bevel box draws at the explicit bounds, not the RastPort origin,
        # so the origin must be left untouched.
        ctx = self._ctx_with_tags(self.vi, True)
        self.lib.DrawBevelBoxA(ctx, self.rp, 0x5F, 0x22, 0x18B, 0x0E, self.taglist)

        self.assertEqual((self._state().x, self._state().y), (0, 0))


class GadToolsGTRefreshWindowTest(unittest.TestCase):
    """``GT_RefreshWindow`` records a host-side repaint signal — not dropped."""

    def setUp(self) -> None:
        self.lib = GadToolsLibrary()
        self.win = 0x0006B2C8  # the app's window address (probe log)

    def test_records_refresh_request(self) -> None:
        self.lib.GT_RefreshWindow(_ctx(), self.win, 0)

        req = self.lib.refresh_requests[-1]
        self.assertEqual(req["win"], self.win)
        self.assertEqual(req["req"], 0)

    def test_multiple_refreshes_accumulate(self) -> None:
        self.lib.GT_RefreshWindow(_ctx(), self.win, 0)
        self.lib.GT_RefreshWindow(_ctx(), 0x00070000, 0)

        self.assertEqual(len(self.lib.refresh_requests), 2)
        self.assertEqual(self.lib.refresh_requests[-1]["win"], 0x00070000)


class GadToolsSharedRegistryTest(unittest.TestCase):
    """DrawBevelBoxA draws into the launcher's shared RastPort registry when present."""

    def test_draw_bevel_box_uses_shared_registry_on_context(self) -> None:
        # The launcher installs one run-wide registry on ctx.rastports so the
        # bevel box, graphics (Text), and intuition (PrintIText) share a single
        # per-RastPort op log. When it is present, DrawBevelBoxA must record
        # into IT, not into the library's private fallback.
        from amiga_ui.vamos.rastport_state import RastPortRegistry

        lib = GadToolsLibrary()
        shared = RastPortRegistry()
        mem = _FakeMem()
        rp, taglist, vi = 0x0006A868, 0x00064BD4, 0x0006C100
        _write_bevel_taglist(mem, taglist, vi, True)
        ctx = SimpleNamespace(mem=mem, rastports=shared)

        lib.DrawBevelBoxA(ctx, rp, 1, 2, 3, 4, taglist)

        shared_state = shared.state(rp)
        if shared_state is None:
            self.fail("no RastPort state tracked in the shared registry")
        self.assertEqual(shared_state.ops[-1]["op"], "DrawBevelBox")
        # And it must NOT have leaked into the library's private fallback.
        self.assertIsNone(lib.rastports.state(rp))


class GadToolsScannerTest(unittest.TestCase):
    """Regression guard: both bevel/refresh methods must be valid .fd traps."""

    def _scan(self):
        from amitools.fd import read_lib_fd
        from amitools.vamos.libcore.impl import LibImplScanner

        from amiga_ui.vamos.fd_creator import get_repo_fd_dir

        # gadtools.library is not in the default amitools FD set; it lives in
        # the repository NDK FD directory (the same one the launcher installs).
        impl = GadToolsLibrary()
        fd = read_lib_fd("gadtools.library", str(get_repo_fd_dir()))
        return LibImplScanner().scan("gadtools.library", impl, fd, True)

    def test_no_scanner_errors(self) -> None:
        scan = self._scan()
        self.assertEqual(scan.get_num_error_funcs(), 0, scan.get_error_func_names())
        self.assertEqual(scan.get_num_invalid_funcs(), 0, scan.get_invalid_func_names())
        self.assertGreater(scan.get_num_valid_funcs(), 0)

    def test_draw_bevel_box_a_is_a_wired_trap(self) -> None:
        scan = self._scan()
        self.assertIn("DrawBevelBoxA", set(scan.get_valid_func_names()))

    def test_gt_refresh_window_is_a_wired_trap(self) -> None:
        scan = self._scan()
        self.assertIn("GT_RefreshWindow", set(scan.get_valid_func_names()))


if __name__ == "__main__":
    unittest.main()
