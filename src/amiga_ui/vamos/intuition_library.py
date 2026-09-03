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

# --- struct DrawInfo (private intuition drawing context) ---------------------
# GetScreenDrawInfo/FreeScreenDrawInfo (V37). The app treats the block as
# opaque (NULL-check + free), but we populate it from the real screen so it is
# a genuine, screen-derived value rather than a bare constant.
_DI_SIZE = 0x20
_DI_OFF_SCREEN = 0x00  # APTR struct Screen *
_DI_OFF_RASTPORT = 0x04  # APTR struct RastPort *
_DI_OFF_WIDTH = 0x08  # WORD screen width
_DI_OFF_HEIGHT = 0x0A  # WORD screen height
_DI_OFF_DEPTH = 0x0C  # UBYTE BitMap depth

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


class IntuitionLibrary(BaseLibrary):
    """Real public-screen state for the Workbench screen the app locks."""

    def __init__(self) -> None:
        super().__init__()
        self._screen_addr: int | None = None
        self._screen_locks = 0
        self._draw_infos: dict[int, object] = {}
        # addr -> (Window, UserPort, WindowPort) Memory blocks.
        self._windows: dict[int, tuple] = {}

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

        ``DrawInfo`` is a private intuition block that carries the RastPort and
        display metrics a drawing routine needs for the screen. The app uses it
        only as an opaque handle (NULL-check, then free), but we build it from
        the real locked screen so it is a genuine value, not a stub constant.
        """
        if not screen:
            return 0
        alloc = ctx.alloc
        mem = ctx.mem
        di = alloc.alloc_memory(_DI_SIZE, label="Intuition.DrawInfo")
        addr = di.addr
        mem.w32(addr + _DI_OFF_SCREEN, screen)
        mem.w32(addr + _DI_OFF_RASTPORT, screen + _OFF_RASTPORT)
        mem.w16(addr + _DI_OFF_WIDTH, mem.r16(screen + _OFF_WIDTH))
        mem.w16(addr + _DI_OFF_HEIGHT, mem.r16(screen + _OFF_HEIGHT))
        mem.w8(addr + _DI_OFF_DEPTH, mem.r8(screen + _BM_OFF_DEPTH))
        self._draw_infos[addr] = di
        return addr

    def FreeScreenDrawInfo(self, ctx, screen, draw_info):
        """Release a ``DrawInfo`` previously returned by ``GetScreenDrawInfo``."""
        if not draw_info:
            return None
        di = self._draw_infos.pop(draw_info, None)
        if di is not None:
            ctx.alloc.free_memory(di)
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
        mem.w32(addr + _WIN_OFF_RPORT, screen + _OFF_RASTPORT)
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
        # (Window, UserPort, WindowPort) Memory blocks, all freed on CloseWindow.
        self._windows[addr] = (win, user_port, window_port)
        return addr

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
        """Release a window opened via OpenWindowTagList and its message ports."""
        rec = self._windows.pop(window, None)
        if rec is None:
            return None
        win, user_port, window_port = rec
        port_mgr = self._get_port_mgr(ctx)
        for port_mem in (user_port, window_port):
            port_mgr.unregister_port(port_mem.addr)
            ctx.alloc.free_memory(port_mem)
        ctx.alloc.free_memory(win)
        return None
