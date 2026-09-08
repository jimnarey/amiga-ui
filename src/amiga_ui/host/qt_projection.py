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

from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

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
    - draw modes other than ``DM_COPY`` are rendered as ``DM_COPY`` in this first
      increment (a documented approximation, not pixel-exact raster-op semantics).
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
        self.setAutoFillBackground(False)
        self._font = QFont("Monospace", 8)
        self._font.setStyleHint(QFont.StyleHint.TypeWriter)

    # -- state ---------------------------------------------------------------
    def replay(self, state: Any) -> None:
        """Store the RastPort state to replay and schedule a repaint."""

        self._state = state
        self.update()

    def state(self) -> Any:
        """The RastPort state currently loaded for replay (or ``None``)."""

        return self._state

    # -- painting ------------------------------------------------------------
    def paintEvent(self, event: Any) -> None:  # noqa: N802 (Qt naming)
        painter = QPainter(self)
        try:
            painter.fillRect(self.rect(), QColor(*self._background))
            if self._state is None:
                return
            painter.setFont(self._font)
            for op in self._state.ops:
                self._draw_op(painter, op)
        finally:
            painter.end()

    def _draw_op(self, painter: QPainter, op: dict[str, Any]) -> None:
        name = op.get("op")
        if name == "Draw" or name == "AreaDraw":
            painter.setPen(QPen(pen_color(op["apen"], self._palette), 1))
            painter.drawLine(op["from_x"], op["from_y"], op["x"], op["y"])
        elif name == "RectFill":
            color = pen_color(op["bpen"], self._palette)
            painter.fillRect(
                op["x_min"],
                op["y_min"],
                (op["x_max"] - op["x_min"]) + 1,
                (op["y_max"] - op["y_min"]) + 1,
                color,
            )
        elif name in ("Text", "PrintIText"):
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
