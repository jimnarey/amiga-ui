"""PySide6-backed host window projection.

This is the concrete :class:`~amiga_ui.host.projection.HostWindowProjection`
that turns window-open / refresh / close intent into *real* host effects:

- one host top-level window (:class:`AmigaHostWindow`, an ordinary ``QWidget``)
  per *app-facing* Amiga window, using the Amiga window's title and initial
  geometry,
- a focused custom drawing surface (:class:`RastPortReplaySurface`) that replays
  the ordered RastPort op stream recorded by the compatibility layer,
- no menu bar unless an Amiga menu strip has actually been attached (none are
  in this increment, so every host window is menu-bar-free by construction),
- no public Workbench screen canvas and no containing desktop surface.

Threading: every widget here is created and mutated on the GUI thread. The
compatibility layer drives the projection during the in-process vamos run,
which executes on the main (GUI) thread, so no ``QThread`` / worker architecture
is introduced.

Qt-only module: import it from the GUI path (tests / a future host shell), not
from the low-level Amiga library implementations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from ..vamos.rastport_state import COMPLEMENT, INVERSVID, JAM2
from .projection import OpenWindowIntent

# --- Classic-style pen palette -----------------------------------------------
# A small, deterministic, classic Workbench-flavoured 16-entry palette. This is
# an *explicit, replaceable* mapping, NOT a claim of exact Workbench palette
# fidelity (that would require the real DrawInfo / screen colour state, which
# the public screen does not render). Pen index wraps into this table.
CLASSIC_PEN_PALETTE: tuple[tuple[int, int, int], ...] = (
    (0x00, 0x00, 0x00),  # 0  black
    (0xFF, 0xFF, 0xFF),  # 1  white
    (0xFF, 0x00, 0x00),  # 2  red
    (0x00, 0xFF, 0x00),  # 3  green
    (0x00, 0x00, 0xFF),  # 4  blue
    (0xFF, 0xFF, 0x00),  # 5  yellow
    (0x00, 0xFF, 0xFF),  # 6  cyan
    (0xFF, 0x00, 0xFF),  # 7  magenta
    (0x80, 0x80, 0x80),  # 8  grey
    (0x80, 0x00, 0x00),  # 9  dark red
    (0x00, 0x80, 0x00),  # 10 dark green
    (0x00, 0x00, 0x80),  # 11 dark blue
    (0x80, 0x80, 0x00),  # 12 dark yellow
    (0x00, 0x80, 0x80),  # 13 dark cyan
    (0x80, 0x00, 0x80),  # 14 dark magenta
    (0xC0, 0xC0, 0xC0),  # 15 light grey
)

# Default neutral window background. Not derived from real DrawInfo/screen
# state (the public screen is notional / invisible); a clean high-contrast
# surface so the replayed chrome reads clearly.
DEFAULT_SURFACE_BACKGROUND: tuple[int, int, int] = (0xFF, 0xFF, 0xFF)


def pen_color(pen: int, palette: tuple[tuple[int, int, int], ...] = CLASSIC_PEN_PALETTE) -> QColor:
    """Map a RastPort pen index to a :class:`QColor` via the palette table."""

    r, g, b = palette[pen % len(palette)]
    return QColor(r, g, b)


def _lighten(rgb: tuple[int, int, int], factor: float = 0.6) -> tuple[int, int, int]:
    return tuple(min(255, int(c + (255 - c) * factor)) for c in rgb)  # type: ignore[return-value]


def _darken(rgb: tuple[int, int, int], factor: float = 0.6) -> tuple[int, int, int]:
    return tuple(int(c * (1 - factor)) for c in rgb)  # type: ignore[return-value]


class RastPortReplaySurface(QWidget):
    """Focused custom drawing surface that replays a recorded RastPort op stream.

    The surface is deliberately independent of ``vamos`` and emulated memory: it
    only consumes a state object exposing an ordered ``ops`` list (a
    :class:`~amiga_ui.vamos.rastport_state.RastPortState`) and draws it. Text is
    drawn from the *recorded* decoded content — never by dereferencing a stale
    emulated pointer.

    Replay rules (see ``docs/host-gui/`` and the increment brief):
    - ops are replayed in order, each drawn with the pen/draw-mode state captured
      on that op;
    - ``TextLength`` is a measurement record, never a paint operation;
    - ``Move`` / ``AreaMove`` and the pen/Font/DrMd state setters are history,
      not visible marks;
    - draw modes use the classic RastPort semantics (NDK ``graphics/rastport.h``):
      ``JAM1`` (0) draws with the foreground pen (APen), ``JAM2`` (1) with the
      background pen (BPen), ``COMPLEMENT`` (2) XORs the raster, and
      ``INVERSVID`` (4) swaps the fg/bg pen roles. ``RectFill`` fills with the
      foreground pen per the NDK AutoDocs ("fill ... with the FgPen color,
      taking into account the drawing mode");
    - ``PrintIText`` uses the IntuiText's own ``FrontPen``: the IntuiText
      ``DrawMode`` is a different value set from the RastPort ``DrMd`` and is
      not decoded in this increment (documented deferral, not an approximation
      of a decoded value);
    - the palette, bevel appearance, and font remain explicit approximations
      (see the module docstrings); undefined draw-mode bits are ignored.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        palette: tuple[tuple[int, int, int], ...] = CLASSIC_PEN_PALETTE,
        background: tuple[int, int, int] = DEFAULT_SURFACE_BACKGROUND,
    ) -> None:
        super().__init__(parent)
        self._palette = palette
        self._background = background
        self._state: Any = None
        self._raster: QImage | None = None
        self._raster_op_count = -1
        self.setAutoFillBackground(False)
        self._font = QFont("Monospace", 8)
        self._font.setStyleHint(QFont.StyleHint.TypeWriter)

    # -- state ---------------------------------------------------------------
    def replay(self, state: Any) -> None:
        """Store the RastPort state to replay and schedule a repaint.

        The op stream is replayed into an offscreen QImage *raster* (built once
        per state change, not per paint), which ``paintEvent`` then blits.
        Building the raster offscreen is what lets ``COMPLEMENT`` (bitwise
        XOR) be a genuine per-pixel raster operation instead of a QPainter
        composition mode (Qt's ``CompositionMode_Xor`` is Porter-Duff
        non-overlap, not the classic bitwise XOR).
        """

        self._state = state
        self._rebuild_raster()
        self.update()

    def state(self) -> Any:
        """The RastPort state currently loaded for replay (or ``None``)."""

        return self._state

    def resizeEvent(self, event: Any) -> None:  # noqa: N802 (Qt naming)
        super().resizeEvent(event)
        if self._state is not None:
            self._rebuild_raster()

    # -- painting ------------------------------------------------------------
    def paintEvent(self, event: Any) -> None:  # noqa: N802 (Qt naming)
        # The op stream can grow after the last ``replay()``/``GT_RefreshWindow``
        # (the app keeps drawing). Rebuild the raster when it is stale so a paint
        # always shows the full recorded stream (this is what the old
        # paint-time replay guaranteed).
        if self._state is not None:
            op_count = len(self._state.ops)
            if (
                self._raster is None
                or op_count != self._raster_op_count
                or (self._raster.width() != self.width() or self._raster.height() != self.height())
            ):
                self._rebuild_raster()
        painter = QPainter(self)
        try:
            painter.fillRect(self.rect(), QColor(*self._background))
            if self._raster is not None:
                painter.drawImage(0, 0, self._raster)
        finally:
            painter.end()

    # -- raster replay ---------------------------------------------------------
    def _rebuild_raster(self) -> None:
        """Replay the loaded op stream into a QImage raster of the surface size."""

        width, height = self.width(), self.height()
        if self._state is None or width <= 0 or height <= 0:
            self._raster = None
            self._raster_op_count = -1
            return
        op_count = len(self._state.ops)
        raster = QImage(width, height, QImage.Format.Format_RGB32)
        raster.fill(QColor(*self._background))
        painter = QPainter(raster)
        try:
            painter.setFont(self._font)
            for op in self._state.ops:
                self._draw_op(painter, raster, op)
        finally:
            painter.end()
        self._raster = raster
        self._raster_op_count = op_count

    @staticmethod
    def _select_pen(op: dict[str, Any]) -> tuple[int, bool]:
        """Pick the pen (and whether to XOR) for a RastPort draw op.

        Classic RastPort ``DrMd`` semantics (NDK 3.2 ``graphics/rastport.h``):
        ``JAM1`` (0) jams the FgPen (APen) into the raster, ``JAM2`` (1) jams
        the BgPen (BPen), ``COMPLEMENT`` (2) XORs bits into the raster, and
        ``INVERSVID`` (4) swaps the fg/bg pen roles. The base source for a
        RastPort draw op is the FgPen (the NDK describes the draw/fill ops in
        terms of the primary pen with the mode applied); undefined bits are
        ignored.
        """

        mode = op.get("draw_mode", JAM2)
        apen = op.get("apen", 0)
        bpen = op.get("bpen", 0)
        if mode & INVERSVID:
            apen, bpen = bpen, apen
        if mode & COMPLEMENT:
            return apen, True
        return (bpen if mode & JAM2 else apen), False

    def _draw_op(self, painter: QPainter, raster: QImage, op: dict[str, Any]) -> None:
        name = op.get("op")
        if name in ("Draw", "AreaDraw", "RectFill", "Text"):
            pen, xor = self._select_pen(op)
            color = pen_color(pen, self._palette)
            if xor:
                # COMPLEMENT: a genuine bitwise XOR of the raster. The op is
                # first drawn onto a coverage mask (white ink on black), then
                # the pen color is XORed into every covered raster pixel —
                # the classic 1-bit raster semantics, not a composition mode.
                box = self._op_bounding_box(op)
                if box is not None:
                    self._xor_into_raster(raster, box, op, color)
                return
            if name == "Draw" or name == "AreaDraw":
                painter.setPen(QPen(color, 1))
                painter.drawLine(op["from_x"], op["from_y"], op["x"], op["y"])
            elif name == "RectFill":
                # NDK AutoDocs: RectFill fills with the FgPen color (draw mode
                # applied) when no areafill pattern is set.
                painter.fillRect(
                    op["x_min"],
                    op["y_min"],
                    (op["x_max"] - op["x_min"]) + 1,
                    (op["y_max"] - op["y_min"]) + 1,
                    color,
                )
            else:  # Text: draws in the RastPort's current pen and draw mode
                text = op.get("text", "")
                if text:
                    painter.setPen(color)
                    painter.drawText(op["x"], op["y"], text)
        elif name == "PrintIText":
            # The IntuiText carries its own FrontPen; the IntuiText DrawMode
            # value set is not decoded in this increment (documented deferral).
            pen = op.get("front_pen", op.get("apen", 0))
            text = op.get("text", "")
            if text:
                painter.setPen(pen_color(pen, self._palette))
                painter.drawText(op["x"], op["y"], text)
        elif name == "DrawBevelBox":
            self._draw_bevel_box(painter, op)
        # TextLength / Move / AreaMove / SetFont / SetAPen / SetBPen / SetDrMd /
        # SetABPenDrMd / SetMaxPen / SetOutlinePen / InitRastPort: state or
        # measurement history, no visible mark.

    @staticmethod
    def _op_bounding_box(op: dict[str, Any]) -> tuple[int, int, int, int] | None:
        """Inclusive (x0, y0, x1, y1) bounding box of a draw op, or ``None``."""

        name = op.get("op")
        if name == "RectFill":
            return op["x_min"], op["y_min"], op["x_max"], op["y_max"]
        if name in ("Draw", "AreaDraw"):
            return (
                min(op["from_x"], op["x"]),
                min(op["from_y"], op["y"]),
                max(op["from_x"], op["x"]),
                max(op["from_y"], op["y"]),
            )
        if name == "Text":
            # The recorded width is the pen advance; the height is bounded by a
            # conservative line box (the exact font metrics are not on the op).
            return op["x"], op["y"], op["x"] + op.get("width", 0), op["y"] + 16
        return None

    def _xor_into_raster(self, raster: QImage, box: tuple[int, int, int, int], op: dict[str, Any], color: QColor) -> None:
        """COMPLEMENT: XOR ``color`` into every raster pixel the op covers.

        The op is first drawn onto a small coverage mask (white ink on black)
        with the same painter settings the normal path uses, so the mask is
        exactly the pixels the op would paint. Each covered pixel then has the
        pen color XORed into its R/G/B channels — the classic 1-bit raster
        semantics (a covered pixel is fully flipped per channel, no alpha
        blending).
        """

        width, height = raster.width(), raster.height()
        x0 = max(0, min(box[0], width - 1))
        y0 = max(0, min(box[1], height - 1))
        x1 = max(0, min(box[2], width - 1))
        y1 = max(0, min(box[3], height - 1))
        if x1 < x0 or y1 < y0:
            return
        box_w, box_h = x1 - x0 + 1, y1 - y0 + 1

        mask = QImage(box_w, box_h, QImage.Format.Format_RGB32)
        mask.fill(QColor(0, 0, 0))
        mp = QPainter(mask)
        try:
            mp.setFont(self._font)
            mp.setPen(QPen(QColor(255, 255, 255), 1))
            name = op.get("op")
            if name in ("Draw", "AreaDraw"):
                mp.drawLine(op["from_x"] - x0, op["from_y"] - y0, op["x"] - x0, op["y"] - y0)
            elif name == "RectFill":
                mp.fillRect(
                    op["x_min"] - x0,
                    op["y_min"] - y0,
                    (op["x_max"] - op["x_min"]) + 1,
                    (op["y_max"] - op["y_min"]) + 1,
                    QColor(255, 255, 255),
                )
            elif name == "Text":
                mp.drawText(op["x"] - x0, op["y"] - y0, op.get("text", ""))
        finally:
            mp.end()

        cr, cg, cb = color.red(), color.green(), color.blue()
        for my in range(box_h):
            ry = y0 + my
            for mx in range(box_w):
                if mask.pixel(mx, my) != 0xFF000000:  # covered pixel (ink on black)
                    p = raster.pixel(x0 + mx, ry)
                    r = ((p >> 16) & 0xFF) ^ cr
                    g = ((p >> 8) & 0xFF) ^ cg
                    b = (p & 0xFF) ^ cb
                    raster.setPixel(x0 + mx, ry, 0xFF000000 | (r << 16) | (g << 8) | b)

    def _draw_bevel_box(self, painter: QPainter, op: dict[str, Any]) -> None:
        """Draw a classic-style bevel frame for a ``DrawBevelBox`` op.

        Light/dark edges are derived from the surface background (not from real
        DrawInfo), so the bevel is a deterministic approximation of the classic
        raised/recessed frame rather than a pixel-exact Workbench bevel.
        """

        left, top = op["left"], op["top"]
        right, bottom = left + op["width"], top + op["height"]
        light = QColor(*_lighten(self._background))
        dark = QColor(*_darken(self._background))
        edge_light, edge_dark = (light, dark) if not op.get("recessed") else (dark, light)
        painter.setPen(QPen(edge_light, 1))
        painter.drawLine(left, top, right, top)  # top
        painter.drawLine(left, top, left, bottom)  # left
        painter.setPen(QPen(edge_dark, 1))
        painter.drawLine(left, bottom, right, bottom)  # bottom
        painter.drawLine(right, top, right, bottom)  # right


class AmigaHostWindow(QWidget):
    """One host top-level window projecting a single app-facing Amiga window.

    A plain top-level ``QWidget`` (not ``QMainWindow``) so it has *no* menu bar
    unless an Amiga menu strip is attached — none are in this increment, so every
    host window is menu-bar-free by construction. It carries the Amiga window's
    title and initial geometry and hosts one :class:`RastPortReplaySurface`.
    """

    def __init__(
        self,
        title: str,
        width: int,
        height: int,
        left: int | None = None,
        top: int | None = None,
        palette: tuple[tuple[int, int, int], ...] = CLASSIC_PEN_PALETTE,
        background: tuple[int, int, int] = DEFAULT_SURFACE_BACKGROUND,
        has_menu_strip: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self._has_menu_strip = has_menu_strip
        # Menu bar only when an Amiga menu strip is actually attached; none in
        # this increment, so the default is "no menu bar".
        self.menu_bar: Any = None
        self.surface = RastPortReplaySurface(self, palette=palette, background=background)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.surface)
        self.resize(max(1, width), max(1, height))
        if left is not None and top is not None:
            self.move(left, top)

    @property
    def has_menu_strip(self) -> bool:
        return self._has_menu_strip


@dataclass
class _ProjectedWindow:
    """Host-side association of one Amiga window address to its projection."""

    intent: OpenWindowIntent
    host_window: AmigaHostWindow | None = None


class QtHostWindowProjection:
    """Real PySide6 projection: one host top-level window per app-facing window.

    The compatibility layer calls :meth:`open_window` / :meth:`refresh_window` /
    :meth:`close_window` with already-interpreted values (title string, geometry
    ints, RastPort address) — this class performs the host effect and keeps the
    window-address -> (RPort, host window) association. It replays the RastPort
    op stream from the run-wide registry bound via :meth:`bind_registry`.
    """

    def __init__(
        self,
        app: QApplication,
        palette: tuple[tuple[int, int, int], ...] = CLASSIC_PEN_PALETTE,
        background: tuple[int, int, int] = DEFAULT_SURFACE_BACKGROUND,
    ) -> None:
        self._app = app
        self._palette = palette
        self._background = background
        self._registry: Any = None
        self._windows: dict[int, _ProjectedWindow] = {}

    # -- HostWindowProjection interface --------------------------------------
    def bind_registry(self, registry: Any) -> None:
        self._registry = registry

    def open_window(self, intent: OpenWindowIntent) -> None:
        projected = _ProjectedWindow(intent=intent, host_window=None)
        self._windows[intent.window_addr] = projected
        if not intent.is_app_facing:
            # Helper / backdrop window: represented internally, not projected.
            return
        window = AmigaHostWindow(
            intent.title,
            intent.width,
            intent.height,
            intent.left,
            intent.top,
            self._palette,
            self._background,
            intent.has_menu_strip,
        )
        projected.host_window = window
        window.show()

    def refresh_window(self, window_addr: int) -> None:
        projected = self._windows.get(window_addr)
        if projected is None or projected.host_window is None or self._registry is None:
            return
        state = self._registry.state(projected.intent.rport_addr)
        if state is None:
            return
        projected.host_window.surface.replay(state)

    def close_window(self, window_addr: int) -> None:
        projected = self._windows.pop(window_addr, None)
        if projected is not None and projected.host_window is not None:
            projected.host_window.close()

    # -- inspection (for tests / the host shell) -----------------------------
    @property
    def windows(self) -> dict[int, _ProjectedWindow]:
        """Live window-address -> projection association map."""

        return self._windows

    def host_window(self, window_addr: int) -> AmigaHostWindow | None:
        projected = self._windows.get(window_addr)
        return projected.host_window if projected is not None else None
