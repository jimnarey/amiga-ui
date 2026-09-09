"""Repo-owned Intuition.library implementation.

Implements enough real host-side state for the Workbench public screen so the
target app receives a well-formed ``struct Screen`` instead of a fake constant.
The app dereferences ``screen->WBorTop``, ``screen->RastPort.TxHeight`` and the
embedded ``RastPort`` / ``ViewPort`` / ``BitMap``; returning an unallocated
constant made those reads land on stale memory and the visual-info gate failed.

Struct layout follows the classic Workbench-era ``struct Screen`` shape the
target binary expects, including the pre-``RasInfo`` embedded ``ViewPort`` that
places ``RastPort`` at ``Screen+0x54``. See
``docs/platform/library-cards/intuition.library.md``.
"""

from __future__ import annotations

from typing import Any

from ..host.projection import OpenWindowIntent
from .base_library import BaseLibrary
from .rastport_state import JAM1, RastPortRegistry

# --- struct Screen (classic, pre-RasInfo ViewPort embedded) ------------------
_SCREEN_SIZE = 0x200
_OFF_WIDTH = 0x0C
_OFF_HEIGHT = 0x0E
_OFF_FLAGS = 0x14
_OFF_TITLE = 0x18
_OFF_BAR_HEIGHT = 0x20
_OFF_WBOR_TOP = 0x25
_OFF_FONT = 0x2C
# NOTE: the ViewPort here is the pre-``RasInfo`` layout (0x24 bytes, AmigaOS
# 3.0 / NDK without the graphics rasterizer extension). ``iTidy`` is compiled
# against that layout, so its ``Screen.RastPort`` sits at 0x54 — NOT the 0x58
# the NDK 3.2 ``RasInfo``-bearing ViewPort would imply. Reading
# ``RastPort.TxHeight`` from the 3.2 offset yields garbage gadget geometry.
_OFF_VIEWPORT = 0x30
_OFF_RASTPORT = 0x54
_OFF_BITMAP = 0xB8

# --- struct ViewPort (pre-``RasInfo``: 36 bytes / 0x24) ----------------------
_VP_OFF_COLORMAP = _OFF_VIEWPORT + 0x04
_VP_OFF_DWIDTH = _OFF_VIEWPORT + 0x18
_VP_OFF_DHEIGHT = _OFF_VIEWPORT + 0x1A

# --- struct RastPort (classic, embedded at _OFF_RASTPORT) --------------------
_RP_OFF_FONT = _OFF_RASTPORT + 0x34
_RP_OFF_TXHEIGHT = _OFF_RASTPORT + 0x3A
_RP_OFF_TXWIDTH = _OFF_RASTPORT + 0x3C

# --- Window-owned RastPort (one per opened window) ---------------------------
# Classic Intuition gives each window its own drawing context (the window
# DrawInfo RPort); drawing for window A must not be replayed into window B's
# host projection, so the public screen's embedded RastPort is NOT shared as a
# window RPort. Each window gets its own RastPort block in 68k memory whose
# ``Window.RPort`` points at it. Offsets per the NDK 3.2 ``graphics/rastport.h``
# (the same offsets the screen-embedded RastPort uses: Font@0x34, TxHeight@0x3A,
# TxWidth@0x3C).
_WIN_RP_SIZE = 0x50  # covers every field the app dereferences (Font .. TxWidth)
_WRP_OFF_MASK = 0x18  # UBYTE Mask
_WRP_OFF_FGPEN = 0x19  # UBYTE FgPen
_WRP_OFF_BGPEN = 0x1A  # UBYTE BgPen
_WRP_OFF_AOLPEN = 0x1B  # UBYTE AOlPen
_WRP_OFF_DRMODE = 0x1C  # UBYTE DrawMode
_WRP_OFF_LINEPTRN = 0x22  # UWORD LinePtrn
_WRP_OFF_FONT = 0x34  # APTR TextFont *Font
_WRP_OFF_TXHEIGHT = 0x3A  # UWORD TxHeight
_WRP_OFF_TXWIDTH = 0x3C  # UWORD TxWidth

# --- struct BitMap (40 bytes) ------------------------------------------------
_BM_OFF_BYTESPERROW = _OFF_BITMAP + 0x00
_BM_OFF_ROWS = _OFF_BITMAP + 0x02
_BM_OFF_DEPTH = _OFF_BITMAP + 0x05

# --- struct DrawInfo (classic, DRI_VERSION 2 — AmigaOS 3.0/3.1) --------------
# GetScreenDrawInfo/FreeScreenDrawInfo (V37).  The target is NOT opaque about
# this block: it dereferences ``dri_Pens``, ``dri_Font`` and ``dri_Depth``.
# Layout matches the classic m68k ``struct DrawInfo`` (``DRI_VERSION_2``); the
# OS4 superset (``DRI_VERSION_3``) appends ``dri_Screen`` and reserved words
# that the 3.x binary does not read and must not be relied on.
#
#     UWORD   dri_Version;      @0x00  structure version (2)
#     UWORD   dri_NumPens;      @0x02  number of pens in the screen palette
#     UWORD   *dri_Pens;        @0x04  pointer to a UWORD pen-index array
#     TextFont *dri_Font;       @0x08  screen default font
#     UWORD   dri_Depth;        @0x0C  screen BitMap depth
#     UWORD   dri_Resolution.X; @0x0E
#     UWORD   dri_Resolution.Y; @0x10
#     ULONG   dri_Flags;        @0x12
#     Image   *dri_CheckMark;   @0x16
#     Image   *dri_AmigaKey;    @0x1A
#     -> 30 bytes (0x1E)
#
# ``dri_Pens`` is a *separately allocated* UWORD array in emulated memory.  Its
# entries are the classic screen semantic pens (``include_h/intuition/screens.h``)
# mapped to host palette indices; the app reads ``dri_Pens[TEXTPEN]`` etc. and
# uses the result as a RastPort pen.  It must outlive the DrawInfo and be freed
# by ``FreeScreenDrawInfo`` without touching the screen or window RastPorts.
_DI_VERSION = 2  # DRI_VERSION_2
_DI_SIZE = 0x1E
_DI_OFF_VERSION = 0x00  # UWORD dri_Version
_DI_OFF_NUMPENS = 0x02  # UWORD dri_NumPens
_DI_OFF_PENS = 0x04  # APTR UWORD *dri_Pens
_DI_OFF_FONT = 0x08  # APTR TextFont *dri_Font
_DI_OFF_DEPTH = 0x0C  # UWORD dri_Depth
_DI_OFF_RESX = 0x0E  # UWORD dri_Resolution.X
_DI_OFF_RESY = 0x10  # UWORD dri_Resolution.Y
_DI_OFF_FLAGS = 0x12  # ULONG dri_Flags
_DI_OFF_CHECKMARK = 0x16  # APTR Image *dri_CheckMark
_DI_OFF_AMIGAKEY = 0x1A  # APTR Image *dri_AmigaKey

# Classic screen semantic pen indices (include_h/intuition/screens.h, V37+).
_DETAILPEN = 0
_BLOCKPEN = 1
_TEXTPEN = 2
_SHINEPEN = 3
_SHADOWPEN = 4
_FILLPEN = 5
_FILLTEXTPEN = 6
_BACKGROUNDPEN = 7
_HIGHLIGHTTEXTPEN = 8
_BARDETAILPEN = 9
_BARBLOCKPEN = 10
_BARTRIMPEN = 11
_NUMDRIPENS = 0x0D  # 13

# The notional public Workbench screen is a documented approximation of the
# classic Workbench palette (mirrors ``CLASSIC_PEN_PALETTE`` in the host
# projection): 0=black, 1=white, 5=yellow, 15=light grey (the window
# background). Maps each semantic pen to the host palette index that renders it
# correctly: shine light (white), shadow dark (black), text dark (black),
# background = the window light grey, highlight text yellow.  ``dri_Pens[i]``
# holds the *palette index* for semantic pen i. The window light grey (pen 15)
# is also the host surface background (see ``qt_projection``) so the group-box
# title clear matches the window background and the white shine / black shadow
# / black text stay distinguishable from it.
_SEMANTIC_PEN_MAP = (
    1,  # DETAILPEN       -> white
    0,  # BLOCKPEN        -> black
    0,  # TEXTPEN         -> black
    1,  # SHINEPEN        -> white
    0,  # SHADOWPEN       -> black
    15,  # FILLPEN         -> window light grey
    0,  # FILLTEXTPEN     -> black
    15,  # BACKGROUNDPEN   -> window light grey
    5,  # HIGHLIGHTTEXTPEN -> highlight yellow
    1,  # BARDETAILPEN    -> white
    0,  # BARBLOCKPEN     -> black
    15,  # BARTRIMPEN      -> window light grey
)
_NUM_SCREEN_PENS = 16  # 4-bit public screen palette size

# --- struct Window (classic intuition) ---------------------------------------
# The app dereferences win->WScreen, win->RPort (TxHeight/Font) and the gadget
# list, so OpenWindowTagList must return a real, populated Window block.
_WIN_SIZE = 0x100
_WIN_OFF_NEXT = 0x00  # APTR struct Window *NextWindow
_WIN_OFF_LEFT = 0x04  # WORD LeftEdge
_WIN_OFF_TOP = 0x06  # WORD TopEdge
_WIN_OFF_WIDTH = 0x08  # WORD Width
_WIN_OFF_HEIGHT = 0x0A  # WORD Height
_WIN_OFF_FLAGS = 0x18  # ULONG Flags
_WIN_OFF_MENUSTRIP = 0x1C  # APTR struct Menu *MenuStrip
_WIN_OFF_TITLE = 0x20  # STRPTR Title
_WIN_OFF_WSCREEN = 0x2E  # APTR struct Screen *WScreen
_WIN_OFF_RPORT = 0x32  # APTR struct RastPort *RPort
_WIN_OFF_FIRSTGADGET = 0x3E  # APTR struct Gadget *FirstGadget
_WIN_OFF_IDCMP = 0x52  # ULONG IDCMPFlags
_WIN_OFF_USERPORT = 0x56  # APTR struct MsgPort *UserPort
_WIN_OFF_WINDOWPORT = 0x5A  # APTR struct MsgPort *WindowPort

# --- struct MsgPort (classic, exec) -------------------------------------------
_MSGPORT_SIZE = 0x14  # mp_NextMsg(0), mp_FirstMsg(4), mp_Task(8), mp_Flags(C), mp_Signals(10)

# WA_ window-open tags (WA_Dummy = 0x80000063).
_WA_LEFT = 0x80000064
_WA_TOP = 0x80000065
_WA_WIDTH = 0x80000066
_WA_HEIGHT = 0x80000067
_WA_IDCMP = 0x8000006A
_WA_GADGETS = 0x8000006C
_WA_TITLE = 0x8000006E
_WA_PUBSCREEN = 0x80000079

# --- struct IntuiText (classic pre-2.0 field names, GCC-aligned on m68k) -----
# The target builds IntuiText with the OLD field names (FrontPen/BackPen/
# DrawMode/LeftEdge/TopEdge/ITextFont/IText/NextText) — the shape the classic
# NDK intuition.h defines for the pre-2.0 layout. The target's ``vc +aos68k``
# compiler aligns members to their natural alignment (it does NOT pack), so the
# string pointer IText sits at 0x0C, not 0x0B. This was confirmed from the
# running target: the three group-box titles decode correctly only at 0x0C
# ("Folder", "Tidy options", "Tools"), with LeftEdge/TopEdge = 0 at 0x04/0x06,
# ITextFont = NULL at 0x08 and NextText = NULL at 0x10. See
# docs/apps/itidy/compatibility-notes.md (IntuiText ABI).
_IT_OFF_FRONT = 0x00  # UBYTE FrontPen
_IT_OFF_BACK = 0x01  # UBYTE BackPen
_IT_OFF_DRMODE = 0x02  # UBYTE DrawMode
# 0x03 is alignment padding (uninitialised stack in the target)
_IT_OFF_LEFT = 0x04  # WORD LeftEdge
_IT_OFF_TOP = 0x06  # WORD TopEdge
# 0x08 is alignment padding before the pointer members
_IT_OFF_FONT = 0x08  # APTR struct TextAttr *ITextFont
_IT_OFF_TEXT = 0x0C  # STRPTR IText (the string pointer)
_IT_OFF_NEXT = 0x10  # APTR struct IntuiText *NextText

# Intuition window tags (WA_*) the target uses with SetWindowPointerA. The
# target's NDK defines TAG_USER as the high bit (1 << 31), so WA_Dummy =
# (1 << 31) + 99 = 0x80000063 and WA_BusyPointer = WA_Dummy + 0x35. This is the
# encoding the running binary uses (the app's .i interface expands WA_BusyPointer
# to (1 << 31) + 99 + 0x35).
_WA_DUMMY = (1 << 31) + 99  # WA_ tag base (TAG_USER + 99)
_WA_LEFT = _WA_DUMMY + 0x01  # new window left edge
_WA_TOP = _WA_DUMMY + 0x02  # new window top edge
_WA_BUSY_POINTER = _WA_DUMMY + 0x35  # WA_BusyPointer (BOOL): busy cursor on/off

# Char-width sanity bounds for the fixed-pitch disk font (Topaz) the repo
# installs. A RastPort TxWidth read outside this range is an unpopulated or
# mis-offset RastPort and falls back to the Topaz baseline rather than a
# garbage width (same policy as graphics.library).
_FALLBACK_CHAR_WIDTH = 6
_MAX_CHAR_WIDTH = 32


class IntuitionLibrary(BaseLibrary):
    """Real public-screen state for the Workbench screen the app locks."""

    def __init__(self) -> None:
        super().__init__()
        self._screen_addr: int | None = None
        self._screen_locks = 0
        self._draw_infos: dict[int, tuple[Any, Any]] = {}
        # addr -> (Window, UserPort, WindowPort) Memory blocks.
        self._windows: dict[int, tuple] = {}
        # Fallback RastPort op log for unit tests; the launcher installs a
        # run-wide shared registry on the context (see _registry).
        self.rastports = RastPortRegistry()
        # Ordered record of IntuiTextLength measurements: the app uses these
        # widths to centre group-box titles, so a probe can see what it measured.
        self.itext_measures: list[dict[str, Any]] = []
        # Ordered record of SetWindowPointerA requests (the app toggles the busy
        # pointer around listview resorting): a host-side op for the future
        # renderer rather than a silent no-op.
        self.set_window_pointer_ops: list[dict[str, Any]] = []

    def get_version(self) -> int:
        """Report a plausible baseline library version for Workbench 3.x startup."""
        return 39

    # -- helpers --------------------------------------------------------------
    def _ensure_screen(self, ctx) -> int:
        """Allocate (once) and fill a well-formed public Screen; return its address."""
        if self._screen_addr is not None:
            return self._screen_addr

        alloc = ctx.alloc
        mem = ctx.mem
        addr = alloc.alloc_memory(_SCREEN_SIZE, label="Screen.Workbench").addr

        # Title string.
        title = alloc.alloc_cstr("Workbench", label="Screen.Title").addr
        # Screen default font (TextAttr: TaName[31], TaFlags@31, TaHeight@32, TaWidth@33).
        font = alloc.alloc_memory(40, label="Screen.Font").addr
        name = b"Topaz"
        for i, ch in enumerate(name):
            mem.w8(font + i, ch)
        mem.w8(font + len(name), 0)  # terminate TaName
        mem.w8(font + 31, 0)  # TaFlags
        mem.w8(font + 32, 8)  # TaHeight
        mem.w8(font + 33, 6)  # TaWidth
        # RastPort font handle: a distinct non-NULL allocation (TextFont stand-in).
        rp_font = alloc.alloc_memory(64, label="Screen.RP.Font").addr

        mem.w16(addr + _OFF_WIDTH, 320)
        mem.w16(addr + _OFF_HEIGHT, 200)
        mem.w16(addr + _OFF_FLAGS, 0)
        mem.w32(addr + _OFF_TITLE, title)
        mem.w8(addr + _OFF_BAR_HEIGHT, 20)
        mem.w8(addr + _OFF_WBOR_TOP, 0)
        mem.w32(addr + _OFF_FONT, font)

        # ViewPort: a plausible 320x200 single-plane display.
        mem.w32(addr + _VP_OFF_COLORMAP, 0)
        mem.w16(addr + _VP_OFF_DWIDTH, 320)
        mem.w16(addr + _VP_OFF_DHEIGHT, 200)

        # RastPort: valid font + text metrics so downstream SetFont/measure work.
        mem.w32(addr + _RP_OFF_FONT, rp_font)
        mem.w16(addr + _RP_OFF_TXHEIGHT, 8)
        mem.w16(addr + _RP_OFF_TXWIDTH, 6)

        # BitMap: 320 px wide, 1 plane, 200 rows (1 byte/row per plane).
        mem.w16(addr + _BM_OFF_BYTESPERROW, 1)
        mem.w16(addr + _BM_OFF_ROWS, 200)
        mem.w8(addr + _BM_OFF_DEPTH, 1)

        self._screen_addr = addr
        return addr

    # -- Intuition.library entry points --------------------------------------
    def LockPubScreen(self, ctx, name):
        """Lock the public (Workbench) screen and return a real Screen pointer."""
        addr = self._ensure_screen(ctx)
        self._screen_locks += 1
        return addr

    def UnlockPubScreen(self, ctx, name, screen):
        """Release a previously locked public screen."""
        if self._screen_locks > 0:
            self._screen_locks -= 1
        return None

    def GetScreenDrawInfo(self, ctx, screen):
        """Return a screen-derived ``DrawInfo`` (the screen's drawing context).

        ``DrawInfo`` is *not* opaque to the target: ``iTidy`` reads
        ``dri_Pens[TEXTPEN]``, ``dri_Pens[BACKGROUNDPEN]`` and friends to pick
        RastPort pens, and reads ``dri_Font`` / ``dri_Depth`` for metrics.  We
        therefore build a genuine classic (``DRI_VERSION_2``) block:

        * ``dri_Pens`` points at a *separately allocated* UWORD array in
          emulated memory holding the screen's semantic pen indices (mapped to
          the host Workbench palette approximation).  It is owned by this
          DrawInfo and released by ``FreeScreenDrawInfo``.
        * ``dri_Font`` / ``dri_Depth`` / resolution are copied from the real
          locked screen so the values are screen-derived, not stub constants.

        Every allocation is tracked so ``FreeScreenDrawInfo`` releases exactly
        the DrawInfo-owned memory (block + pen array) and nothing that belongs
        to the screen or a window RastPort.
        """
        if not screen:
            return 0
        alloc = ctx.alloc
        mem = ctx.mem

        # Separately allocated pen-index array (owned by this DrawInfo).
        pens = alloc.alloc_memory(_NUM_SCREEN_PENS * 2, label="Intuition.DrawInfo.Pens")
        for i in range(_NUM_SCREEN_PENS):
            idx = _SEMANTIC_PEN_MAP[i] if i < len(_SEMANTIC_PEN_MAP) else i
            mem.w16(pens.addr + i * 2, idx)

        di = alloc.alloc_memory(_DI_SIZE, label="Intuition.DrawInfo")
        addr = di.addr
        mem.w16(addr + _DI_OFF_VERSION, _DI_VERSION)
        mem.w16(addr + _DI_OFF_NUMPENS, _NUM_SCREEN_PENS)
        mem.w32(addr + _DI_OFF_PENS, pens.addr)
        mem.w32(addr + _DI_OFF_FONT, mem.r32(screen + _OFF_FONT))
        mem.w16(addr + _DI_OFF_DEPTH, mem.r8(screen + _BM_OFF_DEPTH) & 0xFF)
        mem.w16(addr + _DI_OFF_RESX, mem.r16(screen + _OFF_WIDTH))
        mem.w16(addr + _DI_OFF_RESY, mem.r16(screen + _OFF_HEIGHT))
        mem.w32(addr + _DI_OFF_FLAGS, 0)
        mem.w32(addr + _DI_OFF_CHECKMARK, 0)
        mem.w32(addr + _DI_OFF_AMIGAKEY, 0)
        # Track the DrawInfo block *and* its owned pen array so freeing is
        # exact.  The pen array is DrawInfo-owned; the screen font/BitMap it
        # references are NOT freed here.
        self._draw_infos[addr] = (di, pens)
        return addr

    def FreeScreenDrawInfo(self, ctx, screen, draw_info):
        """Release a ``DrawInfo`` previously returned by ``GetScreenDrawInfo``.

        Frees the DrawInfo block *and* its separately allocated ``dri_Pens``
        array.  Does not touch the screen's RastPort, its font, its BitMap, or
        any window RastPort.
        """
        if not draw_info:
            return None
        entry = self._draw_infos.pop(draw_info, None)
        if entry is not None:
            di, pens = entry
            ctx.alloc.free_memory(di)
            ctx.alloc.free_memory(pens)
        return None

    def OpenWindowTagList(self, ctx, newWindow, tagList):
        """Open a real window on the (public) screen from a tag list.

        Parses the WA_ tags into a genuine ``struct Window``: geometry, title,
        gadget list and IDCMP flags, plus a live ``WScreen`` / ``RPort`` so the
        app's later reads (``win->RPort->TxHeight``, ``win->WScreen``) hit valid
        memory instead of a fake constant.
        """
        alloc = ctx.alloc
        mem = ctx.mem
        left = top = width = height = 0
        title = gadgets = idcmp = 0
        screen = 0
        if tagList:
            off = 0
            for _ in range(0x100):  # bounded: max 256 tags
                item = mem.r32(tagList + off)
                data = mem.r32(tagList + off + 4)
                off += 8
                if item == 0:  # TAG_END
                    break
                if item == _WA_LEFT:
                    left = data
                elif item == _WA_TOP:
                    top = data
                elif item == _WA_WIDTH:
                    width = data
                elif item == _WA_HEIGHT:
                    height = data
                elif item == _WA_TITLE:
                    title = data
                elif item == _WA_GADGETS:
                    gadgets = data
                elif item == _WA_IDCMP:
                    idcmp = data
                elif item == _WA_PUBSCREEN:
                    screen = data
        if not screen:
            screen = self._screen_addr or self._ensure_screen(ctx)
        win = alloc.alloc_memory(_WIN_SIZE, label="Intuition.Window")
        addr = win.addr
        mem.w16(addr + _WIN_OFF_LEFT, left & 0xFFFF)
        mem.w16(addr + _WIN_OFF_TOP, top & 0xFFFF)
        mem.w16(addr + _WIN_OFF_WIDTH, width & 0xFFFF)
        mem.w16(addr + _WIN_OFF_HEIGHT, height & 0xFFFF)
        mem.w32(addr + _WIN_OFF_TITLE, title)
        mem.w32(addr + _WIN_OFF_WSCREEN, screen)
        # Window-owned drawing target: its own RastPort block (NOT the public
        # screen's embedded RastPort) so two windows' drawing streams cannot be
        # mixed or replayed into each other's host projections.
        win_rp = self._create_window_rport(ctx, screen)
        mem.w32(addr + _WIN_OFF_RPORT, win_rp.addr)
        # Register the window's own drawing state in the host RastPort model up
        # front with the window's initial pens and draw mode (the screen's text
        # and background pens, JAM1) so the op stream is isolated per window from
        # open time and starts in the same state the emulated RastPort is in.
        win_state = self._registry(ctx).get_or_create(win_rp.addr)
        win_state.apen = _SEMANTIC_PEN_MAP[_TEXTPEN]
        win_state.bpen = _SEMANTIC_PEN_MAP[_BACKGROUNDPEN]
        win_state.draw_mode = JAM1
        mem.w32(addr + _WIN_OFF_FIRSTGADGET, gadgets)
        mem.w32(addr + _WIN_OFF_IDCMP, idcmp)
        # A real window has Intuition message ports: the app's event loop does
        # WaitPort(win->UserPort) then GT_GetIMsg(win->UserPort). Register
        # genuine MsgPorts (in the same address space) so WaitPort finds valid
        # ports rather than NULL. Track them for CloseWindow to release.
        user_port = self._register_window_port(ctx, "Intuition.UserPort")
        window_port = self._register_window_port(ctx, "Intuition.WindowPort")
        mem.w32(addr + _WIN_OFF_USERPORT, user_port.addr)
        mem.w32(addr + _WIN_OFF_WINDOWPORT, window_port.addr)
        # (Window, UserPort, WindowPort, WindowRPort) blocks, all freed on
        # CloseWindow (the RPort block carries the window-owned drawing state).
        self._windows[addr] = (win, user_port, window_port, win_rp)
        title_text = self._read_cstr(ctx, title) if title else ""
        # Host event bridge hook: register the window (with its real ports
        # and IDCMP flags) so scheduled test/Qt events can be delivered to
        # the UserPort before the app's first WaitPort. No-op without a
        # bridge (plain probes).
        bridge = getattr(ctx, "event_bridge", None)
        if bridge is not None:
            bridge.on_window_opened(ctx, addr, user_port.addr, window_port.addr, idcmp, title_text)
        # Host window projection hook: express the window-open intent through
        # the projection boundary (no Qt import here — OpenWindowIntent is a
        # pure data type). The projection decides whether to create a real
        # host top-level window (app-facing) or keep a helper/backdrop window
        # internal. No-op for plain (non-GUI) probes.
        projection = getattr(ctx, "host_projection", None)
        if projection is not None:
            projection.open_window(
                OpenWindowIntent(
                    window_addr=addr,
                    title=title_text,
                    left=self._s16(left),
                    top=self._s16(top),
                    width=width & 0xFFFF,
                    height=height & 0xFFFF,
                    rport_addr=mem.r32(addr + _WIN_OFF_RPORT),
                    idcmp=idcmp,
                    has_menu_strip=False,
                )
            )
        return addr

    def _create_window_rport(self, ctx, screen: int):
        """Allocate and initialise the window-owned RastPort block.

        The window's drawing target inherits the public screen's default font
        and text metrics — an *explicit copy at open time* (the classic window
        DrawInfo draws in the screen's default font unless the app changes it),
        not a shared mutable reference, so later screen-RPort changes cannot
        leak into an already-open window.

        Pens and draw mode are initialised the way Intuition sets up a window's
        RastPort at open time, *not* the bare ``InitRastPort`` reset:

        * ``FgPen`` is the screen's text pen (``dri_Pens[TEXTPEN]``) and
          ``BgPen`` the screen's background pen (``dri_Pens[BACKGROUNDPEN]``).
          A freshly opened window therefore starts with dark text on the window
          background, matching the classic Workbench look.
        * ``DrawMode`` is ``JAM1`` (the "jam FgPen" mode).  The target's group
          box drawing relies on this: it calls ``SetAPen`` and then ``Draw`` /
          ``RectFill`` expecting the *FgPen* to be used (shine/shadow frame and
          the title clear), and only later switches a specific box to ``JAM2``
          via ``SetDrMd`` (where it also sets the BgPen it wants).  Initialising
          to ``JAM2`` would make the group-box frame and title clear use the
          BgPen instead of the pens the app explicitly selected — the exact
          "black bar" symptom we are fixing.
        """
        alloc = ctx.alloc
        mem = ctx.mem
        rp = alloc.alloc_memory(_WIN_RP_SIZE, label="Intuition.WindowRPort")
        mem.w8(rp.addr + _WRP_OFF_MASK, 0xFF)
        mem.w8(rp.addr + _WRP_OFF_FGPEN, _SEMANTIC_PEN_MAP[_TEXTPEN])
        mem.w8(rp.addr + _WRP_OFF_BGPEN, _SEMANTIC_PEN_MAP[_BACKGROUNDPEN])
        mem.w8(rp.addr + _WRP_OFF_AOLPEN, 0xFF)
        mem.w8(rp.addr + _WRP_OFF_DRMODE, JAM1)
        mem.w16(rp.addr + _WRP_OFF_LINEPTRN, 0xFFFF)
        mem.w32(rp.addr + _WRP_OFF_FONT, mem.r32(screen + _RP_OFF_FONT))
        mem.w16(rp.addr + _WRP_OFF_TXHEIGHT, mem.r16(screen + _RP_OFF_TXHEIGHT))
        mem.w16(rp.addr + _WRP_OFF_TXWIDTH, mem.r16(screen + _RP_OFF_TXWIDTH))
        return rp

    @staticmethod
    def _s16(value: int) -> int:
        """Interpret a 16-bit Amiga coordinate as signed (Left/Top may be < 0)."""

        value &= 0xFFFF
        return value - 0x10000 if value >= 0x8000 else value

    @staticmethod
    def _read_cstr(ctx, ptr, max_len=128) -> str:
        """Read a bounded NUL-terminated C string from 68k memory."""
        mem = ctx.mem
        out = bytearray()
        for i in range(max_len):
            byte = mem.r8(ptr + i)
            if byte == 0:
                break
            out.append(byte)
        return out.decode("latin-1")

    # -- IntuiText (classic pre-2.0 field layout) ----------------------------
    def _registry(self, ctx):
        """The host-side RastPort op log for this run.

        Uses the launcher's run-wide shared registry (``ctx.rastports``) when
        present so graphics (Text) and intuition (PrintIText) draw into one
        unified per-RastPort op log; falls back to this library's own registry
        in unit tests where no shared registry is attached to the context.
        """
        return getattr(ctx, "rastports", None) or self.rastports

    @staticmethod
    def _read_u32(ctx, addr: int) -> int:
        """Read a 32-bit big-endian pointer from 68k memory (0 if unreadable)."""
        mem = getattr(ctx, "mem", None)
        if mem is None or not addr:
            return 0
        try:
            return mem.r32(addr)
        except Exception:
            return 0

    @staticmethod
    def _read_u8(ctx, addr: int) -> int:
        """Read a byte from 68k memory (0 if unreadable)."""
        mem = getattr(ctx, "mem", None)
        if mem is None or not addr:
            return 0
        try:
            return mem.r8(addr)
        except Exception:
            return 0

    def _read_itext_string_ptr(self, ctx, itext: int) -> int:
        """The IntuiText's string pointer (``IText`` field, at 0x0C)."""
        return self._read_u32(ctx, itext + _IT_OFF_TEXT)

    def _read_itext_front_pen(self, ctx, itext: int) -> int:
        """The IntuiText's ``FrontPen`` field (at 0x00)."""
        return self._read_u8(ctx, itext + _IT_OFF_FRONT)

    def _count_string_chars(self, ctx, ptr: int) -> int:
        """Number of characters in the emulated C string at ``ptr`` (to NUL)."""
        mem = getattr(ctx, "mem", None)
        if mem is None or not ptr:
            return 0
        count = 0
        for i in range(256):  # bounded; a title/label is short
            byte = mem.r8(ptr + i)
            if byte == 0:
                break
            count += 1
        return count

    def _read_string(self, ctx, ptr: int) -> str:
        """Best-effort decode of the emulated C string at ``ptr`` (for op records)."""
        mem = getattr(ctx, "mem", None)
        if mem is None or not ptr:
            return ""
        out = bytearray()
        for i in range(256):
            byte = mem.r8(ptr + i)
            if byte == 0:
                break
            out.append(byte)
        return out.decode("latin-1")

    def _rp_font_char_width(self, ctx, rp: int) -> int:
        """Character width (pixels) of a RastPort's font, from 68k memory.

        Reads ``RastPort.TxWidth`` at the classic pre-``RasInfo`` offset; a read
        that is not a plausible fixed-pitch width falls back to the Topaz
        baseline (same policy as graphics.library).
        """
        mem = getattr(ctx, "mem", None)
        if mem is not None and rp:
            try:
                width = mem.r16(rp + 0x3C)
            except Exception:
                width = 0
            if 0 < width <= _MAX_CHAR_WIDTH:
                return width
        return _FALLBACK_CHAR_WIDTH

    def _screen_font_char_width(self, ctx) -> int:
        """Character width of the screen's default font (Topaz baseline).

        ``IntuiTextLength`` takes no RastPort; with the target's ``ITextFont``
        NULL the width comes from the screen font. Reads the screen RastPort's
        TxWidth (written by ``_ensure_screen``) and falls back to Topaz.
        """
        mem = getattr(ctx, "mem", None)
        if mem is not None and self._screen_addr:
            try:
                width = mem.r16(self._screen_addr + _RP_OFF_TXWIDTH)
            except Exception:
                width = 0
            if 0 < width <= _MAX_CHAR_WIDTH:
                return width
        return _FALLBACK_CHAR_WIDTH

    def IntuiTextLength(self, ctx, iText):
        """intuition.library IntuiTextLength(iText)(a0): measure an IntuiText.

        Return the pixel width of the IntuiText's string in its font. The target
        builds the IntuiText with the classic pre-2.0 field names (see the
        ``_IT_*`` constants), so the string pointer (``IText``) is read from 68k
        memory at 0x0C and the string is read to NUL. The width is
        ``count * TxWidth`` using the fixed-pitch screen font (Topaz), matching
        graphics.library TextLength. The app uses this width to centre group-box
        titles; the measurement is recorded on ``self.itext_measures`` so a
        probe can see what the app measured (and what the string was).
        """
        string_ptr = self._read_itext_string_ptr(ctx, iText)
        count = self._count_string_chars(ctx, string_ptr)
        char_width = self._screen_font_char_width(ctx)
        width = count * char_width
        self.itext_measures.append(
            {
                "itext": iText,
                "string": string_ptr,
                "count": count,
                "width": width,
                "text": self._read_string(ctx, string_ptr),
            }
        )
        return width

    def PrintIText(self, ctx, rp, iText, left, top):
        """intuition.library PrintIText(rp, iText, left, top)(a0/a1, d0, d1).

        Draw the IntuiText's string in its font at ``(left, top)`` on ``rp``.
        The draw counterpart of ``IntuiTextLength``. Reads the string pointer
        and front pen from the (classic pre-2.0) IntuiText and records the draw
        on the host-side RastPort op log — explicit position, string pointer,
        decoded content, width, front pen, and font — so a future renderer can
        replay the group-box / requester title. There is no host window yet, so
        this record is what makes the call meaningful rather than a silent
        no-op.
        """
        string_ptr = self._read_itext_string_ptr(ctx, iText)
        count = self._count_string_chars(ctx, string_ptr)
        char_width = self._rp_font_char_width(ctx, rp)
        width = count * char_width
        front_pen = self._read_itext_front_pen(ctx, iText)
        text = self._read_string(ctx, string_ptr)
        self._registry(ctx).get_or_create(rp).print_itext(
            string=string_ptr,
            count=count,
            width=width,
            x=left,
            y=top,
            front_pen=front_pen,
            text=text,
        )
        return None

    @staticmethod
    def _get_port_mgr(ctx):
        """Reach the exec PortManager through the exec VLib's impl.

        The ``VLibManager.exec_lib`` reference is the exec *struct*; the
        queue-backed ``PortManager`` lives on the exec *impl* (lib/ExecLibrary),
        which is attached to the exec VLib as ``impl``.
        """
        vlib = ctx.vlib_mgr.get_vlib_by_name("exec.library")
        if vlib is None or vlib.impl is None:
            raise RuntimeError("Intuition: exec.library impl not available")
        return vlib.impl.port_mgr

    def _register_window_port(self, ctx, label):
        """Allocate a real MsgPort and register it with the exec PortManager.

        The Vamos ``WaitPort`` implementation requires the port to be a known
        port (``port_mgr.has_port``) before it can inspect the queue; a NULL or
        unregistered port is a hard internal error. Registering a genuine
        queue-backed port matches what OpenWindow produces on real AmigaOS.
        """
        port_mgr = self._get_port_mgr(ctx)
        mem = ctx.alloc.alloc_memory(_MSGPORT_SIZE, label=label)
        m = ctx.mem
        m.w32(mem.addr + 0x00, 0)  # mp_NextMsg
        m.w32(mem.addr + 0x04, 0)  # mp_FirstMsg
        m.w32(mem.addr + 0x08, 0)  # mp_Task
        m.w32(mem.addr + 0x0C, 0)  # mp_Flags
        m.w32(mem.addr + 0x10, 0)  # mp_Signals
        port_mgr.register_port(mem.addr)
        return mem

    def SetMenuStrip(self, ctx, window, menu):
        """Attach (or detach, with a NULL menu) a menu strip to a window."""
        if not window:
            return None
        mem = ctx.mem
        mem.w32(window + _WIN_OFF_MENUSTRIP, menu)
        return None

    def SetDefaultPubScreen(self, ctx, name):
        """Stub for SetDefaultPubScreen - returns success."""
        return 0

    def EraseImage(self, ctx, rp, image, leftOffset, topOffset):
        """Stub for EraseImage - clears a rectangle in the render pattern."""
        return None

    def OpenWindow(self, ctx, newWindow):
        """Stub for the classic OpenWindow entry point; iTidy uses OpenWindowTagList."""
        return None

    def CloseWindow(self, ctx, window):
        """Release a window opened via OpenWindowTagList and its owned state.

        Frees the window block, its message ports, and its window-owned RastPort
        block, and removes *only this window's* host drawing state from the
        run-wide registry so a closed window's stream cannot outlive the window
        or be replayed into a later projection.
        """
        rec = self._windows.pop(window, None)
        if rec is None:
            return None
        win, user_port, window_port, win_rp = rec
        port_mgr = self._get_port_mgr(ctx)
        for port_mem in (user_port, window_port):
            port_mgr.unregister_port(port_mem.addr)
            ctx.alloc.free_memory(port_mem)
        self._registry(ctx).remove(win_rp.addr)
        ctx.alloc.free_memory(win_rp)
        ctx.alloc.free_memory(win)
        # Host window projection hook: remove the host projection for this
        # window (idempotent; no Qt import here). No-op for plain probes.
        projection = getattr(ctx, "host_projection", None)
        if projection is not None:
            projection.close_window(window)
        return None

    @staticmethod
    def _parse_window_pointer_tags(mem, taglist: int) -> tuple[int | None, tuple[int, int] | None]:
        """Walk a ``TagItem`` list for ``WA_BusyPointer`` / ``WA_Left`` / ``WA_Top``.

        Returns ``(busy_pointer_or_None, (left, top)_or_None)``. The app uses
        only ``WA_BusyPointer`` (TRUE/FALSE); the position tags are parsed for a
        reusable implementation. Unknown tags are ignored.
        """
        busy: int | None = None
        new_pos: tuple[int, int] | None = None
        left: int | None = None
        top: int | None = None
        if not taglist:
            return busy, new_pos
        offset = 0
        for _ in range(0x200):  # bounded: TAG_DONE always terminates
            tag = mem.r32(taglist + offset)
            if tag == 0:  # TAG_DONE
                break
            data = mem.r32(taglist + offset + 4)
            if tag == _WA_BUSY_POINTER:
                busy = bool(data)
            elif tag == _WA_LEFT:
                left = data
            elif tag == _WA_TOP:
                top = data
            offset += 8
        if left is not None and top is not None:
            new_pos = (left, top)
        return busy, new_pos

    def SetWindowPointerA(self, ctx, win, taglist):
        """intuition.library ``SetWindowPointerA(win, taglist)``.

        The app uses this to toggle the window's busy pointer (``WA_BusyPointer``,
        TRUE/FALSE) around listview resorting. There is no host window yet, so
        this records the request (window address, busy-pointer state, and any new
        position) as a host-side op for the future renderer, rather than silently
        dropping it. Returns None (VOID).
        """
        mem = getattr(ctx, "mem", None)
        busy: int | None = None
        new_pos: tuple[int, int] | None = None
        if mem is not None:
            busy, new_pos = self._parse_window_pointer_tags(mem, taglist)
        self.set_window_pointer_ops.append({"win": win, "busy_pointer": busy, "new_pos": new_pos})
        return None
