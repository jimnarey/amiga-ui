"""Qt-free tests for the ASL library tag decoding and result handling."""
import unittest
from types import SimpleNamespace

from amitools.vamos.error import UnsupportedFeatureError

from amiga_ui.vamos.asllibrary import (
    ASL_FileRequest,
    ASLLibrary,
)


class _FakeMem:
    """A minimal big-endian 68k memory model."""
    def __init__(self):
        self._bytes = {}
    def r8(self, addr):
        return self._bytes.get(addr, 0) & 0xFF
    def w8(self, addr, value):
        self._bytes[addr] = value & 0xFF
    def r16(self, addr):
        return (self.r8(addr) << 8) | self.r8(addr + 1)
    def w16(self, addr, value):
        self.w8(addr, (value >> 8) & 0xFF)
        self.w8(addr + 1, value & 0xFF)
    def r32(self, addr):
        return (self.r8(addr) << 24) | (self.r8(addr + 1) << 16) | (self.r8(addr + 2) << 8) | self.r8(addr + 3)
    def w32(self, addr, value):
        value &= 0xFFFFFFFF
        self.w8(addr, (value >> 24) & 0xFF)
        self.w8(addr + 1, (value >> 16) & 0xFF)
        self.w8(addr + 2, (value >> 8) & 0xFF)
        self.w8(addr + 3, value & 0xFF)


class _FakeAlloc:
    """Fake allocator that writes to the same memory instance."""
    def __init__(self, mem):
        self.blocks = {}
        self.next_addr = 0x1000
        self.mem = mem
    
    def alloc_memory(self, size, label=None):
        addr = self.next_addr
        self.next_addr += size
        self.blocks[addr] = size
        # Initialize to 0
        for i in range(size):
            self.mem.w8(addr + i, 0)
        return SimpleNamespace(addr=addr)
    
    def free_memory(self, addr, label=None):
        if addr in self.blocks:
            del self.blocks[addr]


class ASLAllocTest(unittest.TestCase):
    """Tests for AllocAslRequest (requester allocation)."""

    def test_alloc_file_requester_success(self):
        """AllocAslRequest returns a non-zero address for ASL_FileRequest."""
        mem = _FakeMem()
        alloc = _FakeAlloc(mem)
        ctx = SimpleNamespace(alloc=alloc, mem=mem)
        lib = ASLLibrary()
        result = lib.AllocAslRequest(ctx, ASL_FileRequest, None)
        self.assertEqual(result, 0x1000)

    def test_alloc_requester_initializes_struct_zero(self):
        """AllocAslRequest returns a zero-initialized FileRequester struct."""
        mem = _FakeMem()
        alloc = _FakeAlloc(mem)
        ctx = SimpleNamespace(alloc=alloc, mem=mem)
        lib = ASLLibrary()

        fr_addr = lib.AllocAslRequest(ctx, ASL_FileRequest, None)
        self.assertEqual(fr_addr, 0x1000)

        # Check that the struct is zero-initialized.
        for i in range(0x50):  # classic FileRequester size
            self.assertEqual(mem.r8(fr_addr + i), 0)

    def test_alloc_requester_sets_defaults(self):
        """AllocAslRequest sets default struct fields (fr_File = 0, fr_Drawer = 0)."""
        mem = _FakeMem()
        alloc = _FakeAlloc(mem)
        ctx = SimpleNamespace(alloc=alloc, mem=mem)
        lib = ASLLibrary()

        fr_addr = lib.AllocAslRequest(ctx, ASL_FileRequest, None)
        self.assertEqual(fr_addr, 0x1000)

        # Check default fr_File and fr_Drawer pointers.
        self.assertEqual(mem.r32(fr_addr + 8), 0)  # fr_File offset
        self.assertEqual(mem.r32(fr_addr + 12), 0)  # fr_Drawer offset


class ASLFreeTest(unittest.TestCase):
    """Tests for FreeAslRequest (requester deallocation)."""

    def test_free_null_requester_idempotent(self):
        """FreeAslRequest(NULL) is a no-op."""
        mem = _FakeMem()
        alloc = _FakeAlloc(mem)
        ctx = SimpleNamespace(alloc=alloc, mem=mem)
        lib = ASLLibrary()
        lib.FreeAslRequest(ctx, 0)  # Should not raise.

    def test_free_non_null_requester_releases_memory(self):
        """FreeAslRequest deallocates the FileRequester struct."""
        mem = _FakeMem()
        alloc = _FakeAlloc(mem)
        ctx = SimpleNamespace(alloc=alloc, mem=mem)
        lib = ASLLibrary()

        fr_addr = lib.AllocAslRequest(ctx, ASL_FileRequest, None)
        self.assertEqual(fr_addr, 0x1000)

        lib.FreeAslRequest(ctx, fr_addr)

        # The allocator should have marked the block as freed.
        self.assertNotIn(fr_addr, alloc.blocks)


class ASLRequestTagsTest(unittest.TestCase):
    """Tests for AslRequestTags (blocking requester call)."""

    def test_asl_request_tags_rejects_null_requester(self):
        """AslRequestTags raises UnsupportedFeatureError for NULL requester."""
        mem = _FakeMem()
        alloc = _FakeAlloc(mem)
        ctx = SimpleNamespace(alloc=alloc, mem=mem)
        lib = ASLLibrary()

        with self.assertRaises(UnsupportedFeatureError) as cm:
            lib.AslRequestTags(ctx, 0, None)

        self.assertIn("AllocAslRequest(NULL)", str(cm.exception))

    def test_asl_request_tags_without_projection_fails_honestly(self):
        """AslRequestTags raises UnsupportedFeatureError without a host projection."""
        mem = _FakeMem()
        alloc = _FakeAlloc(mem)
        ctx = SimpleNamespace(alloc=alloc, mem=mem, host_projection=None)
        lib = ASLLibrary()

        fr_addr = lib.AllocAslRequest(ctx, ASL_FileRequest, None)
        self.assertIsNotNone(fr_addr)

        with self.assertRaises(UnsupportedFeatureError) as cm:
            lib.AslRequestTags(ctx, fr_addr, None)

        self.assertIn("headless mode", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
