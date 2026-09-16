"""Tests for the classic menu ABI layer in :mod:`amiga_ui.vamos.menu_state`.

Covers the two things the menu-pick path depends on, without depending on the
iTidy binary:

- the packed ``MenuNumber`` encoding Intuition delivers in ``IntuiMessage.Code``
  (1-based fields: menu bits 0-4, item bits 5-10, sub-item bits 11-15, ``NOMENU``
  / ``NOITEM`` / ``NOSUB`` markers, ``MENUNULL`` = ``$FFFF``), and
- ``ItemAddress``'s selector walk over real ``struct Menu`` / ``struct MenuItem``
  chains (``NextMenu``, ``FirstItem``/``NextItem``, ``SubItem``), including the
  ``MenuItem + 0x22`` user-data slot the shipped target reads for a picked item.

The encoding is what the target and this repo must agree on: the target hands
``Code`` to ``ItemAddress`` *unchanged* (evidence:
``docs/apps/itidy/menu-strip-menupick-abi.md``), so a pick of the first entry of
the first menu must resolve to the first menu's first item here exactly as it
does in the app.
"""

import unittest
from types import SimpleNamespace

from amiga_ui.host.projection import MenuEntryDescription, MenuTitleDescription
from amiga_ui.vamos import menu_state


class _FakeMem:
    """A minimal big-endian 68k memory model (unwritten bytes are 0).

    The same model as ``tests/test_intuition_library.py``: the menu walkers use
    ``r32``/``w32`` for the ``APTR`` links, so one byte-backed store is enough.
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


def _menu(mem: _FakeMem, addr: int, *, next_menu: int, first_item: int) -> None:
    """Write one classic ``struct Menu`` (0x16 bytes) with the walked links set."""

    mem.w32(addr + menu_state.MENU_OFF_NEXT, next_menu)
    mem.w32(addr + menu_state.MENU_OFF_FIRSTITEM, first_item)


def _item(
    mem: _FakeMem,
    addr: int,
    *,
    next_item: int = 0,
    sub_item: int = 0,
    command: int = 0,
    user_data: int = 0,
) -> None:
    """Write one classic ``struct MenuItem`` plus the ``GTMENUITEM_USERDATA`` slot."""

    mem.w32(addr + menu_state.MENUITEM_OFF_NEXT, next_item)
    mem.w32(addr + menu_state.MENUITEM_OFF_SUBITEM, sub_item)
    mem.w8(addr + menu_state.MENUITEM_OFF_CMD, command)
    mem.w32(addr + menu_state.MENUITEM_OFF_USERDATA, user_data)


def _build_two_menu_strip(mem: _FakeMem) -> dict[str, int]:
    """Build ``Menu(0x100) -> Menu(0x116)``, two items each, one item with subs.

    Addresses are arbitrary; only the links matter. Menu 1 has items ``m1i1`` /
    ``m1i2``, menu 2 has ``m2i1`` / ``m2i2``, and ``m1i1`` owns a sub-item chain
    ``s1`` -> ``s2``.
    """

    m1, m2 = 0x100, 0x116
    m1i1, m1i2 = 0x200, 0x226
    m2i1, m2i2 = 0x300, 0x326
    sub1, sub2 = 0x400, 0x426
    _item(mem, m1i1, next_item=m1i2, sub_item=sub1, user_data=0x3E8)
    _item(mem, m1i2, user_data=0x3E9)
    _item(mem, m2i1, next_item=m2i2, user_data=0x3EA)
    _item(mem, m2i2, user_data=0x3EB)
    _item(mem, sub1, next_item=sub2, user_data=0x3EC)
    _item(mem, sub2, user_data=0x3ED)
    _menu(mem, m2, next_menu=0, first_item=m2i1)
    _menu(mem, m1, next_menu=m2, first_item=m1i1)
    return {"strip": m1, "m1i1": m1i1, "m1i2": m1i2, "m2i1": m2i1, "m2i2": m2i2, "sub1": sub1, "sub2": sub2}


class PackMenuNumberTests(unittest.TestCase):
    def test_packs_first_entry_with_nosub(self) -> None:
        code = menu_state.pack_menu_number(0, 0)
        self.assertEqual(code & menu_state.NOMENU, 1, "menu field is 1-based")
        self.assertEqual((code >> 5) & menu_state.NOITEM, 1, "item field is 1-based")
        self.assertEqual((code >> 11) & menu_state.NOSUB, menu_state.NOSUB, "two-level pick says NOSUB")

    def test_packs_third_level_when_given(self) -> None:
        code = menu_state.pack_menu_number(1, 2, 3)
        self.assertEqual(code & menu_state.NOMENU, 2)
        self.assertEqual((code >> 5) & menu_state.NOITEM, 3)
        self.assertEqual((code >> 11) & menu_state.NOSUB, 4)

    def test_rejects_indices_that_do_not_fit(self) -> None:
        with self.subTest("menu field"):
            self.assertRaises(ValueError, menu_state.pack_menu_number, 0x1F, 0)
        with self.subTest("item field"):
            self.assertRaises(ValueError, menu_state.pack_menu_number, 0, 0x3F)
        with self.subTest("sub-item field"):
            self.assertRaises(ValueError, menu_state.pack_menu_number, 0, 0, 0x1F)


class DecodeMenuNumberTests(unittest.TestCase):
    def test_round_trips_packed_selectors(self) -> None:
        for indices in ((0, 0, None), (0, 0, 0), (4, 30, None), (29, 61, 29)):
            menu_index, item_index, sub_index = indices
            code = menu_state.pack_menu_number(menu_index, item_index, sub_index)
            with self.subTest(code=hex(code)):
                decoded = menu_state.decode_menu_number(code)
                self.assertEqual(
                    decoded,
                    menu_state.MenuNumber(menu_index, item_index, sub_index),
                )
                assert decoded is not None
                self.assertEqual(decoded.code, code, "code property round-trips")

    def test_selectors_that_name_no_item_decode_to_none(self) -> None:
        nomenu = menu_state.NOITEM << 5 | menu_state.NOSUB << 11
        noitem = 1 | menu_state.NOSUB << 11
        for label, code in (
            ("MENUNULL", menu_state.MENUNULL),
            ("zero", 0),
            ("NOMENU menu field", nomenu),
            ("NOITEM item field", noitem),
        ):
            with self.subTest(label):
                self.assertIsNone(menu_state.decode_menu_number(code))

    def test_ignores_bits_above_the_selector_word(self) -> None:
        code = menu_state.pack_menu_number(0, 0)
        self.assertEqual(menu_state.decode_menu_number(0x1_0000 | code), menu_state.decode_menu_number(code))


class ResolveMenuItemAddressTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mem = _FakeMem()
        self.nodes = _build_two_menu_strip(self.mem)

    def test_resolves_first_menu_items(self) -> None:
        with self.subTest("first item"):
            self.assertEqual(
                menu_state.resolve_menu_item_address(self.mem, self.nodes["strip"], menu_state.pack_menu_number(0, 0)),
                self.nodes["m1i1"],
            )
        with self.subTest("second item"):
            self.assertEqual(
                menu_state.resolve_menu_item_address(self.mem, self.nodes["strip"], menu_state.pack_menu_number(0, 1)),
                self.nodes["m1i2"],
            )

    def test_walks_next_menu_links(self) -> None:
        with self.subTest("second menu, first item"):
            self.assertEqual(
                menu_state.resolve_menu_item_address(self.mem, self.nodes["strip"], menu_state.pack_menu_number(1, 0)),
                self.nodes["m2i1"],
            )
        with self.subTest("second menu, second item"):
            self.assertEqual(
                menu_state.resolve_menu_item_address(self.mem, self.nodes["strip"], menu_state.pack_menu_number(1, 1)),
                self.nodes["m2i2"],
            )

    def test_walks_sub_item_chain(self) -> None:
        with self.subTest("first sub"):
            self.assertEqual(
                menu_state.resolve_menu_item_address(
                    self.mem, self.nodes["strip"], menu_state.pack_menu_number(0, 0, 0)
                ),
                self.nodes["sub1"],
            )
        with self.subTest("second sub"):
            self.assertEqual(
                menu_state.resolve_menu_item_address(
                    self.mem, self.nodes["strip"], menu_state.pack_menu_number(0, 0, 1)
                ),
                self.nodes["sub2"],
            )

    def test_returns_null_for_selectors_and_chains_that_name_no_item(self) -> None:
        strip = self.nodes["strip"]
        cases = {
            "no strip": menu_state.resolve_menu_item_address(self.mem, 0, menu_state.pack_menu_number(0, 0)),
            "MENUNULL": menu_state.resolve_menu_item_address(self.mem, strip, menu_state.MENUNULL),
            "menu beyond chain": menu_state.resolve_menu_item_address(
                self.mem, strip, menu_state.pack_menu_number(5, 0)
            ),
            "item beyond chain": menu_state.resolve_menu_item_address(
                self.mem, strip, menu_state.pack_menu_number(1, 5)
            ),
            "sub beyond chain": menu_state.resolve_menu_item_address(
                self.mem, strip, menu_state.pack_menu_number(1, 1, 3)
            ),
            "sub on childless item": menu_state.resolve_menu_item_address(
                self.mem, strip, menu_state.pack_menu_number(1, 0, 0)
            ),
        }
        for label, address in cases.items():
            with self.subTest(label):
                self.assertEqual(address, 0, "ItemAddress gives NULL, never a made-up address")

    def test_empty_chain_head_never_dereferences_address_zero(self) -> None:
        """A NULL chain head is an empty chain, and stays NULL at any depth.

        ``Menu.FirstItem`` / ``MenuItem.SubItem`` of NULL means "no items", so the
        walk must not start following links from address 0. Without that guard a
        selector deeper than the first entry reads a link out of address 0 and can
        hand back a garbage address as if it were a real ``MenuItem``.
        """

        mem = _FakeMem()
        mem.w32(menu_state.MENUITEM_OFF_NEXT, 0xDEADBEEF)  # what an unguarded walk follows

        menu = 0x2000
        mem.w32(menu + menu_state.MENU_OFF_FIRSTITEM, 0)  # empty menu
        for item_index in (0, 1, 3):
            with self.subTest(empty_menu=item_index):
                self.assertEqual(
                    menu_state.resolve_menu_item_address(mem, menu, menu_state.pack_menu_number(0, item_index)),
                    0,
                    "an empty menu resolves to NULL at every item index",
                )

        item = 0x2100
        mem.w32(menu + menu_state.MENU_OFF_FIRSTITEM, item)
        mem.w32(item + menu_state.MENUITEM_OFF_SUBITEM, 0)  # item with no sub-items
        for sub_index in (0, 1, 2):
            with self.subTest(empty_sub_chain=sub_index):
                self.assertEqual(
                    menu_state.resolve_menu_item_address(mem, menu, menu_state.pack_menu_number(0, 0, sub_index)),
                    0,
                    "a childless item resolves to NULL at every sub-item index",
                )

    def test_picked_item_reads_user_data_at_the_classic_slot(self) -> None:
        item = menu_state.resolve_menu_item_address(self.mem, self.nodes["strip"], menu_state.pack_menu_number(0, 1))
        self.assertEqual(
            self.mem.r32(item + menu_state.MENUITEM_OFF_USERDATA),
            0x3E9,
            "GTMENUITEM_USERDATA is the LONG after mi_SIZEOF (0x22) — where the shipped binary reads it",
        )


class MenuDescriptionRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = menu_state.MenuDescriptionRegistry()
        self.strip = menu_state.describe_strip(
            [MenuTitleDescription("Project", (MenuEntryDescription(item_addr=0x200, code=0xF821, label="New"),))],
            strip_addr=0x100,
        )

    def test_records_and_returns_by_strip_address(self) -> None:
        self.registry.record(0x100, self.strip)
        self.assertIs(self.registry.get(0x100), self.strip)
        self.assertIn(0x100, self.registry)
        self.assertEqual(len(self.registry), 1)
        self.assertEqual(self.registry.all(), [self.strip])

    def test_release_is_idempotent(self) -> None:
        self.registry.record(0x100, self.strip)
        self.assertIs(self.registry.release(0x100), self.strip)
        self.assertIsNone(self.registry.release(0x100))
        self.assertEqual(len(self.registry), 0)

    def test_ignores_null_strip_address(self) -> None:
        self.registry.record(0, self.strip)
        self.assertEqual(len(self.registry), 0)

    def test_registry_from_ctx_reads_the_context_attribute(self) -> None:
        ctx = SimpleNamespace(menu_descriptions=self.registry)
        self.assertIs(menu_state.menu_registry_from_ctx(ctx), self.registry)
        self.assertIsNone(menu_state.menu_registry_from_ctx(SimpleNamespace()))


class DescribeStripTests(unittest.TestCase):
    def test_derives_the_entry_count_from_the_titles(self) -> None:
        menus = [
            MenuTitleDescription("Project", (MenuEntryDescription(0x200, 0xF821), MenuEntryDescription(0x226, 0xF841))),
            MenuTitleDescription("Help", (MenuEntryDescription(0x300, 0xFA21),)),
        ]
        strip = menu_state.describe_strip(menus, strip_addr=0x100)
        self.assertEqual(strip.strip_addr, 0x100)
        self.assertEqual(strip.entry_count, 3, "derived: separators and all count as chain slots")
        self.assertEqual([menu.title for menu in strip.menus], ["Project", "Help"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
