"""Repo‑owned ``gadtools.library`` implementation for vamos.

``GetVisualInfoA`` (V36) is the entry point ``iTidy`` hits right after
``LockPubScreen`` when it opens its main window. The classic contract is:
return ``NULL`` when the screen is ``NULL``; otherwise hand back a private
block carrying the drawing context GadTools needs (borders, font metrics,
colour depth) so the gadgets and menus it later creates lay out against the
correct grid. ``FreeVisualInfo`` releases that block after the window closes.

The app treats the returned pointer as opaque — it only forwards it into
``NewGadget.ng_VisualInfo`` and the ``LayoutMenusA`` calls — so the exact
field layout only has to be internally consistent between this producer and
the GadTools consumers. The values we fill in are derived from the real
locked screen the app passed in, not constants.
"""

from __future__ import annotations

from typing import Any

from ..host.projection import (
    KIND_BUTTON,
    KIND_CHECKBOX,
    KIND_CONTEXT,
    KIND_CYCLE,
    KIND_GENERIC,
    KIND_INTEGER,
    KIND_LISTVIEW,
    KIND_MX,
    KIND_NUMBER,
    KIND_PALETTE,
    KIND_SCROLLER,
    KIND_SLIDER,
    KIND_STRING,
    KIND_TEXT,
    KIND_UNSUPPORTED,
    GadgetDescription,
)
from .base_library import BaseLibrary
from .gadget_state import gadget_registry_from_ctx
from .rastport_state import RastPortRegistry

# --- struct VisualInfo (private GadTools block, screen‑derived) --------------
_VI_SIZE = 0x20
_VI_OFF_SCREEN = 0x00  # APTR struct Screen *
_VI_OFF_LEFT_BORDER = 0x04  # UWORD
_VI_OFF_TOP_BORDER = 0x06  # UWORD
_VI_OFF_COLOR_DEPTH = 0x08  # UWORD
_VI_OFF_MIN_FONT_WIDTH = 0x0A  # UWORD
_VI_OFF_MIN_FONT_HEIGHT = 0x0C  # UWORD
_VI_OFF_MIN_GADGET_WIDTH = 0x0E  # UWORD
_VI_OFF_MIN_GADGET_HEIGHT = 0x10  # UWORD

# --- struct Screen offsets we read (must stay in sync with intuition_library)
_SCR_OFF_WBOR_LEFT = 0x24  # UBYTE WBorLeft
_SCR_OFF_WBOR_TOP = 0x25  # UBYTE WBorTop
_SCR_OFF_FONT = 0x2C  # APTR struct TextAttr *
_SCR_OFF_BITMAP_DEPTH = 0xC1  # BitMap.PlaneCount (0xBC + 0x05)

# --- struct TextAttr ---------------------------------------------------------
_TA_OFF_HEIGHT = 0x20  # UBYTE TaHeight (31‑byte TaName + TaFlags)

# --- GadTools tag space ------------------------------------------------------
# GadTools tag base. The NDK header defines ``GT_TagBase = TAG_USER + 0x80000``
# and ``TAG_USER = 1UL << 31 = 0x80000000`` (utility/tagitem.h), so the base is
# 0x80080000. The real classic m68k binary emits tags in this space (e.g. the
# cycle taglist carries 0x8008000e/0x8008000f for GTCY_Labels/GTCY_Active), so
# this constant must match it for tag decoding to succeed.
_GT_TAG_BASE = 0x80080000
_GTVI_LEFT_BORDER = _GT_TAG_BASE + 96
_GTVI_TOP_BORDER = _GT_TAG_BASE + 97
# DrawBevelBox(A) tags (the group-box / frame bevel). The app's call passes
# only these two (plus TAG_END); the optional VB_Pen/VB_Bevel attributes are
# ignored (recorded as defaults).
_GTBB_RECESSED = _GT_TAG_BASE + 51  # make the bevel box recessed (TRUE/FALSE)
_GT_VISUALINFO = _GT_TAG_BASE + 52  # a VisualInfo result (APTR)
_TAG_DONE = 0

# --- CreateGadget(A) state tags ----------------------------------------------
# GadTools carries per-kind gadget state in the same tag list as
# ``CreateGadgetA(kind, prevGad, ng, tag, ...)``. These live in the GadTools tag
# space (``GT_TagBase`` = 0x88000), per NDK 3.2 ``libraries/gadtools.h``
# (used here as field-by-field corroboration of the classic tag numbers):
#
#     GTCB_Checked  (GT_TagBase+4)   state of a CHECKBOX gadget (BOOL)
#     GTTX_Text     (GT_TagBase+11)  text to display in a TEXT gadget (STRPTR)
#     GTCY_Labels   (GT_TagBase+14)  NULL-terminated STRPTR array for CYCLE
#     GTCY_Active   (GT_TagBase+15)  active index in a CYCLE gadget (UWORD)
#     GTTX_Border   (GT_TagBase+57)  draw a border around a TEXT gadget (BOOL)
#
# NOTE: the app's ``GA_Disabled`` is an Intuition *gadget-class* tag
# (``GA_Dummy`` = TAG_USER+0x30000 = 0x38000, so ``GA_Disabled`` = 0x3800E) — a
# different tag space from the GadTools one — and classic GadTools' interpretation
# of it is not established by the available evidence. The app passes ``FALSE``
# (enabled) and the default is enabled, so decoded gadgets are recorded enabled;
# we do not claim to have decoded a GadTools disable tag.
_GTCB_CHECKED = _GT_TAG_BASE + 4
_GTTX_TEXT = _GT_TAG_BASE + 11
_GTCY_LABELS = _GT_TAG_BASE + 14
_GTCY_ACTIVE = _GT_TAG_BASE + 15
_GTTX_BORDER = _GT_TAG_BASE + 57

# --- GadTools GadgetType values (NDK 3.2 ``libraries/gadtools.h``) ------------
_GADTYPE_GENERIC = 0
_GADTYPE_BUTTON = 1
_GADTYPE_CHECKBOX = 2
_GADTYPE_INTEGER = 3
_GADTYPE_LISTVIEW = 4
_GADTYPE_MX = 5
_GADTYPE_NUMBER = 6
_GADTYPE_CYCLE = 7
_GADTYPE_PALETTE = 8
_GADTYPE_SCROLLER = 9
# 10 is reserved by the header
_GADTYPE_SLIDER = 11
_GADTYPE_STRING = 12
_GADTYPE_TEXT = 13

_GADTYPE_TO_KIND_NAME = {
    _GADTYPE_GENERIC: KIND_GENERIC,
    _GADTYPE_BUTTON: KIND_BUTTON,
    _GADTYPE_CHECKBOX: KIND_CHECKBOX,
    _GADTYPE_INTEGER: KIND_INTEGER,
    _GADTYPE_LISTVIEW: KIND_LISTVIEW,
    _GADTYPE_MX: KIND_MX,
    _GADTYPE_NUMBER: KIND_NUMBER,
    _GADTYPE_CYCLE: KIND_CYCLE,
    _GADTYPE_PALETTE: KIND_PALETTE,
    _GADTYPE_SCROLLER: KIND_SCROLLER,
    _GADTYPE_SLIDER: KIND_SLIDER,
    _GADTYPE_STRING: KIND_STRING,
    _GADTYPE_TEXT: KIND_TEXT,
}

# Sensible fallbacks when the screen font is not populated.
_DEFAULT_FONT_HEIGHT = 8
_DEFAULT_MIN_GADGET_WIDTH = 12
_DEFAULT_MIN_GADGET_HEIGHT = 14
_DEFAULT_COLOR_DEPTH = 1

# --- struct Gadget (classic/NDK 3.2, NextGadget linkage at 0x00) ------------
_GAD_SIZE = 0x2C
_GAD_OFF_NEXT = 0x00  # APTR struct Gadget *NextGadget
_GAD_OFF_LEFT = 0x04  # WORD LeftEdge
_GAD_OFF_TOP = 0x06  # WORD TopEdge
_GAD_OFF_WIDTH = 0x08  # WORD Width
_GAD_OFF_HEIGHT = 0x0A  # WORD Height
_GAD_OFF_FLAGS = 0x0C  # UWORD Flags
_GAD_OFF_ACTIVATION = 0x0E  # UWORD Activation
_GAD_OFF_TYPE = 0x10  # UWORD GadgetType
_GAD_OFF_RENDER = 0x12  # APTR GadgetRender
_GAD_OFF_SELECT = 0x16  # APTR SelectRender
_GAD_OFF_TEXT = 0x1A  # APTR struct IntuiText *GadgetText
_GAD_OFF_MUTE = 0x1E  # LONG MutualExclude (context: stores glist ptr)
_GAD_OFF_SPECIAL = 0x22  # APTR SpecialInfo
_GAD_OFF_ID = 0x26  # UWORD GadgetID
_GAD_OFF_USERDATA = 0x28  # APTR UserData

# --- struct GContext (Gadget + APTR gc_Group) --------------------------------
_GCTX_SIZE = _GAD_SIZE + 4

# --- struct NewGadget (GadTools creation input) ------------------------------
_NG_OFF_LEFT = 0x00  # WORD ng_LeftEdge
_NG_OFF_TOP = 0x02  # WORD ng_TopEdge
_NG_OFF_WIDTH = 0x04  # WORD ng_Width
_NG_OFF_HEIGHT = 0x06  # WORD ng_Height
_NG_OFF_TEXT = 0x08  # CONST_STRPTR ng_GadgetText
_NG_OFF_TEXTATTR = 0x0C  # APTR ng_TextAttr
_NG_OFF_ID = 0x10  # UWORD ng_GadgetID
_NG_OFF_FLAGS = 0x12  # ULONG ng_Flags
_NG_OFF_VISUAL = 0x16  # APTR ng_VisualInfo
_NG_OFF_USERDATA = 0x1A  # APTR ng_UserData

# --- struct IntuiText (gadget label) ----------------------------------------
# Classic m68k AmigaOS 3.x ``iT_*`` layout (default target per
# docs/architecture/platform-target.md). The old pre-2.0 ``FrontPen``/``IText``
# shape found in the repo's mislabelled "NDK3.2" (actually the AmigaOS 4.1 NDK)
# does NOT apply here.
_IT_SIZE = 0x24
_IT_OFF_FACE = 0x00  # UWORD iT_Face
_IT_OFF_FACE_REL = 0x02  # UBYTE iT_FaceRelative
_IT_OFF_LEFT = 0x04  # WORD iT_Left
_IT_OFF_TOP = 0x06  # WORD iT_Top
_IT_OFF_WIDTH = 0x08  # WORD iT_Width
_IT_OFF_HEIGHT = 0x0A  # WORD iT_Height
_IT_OFF_FORE = 0x0C  # UBYTE iT_ForePen
_IT_OFF_BACK = 0x0D  # UBYTE iT_BackPen
_IT_OFF_DRMODE = 0x0E  # UBYTE iT_DrawMode
_IT_OFF_PROP = 0x0F  # UBYTE iT_Proportion
_IT_OFF_QUALITY = 0x10  # UBYTE iT_Quality
_IT_OFF_TEXT = 0x14  # CONST_STRPTR iT_Text
_IT_OFF_FACE_FONT = 0x18  # APTR iT_FaceFont
_IT_OFF_PENMAP = 0x1C  # UBYTE iT_PenMap[8]

# Sentinel GadgetType for the invisible, unselectable context gadget.
_CONTEXT_KIND = 0xFFFF

# --- struct NewMenu (GadTools creation template) -----------------------------
_NM_SIZE = 0x14
_NM_OFF_TYPE = 0x00  # UBYTE nm_Type
_NM_OFF_LABEL = 0x02  # CONST_STRPTR nm_Label
_NM_OFF_COMMKEY = 0x06  # CONST_STRPTR nm_CommKey
_NM_OFF_FLAGS = 0x0A  # UWORD nm_Flags
_NM_OFF_MUTE = 0x0C  # LONG nm_MutualExclude
_NM_OFF_USERDATA = 0x10  # APTR nm_UserData

# NewMenu nm_Type values.
_NM_END = 0
_NM_TITLE = 1
_NM_ITEM = 2
_NM_SUB = 3
_NM_IGNORE = 64
_MENU_IMAGE = 128
_NM_BARLABEL = 0xFFFFFFFF  # (STRPTR)-1: separator bar

# --- struct Menu (classic intuition, 30 bytes) -------------------------------
_MENU_SIZE = 0x1E
_MENU_OFF_NEXT = 0x00  # APTR struct Menu *NextMenu
_MENU_OFF_LEFT = 0x04  # WORD LeftEdge
_MENU_OFF_TOP = 0x06  # WORD TopEdge
_MENU_OFF_WIDTH = 0x08  # WORD Width
_MENU_OFF_HEIGHT = 0x0A  # WORD Height
_MENU_OFF_FLAGS = 0x0C  # UWORD Flags
_MENU_OFF_NAME = 0x0E  # CONST_STRPTR MenuName
_MENU_OFF_FIRSTITEM = 0x12  # APTR struct MenuItem *FirstItem

# --- struct MenuItem (classic intuition, Cmd field at 0x21) ------------------
_MI_SIZE = 0x25
_MI_OFF_NEXT = 0x00  # APTR struct MenuItem *NextItem
_MI_OFF_LEFT = 0x04  # WORD LeftEdge
_MI_OFF_TOP = 0x06  # WORD TopEdge
_MI_OFF_WIDTH = 0x08  # WORD Width
_MI_OFF_HEIGHT = 0x0A  # WORD Height
_MI_OFF_FLAGS = 0x0C  # UWORD Flags
_MI_OFF_MUTE = 0x0E  # LONG MutualExclude
_MI_OFF_FILL = 0x12  # APTR ItemFill (IntuiText / Image / NULL)
_MI_OFF_SELECT = 0x16  # APTR SelectFill
_MI_OFF_CMD = 0x1A  # BYTE Command (command key)
_MI_OFF_SUBITEM = 0x1B  # APTR SubItem
_MI_OFF_NEXTSELECT = 0x1F  # UWORD NextSelect
_MI_OFF_CMDVAL = 0x21  # LONG Cmd (item id from nm_UserData)


class GadToolsLibrary(BaseLibrary):
    """GadTools visual‑info and gadget‑list support for the public screen path."""

    def __init__(self) -> None:
        super().__init__()
        self._visual_infos: dict[int, object] = {}
        self._gadgets: dict[int, object] = {}
        self._menu_blocks: dict[int, object] = {}
        # Fallback RastPort op log for unit tests; the launcher installs a
        # run-wide shared registry on the context (see _registry).
        self.rastports = RastPortRegistry()
        # Ordered record of GT_RefreshWindow repaint requests — a host-side
        # signal for the future renderer to repaint the window's gadgets.
        self.refresh_requests: list[dict[str, Any]] = []

    def get_version(self) -> int:
        """Report a plausible library version (non‑zero, V36 baseline or newer)."""
        return 40

    def _registry(self, ctx):
        """The host-side RastPort op log (run-wide shared, or the fallback)."""
        return getattr(ctx, "rastports", None) or self.rastports

    # -- helpers --------------------------------------------------------------
    @staticmethod
    def _read_screen_context(mem, screen: int) -> tuple[int, int, int, int]:
        """Read WBorLeft, WBorTop, font height and colour depth from a screen.

        Returns ``(wb_left, wb_top, font_height, color_depth)`` with safe
        fallbacks so a partially populated screen still yields a valid grid.
        """
        wb_left = mem.r8(screen + _SCR_OFF_WBOR_LEFT)
        wb_top = mem.r8(screen + _SCR_OFF_WBOR_TOP)
        font_ptr = mem.r32(screen + _SCR_OFF_FONT)
        font_height = mem.r8(font_ptr + _TA_OFF_HEIGHT) if font_ptr else 0
        color_depth = mem.r8(screen + _SCR_OFF_BITMAP_DEPTH)
        if not font_height:
            font_height = _DEFAULT_FONT_HEIGHT
        if not color_depth:
            color_depth = _DEFAULT_COLOR_DEPTH
        return wb_left, wb_top, font_height, color_depth

    @staticmethod
    def _parse_tag_overrides(mem, taglist: int) -> tuple[int | None, int | None]:
        """Walk a ``TagItem`` list for ``GTVI_LeftBorder`` / ``GTVI_TopBorder``."""
        left: int | None = None
        top: int | None = None
        if not taglist:
            return left, top
        offset = 0
        # Bounded walk: TAG_DONE always terminates the app's tag list.
        for _ in range(0x200):
            tag = mem.r32(taglist + offset)
            if tag == _TAG_DONE:
                break
            data = mem.r32(taglist + offset + 4)
            if tag == _GTVI_LEFT_BORDER:
                left = data
            elif tag == _GTVI_TOP_BORDER:
                top = data
            offset += 8
        return left, top

    @staticmethod
    def _parse_bevel_tags(mem, taglist: int) -> tuple[int | None, bool]:
        """Walk a ``TagItem`` list for ``GT_VisualInfo`` / ``GTBB_Recessed``.

        Returns ``(visual_info_ptr_or_None, recessed)``. Unknown tags (e.g. the
        optional ``VB_Pen``/``VB_Bevel``) are ignored — the app's group-box call
        passes only ``GT_VisualInfo`` and ``GTBB_Recessed`` (then ``TAG_END``).
        """
        vi: int | None = None
        recessed = False
        if not taglist:
            return vi, recessed
        offset = 0
        for _ in range(0x200):  # bounded: TAG_DONE always terminates
            tag = mem.r32(taglist + offset)
            if tag == _TAG_DONE:
                break
            data = mem.r32(taglist + offset + 4)
            if tag == _GT_VISUALINFO:
                vi = data
            elif tag == _GTBB_RECESSED:
                recessed = bool(data)
            offset += 8
        return vi, recessed

    # -- gadtools.library entry points ---------------------------------------
    def GetVisualInfoA(self, ctx, screen, taglist):
        """Return a screen‑derived visual‑info block, or ``NULL`` for a NULL screen."""
        if not screen:
            return 0

        mem = ctx.mem
        alloc = ctx.alloc

        wb_left, wb_top, font_height, color_depth = self._read_screen_context(mem, screen)
        tag_left, tag_top = self._parse_tag_overrides(mem, taglist)

        left_border = wb_left if tag_left is None else tag_left
        # Classic default top grid: WBorTop + font height + 1 (dragbar room).
        top_border = wb_top + font_height + 1 if tag_top is None else tag_top

        vi = alloc.alloc_memory(_VI_SIZE, label="GadTools.VisualInfo")
        addr = vi.addr
        mem.w32(addr + _VI_OFF_SCREEN, screen)
        mem.w16(addr + _VI_OFF_LEFT_BORDER, left_border)
        mem.w16(addr + _VI_OFF_TOP_BORDER, top_border)
        mem.w16(addr + _VI_OFF_COLOR_DEPTH, color_depth)
        mem.w16(addr + _VI_OFF_MIN_FONT_WIDTH, 5)
        mem.w16(addr + _VI_OFF_MIN_FONT_HEIGHT, font_height)
        mem.w16(addr + _VI_OFF_MIN_GADGET_WIDTH, _DEFAULT_MIN_GADGET_WIDTH)
        mem.w16(addr + _VI_OFF_MIN_GADGET_HEIGHT, _DEFAULT_MIN_GADGET_HEIGHT)

        self._visual_infos[addr] = vi
        return addr

    def FreeVisualInfo(self, ctx, vi):
        """Release a block previously returned by ``GetVisualInfoA``."""
        if not vi:
            return None
        mem_obj = self._visual_infos.pop(vi, None)
        if mem_obj is not None:
            ctx.alloc.free_memory(mem_obj)
        return None

    # -- gadget list creation -------------------------------------------------
    # -- Host-safe decoding helpers (68k -> immutable values) ----------------
    # These interpret emulated memory *now*, while it is valid, and return
    # copied host-safe values (str/int/tuple). The projection boundary never
    # sees a live pointer.

    @staticmethod
    def _read_tag(mem, taglist, tag):
        """Return the ULONG data for ``tag`` in a GadTools tag list, or ``None``.

        A tag list is a sequence of ``(tag, data)`` ULONG pairs terminated by
        ``TAG_DONE`` (0). The walk is bounded so a malformed list cannot hang.
        """

        if not taglist:
            return None
        offset = 0
        for _ in range(0x100):
            base = taglist + offset
            current = mem.r32(base)
            if current in (0, _TAG_DONE):
                return None
            if current == tag:
                return mem.r32(base + 4)
            offset += 8
        return None

    @staticmethod
    def _decode_c_string(mem, addr, max_len=1024):
        """Copy a NULL-terminated C string out of emulated memory into a ``str``."""

        if not addr:
            return ""
        out = bytearray()
        for i in range(max_len):
            b = mem.r8(addr + i)
            if b == 0:
                break
            out.append(b)
        return out.decode("latin-1")

    def _decode_cycle_labels(self, mem, labels_ptr, max_items=64):
        """Copy a NULL-terminated array of label pointers into a tuple of ``str``."""

        if not labels_ptr:
            return ()
        labels: list[str] = []
        for i in range(max_items):
            str_addr = mem.r32(labels_ptr + i * 4)
            if not str_addr:
                break
            labels.append(self._decode_c_string(mem, str_addr))
        return tuple(labels)

    def CreateContext(self, ctx, glistptr):
        """Create the invisible context gadget that heads a GadTools list.

        ``glistptr`` is the address of a ``struct Gadget *`` the app has set to
        NULL. We allocate a real GContext, make it the list head, and point the
        app's pointer at it so it becomes ``NewWindow.nw_FirstGadget``. The
        context gadget is invisible and unselectable (``GadgetType`` is a
        sentinel outside the real kind range) so Intuition skips it.
        """
        if not glistptr:
            return 0
        mem = ctx.mem
        alloc = ctx.alloc
        gctx = alloc.alloc_memory(_GCTX_SIZE, label="GadTools.GContext")
        addr = gctx.addr
        mem.w32(addr + _GAD_OFF_NEXT, 0)  # head: no previous gadget
        mem.w16(addr + _GAD_OFF_TYPE, _CONTEXT_KIND)
        mem.w32(addr + _GAD_OFF_MUTE, glistptr)  # remember the glist pointer
        mem.w32(glistptr, addr)  # *glistptr = context gadget
        self._gadgets[addr] = gctx
        # Record the context gadget explicitly (marked KIND_CONTEXT) so the
        # boundary can prove it is present in the chain yet never projected.
        registry = gadget_registry_from_ctx(ctx)
        if registry is not None:
            registry.record(
                GadgetDescription(
                    gadget_addr=addr,
                    gadget_id=0,
                    kind_name=KIND_CONTEXT,
                    kind=_CONTEXT_KIND,
                    left=0,
                    top=0,
                    width=0,
                    height=0,
                    label="",
                )
            )
        return addr

    def CreateGadgetA(self, ctx, kind, prev_gad, ng, taglist):
        """Create a real gadget and chain it after ``prev_gad`` in the list.

        The geometry, kind and id come from the ``NewGadget`` the app filled in;
        a minimal ``IntuiText`` carries the label so ``GadgetText`` is a valid
        structure. The new gadget is linked via ``NextGadget`` and returned.
        """
        if not prev_gad or not ng:
            return 0
        mem = ctx.mem
        alloc = ctx.alloc
        gad = alloc.alloc_memory(_GAD_SIZE, label="GadTools.Gadget")
        addr = gad.addr
        mem.w16(addr + _GAD_OFF_LEFT, mem.r16(ng + _NG_OFF_LEFT))
        mem.w16(addr + _GAD_OFF_TOP, mem.r16(ng + _NG_OFF_TOP))
        mem.w16(addr + _GAD_OFF_WIDTH, mem.r16(ng + _NG_OFF_WIDTH))
        mem.w16(addr + _GAD_OFF_HEIGHT, mem.r16(ng + _NG_OFF_HEIGHT))
        mem.w16(addr + _GAD_OFF_TYPE, kind & 0xFFFF)
        mem.w16(addr + _GAD_OFF_ID, mem.r16(ng + _NG_OFF_ID))
        mem.w32(addr + _GAD_OFF_USERDATA, mem.r32(ng + _NG_OFF_USERDATA))
        mem.w32(addr + _GAD_OFF_NEXT, 0)
        text_ptr = mem.r32(ng + _NG_OFF_TEXT)
        if text_ptr:
            it = alloc.alloc_memory(_IT_SIZE, label="GadTools.IntuiText")
            mem.w16(it.addr + _IT_OFF_FACE, 0)
            mem.w16(it.addr + _IT_OFF_WIDTH, 5)
            mem.w16(it.addr + _IT_OFF_HEIGHT, _DEFAULT_FONT_HEIGHT)
            mem.w32(it.addr + _IT_OFF_TEXT, text_ptr)
            mem.w32(addr + _GAD_OFF_TEXT, it.addr)
            self._gadgets[it.addr] = it
        # chain the new gadget after the previous one in the list
        mem.w32(prev_gad + _GAD_OFF_NEXT, addr)
        self._gadgets[addr] = gad

        # Decode the gadget's immutable, host-safe state *now*, while emulated
        # memory is valid, and record it for the projection boundary. The label
        # is the ``ng_GadgetText`` C string (already read into ``text_ptr``); the
        # per-kind state comes from the GadTools tag list. No live pointer is
        # retained — only copied str/int/bool values.
        raw_kind = kind & 0xFFFF
        kind_name = _GADTYPE_TO_KIND_NAME.get(raw_kind, KIND_UNSUPPORTED)
        gadget_id = mem.r16(ng + _NG_OFF_ID)
        label = self._decode_c_string(mem, text_ptr)
        checked: bool | None = None
        cycle_labels: tuple[str, ...] = ()
        cycle_active = 0
        text: str | None = None
        text_border: bool | None = None
        if raw_kind == _GADTYPE_CHECKBOX:
            checked_val = self._read_tag(mem, taglist, _GTCB_CHECKED)
            checked = bool(checked_val) if checked_val is not None else False
        elif raw_kind == _GADTYPE_CYCLE:
            cycle_labels = self._decode_cycle_labels(mem, self._read_tag(mem, taglist, _GTCY_LABELS))
            active_val = self._read_tag(mem, taglist, _GTCY_ACTIVE)
            cycle_active = int(active_val) if active_val is not None else 0
        elif raw_kind == _GADTYPE_TEXT:
            text_val = self._read_tag(mem, taglist, _GTTX_TEXT)
            text = self._decode_c_string(mem, text_val) if text_val else ""
            border_val = self._read_tag(mem, taglist, _GTTX_BORDER)
            text_border = bool(border_val) if border_val is not None else None

        registry = gadget_registry_from_ctx(ctx)
        if registry is not None:
            registry.record(
                GadgetDescription(
                    gadget_addr=addr,
                    gadget_id=gadget_id,
                    kind_name=kind_name,
                    kind=raw_kind,
                    left=mem.r16(ng + _NG_OFF_LEFT),
                    top=mem.r16(ng + _NG_OFF_TOP),
                    width=mem.r16(ng + _NG_OFF_WIDTH),
                    height=mem.r16(ng + _NG_OFF_HEIGHT),
                    label=label,
                    # Enabled by default. The app's GA_Disabled tag is in the
                    # Intuition gadget-class space (0x3800E), not the GadTools
                    # tag space, and its GadTools interpretation is not
                    # established by classic evidence; the app passes FALSE
                    # (enabled), matching this default. See the tag note above.
                    enabled=True,
                    checked=checked,
                    cycle_labels=cycle_labels,
                    cycle_active=cycle_active,
                    text=text,
                    text_border=text_border,
                )
            )

        # Let the host event bridge resolve IDCMP_GadgetUp IAddress targets to
        # a real gadget struct carrying this id (no-op without a bridge).
        bridge = getattr(ctx, "event_bridge", None)
        if bridge is not None:
            bridge.register_gadget(addr, gadget_id)
        return addr

    def FreeGadgets(self, ctx, gad):
        """Free a gadget list starting at ``gad`` (the context gadget head)."""
        if not gad:
            return None
        mem = ctx.mem
        alloc = ctx.alloc
        cur = gad
        registry = gadget_registry_from_ctx(ctx)
        bridge = getattr(ctx, "event_bridge", None)
        # Bounded walk: the list is always NULL-terminated by CreateGadgetA.
        for _ in range(0x100):
            if not cur:
                break
            it_addr = mem.r32(cur + _GAD_OFF_TEXT)
            if it_addr:
                it_obj = self._gadgets.pop(it_addr, None)
                if it_obj is not None:
                    alloc.free_memory(it_obj)
            obj = self._gadgets.pop(cur, None)
            if obj is not None:
                alloc.free_memory(obj)
            # Release the decoded description for this gadget (idempotent).
            if registry is not None:
                registry.release(cur)
            # Forgetting the gadget in the event bridge makes a late activation
            # on the (now freed) gadget a no-op rather than a stale IntuiMessage
            # (idempotent; no-op when no bridge is installed).
            if bridge is not None:
                bridge.unregister_gadget(cur)
            cur = mem.r32(cur + _GAD_OFF_NEXT)
        return None

    # -- IntuiMessage consumption (the app's event loop) ----------------------
    def GT_GetIMsg(self, ctx, iport):
        """Classic GadTools: ``GetMsg`` on a window's ``UserPort``.

        Returns the address of the next queued ``IntuiMessage`` or ``NULL``
        when the queue is empty. This is what the app's event loop drains
        with after ``WaitPort``; the message it returns is a real
        ``struct IntuiMessage`` block (posted by the host event bridge, see
        ``event_bridge.py``) whose ``Class``/``Code``/``IAddress``/
        ``MouseX``/``MouseY`` the app dereferences directly.
        """
        if not iport:
            return 0
        port_mgr = self._get_port_mgr(ctx)
        if port_mgr is None or not port_mgr.has_port(iport):
            return 0
        return port_mgr.get_msg(iport) or 0

    def GT_ReplyIMsg(self, ctx, imsg):
        """Classic GadTools: reply to and release an ``IntuiMessage``.

        The classic reply (``PutMsg`` to ``msg->ReplyMsg``, i.e. the window's
        ``WindowPort``) has no consumer on the headless host — nothing ever
        waits on the ``WindowPort`` — so the observable work is releasing
        the message block, which the host event bridge tracks. Addresses the
        bridge did not allocate are ignored (honest no-op, not a fake free).
        """
        if not imsg:
            return None
        bridge = getattr(ctx, "event_bridge", None)
        if bridge is not None:
            bridge.release_message(ctx, imsg)
        return None

    @staticmethod
    def _get_port_mgr(ctx):
        """Reach the exec PortManager without a hard dependency (None if absent)."""
        vlib_mgr = getattr(ctx, "vlib_mgr", None)
        if vlib_mgr is None:
            return None
        vlib = vlib_mgr.get_vlib_by_name("exec.library")
        if vlib is None or vlib.impl is None:
            return None
        return vlib.impl.port_mgr

    # -- menu strip creation --------------------------------------------------
    def CreateMenusA(self, ctx, newmenu, taglist):
        """Build a real menu structure from a flat ``NewMenu`` template array.

        The template is a flat array: ``NM_TITLE`` starts a menu, ``NM_ITEM`` /
        ``NM_SUB`` add items to the current menu, ``NM_END`` terminates. We
        allocate genuine ``struct Menu`` / ``struct MenuItem`` blocks, attach
        IntuiText labels, carry the command key and the item id the app set in
        ``nm_UserData``, and link them. The result is a populated menu the app
        can hand to ``LayoutMenus``/``FreeMenus`` -- not an empty handle.
        """
        if not newmenu:
            return 0
        mem = ctx.mem
        alloc = ctx.alloc
        first_menu = 0
        current_menu = 0
        prev_item = 0
        off = 0
        for _ in range(0x400):
            type_val = mem.r8(newmenu + off + _NM_OFF_TYPE)
            off += _NM_SIZE
            if type_val & _NM_IGNORE:
                continue
            if type_val == _NM_END:
                break
            if type_val == _NM_TITLE:
                menu = alloc.alloc_memory(_MENU_SIZE, label="GadTools.Menu")
                addr = menu.addr
                mem.w32(addr + _MENU_OFF_NEXT, 0)
                mem.w32(addr + _MENU_OFF_FIRSTITEM, 0)
                mem.w32(addr + _MENU_OFF_NAME, mem.r32(newmenu + off - _NM_SIZE + _NM_OFF_LABEL))
                mem.w16(addr + _MENU_OFF_FLAGS, mem.r16(newmenu + off - _NM_SIZE + _NM_OFF_FLAGS))
                self._menu_blocks[addr] = menu
                if not first_menu:
                    first_menu = addr
                elif current_menu:
                    mem.w32(current_menu + _MENU_OFF_NEXT, addr)
                current_menu = addr
                prev_item = 0
                continue
            if not current_menu:
                # NM_ITEM before any NM_TITLE: illegal template.
                break
            label = mem.r32(newmenu + off - _NM_SIZE + _NM_OFF_LABEL)
            item = alloc.alloc_memory(_MI_SIZE, label="GadTools.MenuItem")
            iaddr = item.addr
            mem.w32(iaddr + _MI_OFF_NEXT, 0)
            mem.w16(iaddr + _MI_OFF_FLAGS, mem.r16(newmenu + off - _NM_SIZE + _NM_OFF_FLAGS))
            mem.w32(iaddr + _MI_OFF_MUTE, mem.r32(newmenu + off - _NM_SIZE + _NM_OFF_MUTE))
            is_separator = label == _NM_BARLABEL or bool(type_val & _MENU_IMAGE)
            if not is_separator and label:
                it = alloc.alloc_memory(_IT_SIZE, label="GadTools.MenuIntuiText")
                mem.w16(it.addr + _IT_OFF_FACE, 0)
                mem.w16(it.addr + _IT_OFF_WIDTH, 5)
                mem.w16(it.addr + _IT_OFF_HEIGHT, _DEFAULT_FONT_HEIGHT)
                mem.w32(it.addr + _IT_OFF_TEXT, label)
                mem.w32(iaddr + _MI_OFF_FILL, it.addr)
                self._menu_blocks[it.addr] = it
            comm_key = mem.r32(newmenu + off - _NM_SIZE + _NM_OFF_COMMKEY)
            if comm_key:
                mem.w8(iaddr + _MI_OFF_CMD, mem.r8(comm_key) & 0xFF)
            mem.w32(iaddr + _MI_OFF_CMDVAL, mem.r32(newmenu + off - _NM_SIZE + _NM_OFF_USERDATA))
            if not prev_item:
                mem.w32(current_menu + _MENU_OFF_FIRSTITEM, iaddr)
            else:
                mem.w32(prev_item + _MI_OFF_NEXT, iaddr)
            prev_item = iaddr
            self._menu_blocks[iaddr] = item
        return first_menu

    def LayoutMenusA(self, ctx, firstmenu, vi, taglist):
        """Assign position/size to a created menu strip and return success.

        ``CreateMenusA`` leaves the geometry unset; this fills plausible
        per-menu and per-item LeftEdge/TopEdge/Width/Height from the label
        text metrics so the strip has real layout information. Returns TRUE on
        success, FALSE if the strip is missing.
        """
        if not firstmenu:
            return 0
        mem = ctx.mem
        # A reasonable menu row height derived from the font height.
        row_h = _DEFAULT_FONT_HEIGHT + 4
        title_w = 60
        menu = firstmenu
        for _ in range(0x100):
            if not menu:
                break
            mem.w16(menu + _MENU_OFF_HEIGHT, row_h)
            mem.w16(menu + _MENU_OFF_WIDTH, title_w)
            item = mem.r32(menu + _MENU_OFF_FIRSTITEM)
            item_h = row_h
            item_w = title_w
            for _ in range(0x100):
                if not item:
                    break
                mem.w16(item + _MI_OFF_HEIGHT, item_h)
                mem.w16(item + _MI_OFF_WIDTH, item_w)
                mem.w16(item + _MI_OFF_TOP, 0)
                item = mem.r32(item + _MI_OFF_NEXT)
            menu = mem.r32(menu + _MENU_OFF_NEXT)
        return 1

    def FreeMenus(self, ctx, menu):
        """Free a menu strip created by ``CreateMenusA`` (menus, items, texts)."""
        if not menu:
            return None
        mem = ctx.mem
        alloc = ctx.alloc
        cur_menu = menu
        for _ in range(0x100):
            if not cur_menu:
                break
            cur_item = mem.r32(cur_menu + _MENU_OFF_FIRSTITEM)
            for _ in range(0x100):
                if not cur_item:
                    break
                fill = mem.r32(cur_item + _MI_OFF_FILL)
                if fill:
                    it_obj = self._menu_blocks.pop(fill, None)
                    if it_obj is not None:
                        alloc.free_memory(it_obj)
                item_obj = self._menu_blocks.pop(cur_item, None)
                if item_obj is not None:
                    alloc.free_memory(item_obj)
                cur_item = mem.r32(cur_item + _MI_OFF_NEXT)
            menu_obj = self._menu_blocks.pop(cur_menu, None)
            if menu_obj is not None:
                alloc.free_memory(menu_obj)
            cur_menu = mem.r32(cur_menu + _MENU_OFF_NEXT)
        return None

    def DrawBevelBoxA(self, ctx, rport, left, top, width, height, taglist):
        """gadtools.library ``DrawBevelBoxA(rport, left, top, width, height, taglist)``.

        Draw a bevel box (the group-box / frame bevel) on ``rport``. The app's
        group boxes call this (via the varargs ``DrawBevelBox`` wrapper) with
        ``GT_VisualInfo`` and ``GTBB_Recessed`` tags. Reads those tags and records
        a bevel-box op on the host-side RastPort op log (explicit position/size,
        recessed flag, VisualInfo) so a future renderer can replay the frame.
        There is no host window yet, so this record — not a silent no-op — is what
        makes the call meaningful. Returns None (VOID).
        """
        mem = getattr(ctx, "mem", None)
        vi: int | None = None
        recessed = False
        if mem is not None:
            vi, recessed = self._parse_bevel_tags(mem, taglist)
        self._registry(ctx).get_or_create(rport).draw_bevel_box(
            left, top, width, height, recessed=recessed, visual_info=vi or 0
        )
        return None

    def GT_RefreshWindow(self, ctx, win, req):
        """gadtools.library ``GT_RefreshWindow(win, req)``: refresh a window's gadgets.

        Triggers a redraw of the window's gadgets (the app calls it with a
        ``NULL`` requester after drawing). This is the first repaint boundary the
        host projection uses: it records the refresh request (window address) for
        probes, and — when a host projection is installed — asks it to replay the
        window's recorded RastPort op stream onto its drawing surface. Returns
        None (VOID).
        """
        self.refresh_requests.append({"win": win, "req": req})
        projection = getattr(ctx, "host_projection", None)
        if projection is not None:
            projection.refresh_window(win)
        return None
