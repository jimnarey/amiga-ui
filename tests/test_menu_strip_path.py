"""The menu-strip path across the two libraries: CreateMenus -> SetMenuStrip -> ItemAddress.

This is the contract the target actually relies on, exercised without the
binary: the strip is created by ``gadtools.library`` (which knows how to read the
template it turned into real ``struct Menu`` / ``struct MenuItem`` blocks),
attached to a window by ``intuition.library``'s ``SetMenuStrip`` (which projects
it through the host projection), and resolved back by ``ItemAddress`` with a
packed ``MenuNumber`` — exactly the value an ``IDCMP_MENUPICK`` carries in
``Code``.

The core assertion is the round trip: for every entry the projection is offered,
``ItemAddress(strip, entry.code)`` returns *that entry's* item, and the id read
from ``GTMENUITEM_USERDATA`` (``MenuItem + 0x22``) is the id the template put in
``nm_UserData``. That is the same pair of facts the shipped iTidy dispatcher
combines (``jsr _LVOItemAddress`` then ``move.l $22(a2),d1``), so host click and
app resolution cannot drift apart — see
``docs/apps/itidy/menu-strip-menupick-abi.md``.

The window projection here is the repo's own Qt-free
:class:`NullHostWindowProjection`, which records what it is asked to project;
``tests/test_qt_menu_strip.py`` covers the real ``QMenuBar`` side.
"""

import unittest
from types import SimpleNamespace

from amiga_ui.host.projection import NullHostWindowProjection, OpenWindowIntent
from amiga_ui.vamos.gadtools_library import (
    _NM_END,
    _NM_ITEM,
    _NM_OFF_COMMKEY,
    _NM_OFF_FLAGS,
    _NM_OFF_LABEL,
    _NM_OFF_MUTE,
    _NM_OFF_TYPE,
    _NM_OFF_USERDATA,
    _NM_SIZE,
    _NM_SUB,
    _NM_TITLE,
    GadToolsLibrary,
)
from amiga_ui.vamos.intuition_library import _WIN_OFF_MENUSTRIP, IntuitionLibrary
from amiga_ui.vamos.menu_state import (
    MENUITEM_OFF_NEXTSELECT,
    MENUITEM_OFF_USERDATA,
    MENUNULL,
    MenuDescriptionRegistry,
    pack_menu_number,
)

IDCMP_MENUPICK = 0x00000100
BARLABEL = 0xFFFFFFFF  # NM_BARLABEL == (STRPTR)-1

# The iTidy main-window Project menu, verbatim from
# amiga_apps/itidy1classic/source/src/GUI/main_window.c:103 (labels, command
# keys, and the MENU_PROJECT_* ids it stores in nm_UserData).
PROJECT_MENU: tuple[tuple[str, str, str | None, int | None], ...] = (
    ("title", "Project", None, None),
    ("item", "New", "N", 1001),
    ("item", "Open...", "O", 1002),
    ("bar", "", None, None),
    ("item", "Save", "S", 1003),
    ("item", "Save as...", "A", 1004),
    ("bar", "", None, None),
    ("item", "About...", None, 1006),
    ("bar", "", None, None),
    ("item", "Close", "C", 1005),
)


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
    """A bump allocator over :class:`_FakeMem` (long word-aligned, never zeroed).

    Deliberately non-zeroing, like vamos' real allocator: any field a later
    reader reaches has to be written by the code under test, not assumed.
    """

    def __init__(self, mem: _FakeMem, base: int = 0x5000) -> None:
        self._mem = mem
        self._next = base

    def alloc_memory(self, size: int, label: str = "") -> SimpleNamespace:
        addr = self._next
        self._next += max(4, (size + 3) & ~3)
        return SimpleNamespace(addr=addr, size=size, label=label)


def _write_cstring(mem: _FakeMem, addr: int, text: str) -> int:
    for offset, char in enumerate(text.encode("ascii")):
        mem.w8(addr + offset, char)
    mem.w8(addr + len(text), 0)
    return addr


def _write_template(mem: _FakeMem, entries: list[tuple[int, int, int, int, int]]) -> int:
    """Write a ``struct NewMenu`` array (0x14 each) and return its address."""

    base = 0x1000
    for index, (kind, label, comm_key, flags, user_data) in enumerate(entries):
        entry = base + index * _NM_SIZE
        mem.w8(entry + _NM_OFF_TYPE, kind)
        mem.w32(entry + _NM_OFF_LABEL, label)
        mem.w32(entry + _NM_OFF_COMMKEY, comm_key)
        mem.w16(entry + _NM_OFF_FLAGS, flags)
        mem.w32(entry + _NM_OFF_MUTE, 0)
        mem.w32(entry + _NM_OFF_USERDATA, user_data)
    return base


def _build_strip(mem: _FakeMem, entries: list[tuple[str, str, str | None, int | None]]) -> int:
    """Encode ``entries`` (kind, label, comm-key, id) into a real NewMenu array."""

    strings = 0x2000
    template: list[tuple[int, int, int, int, int]] = []
    for kind, label, comm_key, user_data in entries:
        kind_val = {"title": _NM_TITLE, "item": _NM_ITEM, "bar": _NM_ITEM, "sub": _NM_SUB}[kind]
        if kind == "bar":
            label_addr = BARLABEL
        elif label:
            label_addr = _write_cstring(mem, strings, label)
            strings += len(label) + 1
        else:
            label_addr = 0
        comm_addr = 0
        if comm_key:
            comm_addr = _write_cstring(mem, strings, comm_key)
            strings += len(comm_key) + 1
        template.append((kind_val, label_addr, comm_addr, 0, user_data or 0))
    template.append((_NM_END, 0, 0, 0, 0))
    return _write_template(mem, template)


def _harness(entries: list[tuple[str, str, str | None, int | None]]) -> SimpleNamespace:
    """A library context with memory, an allocator, and a recording projection."""

    mem = _FakeMem()
    template = _build_strip(mem, entries)
    projection = NullHostWindowProjection()
    projection.open_window(
        OpenWindowIntent(
            window_addr=0x8000,
            title="iTidy",
            left=0,
            top=0,
            width=640,
            height=200,
            rport_addr=0x9000,
            idcmp=IDCMP_MENUPICK,
        )
    )
    return SimpleNamespace(
        mem=mem,
        alloc=_FakeAlloc(mem),
        menu_descriptions=MenuDescriptionRegistry(),
        host_projection=projection,
        template=template,
        window_addr=0x8000,
    )


class CreateAndAttachProjectMenuTests(unittest.TestCase):
    """The iTidy Project menu: created, attached, resolved, detached."""

    def setUp(self) -> None:
        self.ctx = _harness(list(PROJECT_MENU))
        self.strip = GadToolsLibrary().CreateMenusA(self.ctx, self.ctx.template, 0)
        self.description = self.ctx.menu_descriptions.get(self.strip)

    def test_create_menus_builds_a_real_strip(self) -> None:
        self.assertNotEqual(self.strip, 0)
        self.assertIsNotNone(self.description)
        assert self.description is not None
        self.assertEqual(self.description.strip_addr, self.strip)
        self.assertEqual([menu.title for menu in self.description.menus], ["Project"])
        self.assertEqual(self.description.entry_count, 9, "every chain slot counts, separators included")

    def test_entries_keep_template_order_labels_and_ids(self) -> None:
        assert self.description is not None
        items = self.description.menus[0].items
        expected = [
            ("New", 1001),
            ("Open...", 1002),
            ("", 0),
            ("Save", 1003),
            ("Save as...", 1004),
            ("", 0),
            ("About...", 1006),
            ("", 0),
            ("Close", 1005),
        ]
        for index, (label, item_id) in enumerate(expected):
            with self.subTest(index=index):
                self.assertEqual(items[index].label, label)
                self.assertEqual(items[index].item_data, item_id)
        self.assertEqual(
            [item.is_separator for item in items],
            [False] * 2 + [True] + [False] * 2 + [True] + [False] + [True] + [False],
        )

    def test_set_menu_strip_sets_the_window_field_and_projects_the_strip(self) -> None:
        IntuitionLibrary().SetMenuStrip(self.ctx, self.ctx.window_addr, self.strip)
        self.assertEqual(self.ctx.mem.r32(self.ctx.window_addr + _WIN_OFF_MENUSTRIP), self.strip)
        self.assertIs(self.ctx.host_projection.strips.get(self.ctx.window_addr), self.description)

    def test_every_projected_code_resolves_back_to_its_own_item(self) -> None:
        """The host click and the app's resolution can never disagree."""

        assert self.description is not None
        lib = IntuitionLibrary()
        for entry in self.description.menus[0].items:
            item = lib.ItemAddress(self.ctx, self.strip, entry.code)
            with self.subTest(label=entry.label or "separator"):
                self.assertEqual(item, entry.item_addr, "ItemAddress(strip, Code) finds this very entry")
                if entry.is_separator:
                    continue
                self.assertEqual(
                    self.ctx.mem.r32(item + MENUITEM_OFF_USERDATA),
                    entry.item_data,
                    "GTMENUITEM_USERDATA reads back the nm_UserData the template carried",
                )

    def test_closing_menu_entry_round_trips_to_the_app_close_id(self) -> None:
        """The exact chain a Project -> Close pick walks, in one assertion."""

        assert self.description is not None
        close = next(item for item in self.description.menus[0].items if item.label == "Close")
        item = IntuitionLibrary().ItemAddress(self.ctx, self.strip, close.code)
        self.assertEqual(self.ctx.mem.r32(item + MENUITEM_OFF_USERDATA), 1005, "MENU_PROJECT_CLOSE")

    def test_picked_item_terminates_the_apps_selection_walk(self) -> None:
        """Replay the shipped dispatcher: ItemAddress, read id, advance ``NextSelect``.

        ``handle_main_window_menu_selection`` loops ``while (menu_number !=
        MENUNULL)`` and advances with ``menu_number = menu_item->NextSelect``; the
        binary does it at 0x21cd4 as ``moveq #0,d4 / move.w $20(a2),d4 /
        cmpa.l #$ffff,a4 / bne.w 0x21c4e``, i.e. the UWORD is read *zero-extended*
        and only ``MENUNULL`` ends the walk.  A created item therefore has to
        carry ``MENUNULL`` in ``mi_NextSelect``: with a zero there the target
        calls ``ItemAddress(strip, 0)`` forever instead of returning to WaitPort.
        """

        assert self.description is not None
        lib = IntuitionLibrary()
        close = next(item for item in self.description.menus[0].items if item.label == "Close")
        visited: list[int] = []
        code = close.code
        for _ in range(4):  # one step is expected; the cap turns a spin into a failure
            item = lib.ItemAddress(self.ctx, self.strip, code)
            self.assertNotEqual(item, 0, "the walk must not fall off the strip")
            visited.append(self.ctx.mem.r32(item + MENUITEM_OFF_USERDATA))
            code = self.ctx.mem.r16(item + MENUITEM_OFF_NEXTSELECT)
            if code == MENUNULL:
                break
        self.assertEqual(visited, [1005], "a single pick walks exactly one item, MENU_PROJECT_CLOSE")

    def test_every_created_item_terminates_its_selection_chain(self) -> None:
        """No created item -- top level or sub -- chains into a phantom selection."""

        assert self.description is not None

        def check(entries) -> None:
            for entry in entries:
                with self.subTest(label=entry.label or "separator"):
                    self.assertEqual(
                        self.ctx.mem.r16(entry.item_addr + MENUITEM_OFF_NEXTSELECT),
                        MENUNULL,
                    )
                    check(entry.sub_items)

        check([item for menu in self.description.menus for item in menu.items])

    def test_menull_resolves_to_null(self) -> None:
        self.assertEqual(IntuitionLibrary().ItemAddress(self.ctx, self.strip, MENUNULL), 0)

    def test_null_strip_resolves_to_null_for_any_code(self) -> None:
        code = pack_menu_number(0, 0)
        self.assertEqual(IntuitionLibrary().ItemAddress(self.ctx, 0, code), 0)
        self.assertEqual(IntuitionLibrary().ItemAddress(self.ctx, 0, MENUNULL), 0)

    def test_codes_are_the_packed_first_menu_positions(self) -> None:
        assert self.description is not None
        items = self.description.menus[0].items
        self.assertEqual(items[0].code, pack_menu_number(0, 0), "first item of the first menu")
        self.assertEqual(items[8].code, pack_menu_number(0, 8), "ninth chain slot (Close)")

    def test_clear_menu_strip_detaches_field_and_projection(self) -> None:
        lib = IntuitionLibrary()
        lib.SetMenuStrip(self.ctx, self.ctx.window_addr, self.strip)
        lib.ClearMenuStrip(self.ctx, self.ctx.window_addr)
        self.assertEqual(self.ctx.mem.r32(self.ctx.window_addr + _WIN_OFF_MENUSTRIP), 0)
        self.assertNotIn(self.ctx.window_addr, self.ctx.host_projection.strips)
        self.assertIn(self.ctx.window_addr, self.ctx.host_projection.strips_cleared)

    def test_null_menu_detaches_like_clear(self) -> None:
        lib = IntuitionLibrary()
        lib.SetMenuStrip(self.ctx, self.ctx.window_addr, self.strip)
        lib.SetMenuStrip(self.ctx, self.ctx.window_addr, 0)
        self.assertEqual(self.ctx.mem.r32(self.ctx.window_addr + _WIN_OFF_MENUSTRIP), 0)
        self.assertIn(self.ctx.window_addr, self.ctx.host_projection.strips_cleared)

    def test_foreign_strip_is_recorded_not_invented(self) -> None:
        """A strip this layer did not create has no description: no fake menu bar."""

        lib = IntuitionLibrary()
        lib.SetMenuStrip(self.ctx, self.ctx.window_addr, 0x1234)
        self.assertEqual(lib.unprojected_menu_strips, [0x1234])
        self.assertEqual(self.ctx.host_projection.strips, {})
        self.assertEqual(self.ctx.mem.r32(self.ctx.window_addr + _WIN_OFF_MENUSTRIP), 0x1234)

    def test_detaching_a_foreign_strip_clears_its_record(self) -> None:
        lib = IntuitionLibrary()
        lib.SetMenuStrip(self.ctx, self.ctx.window_addr, 0x1234)
        lib.ClearMenuStrip(self.ctx, self.ctx.window_addr)
        self.assertEqual(lib.unprojected_menu_strips, [])

    def test_without_projection_still_sets_the_classic_field(self) -> None:
        ctx = SimpleNamespace(
            mem=self.ctx.mem,
            alloc=self.ctx.alloc,
            menu_descriptions=self.ctx.menu_descriptions,
        )
        IntuitionLibrary().SetMenuStrip(ctx, self.ctx.window_addr, self.strip)
        self.assertEqual(ctx.mem.r32(self.ctx.window_addr + _WIN_OFF_MENUSTRIP), self.strip)

    def test_null_window_is_an_honest_no_op(self) -> None:
        lib = IntuitionLibrary()
        self.assertIsNone(lib.SetMenuStrip(self.ctx, 0, self.strip))
        self.assertIsNone(lib.ClearMenuStrip(self.ctx, 0))


class SubItemMenuTests(unittest.TestCase):
    """``NM_SUB`` chains: real ``SubItem`` links, nested descriptions, sub codes."""

    def setUp(self) -> None:
        entries: list[tuple[str, str, str | None, int | None]] = [
            ("title", "Tools", None, None),
            ("item", "Tidy", "T", 2001),
            ("sub", "Clean HTML", None, 2002),
            ("sub", "Check Links", None, 2003),
            ("item", "Quit", "Q", 2004),
        ]
        self.ctx = _harness(entries)
        self.strip = GadToolsLibrary().CreateMenusA(self.ctx, self.ctx.template, 0)
        self.description = self.ctx.menu_descriptions.get(self.strip)

    def test_parent_entry_carries_its_sub_chain(self) -> None:
        assert self.description is not None
        tidy = self.description.menus[0].items[0]
        self.assertEqual([sub.label for sub in tidy.sub_items], ["Clean HTML", "Check Links"])
        self.assertFalse(tidy.is_selectable, "a sub-menu parent opens the sub-menu, it is not picked")

    def test_sub_codes_resolve_into_the_sub_item_chain(self) -> None:
        assert self.description is not None
        lib = IntuitionLibrary()
        tidy = self.description.menus[0].items[0]
        for sub in tidy.sub_items:
            with self.subTest(label=sub.label):
                item = lib.ItemAddress(self.ctx, self.strip, sub.code)
                self.assertEqual(item, sub.item_addr)
                self.assertEqual(self.ctx.mem.r32(item + MENUITEM_OFF_USERDATA), sub.item_data)

    def test_sibling_after_a_sub_chain_stays_a_top_level_item(self) -> None:
        assert self.description is not None
        lib = IntuitionLibrary()
        quit_entry = self.description.menus[0].items[1]
        self.assertEqual(quit_entry.label, "Quit")
        self.assertEqual(quit_entry.code, pack_menu_number(0, 1))
        self.assertEqual(lib.ItemAddress(self.ctx, self.strip, quit_entry.code), quit_entry.item_addr)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
