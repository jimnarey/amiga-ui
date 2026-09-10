"""Qt-free tests for the GadTools gadget decode / projection boundary.

These exercise the *decode* half of the gadget projection without Qt, iTidy, or
a display: the compatibility layer must turn the 68k ``struct Gadget`` /
``NewGadget`` + GadTools tag list into an immutable, host-safe
:class:`~amiga_ui.host.projection.GadgetDescription` (and, at ``OpenWindow``
time, resolve a window's own gadgets from its real ``FirstGadget`` chain).

Everything here is synthetic (no iTidy labels, ids, or window titles): the cycle
label arrays and active indices are arbitrary values chosen to prove the decode
mechanism, and the two-window isolation test uses two independent gadget chains.
The real-iTidy assertion (observed labels/geometry on the projected window)
lives in the Xvfb-backed integration test.
"""

import unittest
from types import SimpleNamespace

from amiga_ui.host.projection import (
    KIND_BUTTON,
    KIND_CHECKBOX,
    KIND_CONTEXT,
    KIND_CYCLE,
    KIND_TEXT,
    GadgetDescription,
)
from amiga_ui.vamos.gadget_state import GadgetDescriptionRegistry
from amiga_ui.vamos.gadtools_library import (
    _GADTYPE_BUTTON,
    _GADTYPE_CHECKBOX,
    _GADTYPE_CYCLE,
    _GADTYPE_TEXT,
    _GTCB_CHECKED,
    _GTCY_ACTIVE,
    _GTCY_LABELS,
    _GTTX_BORDER,
    _GTTX_TEXT,
    _NG_OFF_HEIGHT,
    _NG_OFF_ID,
    _NG_OFF_LEFT,
    _NG_OFF_TEXT,
    _NG_OFF_TOP,
    _NG_OFF_WIDTH,
    GadToolsLibrary,
)
from amiga_ui.vamos.intuition_library import IntuitionLibrary


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


class _FakeAlloc:
    """A minimal MemoryAlloc that hands out aligned, non-overlapping blocks."""

    def __init__(self) -> None:
        self._next = 0x0010_0000
        self._blocks: dict[int, SimpleNamespace] = {}

    def alloc_memory(self, size: int, label: str = "") -> SimpleNamespace:
        addr = self._next
        self._next += (size + 0x30) & ~0x30
        block = SimpleNamespace(addr=addr, size=size, label=label)
        self._blocks[addr] = block
        return block

    def free_memory(self, block: SimpleNamespace) -> None:
        self._blocks.pop(block.addr, None)


def _write_c_string(mem: _FakeMem, addr: int, s: str) -> int:
    for i, ch in enumerate(s):
        mem.w8(addr + i, ord(ch) & 0xFF)
    mem.w8(addr + len(s), 0)
    return len(s) + 1


def _write_ng(
    mem: _FakeMem,
    ng: int,
    *,
    left: int,
    top: int,
    width: int,
    height: int,
    text_ptr: int,
    gadget_id: int,
) -> None:
    mem.w16(ng + _NG_OFF_LEFT, left)
    mem.w16(ng + _NG_OFF_TOP, top)
    mem.w16(ng + _NG_OFF_WIDTH, width)
    mem.w16(ng + _NG_OFF_HEIGHT, height)
    mem.w32(ng + _NG_OFF_TEXT, text_ptr)
    mem.w16(ng + _NG_OFF_ID, gadget_id)


def _write_taglist(mem: _FakeMem, taglist: int, pairs: list[tuple[int, int]]) -> None:
    off = 0
    for tag, data in pairs:
        mem.w32(taglist + off, tag)
        mem.w32(taglist + off + 4, data)
        off += 8
    mem.w32(taglist + off, 0)  # TAG_END


class _Ctx:
    """A call context bundling the mem / alloc / registry the decode needs."""

    def __init__(self) -> None:
        self.mem = _FakeMem()
        self.alloc = _FakeAlloc()
        self.registry = GadgetDescriptionRegistry()
        self.ctx = SimpleNamespace(
            mem=self.mem,
            alloc=self.alloc,
            gadget_descriptions=self.registry,
            event_bridge=None,  # CreateGadgetA tolerates no bridge
        )


class GadgetDecodeButtonTest(unittest.TestCase):
    def test_button_decodes_geometry_label_id(self) -> None:
        c = _Ctx()
        mem, lib = c.mem, GadToolsLibrary()
        text = 0x0020_0000
        _write_c_string(mem, text, "Push Me")
        ng = 0x0021_0000
        _write_ng(mem, ng, left=12, top=34, width=96, height=14, text_ptr=text, gadget_id=2)
        taglist = 0x0022_0000
        _write_taglist(mem, taglist, [])  # TAG_END only
        glist = 0x0023_0000
        mem.w32(glist, 0)
        ctx_gad = lib.CreateContext(c.ctx, glist)
        addr = lib.CreateGadgetA(c.ctx, _GADTYPE_BUTTON, ctx_gad, ng, taglist)

        self.assertTrue(addr)
        desc = c.registry.get(addr)
        assert isinstance(desc, GadgetDescription)
        self.assertEqual(desc.kind_name, KIND_BUTTON)
        self.assertEqual(desc.kind, _GADTYPE_BUTTON)
        self.assertEqual((desc.left, desc.top, desc.width, desc.height), (12, 34, 96, 14))
        self.assertEqual(desc.label, "Push Me")
        self.assertEqual(desc.gadget_id, 2)
        self.assertTrue(desc.enabled)
        self.assertTrue(desc.is_projectable)


class GadgetDecodeTextTest(unittest.TestCase):
    def test_text_decodes_display_text_and_border(self) -> None:
        c = _Ctx()
        mem, lib = c.mem, GadToolsLibrary()
        label = 0x0020_0000
        _write_c_string(mem, label, "Folder:")
        text_val = 0x0020_0040
        _write_c_string(mem, text_val, "/tmp/SYS")
        ng = 0x0021_0000
        _write_ng(mem, ng, left=30, top=40, width=70, height=12, text_ptr=label, gadget_id=0)
        taglist = 0x0022_0000
        _write_taglist(mem, taglist, [(_GTTX_TEXT, text_val), (_GTTX_BORDER, 1)])
        glist = 0x0023_0000
        mem.w32(glist, 0)
        ctx_gad = lib.CreateContext(c.ctx, glist)
        addr = lib.CreateGadgetA(c.ctx, _GADTYPE_TEXT, ctx_gad, ng, taglist)

        desc = c.registry.get(addr)
        assert isinstance(desc, GadgetDescription)
        self.assertEqual(desc.kind_name, KIND_TEXT)
        self.assertEqual(desc.label, "Folder:")
        self.assertEqual(desc.text, "/tmp/SYS")
        self.assertTrue(desc.text_border)
        self.assertTrue(desc.is_projectable)

    def test_text_without_border_tag_is_none(self) -> None:
        c = _Ctx()
        mem, lib = c.mem, GadToolsLibrary()
        label = 0x0020_0000
        _write_c_string(mem, label, "Static")
        ng = 0x0021_0000
        _write_ng(mem, ng, left=1, top=2, width=3, height=4, text_ptr=label, gadget_id=9)
        taglist = 0x0022_0000
        _write_taglist(mem, taglist, [(_GTTX_TEXT, 0)])  # GTTX_Text = NULL -> ""
        glist = 0x0023_0000
        mem.w32(glist, 0)
        ctx_gad = lib.CreateContext(c.ctx, glist)
        addr = lib.CreateGadgetA(c.ctx, _GADTYPE_TEXT, ctx_gad, ng, taglist)

        desc = c.registry.get(addr)
        assert isinstance(desc, GadgetDescription)
        self.assertEqual(desc.text, "")
        self.assertIsNone(desc.text_border)


class GadgetDecodeCycleTest(unittest.TestCase):
    """Cycle labels + active index with *arbitrary* (non-iTidy) values."""

    def test_cycle_decodes_labels_array_and_active_index(self) -> None:
        c = _Ctx()
        mem, lib = c.mem, GadToolsLibrary()
        labels = ["Alpha", "Beta", "Gamma", "Delta"]
        label = 0x0020_0000
        _write_c_string(mem, label, "Choose:")
        # Label pointer array at 0x0020_0100; each string at a fixed slot.
        array = 0x0020_0100
        str_base = 0x0020_0200
        for i, s in enumerate(labels):
            str_addr = str_base + i * 64
            _write_c_string(mem, str_addr, s)
            mem.w32(array + i * 4, str_addr)
        mem.w32(array + len(labels) * 4, 0)  # NULL terminator
        ng = 0x0021_0000
        _write_ng(mem, ng, left=100, top=60, width=120, height=14, text_ptr=label, gadget_id=6)
        taglist = 0x0022_0000
        _write_taglist(mem, taglist, [(_GTCY_LABELS, array), (_GTCY_ACTIVE, 2)])
        glist = 0x0023_0000
        mem.w32(glist, 0)
        ctx_gad = lib.CreateContext(c.ctx, glist)
        addr = lib.CreateGadgetA(c.ctx, _GADTYPE_CYCLE, ctx_gad, ng, taglist)

        desc = c.registry.get(addr)
        assert isinstance(desc, GadgetDescription)
        self.assertEqual(desc.kind_name, KIND_CYCLE)
        self.assertEqual(desc.label, "Choose:")
        self.assertEqual(desc.cycle_labels, tuple(labels))
        self.assertEqual(desc.cycle_active, 2)
        self.assertEqual(desc.gadget_id, 6)
        self.assertTrue(desc.is_projectable)


class GadgetDecodeCheckboxTest(unittest.TestCase):
    def test_checkbox_decodes_checked_state(self) -> None:
        c = _Ctx()
        mem, lib = c.mem, GadToolsLibrary()
        label = 0x0020_0000
        _write_c_string(mem, label, "Enable")
        ng = 0x0021_0000
        _write_ng(mem, ng, left=100, top=70, width=26, height=12, text_ptr=label, gadget_id=10)
        taglist = 0x0022_0000
        _write_taglist(mem, taglist, [(_GTCB_CHECKED, 1)])  # checked
        glist = 0x0023_0000
        mem.w32(glist, 0)
        ctx_gad = lib.CreateContext(c.ctx, glist)
        addr = lib.CreateGadgetA(c.ctx, _GADTYPE_CHECKBOX, ctx_gad, ng, taglist)

        desc = c.registry.get(addr)
        assert isinstance(desc, GadgetDescription)
        self.assertEqual(desc.kind_name, KIND_CHECKBOX)
        self.assertTrue(desc.checked)
        self.assertEqual(desc.label, "Enable")
        self.assertTrue(desc.is_projectable)

    def test_checkbox_default_unchecked_when_tag_absent(self) -> None:
        c = _Ctx()
        mem, lib = c.mem, GadToolsLibrary()
        label = 0x0020_0000
        _write_c_string(mem, label, "Off")
        ng = 0x0021_0000
        _write_ng(mem, ng, left=1, top=2, width=26, height=12, text_ptr=label, gadget_id=11)
        taglist = 0x0022_0000
        _write_taglist(mem, taglist, [])  # no GTCB_Checked
        glist = 0x0023_0000
        mem.w32(glist, 0)
        ctx_gad = lib.CreateContext(c.ctx, glist)
        addr = lib.CreateGadgetA(c.ctx, _GADTYPE_CHECKBOX, ctx_gad, ng, taglist)

        desc = c.registry.get(addr)
        assert isinstance(desc, GadgetDescription)
        self.assertFalse(desc.checked)


class GadgetDecodeContextTest(unittest.TestCase):
    def test_context_gadget_recorded_but_not_projectable(self) -> None:
        c = _Ctx()
        mem, lib = c.mem, GadToolsLibrary()
        glist = 0x0023_0000
        mem.w32(glist, 0)
        ctx_gad = lib.CreateContext(c.ctx, glist)

        self.assertTrue(ctx_gad)
        desc = c.registry.get(ctx_gad)
        assert isinstance(desc, GadgetDescription)
        self.assertEqual(desc.kind_name, KIND_CONTEXT)
        self.assertFalse(desc.is_projectable)
        self.assertEqual(desc.label, "")


class GadgetDecodeFreeTest(unittest.TestCase):
    def test_free_gadgets_releases_descriptions(self) -> None:
        c = _Ctx()
        mem, lib = c.mem, GadToolsLibrary()
        label = 0x0020_0000
        _write_c_string(mem, label, "X")
        ng = 0x0021_0000
        _write_ng(mem, ng, left=1, top=2, width=3, height=4, text_ptr=label, gadget_id=1)
        taglist = 0x0022_0000
        _write_taglist(mem, taglist, [])
        glist = 0x0023_0000
        mem.w32(glist, 0)
        ctx_gad = lib.CreateContext(c.ctx, glist)
        addr = lib.CreateGadgetA(c.ctx, _GADTYPE_BUTTON, ctx_gad, ng, taglist)
        self.assertIn(addr, c.registry)
        self.assertIn(ctx_gad, c.registry)

        lib.FreeGadgets(c.ctx, ctx_gad)
        self.assertNotIn(addr, c.registry)
        self.assertNotIn(ctx_gad, c.registry)
        self.assertEqual(len(c.registry), 0)


class GadgetTwoWindowIsolationTest(unittest.TestCase):
    """Two independent gadget chains resolve to their own projectable sets."""

    def _chain(self, c: _Ctx, lib: GadToolsLibrary, glist: int, n: int, base_id: int) -> int:
        mem = c.mem
        mem.w32(glist, 0)
        head = lib.CreateContext(c.ctx, glist)
        prev = head
        for i in range(n):
            label = 0x0040_0000 + i * 0x40
            _write_c_string(mem, label, f"Label{i}")
            ng = 0x0041_0000 + i * 0x40
            _write_ng(mem, ng, left=10 + i, top=20 + i, width=50, height=12, text_ptr=label, gadget_id=base_id + i)
            taglist = 0x0042_0000 + i * 0x40
            _write_taglist(mem, taglist, [])
            prev = lib.CreateGadgetA(c.ctx, _GADTYPE_BUTTON, prev, ng, taglist)
        return head

    def test_each_window_resolves_only_its_own_gadgets(self) -> None:
        c = _Ctx()
        lib = GadToolsLibrary()
        head_a = self._chain(c, lib, 0x0050_0000, 2, base_id=100)  # 2 buttons for A
        head_b = self._chain(c, lib, 0x0051_0000, 3, base_id=200)  # 3 buttons for B

        ilt = IntuitionLibrary()
        a = ilt._collect_window_gadgets(c.ctx, head_a)
        b = ilt._collect_window_gadgets(c.ctx, head_b)

        self.assertEqual([d.gadget_id for d in a], [100, 101])
        self.assertEqual([d.gadget_id for d in b], [200, 201, 202])
        # The context gadget is excluded from both.
        self.assertNotIn(head_a, [d.gadget_addr for d in a])
        self.assertNotIn(head_b, [d.gadget_addr for d in b])

    def test_unknown_gadget_addr_is_skipped(self) -> None:
        # A chain head the GadTools library never decoded must resolve to empty,
        # not crash and not invent gadgets.
        c = _Ctx()
        ilt = IntuitionLibrary()
        self.assertEqual(ilt._collect_window_gadgets(c.ctx, 0xDEAD_0000), ())


if __name__ == "__main__":
    unittest.main()
