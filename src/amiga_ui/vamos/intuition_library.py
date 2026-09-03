"""Repo-owned Intuition.library implementation.

Implements enough real host-side state for the Workbench public screen so the
target app receives a well-formed ``struct Screen`` instead of a fake constant.
The app dereferences ``screen->WBorTop``, ``screen->RastPort.TxHeight`` and the
embedded ``RastPort`` / ``ViewPort`` / ``BitMap``; returning an unallocated
constant made those reads land on stale memory and the visual-info gate failed.

Struct layout follows the AmigaOS-4-style ``struct Screen`` the binary was built
against (embedded classic ``RastPort`` and ``ViewPort``), see
``docs/platform/library-cards/intuition.library.md``.
"""

from __future__ import annotations

from .base_library import BaseLibrary

# --- struct Screen (AmigaOS-4-style, classic RastPort/ViewPort embedded) -----
_SCREEN_SIZE = 0x200
_OFF_WIDTH = 0x0C
_OFF_HEIGHT = 0x0E
_OFF_FLAGS = 0x14
_OFF_TITLE = 0x18
_OFF_BAR_HEIGHT = 0x20
_OFF_WBOR_TOP = 0x25
_OFF_FONT = 0x2C
_OFF_VIEWPORT = 0x30
_OFF_RASTPORT = 0x58
_OFF_BITMAP = 0xBC

# --- struct ViewPort (40 bytes / 0x28) ---------------------------------------
_VP_OFF_COLORMAP = _OFF_VIEWPORT + 0x04
_VP_OFF_DWIDTH = _OFF_VIEWPORT + 0x18
_VP_OFF_DHEIGHT = _OFF_VIEWPORT + 0x1A

# --- struct RastPort (classic, embedded at _OFF_RASTPORT) --------------------
_RP_OFF_FONT = _OFF_RASTPORT + 0x34
_RP_OFF_TXHEIGHT = _OFF_RASTPORT + 0x3A
_RP_OFF_TXWIDTH = _OFF_RASTPORT + 0x3C

# --- struct BitMap (40 bytes) ------------------------------------------------
_BM_OFF_BYTESPERROW = _OFF_BITMAP + 0x00
_BM_OFF_ROWS = _OFF_BITMAP + 0x02
_BM_OFF_DEPTH = _OFF_BITMAP + 0x05


class IntuitionLibrary(BaseLibrary):
    """Real public-screen state for the Workbench screen the app locks."""

    def __init__(self) -> None:
        super().__init__()
        self._screen_addr: int | None = None
        self._screen_locks = 0

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
        mem.w8(font + 31, 0)         # TaFlags
        mem.w8(font + 32, 8)         # TaHeight
        mem.w8(font + 33, 6)         # TaWidth
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

    def OpenWindowTagList(self, ctx, newWindow, tagList):
        """Stub for OpenWindowTagList - returns a default window pointer.

        iTidy calls OpenWindowTagList to create a window during GUI initialization.
        This stub returns a default window handle to allow further initialization.
        """
        return 0x20000

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
        """Stub for the classic CloseWindow entry point."""
        return None
