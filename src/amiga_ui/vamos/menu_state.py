"""Classic Intuition menu-strip layout, menu-number encoding, and host descriptions.

This module is the single source of truth for the two pieces of ABI the menu
path depends on, and for the run-wide registry of decoded menu strips.

**The menu number (``MenuNumber`` / ``IntuiMessage.Code``).** Classic Intuition
delivers a menu pick as a single packed 16-bit selector: menu number in bits
0-4, item number in bits 5-10, optional sub-item number in bits 11-15, each
component 1-based, with ``NOMENU`` / ``NOITEM`` / ``NOSUB`` marking "this level
was not selected" and ``MENUNULL`` (``$FFFF``) meaning "no menu event". The
target follows exactly this contract: its event loop copies ``IntuiMessage.Code``
into the ``menu_number`` argument and calls ``ItemAddress(strip, menu_number)``
with it *unchanged* (see ``docs/apps/itidy/menu-strip-menupick-abi.md``).

**The ``struct Menu`` / ``struct MenuItem`` field positions** are the classic
NDK 3.2 ones (``Include_I/intuition/intuition.i``, ``STRUCTURE Menu,0`` /
``STRUCTURE MenuItem,0``): ``mi_SubItem`` at 0x1C, ``mi_NextSelect`` at 0x20,
``mi_SIZEOF`` = 0x22. The value the app reads back for a picked item is
``GTMENUITEM_USERDATA(item)``, which ``CreateMenus`` stores in the private area
*immediately after* the classic struct — a ``LONG`` at ``MenuItem + 0x22``. The
shipped binary reads it there (``move.l $22(a2),d1`` in its menu dispatcher),
which is what fixes both the offset and the allocation size of our item blocks.

Everything here is Qt-free and (for the walkers) memory-only: the compatibility
layer decodes a real strip into immutable, host-safe
:class:`~amiga_ui.host.projection.MenuStripDescription` values while emulated
memory is valid, and the Qt projection never dereferences emulated memory.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from ..host.projection import MenuStripDescription, MenuTitleDescription

# --- the classic menu-number encoding ----------------------------------------
MENUNULL = 0xFFFF  # no menu event at all
NOMENU = 0x001F  # menu field: no menu selected
NOITEM = 0x003F  # item field: no item selected (title clicked, then released)
NOSUB = 0x001F  # sub-item field: no third level (the common two-level case)

# --- struct Menu (classic: Menu_SIZEOF == 0x16) -------------------------------
MENU_SIZE = 0x16
MENU_OFF_NEXT = 0x00  # APTR struct Menu *NextMenu
MENU_OFF_LEFT = 0x04  # WORD LeftEdge
MENU_OFF_TOP = 0x06  # WORD TopEdge
MENU_OFF_WIDTH = 0x08  # WORD Width
MENU_OFF_HEIGHT = 0x0A  # WORD Height
MENU_OFF_FLAGS = 0x0C  # UWORD mn_Flags
MENU_OFF_NAME = 0x0E  # CONST_STRPTR MenuName
MENU_OFF_FIRSTITEM = 0x12  # APTR struct MenuItem *FirstItem

# --- struct MenuItem (classic: mi_SIZEOF == 0x22) -----------------------------
MENUITEM_SIZE = 0x22
MENUITEM_OFF_NEXT = 0x00  # APTR struct MenuItem *NextItem
MENUITEM_OFF_LEFT = 0x04  # WORD LeftEdge
MENUITEM_OFF_TOP = 0x06  # WORD TopEdge
MENUITEM_OFF_WIDTH = 0x08  # WORD Width
MENUITEM_OFF_HEIGHT = 0x0A  # WORD Height
MENUITEM_OFF_FLAGS = 0x0C  # UWORD mn_Flags
MENUITEM_OFF_MUTE = 0x0E  # LONG MutualExclude
MENUITEM_OFF_FILL = 0x12  # APTR ItemFill (IntuiText / Image / NULL)
MENUITEM_OFF_SELECT = 0x16  # APTR SelectFill
MENUITEM_OFF_CMD = 0x1A  # UBYTE Command (command key)
MENUITEM_OFF_SUBITEM = 0x1C  # APTR struct MenuItem *SubItem
MENUITEM_OFF_NEXTSELECT = 0x20  # UWORD NextSelect
MENUITEM_OFF_USERDATA = 0x22  # APTR GTMENUITEM_USERDATA(item): past mi_SIZEOF
# What ``CreateMenus`` must allocate per item: the classic struct *plus* the
# user-data slot, so reading it stays inside the block we own.
MENUITEM_BLOCK_SIZE = MENUITEM_OFF_USERDATA + 4  # 0x26
# ``mi_NextSelect`` for an item that is not chained into a selection.  Intuition
# links the items selected by one MENUPICK through this UWORD and terminates the
# chain with ``MENUNULL``; every other item carries ``MENUNULL`` there too.  This
# is not cosmetic: the shipped iTidy selection walk advances with
# ``moveq #0,d4 / move.w $20(a2),d4 / cmpa.l #$ffff,a4 / bne <loop>`` (handler at
# runtime address 0x21c34), so a zero ``NextSelect`` turns the app's
# ``while (menu_number != MENUNULL)`` loop into an endless ``ItemAddress`` spin.
NEXTSELECT_NULL = MENUNULL


@dataclass(frozen=True)
class MenuNumber:
    """A decoded classic menu selector: 0-based indices into the real chains."""

    menu_index: int
    item_index: int
    sub_index: int | None = None

    @property
    def code(self) -> int:
        """The packed selector this decodes from (round-trip identity)."""

        return pack_menu_number(self.menu_index, self.item_index, self.sub_index)


def pack_menu_number(menu_index: int, item_index: int, sub_index: int | None = None) -> int:
    """Pack 0-based chain indices into the 16-bit selector Intuition delivers.

    The fields are 1-based on the wire (classic Intuition counts menus and items
    from 1); a two-level pick carries ``NOSUB`` in the top field. Raises
    ``ValueError`` for indices that do not fit their field — a caller that has
    more menus/items than Intuition can encode is a real bug, not something to
    silently truncate.
    """

    if not 1 <= menu_index + 1 < NOMENU:
        raise ValueError(f"menu index {menu_index} does not fit the 5-bit menu field")
    if not 1 <= item_index + 1 < NOITEM:
        raise ValueError(f"item index {item_index} does not fit the 6-bit item field")
    code = (menu_index + 1) | ((item_index + 1) << 5)
    if sub_index is None:
        return code | (NOSUB << 11)
    if not 1 <= sub_index + 1 < NOSUB:
        raise ValueError(f"sub-item index {sub_index} does not fit the 5-bit sub-item field")
    return code | ((sub_index + 1) << 11)


def decode_menu_number(menu_number: int) -> MenuNumber | None:
    """Decode a delivered selector, or ``None`` when it selects no item.

    ``MENUNULL`` (and any selector whose menu or item field says "not
    selected") identifies no menu item, exactly like the classic macros
    ``MENUNUM()`` / ``ITEMNUM()`` / ``SUBNUM()`` combined with the ``NOMENU`` /
    ``NOITEM`` / ``NOSUB`` markers. Only the low 16 bits are a selector; the
    app zero-extends the ``Code`` word, and so do we.
    """

    code = menu_number & 0xFFFF
    if code == MENUNULL:
        return None
    menu_field = code & NOMENU
    item_field = (code >> 5) & NOITEM
    sub_field = (code >> 11) & NOSUB
    if menu_field in (0, NOMENU) or item_field in (0, NOITEM):
        return None
    sub_index = None if sub_field in (0, NOSUB) else sub_field - 1
    return MenuNumber(menu_field - 1, item_field - 1, sub_index)


def _nth_link(mem: Any, start: int, next_offset: int, steps: int, limit: int = 0x100) -> int:
    """Follow ``next_offset`` links ``steps`` times from ``start`` (0 = ``start``).

    A null ``start`` (an empty ``FirstItem`` / ``SubItem`` chain) is NULL right
    away: the walk never dereferences address 0, and a chain that runs out
    before the selector is exhausted gives NULL like the real walk does.
    """

    node = start
    if not node:
        return 0
    for _ in range(min(steps, limit)):
        node = mem.r32(node + next_offset)
        if not node:
            return 0
    return node


def resolve_menu_item_address(mem: Any, menu_strip: int, menu_number: int) -> int:
    """The ``struct MenuItem *`` a menu number addresses, or 0 (NULL).

    The real ``ItemAddress()`` walk: ``Menu.NextMenu`` picks the menu, that
    menu's ``FirstItem``/``NextItem`` chain picks the item, and a sub-item
    component follows ``MenuItem.SubItem`` and its own ``NextItem`` chain. A
    selector that names no item (``MENUNULL``, ``NOMENU``, ``NOITEM``) or a chain
    that runs out returns NULL rather than a made-up address.
    """

    if not menu_strip:
        return 0
    decoded = decode_menu_number(menu_number)
    if decoded is None:
        return 0
    menu = _nth_link(mem, menu_strip, MENU_OFF_NEXT, decoded.menu_index)
    if not menu:
        return 0
    item = _nth_link(mem, mem.r32(menu + MENU_OFF_FIRSTITEM), MENUITEM_OFF_NEXT, decoded.item_index)
    if not item:
        return 0
    if decoded.sub_index is None:
        return item
    return _nth_link(mem, mem.r32(item + MENUITEM_OFF_SUBITEM), MENUITEM_OFF_NEXT, decoded.sub_index)


@dataclass
class MenuDescriptionRegistry:
    """Run-wide map of an emulated ``struct Menu *`` strip to its decoded form.

    Installed on the library context as ``ctx.menu_descriptions`` so the
    GadTools library (which *creates* the strip and therefore knows how to read
    its labels) and the Intuition library (which *attaches* it to a window and
    must project it) share one decoded view without importing each other.
    """

    # strip addr (emulated ``struct Menu *``) -> decoded description
    _descriptions: dict[int, MenuStripDescription] = field(default_factory=dict)

    def record(self, strip_addr: int, description: MenuStripDescription) -> None:
        """Record (or replace) the decoded description of one created strip."""

        if strip_addr:
            self._descriptions[strip_addr] = description

    def get(self, strip_addr: int) -> MenuStripDescription | None:
        """Return the decoded description for ``strip_addr`` (or ``None``)."""

        return self._descriptions.get(strip_addr)

    def release(self, strip_addr: int) -> MenuStripDescription | None:
        """Remove and return the description for ``strip_addr`` (idempotent)."""

        return self._descriptions.pop(strip_addr, None)

    def release_all(self) -> None:
        """Drop every recorded description."""

        self._descriptions.clear()

    def all(self) -> list[MenuStripDescription]:
        """All decoded strips, in first-recorded (insertion) order."""

        return list(self._descriptions.values())

    def __len__(self) -> int:
        return len(self._descriptions)

    def __contains__(self, strip_addr: int) -> bool:  # type: ignore[override]
        return strip_addr in self._descriptions


def menu_registry_from_ctx(ctx: Any) -> MenuDescriptionRegistry | None:
    """Return the menu-description registry installed on ``ctx`` (or ``None``)."""

    return getattr(ctx, "menu_descriptions", None)


def describe_strip(menus: Sequence[MenuTitleDescription], strip_addr: int = 0) -> MenuStripDescription:
    """Assemble one host-safe strip description from already-decoded titles.

    The entry count is derived, not supplied, so it can never disagree with the
    titles it wraps (it is what the host uses to report an honest "the app
    attached a menu strip with N entries" observation).
    """

    return MenuStripDescription(
        strip_addr=strip_addr,
        menus=tuple(menus),
        entry_count=sum(len(menu.items) for menu in menus),
    )
