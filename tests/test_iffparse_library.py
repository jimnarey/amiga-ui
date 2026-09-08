"""Tests for the repo ``iffparse.library`` ``AllocIFF``/``FreeIFF`` lifecycle.

Covers, without depending on the iTidy binary, the iffparse call the target
makes during startup in ``window_management.c`` / ``Settings/IControlPrefs.c``:
the app calls ``AllocIFF()`` to get a parser, fails to open an absent
``ENV:sys/*.prefs`` file, and calls ``FreeIFF(iff)`` to release it. No chunk
parsing is exercised in that path.

The assertions pin the honest handle semantics (not a constant dummy handle):

- ``AllocIFF()()`` returns a real, distinct emulated-memory address on each call
  (the handle the caller may write through), tracked by the library;
- ``FreeIFF(iff)`` (A0 = handle) releases exactly a handle this library handed
  out and frees the underlying allocation;
- freeing an unknown or already-freed handle is an honest no-op (not a success
  on garbage, and no double free);
- a scanner regression guard: ``AllocIFF`` and ``FreeIFF`` must be valid ``.fd``
  traps (``ctx`` first, exact arg count) so vamos wires them instead of
  silently dropping ``FreeIFF`` as an ``UNKNOWN`` trap.

The remaining iffparse traps (``OpenIFF``/``ParseIFF``/``CurrentChunk``/...) are
pre-existing no-op boundary stubs the target never reaches in this path and are
deliberately not a general IFF parser; they are not asserted here.
"""

import unittest
from types import SimpleNamespace

from amitools.vamos.machine.regs import REG_A0

from amiga_ui.vamos.iffparse_library import IffParseLibrary


class _FakeCpu:
    """A minimal CPU whose register reads return a fixed value for REG_A0."""

    def __init__(self, a0: int = 0) -> None:
        self._a0 = a0

    def r_reg(self, reg: int) -> int:
        return self._a0 if reg == REG_A0 else 0


class _FakeAlloc:
    """A minimal ``ctx.alloc`` model that tracks allocations and frees."""

    def __init__(self) -> None:
        self._next_addr = 0x00D00000
        self.freed: list[int] = []
        self.sizes: dict[int, int] = {}

    def alloc_memory(self, size: int, label: str | None = None, except_on_failure: bool = True):
        addr = self._next_addr
        self._next_addr += (size + 15) & ~15
        self.sizes[addr] = size
        return SimpleNamespace(addr=addr, size=size, label=label)

    def free_memory(self, mem) -> None:
        self.freed.append(getattr(mem, "addr", 0))


def _ctx(a0: int = 0, alloc: _FakeAlloc | None = None) -> SimpleNamespace:
    return SimpleNamespace(cpu=_FakeCpu(a0), alloc=alloc)


class AllocIFFTest(unittest.TestCase):
    """``AllocIFF`` returns a real, tracked, distinct handle per call."""

    def test_returns_distinct_nonzero_handles(self) -> None:
        lib = IffParseLibrary()
        alloc = _FakeAlloc()

        h1 = lib.AllocIFF(_ctx(alloc=alloc))
        h2 = lib.AllocIFF(_ctx(alloc=alloc))

        self.assertTrue(h1)
        self.assertTrue(h2)
        self.assertNotEqual(h1, h2)
        # Both handles are tracked by the library.
        self.assertEqual(set(lib._iff_handles), {h1, h2})
        # Nothing has been freed yet.
        self.assertEqual(alloc.freed, [])

    def test_handles_are_real_alloc_addresses(self) -> None:
        lib = IffParseLibrary()
        alloc = _FakeAlloc()

        h1 = lib.AllocIFF(_ctx(alloc=alloc))

        # The handle is the emulated address of the allocation the fake made,
        # backed by the documented IFFparse control-block size.
        self.assertEqual(h1, 0x00D00000)
        self.assertEqual(alloc.sizes[h1], 256)

    def test_without_alloc_returns_null(self) -> None:
        lib = IffParseLibrary()

        # No allocator available -> honest NULL, nothing tracked.
        self.assertEqual(lib.AllocIFF(_ctx(alloc=None)), 0)
        self.assertEqual(lib._iff_handles, {})


class FreeIFFTest(unittest.TestCase):
    """``FreeIFF`` releases exactly the handles this library allocated."""

    def test_releases_a_tracked_handle(self) -> None:
        lib = IffParseLibrary()
        alloc = _FakeAlloc()
        h1 = lib.AllocIFF(_ctx(alloc=alloc))

        lib.FreeIFF(_ctx(a0=h1, alloc=alloc))

        self.assertNotIn(h1, lib._iff_handles)
        self.assertEqual(alloc.freed, [h1])

    def test_ignores_an_unknown_handle(self) -> None:
        lib = IffParseLibrary()
        alloc = _FakeAlloc()

        # Freeing a handle this library never allocated is an honest no-op.
        lib.FreeIFF(_ctx(a0=0xDEAD0001, alloc=alloc))

        self.assertEqual(lib._iff_handles, {})
        self.assertEqual(alloc.freed, [])

    def test_double_free_frees_exactly_once(self) -> None:
        lib = IffParseLibrary()
        alloc = _FakeAlloc()
        h1 = lib.AllocIFF(_ctx(alloc=alloc))

        lib.FreeIFF(_ctx(a0=h1, alloc=alloc))
        lib.FreeIFF(_ctx(a0=h1, alloc=alloc))

        # The underlying allocation is freed exactly once, not twice.
        self.assertEqual(alloc.freed, [h1])
        self.assertEqual(lib._iff_handles, {})

    def test_releases_only_the_matching_handle(self) -> None:
        lib = IffParseLibrary()
        alloc = _FakeAlloc()
        h1 = lib.AllocIFF(_ctx(alloc=alloc))
        h2 = lib.AllocIFF(_ctx(alloc=alloc))

        lib.FreeIFF(_ctx(a0=h1, alloc=alloc))

        self.assertNotIn(h1, lib._iff_handles)
        self.assertIn(h2, lib._iff_handles)
        self.assertEqual(alloc.freed, [h1])


class IffParseScannerTest(unittest.TestCase):
    """Regression guard: AllocIFF/FreeIFF must be valid .fd traps."""

    def _scan(self):
        from amitools.fd import read_lib_fd
        from amitools.vamos.libcore.impl import LibImplScanner

        impl = IffParseLibrary()
        fd = read_lib_fd("iffparse.library")
        return LibImplScanner().scan("iffparse.library", impl, fd, True)

    def test_allociff_and_freeiff_are_wired_traps(self) -> None:
        scan = self._scan()
        valid = set(scan.get_valid_func_names())
        self.assertIn("AllocIFF", valid)
        self.assertIn("FreeIFF", valid)

    def test_freeiff_has_no_scanner_error(self) -> None:
        # FreeIFF was the defaulted blocker: it must no longer be a scanner
        # error (missing ctx / wrong arg count), or vamos would not wire it.
        scan = self._scan()
        self.assertNotIn("FreeIFF", set(scan.get_error_func_names()))
        self.assertNotIn("FreeIFF", set(scan.get_invalid_func_names()))


if __name__ == "__main__":
    unittest.main()
