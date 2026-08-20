"""Repo-owned minimal ``graphics.library`` implementation for vamos."""

from __future__ import annotations

from amitools.vamos.libcore import LibImpl


class GraphicsLibrary(LibImpl):
    """Provide the first project-owned ``graphics.library`` implementation seam."""

    def get_version(self) -> int:
        """Report a plausible baseline library version for Workbench 3.x startup."""
        # Use the same baseline as icon.library for consistency.
        return 40

    def InitRastPort(self, rp):
        """Initialize a RastPort.

        Args:
            rp: RastPort pointer (a1 register)
        """
        return None

    def InitVPort(self, vp):
        """Initialize a ViewPort.

        Args:
            vp: ViewPort pointer (a0 register)
        """
        return None

    def MakeVPort(self, view, vp):
        """Create a ViewPort from a View.

        Args:
            view: View pointer (a0 register)
            vp: ViewPort pointer (a1 register)
        """
        return None

    def SetAPen(self, rp, pen):
        """Set the active pen in a RastPort.

        Args:
            rp: RastPort pointer (a1 register)
            pen: pen number (d0 register)
        """
        return None

    def SetBPen(self, rp, pen):
        """Set the background pen in a RastPort.

        Args:
            rp: RastPort pointer (a1 register)
            pen: pen number (d0 register)
        """
        return None

    def SetDrMd(self, rp, drawMode):
        """Set the draw mode in a RastPort.

        Args:
            rp: RastPort pointer (a1 register)
            drawMode: draw mode (d0 register)
        """
        return None

    def Move(self, rp, x, y):
        """Move the current position in a RastPort.

        Args:
            rp: RastPort pointer (a1 register)
            x: x coordinate (d0 register)
            y: y coordinate (d1 register)
        """
        return None

    def Draw(self, rp, x, y):
        """Draw a line from the current position in a RastPort.

        Args:
            rp: RastPort pointer (a1 register)
            x: x coordinate (d0 register)
            y: y coordinate (d1 register)
        """
        return None

    def AreaMove(self, rp, x, y):
        """Move the current position for area operations.

        Args:
            rp: RastPort pointer (a1 register)
            x: x coordinate (d0 register)
            y: y coordinate (d1 register)
        """
        return None

    def AreaDraw(self, rp, x, y):
        """Draw an area line.

        Args:
            rp: RastPort pointer (a1 register)
            x: x coordinate (d0 register)
            y: y coordinate (d1 register)
        """
        return None

    def SetRGB32(self, vp, n, r, g, b):
        """Set a RGB32 color in a ViewPort.

        Args:
            vp: ViewPort pointer (a0 register)
            n: color index (d0 register)
            r: red component (d1 register)
            g: green component (d2 register)
            b: blue component (d3 register)
        """
        return None

    def SetRGB32CM(self, cm, n, r, g, b):
        """Set a RGB32 color in a ColorMap.

        Args:
            cm: ColorMap pointer (a0 register)
            n: color index (d0 register)
            r: red component (d1 register)
            g: green component (d2 register)
            b: blue component (d3 register)
        """
        return None

    def SetMaxPen(self, rp, maxpen):
        """Set the maximum pen number.

        Args:
            rp: RastPort pointer (a0 register)
            maxpen: maximum pen number (d0 register)
        """
        return maxpen

    def SetOutlinePen(self, rp, pen):
        """Set the outline pen in a RastPort.

        Args:
            rp: RastPort pointer (a0 register)
            pen: pen number (d0 register)
        """
        return pen

    def LoadRGB32(self, vp, table):
        """Load RGB32 color table into a ViewPort.

        Args:
            vp: ViewPort pointer (a0 register)
            table: color table pointer (a1 register)
        """
        return None

    def LoadRGB4(self, vp, colors, count):
        """Load RGB4 color table into a ViewPort.

        Args:
            vp: ViewPort pointer (a0 register)
            colors: color table (a1 register)
            count: number of entries (d0 register)
        """
        return None

    def GetVPModeID(self, vp):
        """Get the ViewPort mode ID.

        Args:
            vp: ViewPort pointer (a0 register)
        """
        return 0

    def FreeDBufInfo(self, dbi):
        """Free a Display Buffer Info object.

        Args:
            dbi: Display Buffer Info pointer (a1 register)
        """
        return None

    def GetDisplayInfoData(self, tag, buffer, length):
        """Get display info data.

        Args:
            tag: tag item address (a0 register)
            buffer: data buffer (a1 register)
            length: buffer length (d0 register)
        """
        # Return a minimal display info structure
        return 0x10000

    def InitView(self, view):
        """Initialize a View.

        Args:
            view: View pointer (a1 register)
        """
        return None

    def FindDisplayInfo(self, tag):
        """Find a DisplayInfo structure.

        Args:
            tag: tag item address (a0 register)
        """
        return None

    def NextDisplayInfo(self, dnode):
        """Get the next DisplayInfo node.

        Args:
            dnode: DisplayInfo node pointer (a0 register)
        """
        return None

    def AllocBitMap(self, bitMap, depth, width, height):
        """Allocate a bitmap.

        Args:
            bitMap: bitMap pointer (a0 register)
            depth: bit depth (d0 register)
            width: bitmap width (d1 register)
            height: bitmap height (d2 register)
        """
        return None

    def FreeBitMap(self, bitMap):
        """Free a bitmap.

        Args:
            bitMap: bitMap pointer (a0 register)
        """
        return None

    def SetRPAttrsA(self, rp, attrs):
        """Set RastPort attributes.

        Args:
            rp: RastPort pointer (a1 register)
            attrs: attribute list (a0 register)
        """
        return None

    def GetRPAttrsA(self, rp, attrs):
        """Get RastPort attributes.

        Args:
            rp: RastPort pointer (a1 register)
            attrs: attribute list (a0 register)
        """
        return None

    def ObtainBestPenA(self, cm, penType, *args):
        """Obtain the best pen for a colormap.

        Args:
            colormap: colormap pointer (a0 register)
            penType: pen type (d0 register)
        """
        return 0

    def ObtainPen(self, cm, penType):
        """Obtain a pen from a colormap.

        Args:
            colormap: colormap pointer (a0 register)
            penType: pen type (d0 register)
        """
        return 0

    def ReleasePen(self, cm, pen):
        """Release a pen back to a colormap.

        Args:
            colormap: colormap pointer (a0 register)
            pen: pen number (d0 register)
        """
        return None

    def GetBestPen(self, cm, r, g, b):
        """Get the best pen match for RGB values.

        Args:
            colormap: colormap pointer (a0 register)
            red: red component (d1 register)
            green: green component (d2 register)
            blue: blue component (d3 register)
        """
        return 0

    def SetABPenDrMd(self, rp, apen, bpen, drMode):
        """Set active, background, and draw mode pens.

        Args:
            rp: RastPort pointer (a1 register)
            apen: active pen (d0 register)
            bpen: background pen (d1 register)
            drMode: draw mode (d2 register)
        """
        return None

    def CreateEasyFont(self, font, name, height):
        """Create an EasyFont.

        Args:
            font: font pointer (a0 register)
            font name: font name (d0 register)
            height: font height (d1 register)
        """
        return None

    def OpenFont(self, textAttr):
        """Open a font.

        Args:
            textAttr: text attribute pointer (a0 register)
        """
        return None

    def CloseFont(self, font):
        """Close a font.

        Args:
            font: font pointer (a1 register)
        """
        return None
        """Initialize a View.

        Args:
            view: View pointer (a1 register)
        """
        return None

    def SetRGB4(self, vp, index, red, green, blue):
        """Set RGB4 color in a ViewPort.

        Args:
            vp: ViewPort pointer (a0 register)
            index: color index (d0 register)
            red: red component (d1 register)
            green: green component (d2 register)
            blue: blue component (d3 register)
        """
        return None

    def BltClear(self, memBlock, byteCount, flags):
        """Block clear memory.

        Args:
            memBlock: memory block address (a1 register)
            byteCount: byte count (d0 register)
            flags: flags (d1 register)
        """
        return None

    def RectFill(self, rp, xMin, yMin, xMax, yMax):
        """Fill a rectangle in a RastPort.

        Args:
            rp: RastPort pointer (a1 register)
            xMin: x minimum (d0 register)
            yMin: y minimum (d1 register)
            xMax: x maximum (d2 register)
            yMax: y maximum (d3 register)
        """
        return None

    def BltBitMap(self, srcBitMap, xSrc, ySrc, destBitMap, xDest, yDest,
                  xSize, ySize, minterm, mask, tempA):
        """Block transfer between bitmaps.

        Args:
            srcBitMap: source bitmap (a0 register)
            xSrc: source x (d0 register)
            ySrc: source y (d1 register)
            destBitMap: destination bitmap (a1 register)
            xDest: dest x (d2 register)
            yDest: dest y (d3 register)
            xSize: width (d4 register)
            ySize: height (d5 register)
            minterm: minterm (d6 register)
            mask: mask (d7 register)
            tempA: temp A (a2 register)
        """
        return None

    def RectFill(self, rp, xMin, yMin, xMax, yMax):
        """Fill a rectangle.

        Args:
            rp: RastPort (a1)
            xMin: left (d0)
            yMin: top (d1)
            xMax: right (d2)
            yMax: bottom (d3)
        """
        return None