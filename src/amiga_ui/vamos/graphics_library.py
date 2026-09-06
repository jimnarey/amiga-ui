"""Repo-owned ``graphics.library`` implementation for vamos.

Every method takes ``ctx`` first (after ``self``) and its remaining parameters
match the pinned ``graphics.library`` ``.fd`` entry exactly (name + count), so
``amitools``' ``LibImplScanner`` wires them into the library jump table instead
of dropping them as ``UNKNOWN`` traps. See ``docs/runtime/writing-a-library-impl.md``.

Drawing calls (``SetFont``/``SetAPen``/``SetBPen``/``SetDrMd``/``SetABPenDrMd``/
``SetMaxPen``/``SetOutlinePen``/``Move``/``AreaMove``/``Draw``/``AreaDraw``/
``RectFill``/``InitRastPort``) update a host-side :class:`RastPortState` (see
``rastport_state.py``): the drawing state the app configured and the ordered
sequence of drawing operations it issued. There is no host window yet, so this
record — not a silent no-op — is what makes the calls meaningful.

``TextLength`` is a real text-metrics entry point: it measures the pixel width
of the requested characters using the RastPort's current font (read from 68k
memory) and records the measurement, rather than returning a fake zero.

Other frontier functions record their invocation in ``call_log`` rather than
faking a success, and return honest defaults.
"""

from __future__ import annotations

from typing import Any

from .base_library import BaseLibrary
from .rastport_state import RastPortRegistry

# ``RastPort.TxWidth`` — the pixel width of the font's characters — at the
# classic pre-``RasInfo`` offset the target binary was compiled against. This
# matches ``intuition_library._RP_OFF_TXWIDTH`` (``Screen+0x54`` RastPort +
# ``0x3C``), where the Workbench screen font's fixed width is written.
_RP_TXWIDTH_OFFSET = 0x3C
# Fixed-pitch character width of the Topaz 8x6 screen font the repo installs —
# used only as a fallback when the RastPort does not carry a usable width.
_FALLBACK_CHAR_WIDTH = 6
# A plausible fixed-pitch disk-font character width; anything outside this band
# means the read did not land on ``TxWidth`` and we fall back instead.
_MAX_CHAR_WIDTH = 32


class GraphicsLibrary(BaseLibrary):
    """Project-owned ``graphics.library`` with a real RastPort drawing model."""

    def __init__(self) -> None:
        super().__init__()
        # Host-side drawing state, keyed by emulated RastPort pointer.
        self.rastports = RastPortRegistry()
        # Ordered record of non-drawing graphics calls (frontier functions the
        # app has not driven yet): {"func": name, "args": {...}}.
        self.call_log: list[dict[str, Any]] = []

    def get_version(self) -> int:
        """Report a plausible baseline library version for Workbench 3.x startup."""
        # Use the same baseline as icon.library for consistency.
        return 40

    # -- helpers -------------------------------------------------------------
    def _log_call(self, name: str, **args: Any) -> None:
        self.call_log.append({"func": name, "args": args})

    def _rp(self, rp: int):
        """The host-side drawing state for an emulated RastPort pointer."""
        return self.rastports.get_or_create(rp)

    # -- RastPort drawing state (recorded, not no-op'ed) --------------------
    def InitRastPort(self, ctx, rp):
        """graphics.library InitRastPort(rp)(a1): reset a RastPort's state."""
        self._rp(rp).init()
        return None

    def SetFont(self, ctx, rp, textFont):
        """graphics.library SetFont(rp, textFont)(a1, a0): set the RastPort font.

        Records the font on the host-side RastPort state and returns the
        previous font pointer, per the classic contract.
        """
        return self._rp(rp).set_font(textFont)

    def SetAPen(self, ctx, rp, pen):
        """graphics.library SetAPen(rp, pen)(a1, d0): set the active pen."""
        self._rp(rp).set_apen(pen)
        return None

    def SetBPen(self, ctx, rp, pen):
        """graphics.library SetBPen(rp, pen)(a1, d0): set the background pen."""
        self._rp(rp).set_bpen(pen)
        return None

    def SetDrMd(self, ctx, rp, drawMode):
        """graphics.library SetDrMd(rp, drawMode)(a1, d0): set the draw mode."""
        self._rp(rp).set_dr_md(drawMode)
        return None

    def SetABPenDrMd(self, ctx, rp, apen, bpen, drawmode):
        """graphics.library SetABPenDrMd(rp, apen, bpen, drawmode)(a1, d0-d2)."""
        self._rp(rp).set_ab_pen_dr_md(apen, bpen, drawmode)
        return None

    def SetMaxPen(self, ctx, rp, maxpen):
        """graphics.library SetMaxPen(rp, maxpen)(a0, d0): returns prior max pen."""
        return self._rp(rp).set_max_pen(maxpen)

    def SetOutlinePen(self, ctx, rp, pen):
        """graphics.library SetOutlinePen(rp, pen)(a0, d0): returns prior pen."""
        return self._rp(rp).set_outline_pen(pen)

    def Move(self, ctx, rp, x, y):
        """graphics.library Move(rp, x, y)(a1, d0, d1): move the pen position."""
        self._rp(rp).move(x, y)
        return None

    def AreaMove(self, ctx, rp, x, y):
        """graphics.library AreaMove(rp, x, y)(a1, d0, d1): area move."""
        self._rp(rp).area_move(x, y)
        return None

    def Draw(self, ctx, rp, x, y):
        """graphics.library Draw(rp, x, y)(a1, d0, d1): draw a line to (x, y)."""
        self._rp(rp).draw(x, y)
        return None

    def AreaDraw(self, ctx, rp, x, y):
        """graphics.library AreaDraw(rp, x, y)(a1, d0, d1): area line to (x, y)."""
        self._rp(rp).area_draw(x, y)
        return None

    def RectFill(self, ctx, rp, xMin, yMin, xMax, yMax):
        """graphics.library RectFill(rp, xMin, yMin, xMax, yMax)(a1, d0-d3)."""
        self._rp(rp).rect_fill(xMin, yMin, xMax, yMax)
        return None

    # -- text metrics (measured from the RastPort font, not a stub) ----------
    def TextLength(self, ctx, rp, string, count):
        """graphics.library TextLength(rp, string, count)(a1, a0, d0).

        Return the pixel width of the first ``count`` characters of ``string``
        in the RastPort's current font. On classic AmigaOS the library sums the
        per-character widths from the font; for the fixed-pitch disk font this
        repo installs (Topaz) every glyph is ``RastPort.TxWidth`` wide, so the
        width is ``count * TxWidth``. The width is read from the RastPort in
        68k memory so the result reflects the font the app actually set, not a
        baked-in constant. The measurement is recorded on the host-side RastPort
        model so a future renderer/probe can see what was measured and how wide
        it was told the text was.
        """
        char_width = self._font_char_width(ctx, rp)
        length = count * char_width
        self._rp(rp).record_text_length(string=string, count=count, length=length)
        return length

    def _font_char_width(self, ctx, rp) -> int:
        """Character width (pixels) of the RastPort's font, from 68k memory.

        Reads ``RastPort.TxWidth`` at the classic pre-``RasInfo`` offset. A read
        that is not a plausible fixed-pitch width (an unpopulated or
        mis-offset RastPort) falls back to the Topaz baseline so the result
        stays sane rather than returning a garbage value.
        """
        mem = getattr(ctx, "mem", None)
        if mem is not None and rp:
            width = mem.r16(rp + _RP_TXWIDTH_OFFSET)
            if 0 < width <= _MAX_CHAR_WIDTH:
                return width
        return _FALLBACK_CHAR_WIDTH

    # -- ViewPort / colour (frontier: recorded, honest default) --------------
    def SetRGB32(self, ctx, vp, n, r, g, b):
        """graphics.library SetRGB32(vp, n, r, g, b)(a0, d0-d3)."""
        self._log_call("SetRGB32", vp=vp, n=n, r=r, g=g, b=b)
        return None

    def SetRGB32CM(self, ctx, cm, n, r, g, b):
        """graphics.library SetRGB32CM(cm, n, r, g, b)(a0, d0-d3)."""
        self._log_call("SetRGB32CM", cm=cm, n=n, r=r, g=g, b=b)
        return None

    def SetRGB4(self, ctx, vp, index, red, green, blue):
        """graphics.library SetRGB4(vp, index, red, green, blue)(a0, d0-d3)."""
        self._log_call("SetRGB4", vp=vp, index=index, red=red, green=green, blue=blue)
        return None

    def LoadRGB32(self, ctx, vp, table):
        """graphics.library LoadRGB32(vp, table)(a0, a1)."""
        self._log_call("LoadRGB32", vp=vp, table=table)
        return None

    def LoadRGB4(self, ctx, vp, colors, count):
        """graphics.library LoadRGB4(vp, colors, count)(a0, a1, d0)."""
        self._log_call("LoadRGB4", vp=vp, colors=colors, count=count)
        return None

    def GetVPModeID(self, ctx, vp):
        """graphics.library GetVPModeID(vp)(a0). No host display: report 0."""
        self._log_call("GetVPModeID", vp=vp)
        return 0

    # -- View / ViewPort construction (frontier) -----------------------------
    def InitVPort(self, ctx, vp):
        """graphics.library InitVPort(vp)(a0)."""
        self._log_call("InitVPort", vp=vp)
        return None

    def MakeVPort(self, ctx, view, vp):
        """graphics.library MakeVPort(view, vp)(a0, a1)."""
        self._log_call("MakeVPort", view=view, vp=vp)
        return None

    def InitView(self, ctx, view):
        """graphics.library InitView(view)(a1)."""
        self._log_call("InitView", view=view)
        return None

    # -- display info (frontier) ---------------------------------------------
    def FindDisplayInfo(self, ctx, displayID):
        """graphics.library FindDisplayInfo(displayID)(d0). No host display."""
        self._log_call("FindDisplayInfo", displayID=displayID)
        return 0

    def NextDisplayInfo(self, ctx, displayID):
        """graphics.library NextDisplayInfo(displayID)(d0)."""
        self._log_call("NextDisplayInfo", displayID=displayID)
        return 0

    def GetDisplayInfoData(self, ctx, handle, buf, size, tagID, displayID):
        """graphics.library GetDisplayInfoData(handle, buf, size, tagID, displayID)
        (a0, a1, d0, d1, d2). No host display: report no data written (0)."""
        self._log_call(
            "GetDisplayInfoData",
            handle=handle,
            buf=buf,
            size=size,
            tagID=tagID,
            displayID=displayID,
        )
        return 0

    def FreeDBufInfo(self, ctx, dbi):
        """graphics.library FreeDBufInfo(dbi)(a1)."""
        self._log_call("FreeDBufInfo", dbi=dbi)
        return None

    # -- BitMap (frontier) ----------------------------------------------------
    def AllocBitMap(self, ctx, sizex, sizey, depth, flags, friend_bitmap):
        """graphics.library AllocBitMap(sizex, sizey, depth, flags, friend_bitmap)
        (d0, d1, d2, d3, a0). No host BitMap allocation yet: honest failure (0)."""
        self._log_call(
            "AllocBitMap",
            sizex=sizex,
            sizey=sizey,
            depth=depth,
            flags=flags,
            friend_bitmap=friend_bitmap,
        )
        return 0

    def FreeBitMap(self, ctx, bm):
        """graphics.library FreeBitMap(bm)(a0)."""
        self._log_call("FreeBitMap", bm=bm)
        return None

    def BltBitMap(
        self,
        ctx,
        srcBitMap,
        xSrc,
        ySrc,
        destBitMap,
        xDest,
        yDest,
        xSize,
        ySize,
        minterm,
        mask,
        tempA,
    ):
        """graphics.library BltBitMap(...)(a0, d0-d7, a1, a2)."""
        self._log_call(
            "BltBitMap",
            srcBitMap=srcBitMap,
            xSrc=xSrc,
            ySrc=ySrc,
            destBitMap=destBitMap,
            xDest=xDest,
            yDest=yDest,
            xSize=xSize,
            ySize=ySize,
            minterm=minterm,
            mask=mask,
            tempA=tempA,
        )
        return None

    def BltClear(self, ctx, memBlock, byteCount, flags):
        """graphics.library BltClear(memBlock, byteCount, flags)(a1, d0, d1)."""
        self._log_call("BltClear", memBlock=memBlock, byteCount=byteCount, flags=flags)
        return None

    # -- RastPort attributes (frontier) ---------------------------------------
    def SetRPAttrsA(self, ctx, rp, tags):
        """graphics.library SetRPAttrsA(rp, tags)(a0, a1)."""
        self._log_call("SetRPAttrsA", rp=rp, tags=tags)
        return None

    def GetRPAttrsA(self, ctx, rp, tags):
        """graphics.library GetRPAttrsA(rp, tags)(a0, a1)."""
        self._log_call("GetRPAttrsA", rp=rp, tags=tags)
        return 0

    # -- pens on a ColorMap (frontier) ----------------------------------------
    def ObtainBestPenA(self, ctx, cm, r, g, b, tags):
        """graphics.library ObtainBestPenA(cm, r, g, b, tags)(a0, d1-d3, a1)."""
        self._log_call("ObtainBestPenA", cm=cm, r=r, g=g, b=b, tags=tags)
        return 0

    def ObtainPen(self, ctx, cm, n, r, g, b, f):
        """graphics.library ObtainPen(cm, n, r, g, b, f)(a0, d0-d4)."""
        self._log_call("ObtainPen", cm=cm, n=n, r=r, g=g, b=b, f=f)
        return 0

    def ReleasePen(self, ctx, cm, n):
        """graphics.library ReleasePen(cm, n)(a0, d0)."""
        self._log_call("ReleasePen", cm=cm, n=n)
        return None

    # -- fonts (frontier) ------------------------------------------------------
    def OpenFont(self, ctx, textAttr):
        """graphics.library OpenFont(textAttr)(a0). No host font: NULL (0)."""
        self._log_call("OpenFont", textAttr=textAttr)
        return 0

    def CloseFont(self, ctx, textFont):
        """graphics.library CloseFont(textFont)(a1)."""
        self._log_call("CloseFont", textFont=textFont)
        return None
