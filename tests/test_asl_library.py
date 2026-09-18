"""Qt-free tests for the ASL library: tag decoding, requester state, results.

The fake allocator mirrors the *real* vamos allocator surface the library is
allowed to use: ``alloc_memory(size, label=None)`` returns a Memory-like
object with an ``addr``; ``free_memory(mem)`` takes exactly one such object
(no label kwarg); ``get_memory(addr)`` resolves an address back to it. A fake
that diverges from that surface would let implementation bugs (e.g. passing
an int + label to ``free_memory``) pass green.
"""

import unittest
from types import SimpleNamespace

from amitools.vamos.error import UnsupportedFeatureError

from amiga_ui.vamos.asllibrary import (
    _FILE_REQUESTER_SIZE,
    _FR_OFF_DRAWER,
    _FR_OFF_FILE,
    _FR_OFF_PATTERN,
    _FR_OFF_USER_DATA,
    ASL_TB,
    TAG_DONE,
    TAG_IGNORE,
    TAG_MORE,
    TAG_SKIP,
    ASL_FileRequest,
    ASLFR_DoSaveMode,
    ASLFR_DrawersOnly,
    ASLFR_InitialDrawer,
    ASLFR_InitialFile,
    ASLFR_TitleText,
    ASLFR_UserData,
    ASLFR_Window,
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

    def cstr(self, addr):
        """Read a NUL-terminated string back as Latin-1 (test-side helper)."""
        out = bytearray()
        i = 0
        while True:
            b = self.r8(addr + i)
            if b == 0:
                break
            out.append(b)
            i += 1
        return out.decode("latin-1")


class _FakeBlock:
    """Stands in for the vamos ``Memory`` object returned by alloc_memory."""

    def __init__(self, addr, size):
        self.addr = addr
        self.size = size


class _FakeAlloc:
    """Fake allocator mirroring the real vamos allocator call surface."""

    def __init__(self, mem):
        self.blocks = {}  # addr -> _FakeBlock (live allocations only)
        self.next_addr = 0x1000
        self.mem = mem

    def alloc_memory(self, size, label=None):
        addr = self.next_addr
        self.next_addr += size
        block = _FakeBlock(addr, size)
        self.blocks[addr] = block
        for i in range(size):
            self.mem.w8(addr + i, 0)
        return block

    def free_memory(self, mem):
        # Real signature: one Memory object. An int (or a label kwarg)
        # reaching here means the implementation misused the allocator.
        assert not isinstance(mem, int), "free_memory() must receive the Memory object, not an address"
        self.blocks.pop(mem.addr, None)

    def get_memory(self, addr):
        return self.blocks.get(addr)


class _RecordingProjection:
    """Records show_file_dialog intents and answers with a scripted reply."""

    def __init__(self, answer):
        self.answer = answer
        self.calls = []

    def show_file_dialog(
        self,
        window_addr,
        title,
        initial_directory="",
        directories_only=False,
        save_mode=False,
        allow_patterns=False,
        initial_file="",
    ):
        call = {
            "window_addr": window_addr,
            "title": title,
            "initial_directory": initial_directory,
            "directories_only": directories_only,
            "save_mode": save_mode,
            "allow_patterns": allow_patterns,
            "initial_file": initial_file,
        }
        self.calls.append(call)
        return self.answer


def _make_ctx(**extra):
    mem = _FakeMem()
    alloc = _FakeAlloc(mem)
    ctx = SimpleNamespace(alloc=alloc, mem=mem, host_projection=None)
    for key, value in extra.items():
        setattr(ctx, key, value)
    return ctx


def _put_cstr(alloc, mem, text):
    """Write a Latin-1 C string into (fake) guest memory; return its address."""
    raw = text.encode("latin-1")
    block = alloc.alloc_memory(len(raw) + 1, label="test.string")
    for i, byte in enumerate(raw):
        mem.w8(block.addr + i, byte)
    mem.w8(block.addr + len(raw), 0)
    return block.addr


def _build_tag_list(alloc, mem, pairs):
    """Write ``(tag, data)`` pairs as a classic tag list (caller closes with TAG_DONE)."""
    items = list(pairs) + [(TAG_DONE, 0)]
    addr = alloc.alloc_memory(8 * len(items), label="test.taglist").addr
    for i, (tag, data) in enumerate(items):
        mem.w32(addr + i * 8, tag)
        mem.w32(addr + i * 8 + 4, data)
    return addr


class TagBaseTest(unittest.TestCase):
    """The ASL tag base must be the real 32-bit value, not a masked fake."""

    def test_tag_base_is_tag_user_plus_0x80000(self):
        self.assertEqual(ASL_TB, 0x80080000)
        # Spot-check a few against the NDK header arithmetic.
        self.assertEqual(ASLFR_TitleText, 0x80080001)
        self.assertEqual(ASLFR_Window, 0x80080002)
        self.assertEqual(ASLFR_InitialDrawer, 0x80080009)
        self.assertEqual(ASLFR_DoSaveMode, 0x8008002C)
        self.assertEqual(ASLFR_DrawersOnly, 0x8008002F)


class ASLAllocTest(unittest.TestCase):
    """AllocAslRequest: struct allocation, zero-init, and tag initialization."""

    def test_alloc_file_requester_success(self):
        ctx = _make_ctx()
        lib = ASLLibrary()
        self.assertEqual(lib.AllocAslRequest(ctx, ASL_FileRequest, None), 0x1000)

    def test_alloc_unsupported_request_type_fails(self):
        ctx = _make_ctx()
        lib = ASLLibrary()
        with self.assertRaises(UnsupportedFeatureError):
            lib.AllocAslRequest(ctx, 1, None)  # ASL_FontRequest

    def test_alloc_requester_initializes_struct_zero(self):
        """No invented defaults: every field — including geometry — is 0."""
        ctx = _make_ctx()
        lib = ASLLibrary()
        fr_addr = lib.AllocAslRequest(ctx, ASL_FileRequest, None)
        for i in range(_FILE_REQUESTER_SIZE):
            self.assertEqual(ctx.mem.r8(fr_addr + i), 0, f"byte {i:#x} of the struct must start zeroed")
        # Geometry (fr_LeftEdge/Top/Width/Height) stays 0 until the requester
        # is actually opened; the library must not fabricate screen geometry.
        self.assertEqual(ctx.mem.r16(fr_addr + 0x16), 0)
        self.assertEqual(ctx.mem.r16(fr_addr + 0x18), 0)
        self.assertEqual(ctx.mem.r16(fr_addr + 0x1A), 0)
        self.assertEqual(ctx.mem.r16(fr_addr + 0x1C), 0)

    def test_alloc_defaults_are_null_string_pointers(self):
        ctx = _make_ctx()
        lib = ASLLibrary()
        fr_addr = lib.AllocAslRequest(ctx, ASL_FileRequest, None)
        self.assertEqual(ctx.mem.r32(fr_addr + _FR_OFF_FILE), 0)
        self.assertEqual(ctx.mem.r32(fr_addr + _FR_OFF_DRAWER), 0)
        self.assertEqual(ctx.mem.r32(fr_addr + _FR_OFF_PATTERN), 0)

    def test_alloc_applies_initial_drawer_as_own_copy(self):
        """ASLFR_InitialDrawer is COPIED into ASL memory (real ASL owns its buffers)."""
        ctx = _make_ctx()
        lib = ASLLibrary()
        app_str = _put_cstr(ctx.alloc, ctx.mem, "SYS:Utilities")
        tag_list = _build_tag_list(ctx.alloc, ctx.mem, [(ASLFR_InitialDrawer, app_str)])

        fr_addr = lib.AllocAslRequest(ctx, ASL_FileRequest, tag_list)
        drawer_ptr = ctx.mem.r32(fr_addr + _FR_OFF_DRAWER)
        self.assertNotEqual(drawer_ptr, 0)
        self.assertNotEqual(drawer_ptr, app_str, "the app's string must be copied, not aliased")
        self.assertEqual(ctx.mem.cstr(drawer_ptr), "SYS:Utilities")

    def test_alloc_applies_user_data_to_struct(self):
        ctx = _make_ctx()
        lib = ASLLibrary()
        tag_list = _build_tag_list(ctx.alloc, ctx.mem, [(ASLFR_UserData, 0xDEADBEEF)])
        fr_addr = lib.AllocAslRequest(ctx, ASL_FileRequest, tag_list)
        self.assertEqual(ctx.mem.r32(fr_addr + _FR_OFF_USER_DATA), 0xDEADBEEF)


class TagProtocolTest(unittest.TestCase):
    """TAG_IGNORE / TAG_SKIP / TAG_MORE are honored, not mistaken for user tags."""

    def _drawer_after_protocol_items(self, pairs):
        ctx = _make_ctx()
        lib = ASLLibrary()
        drawer = _put_cstr(ctx.alloc, ctx.mem, "WORK:")
        tag_list = _build_tag_list(ctx.alloc, ctx.mem, pairs + [(ASLFR_InitialDrawer, drawer)])
        fr_addr = lib.AllocAslRequest(ctx, ASL_FileRequest, tag_list)
        return ctx, fr_addr, drawer

    def test_tag_ignore_is_skipped(self):
        ctx, fr_addr, drawer = self._drawer_after_protocol_items([(TAG_IGNORE, 0x1234)])
        self.assertEqual(ctx.mem.cstr(ctx.mem.r32(fr_addr + _FR_OFF_DRAWER)), "WORK:")

    def test_tag_skip_jumps_the_right_number_of_items(self):
        # A bogus entry pair must be skipped over entirely (data=1 item).
        ctx, fr_addr, _ = self._drawer_after_protocol_items([(TAG_SKIP, 1), (0x11111111, 0x22222222)])
        self.assertEqual(ctx.mem.cstr(ctx.mem.r32(fr_addr + _FR_OFF_DRAWER)), "WORK:")

    def test_tag_more_chains_to_a_second_list(self):
        ctx = _make_ctx()
        lib = ASLLibrary()
        drawer = _put_cstr(ctx.alloc, ctx.mem, "RAM:")
        # Inner list (ends at TAG_DONE) chained via TAG_MORE from the outer.
        inner = _build_tag_list(ctx.alloc, ctx.mem, [(ASLFR_InitialDrawer, drawer)])
        outer = _build_tag_list(ctx.alloc, ctx.mem, [(TAG_MORE, inner)])
        fr_addr = lib.AllocAslRequest(ctx, ASL_FileRequest, outer)
        self.assertEqual(ctx.mem.cstr(ctx.mem.r32(fr_addr + _FR_OFF_DRAWER)), "RAM:")

    def test_malformed_list_without_terminator_is_bounded(self):
        # 0x100 items of pure user tags, no TAG_DONE: must not hang.
        ctx = _make_ctx()
        lib = ASLLibrary()
        addr = ctx.alloc.alloc_memory(8 * 0x200, label="test.bad").addr
        for i in range(0x200):
            ctx.mem.w32(addr + i * 8, ASLFR_TitleText)
            ctx.mem.w32(addr + i * 8 + 4, 0)
        fr_addr = lib.AllocAslRequest(ctx, ASL_FileRequest, addr)
        self.assertNotEqual(fr_addr, 0)


class ASLFreeTest(unittest.TestCase):
    """FreeAslRequest: releases the struct and every ASL-owned string."""

    def test_free_null_requester_idempotent(self):
        ctx = _make_ctx()
        lib = ASLLibrary()
        lib.FreeAslRequest(ctx, 0)  # must not raise

    def test_free_releases_struct_and_owned_strings(self):
        ctx = _make_ctx()
        lib = ASLLibrary()
        app_str = _put_cstr(ctx.alloc, ctx.mem, "SYS:")
        tag_list = _build_tag_list(ctx.alloc, ctx.mem, [(ASLFR_InitialDrawer, app_str)])
        fr_addr = lib.AllocAslRequest(ctx, ASL_FileRequest, tag_list)
        struct_block = ctx.alloc.get_memory(fr_addr)
        string_addrs = {fr_addr} | {b.addr for b in lib._requesters[fr_addr].owned_strings}

        lib.FreeAslRequest(ctx, fr_addr)

        for addr in string_addrs:
            self.assertNotIn(addr, ctx.alloc.blocks, f"block {addr:#x} must be released")
        self.assertIsNotNone(struct_block)

    def test_free_is_safe_after_double_free(self):
        ctx = _make_ctx()
        lib = ASLLibrary()
        fr_addr = lib.AllocAslRequest(ctx, ASL_FileRequest, None)
        lib.FreeAslRequest(ctx, fr_addr)
        lib.FreeAslRequest(ctx, fr_addr)  # double-free must not raise

    def test_free_uses_real_allocator_signature(self):
        # The fake asserts free_memory() only ever receives Memory objects;
        # if the implementation passed an int + label, this raises.
        ctx = _make_ctx()
        lib = ASLLibrary()
        fr_addr = lib.AllocAslRequest(ctx, ASL_FileRequest, None)
        lib.FreeAslRequest(ctx, fr_addr)


class ASLRequestTest(unittest.TestCase):
    """AslRequest: request/alloc state merge, projection call, result write-back."""

    def _alloc(self, ctx, lib, pairs=()):
        tag_list = _build_tag_list(ctx.alloc, ctx.mem, list(pairs)) if pairs else None
        return lib.AllocAslRequest(ctx, ASL_FileRequest, tag_list)

    def test_null_requester_returns_false(self):
        # Documented contract: AslRequest(NULL, ...) always returns FALSE —
        # it must not raise into the emulator.
        ctx = _make_ctx()
        lib = ASLLibrary()
        self.assertIs(lib.AslRequest(ctx, 0, None), False)

    def test_foreign_requester_raises_value_error(self):
        ctx = _make_ctx()
        lib = ASLLibrary()
        with self.assertRaises(ValueError):
            lib.AslRequest(ctx, 0x99999, None)

    def test_no_projection_fails_honestly(self):
        ctx = _make_ctx(host_projection=None)
        lib = ASLLibrary()
        fr_addr = self._alloc(ctx, lib)
        with self.assertRaises(UnsupportedFeatureError):
            lib.AslRequest(ctx, fr_addr, None)

    def test_alloc_time_options_reach_projection_with_null_request_tags(self):
        """iTidy menu pattern: AllocAslRequestTags(...) then AslRequest(freq, NULL)."""
        ctx = _make_ctx()
        projection = _RecordingProjection(answer="/host/dir/target.bin")
        ctx.host_projection = projection
        lib = ASLLibrary()
        title = _put_cstr(ctx.alloc, ctx.mem, "Save Preferences As...")
        drawer = _put_cstr(ctx.alloc, ctx.mem, "/tmp/start")
        file_str = _put_cstr(ctx.alloc, ctx.mem, "iTidy.prefs")
        window = 0x0002ABCD
        fr_addr = self._alloc(
            ctx,
            lib,
            [
                (ASLFR_TitleText, title),
                (ASLFR_InitialDrawer, drawer),
                (ASLFR_InitialFile, file_str),
                (ASLFR_DoSaveMode, 1),
                (ASLFR_Window, window),
            ],
        )

        result = lib.AslRequest(ctx, fr_addr, None)

        self.assertTrue(result)
        self.assertEqual(len(projection.calls), 1)
        call = projection.calls[0]
        self.assertEqual(call["title"], "Save Preferences As...")
        self.assertEqual(call["initial_directory"], "/tmp/start")
        self.assertEqual(call["initial_file"], "iTidy.prefs")
        self.assertTrue(call["save_mode"])
        self.assertFalse(call["directories_only"])
        self.assertEqual(call["window_addr"], window)

    def test_directory_selection_writes_drawer_only(self):
        """iTidy Browse pattern: drawers-only request writes fr_Drawer, not a file."""
        ctx = _make_ctx()
        projection = _RecordingProjection(answer="/tmp/pictures")
        ctx.host_projection = projection
        lib = ASLLibrary()
        title = _put_cstr(ctx.alloc, ctx.mem, "Select Folder to Process")
        drawer = _put_cstr(ctx.alloc, ctx.mem, "existing")
        window = 0x0002ABCD
        tag_list = _build_tag_list(
            ctx.alloc,
            ctx.mem,
            [
                (ASLFR_TitleText, title),
                (ASLFR_DrawersOnly, 1),
                (ASLFR_InitialDrawer, drawer),
            ],
        )
        fr_addr = self._alloc(ctx, lib, [(ASLFR_Window, window)])

        result = lib.AslRequest(ctx, fr_addr, tag_list)

        self.assertTrue(result)
        call = projection.calls[0]
        self.assertEqual(call["title"], "Select Folder to Process")
        self.assertTrue(call["directories_only"])
        # Request-time tags override alloc-time ones.
        self.assertEqual(call["initial_directory"], "existing")
        self.assertEqual(ctx.mem.cstr(ctx.mem.r32(fr_addr + _FR_OFF_DRAWER)), "/tmp/pictures")
        self.assertEqual(ctx.mem.cstr(ctx.mem.r32(fr_addr + _FR_OFF_FILE)), "")

    def test_file_selection_writes_drawer_and_file_parts(self):
        ctx = _make_ctx()
        projection = _RecordingProjection(answer="/tmp/dir/name.bin")
        ctx.host_projection = projection
        lib = ASLLibrary()
        fr_addr = self._alloc(ctx, lib)

        self.assertTrue(lib.AslRequest(ctx, fr_addr, None))
        self.assertEqual(ctx.mem.cstr(ctx.mem.r32(fr_addr + _FR_OFF_DRAWER)), "/tmp/dir")
        self.assertEqual(ctx.mem.cstr(ctx.mem.r32(fr_addr + _FR_OFF_FILE)), "name.bin")

    def test_cancel_returns_false_and_leaves_struct_untouched(self):
        ctx = _make_ctx()
        projection = _RecordingProjection(answer=None)  # the user cancelled
        ctx.host_projection = projection
        lib = ASLLibrary()
        drawer = _put_cstr(ctx.alloc, ctx.mem, "SYS:initial")
        tag_list = _build_tag_list(ctx.alloc, ctx.mem, [(ASLFR_InitialDrawer, drawer)])
        fr_addr = self._alloc(ctx, lib, [(ASLFR_InitialDrawer, drawer)])
        before = ctx.mem.r32(fr_addr + _FR_OFF_DRAWER)

        result = lib.AslRequest(ctx, fr_addr, tag_list)

        self.assertFalse(result)
        self.assertEqual(ctx.mem.r32(fr_addr + _FR_OFF_DRAWER), before, "cancel must not rewrite the struct")

    def test_latin1_string_round_trip(self):
        """Guest strings are Latin-1 (classic 8-bit); non-ASCII survives both ways."""
        ctx = _make_ctx()
        projection = _RecordingProjection(answer="/tmp/Ärde")
        ctx.host_projection = projection
        lib = ASLLibrary()
        title = _put_cstr(ctx.alloc, ctx.mem, "Välj mapp")
        tag_list = _build_tag_list(ctx.alloc, ctx.mem, [(ASLFR_TitleText, title), (ASLFR_DrawersOnly, 1)])
        fr_addr = self._alloc(ctx, lib)

        self.assertTrue(lib.AslRequest(ctx, fr_addr, tag_list))
        self.assertEqual(projection.calls[0]["title"], "Välj mapp")
        self.assertEqual(ctx.mem.cstr(ctx.mem.r32(fr_addr + _FR_OFF_DRAWER)), "/tmp/Ärde")

    def test_asl_request_tags_is_alias_of_asl_request(self):
        """AslRequestTags (an app-side inline wrapper, not an LVO) delegates."""
        ctx = _make_ctx()
        projection = _RecordingProjection(answer="/tmp/alias")
        ctx.host_projection = projection
        lib = ASLLibrary()
        fr_addr = self._alloc(ctx, lib, [(ASLFR_DrawersOnly, 1)])
        self.assertTrue(lib.AslRequestTags(ctx, fr_addr, None))
        self.assertEqual(ctx.mem.cstr(ctx.mem.r32(fr_addr + _FR_OFF_DRAWER)), "/tmp/alias")


if __name__ == "__main__":
    unittest.main()
