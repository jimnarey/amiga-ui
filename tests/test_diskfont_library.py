"""Tests for the repo ``diskfont.library`` ``OpenDiskFont``.

Covers, without depending on the iTidy binary, the ``diskfont.library`` call the
target drives to load a window/icon font:

- ``OpenDiskFont(textAttr)`` reads the ``TextAttr`` (``ta_Name`` font-name
  pointer, ``ta_YSize``) and returns a repo-allocated ``TextFont`` stand-in
  carrying the requested attributes — so the app's ``SetFont`` records a real
  font handle on the RastPort (meaningful emulated state, not an empty success).
  The request (name, size) is recorded for the future renderer;
- a scanner regression guard: the method must be a valid ``.fd`` trap
  (``ctx`` first, exact arg count) so vamos wires it instead of silently
  dropping it as an ``UNKNOWN`` trap.

The ``TextAttr`` layout used here matches the classic m68k NDK:
``ta_Name`` (STRPTR) @ 0x00, ``ta_YSize`` (WORD) @ 0x04.
"""

import unittest
from types import SimpleNamespace

from amiga_ui.vamos.diskfont_library import DiskFontLibrary


def _ctx() -> SimpleNamespace:
    """A minimal call context with no 68k memory (the read must be safe)."""
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


def _write_textattr(mem: _FakeMem, ta: int, name_ptr: int, size: int) -> None:
    """Write a classic ``struct TextAttr``.

    Layout (``<graphics/text.h>`` [S1]): ``ta_Name`` (STRPTR) @ 0x00,
    ``ta_YSize`` (UWORD) @ 0x04, ``ta_Style`` (UBYTE) @ 0x06, ``ta_Flags`` (UBYTE) @ 0x07.
    """
    mem.w32(ta + 0x00, name_ptr)  # STRPTR ta_Name
    mem.w16(ta + 0x04, size)  # UWORD ta_YSize
    mem.w8(ta + 0x06, 0)  # UBYTE ta_Style
    mem.w8(ta + 0x07, 0)  # UBYTE ta_Flags


def _write_string(mem: _FakeMem, addr: int, text: bytes) -> None:
    for i, ch in enumerate(text):
        mem.w8(addr + i, ch)
    mem.w8(addr + len(text), 0)  # NUL terminator


class DiskFontOpenDiskFontTest(unittest.TestCase):
    """``OpenDiskFont`` returns a real font handle — not an empty success."""

    def setUp(self) -> None:
        self.lib = DiskFontLibrary()
        self.ta = 0x00065084  # the app's TextAttr address (probe log)
        self.name_addr = 0x00025000

    def _ctx_with(self, name: bytes, size: int, ta: int | None = None) -> SimpleNamespace:
        mem = _FakeMem()
        ta = ta if ta is not None else self.ta
        name_addr = self.name_addr if ta == self.ta else 0x00026000
        _write_textattr(mem, ta, name_addr, size)
        _write_string(mem, name_addr, name)
        return SimpleNamespace(mem=mem, alloc=_FakeAlloc())

    def test_returns_non_null_font_handle(self) -> None:
        ctx = self._ctx_with(b"Topaz", 8)
        handle = self.lib.OpenDiskFont(ctx, self.ta)

        self.assertNotEqual(handle, 0)

    def test_records_requested_name(self) -> None:
        ctx = self._ctx_with(b"Topaz", 8)
        self.lib.OpenDiskFont(ctx, self.ta)

        op = self.lib.font_opens[-1]
        self.assertEqual(op["name"], "Topaz")
        self.assertEqual(op["text_attr"], self.ta)

    def test_records_requested_size(self) -> None:
        ctx = self._ctx_with(b"Topaz", 10)
        self.lib.OpenDiskFont(ctx, self.ta)

        self.assertEqual(self.lib.font_opens[-1]["size"], 10)

    def test_handle_carries_font_name(self) -> None:
        # The returned handle is a real font block carrying the requested name,
        # so a future renderer can see which font the app asked for.
        ctx = self._ctx_with(b"Topaz", 8)
        handle = self.lib.OpenDiskFont(ctx, self.ta)

        stored = b"".join(bytes([ctx.mem.r8(handle + i)]) for i in range(5))
        self.assertEqual(stored, b"Topaz")

    def test_no_mem_returns_null(self) -> None:
        # No 68k memory -> no TextAttr to read -> NULL (the app falls back to the
        # screen font, which it handles gracefully).
        self.assertEqual(self.lib.OpenDiskFont(_ctx(), self.ta), 0)

    def test_multiple_opens_accumulate(self) -> None:
        # Each open appends a record, read from its own TextAttr address.
        self.lib.OpenDiskFont(self._ctx_with(b"Topaz", 8), self.ta)
        self.lib.OpenDiskFont(self._ctx_with(b"FixedSys", 8, ta=0x000650A8), 0x000650A8)

        self.assertEqual(len(self.lib.font_opens), 2)
        self.assertEqual(self.lib.font_opens[0]["name"], "Topaz")
        self.assertEqual(self.lib.font_opens[-1]["name"], "FixedSys")


class _FakeAlloc:
    """A minimal memory allocator that hands out distinct, monotonically-increasing
    addresses (enough to verify OpenDiskFont returns a real handle)."""

    def __init__(self) -> None:
        self._next = 0x00070000

    def alloc_memory(self, size: int, label: str = "") -> SimpleNamespace:
        addr = self._next
        self._next += max(size, 16)
        return SimpleNamespace(addr=addr)


class DiskFontScannerTest(unittest.TestCase):
    """Regression guard: OpenDiskFont must be a valid .fd trap."""

    def _scan(self):
        from amitools.fd import read_lib_fd
        from amitools.vamos.libcore.impl import LibImplScanner

        from amiga_ui.vamos.fd_creator import get_repo_fd_dir

        # diskfont.library is not in the default amitools FD set; it lives in the
        # repository NDK FD directory (the same one the launcher installs).
        impl = DiskFontLibrary()
        fd = read_lib_fd("diskfont.library", str(get_repo_fd_dir()))
        return LibImplScanner().scan("diskfont.library", impl, fd, True)

    def test_no_scanner_errors(self) -> None:
        scan = self._scan()
        self.assertEqual(scan.get_num_error_funcs(), 0, scan.get_error_func_names())
        self.assertEqual(scan.get_num_invalid_funcs(), 0, scan.get_invalid_func_names())
        self.assertGreater(scan.get_num_valid_funcs(), 0)

    def test_open_disk_font_is_a_wired_trap(self) -> None:
        scan = self._scan()
        self.assertIn("OpenDiskFont", set(scan.get_valid_func_names()))


if __name__ == "__main__":
    unittest.main()
