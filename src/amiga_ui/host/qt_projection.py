"""PySide6-backed host window projection.

This is the concrete :class:`~amiga_ui.host.projection.HostWindowProjection`
that turns window-open / refresh / close intent into *real* host effects:

- one host top-level window (:class:`AmigaHostWindow`, an ordinary ``QWidget``)
  per *app-facing* Amiga window, using the Amiga window's title and initial
  geometry,
- a focused custom drawing surface (:class:`RastPortReplaySurface`) that replays
  the ordered RastPort op stream recorded by the compatibility layer,
- the window's GadTools gadgets, projected as positioned host widgets that
  *overlay* the RastPort surface (the surface fills the host window, so the
  widgets are placed at the gadget's window-relative NewGadget coordinates):
  ``BUTTON`` -> :class:`QPushButton`, ``TEXT`` -> :class:`QLabel`,
  ``CYCLE`` -> :class:`QComboBox` (plus its left-hand caption, approximating the
  classic ``PLACETEXT_LEFT`` cycle label), ``CHECKBOX`` -> :class:`QCheckBox`;
  only the projectable kinds are rendered — the invisible context gadget and any
  unsupported kind are recorded by the boundary but never projected,
- a host menu bar (:class:`QMenuBar`, non-native) built from the Amiga menu
  strip the app attached with ``SetMenuStrip`` — and only then, so a window
  without a strip stays menu-bar-free by construction. Activating a projected
  menu entry posts a real ``IDCMP_MENUPICK`` carrying the packed ``MenuNumber``
  the strip was created with (see :class:`QtMenuAction`),
- no public Workbench screen canvas and no containing desktop surface.

The projected widgets carry the Amiga-side *addresses* they stand for and are
wired to the Amiga event loop through the event bridge: a ``BUTTON`` click posts
a real ``IDCMP_GADGETUP`` (``IAddress`` = the real ``struct Gadget *``), a menu
entry posts a real ``IDCMP_MENUPICK`` (``Code`` = the packed ``MenuNumber``), and
a host window-manager close request posts a real ``IDCMP_CLOSEWINDOW`` — each
queued on the window's real ``UserPort`` for ``WaitPort`` -> ``GT_GetIMsg`` ->
``GT_ReplyIMsg`` to pick up. A projection without an event source (plain smoke
tests) keeps the widgets display-only.

Threading: every widget here is created and mutated on the GUI thread. The
compatibility layer drives the projection during the in-process vamos run,
which executes on the main (GUI) thread, so no ``QThread`` / worker architecture
is introduced.

Qt-only module: import it from the GUI path (tests / a future host shell), not
from the low-level Amiga library implementations.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor, QFont, QImage, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QLabel,
    QMenu,
    QMenuBar,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..vamos.rastport_state import COMPLEMENT, INVERSVID, JAM2
from .projection import (
    KIND_BUTTON,
    KIND_CHECKBOX,
    KIND_CYCLE,
    KIND_TEXT,
    GadgetDescription,
    MenuEntryDescription,
    MenuStripDescription,
    OpenWindowIntent,
)

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

# Default window background: the classic Workbench window light grey (pen 15).
# Not derived from real DrawInfo/screen state (the public screen is notional /
# invisible), but chosen to match the notional public screen's ``BACKGROUNDPEN``
# (see ``intuition_library._SEMANTIC_PEN_MAP``) so a ``RectFill`` with
# ``dri_Pens[BACKGROUNDPEN]`` clears to the same colour as the window surface —
# the group-box title clear must read as "the background", not a black bar, and
# the white shine / black shadow / black text stay distinguishable from it.
DEFAULT_SURFACE_BACKGROUND: tuple[int, int, int] = (0xC0, 0xC0, 0xC0)


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
        """Pick the source pen (and whether to XOR) for a RastPort *vector/fill* op.

        Classic RastPort ``DrMd`` semantics (NDK 3.2 ``graphics/rastport.h``),
        for the fill and line ops (``Draw`` / ``AreaDraw`` / ``RectFill``):
        ``JAM1`` (0) jams the FgPen (APen) into the raster, ``JAM2`` (1) jams
        the BgPen (BPen), ``COMPLEMENT`` (2) XORs the FgPen bits into the
        raster, and ``INVERSVID`` (4) swaps the fg/bg pen roles first. This is
        the *source* (the pen the vector/fill op paints with) — it is NOT the
        rule for text, whose glyphs always use the FgPen foreground and whose
        JAM1/JAM2 treatment applies to the background behind the glyphs (see
        ``_draw_op``'s ``Text`` branch). Undefined bits are ignored.
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
        if name in ("Draw", "AreaDraw", "RectFill"):
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
            else:  # RectFill: fills with the source pen (draw mode applied);
                # the NDK AutoDocs describe it as "fill ... with the FgPen
                # color, taking into account the drawing mode".
                painter.fillRect(
                    op["x_min"],
                    op["y_min"],
                    (op["x_max"] - op["x_min"]) + 1,
                    (op["y_max"] - op["y_min"]) + 1,
                    color,
                )
        elif name == "Text":
            # Text glyphs are painted in the RastPort *FgPen* (APen) foreground,
            # regardless of JAM1/JAM2: the draw mode's foreground/background
            # treatment applies to the *background* cleared behind the glyphs
            # (0 under JAM1, the BgPen under JAM2 — see the ClearEOL AutoDocs),
            # not to the glyphs themselves. That background is already present
            # in the raster from the preceding RectFill, so this op paints the
            # characters in the FgPen. This is what makes a JAM2 box that sets
            # FgPen=TEXTPEN, BgPen=BACKGROUNDPEN render dark text on the window
            # background instead of background-coloured (invisible) glyphs.
            apen = op.get("apen", 0)
            mode = op.get("draw_mode", JAM2)
            if mode & INVERSVID:
                apen = op.get("bpen", 0)  # INVERSVID swaps the pen roles
            if mode & COMPLEMENT:
                color = pen_color(apen, self._palette)
                box = self._op_bounding_box(op)
                if box is not None:
                    self._xor_into_raster(raster, box, op, color)
                return
            text = op.get("text", "")
            if text:
                painter.setPen(pen_color(apen, self._palette))
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

    def _xor_into_raster(
        self, raster: QImage, box: tuple[int, int, int, int], op: dict[str, Any], color: QColor
    ) -> None:
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

    A plain top-level ``QWidget`` (not ``QMainWindow``): it has *no* menu bar
    unless an Amiga menu strip is attached to this very window via
    :meth:`attach_menu_strip` — the classic menu strip belongs to the window that
    called ``SetMenuStrip``, never to a shared application-wide or native menu
    bar. It carries the Amiga window's title and initial geometry and hosts one
    :class:`RastPortReplaySurface`.

    Host close requests are **deferred, not honoured**, whenever an event source
    is wired (``close_request_handler``): the window-manager / close-button
    request is answered with a real ``IDCMP_CLOSEWINDOW`` ``IntuiMessage`` for
    this window's real ``struct Window *``, and the widget stays open. Only the
    application's own ``CloseWindow`` — which reaches the projection through
    :meth:`QtHostWindowProjection.close_window` — destroys the widget while the
    session is live; a forced host shutdown (after the session ended, see
    :meth:`QtHostWindowProjection.mark_session_ended`) completes in Qt. See
    ``docs/architecture/cooperative-host-scheduler.md`` "Window Close Semantics".
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
        window_addr: int = 0,
        close_request_handler: Any = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self._has_menu_strip = has_menu_strip
        # Emulated identity key (never dereferenced by the host): the real
        # ``struct Window *`` this widget projects. The close path is
        # address-based, exactly like :class:`QtGadgetButton`'s activation.
        self.amiga_window_addr = window_addr
        # ``close_request_handler(window_addr) -> bool``: set by the projection
        # when an event source exists. Truthy means "the Amiga-side close path
        # took the request over" (stay open); falsy means there is no Amiga
        # window left to notify — the app already called ``CloseWindow`` and the
        # release path is closing this widget, so Qt may finish the job.
        self._close_request_handler = close_request_handler
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

    # -- menu strip projection -------------------------------------------------
    @staticmethod
    def _menu_text(label: str) -> str:
        """The label as literal menu text: Qt reads ``&`` as a mnemonic prefix.

        Classic Amiga menu labels are literal text (their own shortcut marker is
        ``\\1``, and iTidy's templates use neither), so doubling the ``&`` keeps
        what the app wrote on screen instead of swallowing a character.
        """

        return label.replace("&", "&&")

    @staticmethod
    def _add_submenu(container: Any, title: str) -> QMenu:
        """Create a ``QMenu`` owned by ``container`` (a ``QMenuBar`` or ``QMenu``) and add it.

        Never ``container.addMenu(title)``: under PySide6 that hands *Python*
        ownership of the new menu, so the C++ menu is destroyed as soon as the
        local name is rebound — while the bar or parent menu still shows it, and
        the next access raises ``Internal C++ object ... already deleted``.
        Passing the Qt parent explicitly keeps the menu alive exactly as long as
        the widget it belongs to.
        """

        menu = QMenu(title, container)
        container.addMenu(menu)
        return menu

    def _fill_menu(
        self, menu: QMenu, entries: Sequence[MenuEntryDescription], pick_handler: Any, *, depth: int
    ) -> None:
        """Add one level of decoded menu entries to ``menu``, in chain order.

        ``NM_BARLABEL`` entries become real separators (they consume a slot in the
        Amiga item chain, so they are *not* triggerable actions), a sub-item chain
        becomes a nested ``QMenu`` — classic Intuition opens a sub-menu instead of
        delivering a pick, so a parent entry is never itself triggerable — and a
        selectable entry becomes one :class:`QtMenuAction`. An entry this layer
        cannot render (no label at all, e.g. an image menu) adds nothing: the host
        never shows a menu entry the app did not give text to.
        """

        if depth >= 4:  # bounded nesting, mirroring the decode-side chain walk
            return
        for entry in entries:
            if entry.is_separator:
                menu.addSeparator()
                continue
            if entry.sub_items:
                submenu = self._add_submenu(menu, self._menu_text(entry.label))
                self._fill_menu(submenu, entry.sub_items, pick_handler, depth=depth + 1)
                continue
            if not entry.is_selectable:
                continue
            action = QtMenuAction(
                self._menu_text(entry.label), self.amiga_window_addr, entry.code, entry.item_addr, menu
            )
            menu.addAction(action)
            if pick_handler is not None:
                action.triggered.connect(lambda _checked=False, act=action: pick_handler(act))

    def attach_menu_strip(self, strip: MenuStripDescription, pick_handler: Any = None) -> QMenuBar:
        """Build this window's host menu bar from a decoded Amiga menu strip.

        The real host effect behind ``SetMenuStrip``: one ``QMenu`` per
        ``struct Menu`` title and one triggerable ``QAction`` per selectable
        ``struct MenuItem``, in the order of the real Amiga chains. The bar is
        non-native (``setNativeMenuBar(False)``) and a child of *this* window,
        because the classic strip belongs to the window the app attached it to —
        never to a shared application-wide or platform menu bar — and is placed
        above the window's drawing surface.

        ``pick_handler(action)`` is connected to every selectable action; that
        action carries the real ``struct Window *`` and the packed ``MenuNumber``
        recorded when the strip was created, so the activation path needs no
        label, title or hard-coded id. Re-attaching replaces the previous bar (an
        app may legitimately call ``SetMenuStrip`` again with a different strip).
        """

        self.clear_menu_strip()
        bar = QMenuBar(self)
        bar.setNativeMenuBar(False)
        for menu in strip.menus:
            submenu = self._add_submenu(bar, self._menu_text(menu.title))
            self._fill_menu(submenu, menu.items, pick_handler, depth=0)
        layout = self.layout()
        if isinstance(layout, QVBoxLayout):
            layout.insertWidget(0, bar)
        self.menu_bar = bar
        self._has_menu_strip = True
        bar.show()
        return bar

    def clear_menu_strip(self) -> None:
        """Remove this window's host menu bar. Idempotent.

        The bar is a child widget, so it is destroyed with its actions when the
        window closes; this is the ``ClearMenuStrip`` path that has to drop it
        while the window itself stays open.
        """

        bar = self.menu_bar
        if bar is None:
            return
        self.menu_bar = None
        layout = self.layout()
        if layout is not None:
            layout.removeWidget(bar)
        bar.setParent(None)
        bar.deleteLater()
        self._has_menu_strip = False

    def closeEvent(self, event: Any) -> None:  # noqa: N802 (Qt naming)
        """Defer a host close request to the Amiga side; never self-destroy.

        A window-manager close request is *not* permission to destroy the
        projection: the app owns the window's lifetime. When an event source is
        wired, the event is refused (``event.ignore()`` — the widget stays open)
        and the request is forwarded, by real window address, to the projection,
        which asks the event bridge for a real ``IDCMP_CLOSEWINDOW`` message.
        Repeated requests are harmless: the bridge treats a second request while
        the first is still in flight as an idempotent no-op.

        The cases that must still close: the app-driven release
        (:meth:`QtHostWindowProjection.close_window` pops the projection record
        *before* calling ``host_window.close()``, so the handler reports "no
        window left to notify" and the close proceeds), and a forced host
        shutdown once the Amiga session has ended
        (:meth:`QtHostWindowProjection.mark_session_ended` — including the
        synthesised close events that ``QApplication::quit()`` delivers).
        """

        handler = self._close_request_handler
        if handler is None:
            # No event source (display-only projection / plain smoke tests):
            # keep the pre-existing Qt behaviour and close normally.
            super().closeEvent(event)
            return
        if handler(self.amiga_window_addr):
            event.ignore()
            return
        super().closeEvent(event)


class QtGadgetButton(QPushButton):
    """A projected ``BUTTON`` gadget recording its real Amiga window/gadget address.

    The recorded addresses are what the *generic* activation path posts: a click
    becomes a real ``IDCMP_GADGETUP`` IntuiMessage whose ``IAddress`` is this
    gadget's real emulated ``struct Gadget *``, queued on the owning window's
    real ``UserPort``. Which button gets clicked is the host/test's business (a
    person clicks, or a test locates the widget by its visible text); the
    *translation* of a click into an Amiga message is always address-based, never
    string-based — no ``"Exit"`` literal or hard-coded ``GadgetID`` ever appears
    in the production path.
    """

    def __init__(
        self,
        text: str,
        window_addr: int,
        gadget_addr: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        # Emulated addresses (identity keys only — never dereferenced by the
        # host). ``window_addr`` is the owning window's real ``struct Window *``
        # (its ``UserPort`` is what the message is queued on); ``gadget_addr`` is
        # this gadget's real ``struct Gadget *`` (preserved as ``IAddress``).
        self.amiga_window_addr = window_addr
        self.amiga_gadget_addr = gadget_addr


class QtGadgetCheckbox(QCheckBox):
    """A projected ``CHECKBOX`` gadget recording its real Amiga window/gadget address.

    Same address-recording pattern as :class:`QtGadgetButton`, for checkboxes: a
    real toggle becomes a real ``IDCMP_GADGETUP`` IntuiMessage (``IAddress`` =
    this gadget's real ``struct Gadget *``) queued on the owning window's real
    ``UserPort``. The host-side registry also tracks the live checked state so
    ``GT_GetGadgetAttrsA``/``GT_SetGadgetAttrsA`` (``GTCB_Checked``) round-trip
    through the real app's own reads and writes of the checkbox.
    """

    def __init__(
        self,
        text: str,
        window_addr: int,
        gadget_addr: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        # Emulated addresses (identity keys only — never dereferenced by the
        # host); see :class:`QtGadgetButton` for the roles.
        self.amiga_window_addr = window_addr
        self.amiga_gadget_addr = gadget_addr


class QtMenuAction(QAction):
    """A projected Amiga menu entry recording the real addresses it stands for.

    Same address-based pattern as :class:`QtGadgetButton`, for menu picks: the
    activation is translated from ``amiga_window_addr`` (the owning window's real
    ``struct Window *``, whose ``UserPort`` the message goes to) and
    ``amiga_menu_code`` (the packed ``MenuNumber`` recorded when the strip was
    created, delivered as ``IntuiMessage.Code``). That is exactly the word the
    app hands to ``ItemAddress(strip, Code)``, so the entry the user clicked is
    the entry the app resolves — no label, title or hard-coded item id
    participates. ``amiga_item_addr`` is the entry's real ``struct MenuItem *``,
    carried as identity only (never dereferenced by the host).
    """

    def __init__(
        self,
        text: str,
        window_addr: int,
        menu_code: int,
        item_addr: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        self.amiga_window_addr = window_addr
        self.amiga_menu_code = menu_code
        self.amiga_item_addr = item_addr


@dataclass
class _ProjectedWindow:
    """Host-side association of one Amiga window address to its projection."""

    intent: OpenWindowIntent
    host_window: AmigaHostWindow | None = None
    # The host widgets this window owns (one or two per projectable gadget).
    # They are children of ``host_window``; closing the host window releases
    # them. Tracked here so tests / the shell can inspect and count them.
    gadget_widgets: list[QWidget] = field(default_factory=list)


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
        event_source: Any = None,
        window_projected_hook: Any = None,
    ) -> None:
        self._app = app
        self._palette = palette
        self._background = background
        self._registry: Any = None
        self._windows: dict[int, _ProjectedWindow] = {}
        # Host event source (the Intuition event bridge). When set, a projected
        # ``BUTTON`` click is translated into a real ``IDCMP_GADGETUP``
        # IntuiMessage on the owning window's real ``UserPort`` (address-based;
        # see :class:`QtGadgetButton`). ``None`` keeps the widgets display-only
        # (the pre-interactive behaviour), so plain projection smoke tests never
        # need an event bridge.
        self._event_source = event_source
        # Optional host callback ``window_projected(window_addr)`` invoked after
        # an app-facing window is fully projected (window + gadget widgets built
        # and shown). A generic readiness hook: the host shell can use it to
        # enable its chrome, and the interactive test uses it to schedule the
        # gadget activation once the window (and its buttons) exist.
        self._window_projected_hook = window_projected_hook
        # Set once the Amiga session behind this projection has ended (the
        # target returned from the run): no later host close request can be
        # translated into a target event any more — the bridge's emulated
        # context is gone. From then on a close request is the *forced host
        # shutdown* case of "Window Close Semantics": a host-lifecycle
        # outcome, never a deferrable interactive request. See
        # :meth:`mark_session_ended`.
        self._session_ended = False

    # -- HostWindowProjection interface --------------------------------------
    def bind_registry(self, registry: Any) -> None:
        self._registry = registry

    # -- GadTools gadget projection -------------------------------------------
    @staticmethod
    def _cycle_caption_width(label: str, window: QWidget) -> int:
        """Approximate pixel width of a cycle caption in the window's font."""

        return window.fontMetrics().horizontalAdvance(label) + 2

    def _build_gadget_widget(self, window: AmigaHostWindow, desc: GadgetDescription, window_addr: int) -> list[QWidget]:
        """Build the positioned host widget(s) for one projectable gadget.

        The widget(s) are *direct children of* ``window`` (not in its layout),
        placed at the gadget's NewGadget coordinates so they overlay the
        RastPort surface (which fills the host window). NewGadget coordinates
        are window-relative (window top-left, including the title bar area), and
        the surface fills the host window, so the coordinates are used directly.

        The gadget box geometry ``(left, top, width, height)`` is the *interactive
        box*. The classic GadTools label placement (``PLACETEXT_IN`` / ``LEFT`` /
        ``RIGHT``, not decoded here) means the label can sit inside the box
        (button/text), to its left (cycle) or to its right (checkbox). The Qt
        widget mapping handles each: button/checkbox/label carry their own text;
        the cycle caption is a separate :class:`QLabel` to the left of the
        :class:`QComboBox` (approximating ``PLACETEXT_LEFT``); the checkbox text
        extends the box to the right (``PLACETEXT_RIGHT``).
        """

        left, top = desc.left, desc.top
        width, height = desc.width, desc.height
        kind = desc.kind_name
        widgets: list[QWidget] = []
        if kind == KIND_BUTTON:
            # A BUTTON is an address-recording widget: a click is translated
            # (generically, address-based) into a real ``IDCMP_GADGETUP`` on the
            # owning window's real ``UserPort`` via the event bridge. Without an
            # event source the button stays display-only (pre-interactive).
            widget = QtGadgetButton(desc.label, window_addr, desc.gadget_addr, window)
            widget.setGeometry(left, top, max(1, width), max(1, height))
            if self._event_source is not None:
                widget.clicked.connect(lambda _checked=False, btn=widget: self._on_gadget_clicked(btn))
            widgets.append(widget)
        elif kind == KIND_CHECKBOX:
            widget = QtGadgetCheckbox(desc.label, window_addr, desc.gadget_addr, window)
            if desc.checked is not None:
                widget.setChecked(desc.checked)
            # The 26px box is the interactive part; the label extends to the
            # right (PLACETEXT_RIGHT), so size the widget to box + label.
            extra = self._cycle_caption_width(desc.label, window) if desc.label else 0
            widget.setGeometry(left, top, max(1, width + extra + 4), max(1, height))
            # A CHECKBOX, like a BUTTON, is an address-recording interactive
            # widget: a real user click is routed (generically, address-based)
            # to the event bridge's ``gadget_up``. The bridge toggles the
            # gadget's live checked state (host-side registry) and posts a real
            # ``IDCMP_GADGETUP`` on the owning window's ``UserPort`` — so the
            # app's ``GT_GetGadgetAttrs(GTCB_Checked)`` read sees the value the
            # user just set. Without an event source the checkbox stays
            # display-only (pre-interactive), exactly like the buttons.
            if self._event_source is not None:
                widget.toggled.connect(
                    lambda _checked, win=window_addr, gad=desc.gadget_addr: self._event_source.gadget_up(win, gad)
                )
            widgets.append(widget)
        elif kind == KIND_CYCLE:
            combo = QComboBox(window)
            combo.addItems(list(desc.cycle_labels))
            if 0 <= desc.cycle_active < len(desc.cycle_labels):
                combo.setCurrentIndex(desc.cycle_active)
            combo.setGeometry(left, top, max(1, width), max(1, height))
            widgets.append(combo)
            if desc.label:
                # Caption to the left of the dropdown (PLACETEXT_LEFT): anchor
                # its right edge a small gap left of the combo's left edge.
                gap = 6
                cap_w = self._cycle_caption_width(desc.label, window)
                caption = QLabel(desc.label, window)
                caption.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                caption.setGeometry(max(0, left - gap - cap_w), top, cap_w, max(1, height))
                widgets.append(caption)
        elif kind == KIND_TEXT:
            # Show the displayed text (GTTX_Text) when non-empty; otherwise the
            # gadget label (e.g. the "Folder:" static caption).
            text = desc.text if desc.text else desc.label
            widget = QLabel(text, window)
            widget.setGeometry(left, top, max(1, width), max(1, height))
            widgets.append(widget)
        else:
            return []
        for w in widgets:
            if not desc.enabled:
                w.setEnabled(False)
            w.raise_()  # ensure the gadget overlay sits above the RastPort surface
        return widgets

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
            # The close path is address-based, like the gadget path: the widget
            # carries the real ``struct Window *`` it projects and defers any
            # host close request back to the projection (only with an event
            # source; otherwise the widget keeps the plain display-only
            # behaviour and closes normally).
            window_addr=intent.window_addr,
            close_request_handler=self._on_close_request if self._event_source is not None else None,
        )
        projected.host_window = window
        # Project the window's own GadTools gadgets as positioned overlay
        # widgets. Only projectable kinds appear in ``intent.gadgets`` (the
        # compatibility layer already excludes the context gadget and any
        # unsupported kind), but double-check before building.
        for desc in intent.gadgets:
            if desc.is_projectable:
                projected.gadget_widgets.extend(self._build_gadget_widget(window, desc, intent.window_addr))
        window.show()
        if self._window_projected_hook is not None:
            # A generic readiness notification (not Amiga-specific): the app's
            # window and its gadget widgets now exist on the host. The
            # interactive test uses this to schedule the gadget activation once
            # the buttons exist; the host shell could use it to enable chrome.
            self._window_projected_hook(intent.window_addr)

    def _on_gadget_clicked(self, button: QtGadgetButton) -> None:
        """Translate a projected BUTTON click into a real Amiga gadget event.

        The generic, address-based activation path: it asks the event source
        (the Intuition event bridge) to post a real ``IDCMP_GADGETUP``
        IntuiMessage — carrying this button's real emulated ``struct Gadget *``
        as ``IAddress`` — onto the owning window's real ``UserPort``. No host
        event is ever fabricated by the scheduler itself; the real message is
        what wakes any target parked in ``WaitPort``. Stale clicks (the window
        already closed, the gadget already released) are handled by the bridge
        as honest no-ops (recorded in its ``skipped`` list), so a late signal
        after release can never corrupt a released port.
        """

        if self._event_source is None:
            return
        self._event_source.gadget_up(button.amiga_window_addr, button.amiga_gadget_addr)

    # -- menu strip projection -------------------------------------------------
    def set_menu_strip(self, window_addr: int, strip: MenuStripDescription) -> None:
        """Give ``window_addr``'s host window a real menu bar for ``strip``.

        The host effect behind ``intuition.library``'s ``SetMenuStrip``: the strip
        description is the one recorded when ``CreateMenus`` built the real
        ``struct Menu``/``struct MenuItem`` chain, so the bar mirrors the app's
        own menus (titles, entries, separators, sub-menus, chain order). When an
        event source is wired, each selectable entry is connected to
        :meth:`_on_menu_pick`; without one the bar stays display-only, exactly
        like the gadget widgets.

        A window this projection does not have (a helper window kept internal, or
        one already closed) gets nothing: there is no host surface to attach the
        bar to, and no fabricated fallback bar.
        """

        projected = self._windows.get(window_addr)
        if projected is None or projected.host_window is None:
            return
        projected.intent.has_menu_strip = True
        pick_handler = self._on_menu_pick if self._event_source is not None else None
        projected.host_window.attach_menu_strip(strip, pick_handler)

    def clear_menu_strip(self, window_addr: int) -> None:
        """Remove ``window_addr``'s host menu bar (``ClearMenuStrip``). Idempotent."""

        projected = self._windows.get(window_addr)
        if projected is None or projected.host_window is None:
            return
        projected.intent.has_menu_strip = False
        projected.host_window.clear_menu_strip()

    def _on_menu_pick(self, action: QtMenuAction) -> None:
        """Translate a projected menu-entry activation into a real menu pick.

        The generic, address-based counterpart of :meth:`_on_gadget_clicked`: it
        asks the event source (the Intuition event bridge) for a real
        ``IDCMP_MENUPICK`` ``IntuiMessage`` whose ``Code`` is this action's packed
        ``MenuNumber``, queued on the owning window's real ``UserPort`` — which is
        what wakes a target parked in ``WaitPort``. The app then runs its own
        ``ItemAddress(strip, Code)`` walk over its own menu chain, so the resolved
        item is the app's, not a host invention. A pick racing the app's own
        ``CloseWindow`` is an honest no-op in the bridge (recorded in its
        ``skipped`` list).
        """

        if self._event_source is None:
            return
        self._event_source.menu_pick(action.amiga_window_addr, action.amiga_menu_code)

    def mark_session_ended(self) -> None:
        """Record that the Amiga session behind this projection has ended.

        The host shell calls this as soon as the target returns from the run.
        The emulated context is gone by then, so a close request can no longer
        be translated into a real ``IDCMP_CLOSEWINDOW`` message for the app —
        and per ``docs/architecture/cooperative-host-scheduler.md`` ("Window
        Close Semantics") an *explicit forced host shutdown* remains possible
        as a host-lifecycle outcome. Marking the session ended is exactly that
        switch: subsequent close requests are completed by Qt instead of being
        deferred to a session that can no longer answer them.

        This is also what keeps ``QApplication::quit()`` working: the widgets
        layer turns an application quit into a synthesised (non-spontaneous)
        ``QCloseEvent`` per visible top-level window, so deferring those
        forever — with nothing left to notify, and a dead bridge context
        behind them — would both crash and wedge the shutdown.
        """

        self._session_ended = True

    def _on_close_request(self, window_addr: int) -> bool:
        """Route one host window-manager close request to the Amiga side.

        Called from :meth:`AmigaHostWindow.closeEvent` with that widget's real
        ``struct Window *`` — the same address-based pattern as
        :meth:`_on_gadget_clicked`. It asks the event source for a real
        ``IDCMP_CLOSEWINDOW`` ``IntuiMessage`` on that window's real
        ``UserPort``; the bridge filters it (window gone, or the window never
        requested ``IDCMP_CLOSEWINDOW``) and makes a second request while the
        first is still in flight an idempotent no-op.

        Returns ``True`` when the window is still projected and the session is
        live: the app owns the close decision, so the widget must stay open
        until *it* calls ``CloseWindow`` (a close request that never gets a
        reply leaves the host window open rather than silently vanishing).
        Returns ``False`` — let Qt complete the close — when there is no Amiga
        window left to notify: either this address is no longer projected
        (exactly the app-driven release in :meth:`close_window`, where the
        record is popped before the widget is closed), or the session has
        ended (:meth:`mark_session_ended`) and the request is a forced host
        shutdown, not a deferrable interactive close.
        """

        if self._event_source is None or self._session_ended or window_addr not in self._windows:
            return False
        self._event_source.request_close_window(window_addr)
        return True

    def refresh_window(self, window_addr: int) -> None:
        projected = self._windows.get(window_addr)
        if projected is None or projected.host_window is None or self._registry is None:
            return
        state = self._registry.state(projected.intent.rport_addr)
        if state is None:
            return
        projected.host_window.surface.replay(state)

    def show_easy_request(self, window_addr: int, title: str, body: str, buttons: Sequence[str]) -> int:
        """Show the app's EasyStruct as a real, blocking :class:`QMessageBox`.

        The host half of ``intuition.library``'s ``EasyRequestArgs``: a real
        confirmation dialog, parented to the app's own host window (the same
        top-level the requester logically lives on), carrying the app's own title,
        body text and button labels. ``.exec()`` blocks the GUI thread until the
        user actually clicks a button, and the method returns the 0-based index
        of the clicked button in ``buttons``. The *classic result-code* mapping
        (positive -> nonzero, cancel -> 0) is the caller's job (the Qt-free
        Intuition library), not the host's — the host only reports which of the
        app's own buttons was chosen.

        The last button is added with ``RejectRole`` (so Escape maps to it, as
        classic) and the first with ``YesRole``; a single button is ``AcceptRole``.
        """
        parent = self.host_window(window_addr)
        if parent is None:
            # No host surface to parent the requester to: there is no app window
            # here. Failing beats showing an unparented top-level that the app
            # would not have produced.
            raise ValueError(f"show_easy_request: window {window_addr:06x} is not projected")
        box = QMessageBox(parent)
        box.setWindowTitle(title)
        box.setText(body)
        for i, label in enumerate(buttons):
            if len(buttons) == 1:
                role = QMessageBox.ButtonRole.AcceptRole
            elif i == 0:
                role = QMessageBox.ButtonRole.YesRole
            elif i == len(buttons) - 1:
                role = QMessageBox.ButtonRole.RejectRole
            else:
                role = QMessageBox.ButtonRole.ActionRole
            box.addButton(label, role)
        box.exec()
        clicked = box.clickedButton()
        if clicked is not None:
            for i, label in enumerate(buttons):
                if clicked.text() == label:
                    return i
        # Defensive: exec() always returns via a button click, so this is not
        # reachable in practice; fall back to the (cancel) position.
        return len(buttons) - 1

    def show_file_dialog(
        self,
        window_addr: int | None,
        title: str,
        initial_directory: str = "",
        directories_only: bool = False,
        save_mode: bool = False,
        allow_patterns: bool = False,
        initial_file: str = "",
    ) -> str | None:
        """Show the app's ASL file/directory requester as a real, blocking :class:`QFileDialog`.

        The host half of ``asl.library``'s ``AslRequest``: a real picker,
        carrying the app's own title, initial drawer, initial file, and mode
        (directory-only vs. save vs. open). ``.exec()`` blocks the GUI thread
        (vamos runs on this thread, so this is the app's own blocking wait)
        until the user actually confirms or cancels, and the method returns
        the user's actual choice: the selected host path, or ``None`` when the
        user cancelled — in which case nothing is written back to the
        requester struct by the caller.

        The dialog is forced non-native (``DontUseNativeDialog``): the
        projection must behave identically on every host and stay observable
        to the in-process tests, and a hosted app's dialogs belong to the
        projection, not to a foreign platform shell.

        ``window_addr`` may be ``None``/0: ASL requesters are legal without
        ``ASLFR_Window`` (iTidy's directory picker passes none), and the real
        requester then simply opens its own top-level window — here an
        unparented modal dialog. When a window *is* named it must be
        projected, or the dialog would attach to a surface the app does not
        own.

        Args:
            window_addr: The app's parent Amiga window address, or ``None``/0
                for no parent.
            title: Dialog title (from ``ASLFR_TitleText``).
            initial_directory: Initial directory (from ``ASLFR_InitialDrawer``).
            directories_only: Directory-only picker (from ``ASLFR_DrawersOnly``).
            save_mode: Save-style picker, accepting a not-yet-existing name
                (from ``ASLFR_DoSaveMode``); overwriting is the app's check,
                as classic, so no host overwrite prompt.
            allow_patterns: ``ASLFR_DoPatterns``. Recorded in the intent but
                not translated: host-side pattern filtering is a separate
                obligation (see docs/host-gui/translation-obligations.md).
            initial_file: Initial file gadget contents (from
                ``ASLFR_InitialFile``).

        Returns:
            str | None: The selected host path, or ``None`` on cancel.

        Raises:
            ValueError: If ``window_addr`` names a window that is not projected.
        """
        parent: QWidget | None = None
        if window_addr:
            parent = self.host_window(window_addr)
            if parent is None:
                raise ValueError(f"show_file_dialog: window {window_addr:06x} is not projected")

        dialog = QFileDialog(parent, title)
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)

        if directories_only:
            dialog.setFileMode(QFileDialog.FileMode.Directory)
        elif save_mode:
            # Save mode accepts a name that does not exist yet; classic ASL
            # performs no overwrite check itself (the app checks with Lock()).
            dialog.setFileMode(QFileDialog.FileMode.AnyFile)
            dialog.setOption(QFileDialog.Option.DontConfirmOverwrite, True)
        else:
            dialog.setFileMode(QFileDialog.FileMode.ExistingFile)

        if initial_directory:
            dialog.setDirectory(initial_directory)
        if initial_file:
            dialog.selectFile(initial_file)
        # Note: the classic requester also lists dot-entries; QFileDialog has
        # no public option to reveal them (QFileDialog.Option has no
        # ShowHiddenFiles member on the installed PySide6), and the accepted
        # target does not depend on it. Left as a documented gap rather than
        # poked around via private dialog internals.

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None  # the user actually cancelled
        selected = dialog.selectedFiles()
        return selected[0] if selected else None

    def close_window(self, window_addr: int) -> None:
        projected = self._windows.pop(window_addr, None)
        if projected is None:
            return  # idempotent: already closed / never opened
        host_window = projected.host_window
        projected.host_window = None
        projected.gadget_widgets.clear()
        if host_window is not None:
            # Release this window's host projection — and, with it, the child
            # gadget widgets it owns (Qt parent/child ownership). ``deleteLater``
            # frees the C++ objects once control returns to the event loop; the
            # association is already popped above, so a second close is a no-op.
            host_window.close()
            host_window.deleteLater()

    # -- inspection (for tests / the host shell) -----------------------------
    @property
    def windows(self) -> dict[int, _ProjectedWindow]:
        """Live window-address -> projection association map."""

        return self._windows

    def host_window(self, window_addr: int) -> AmigaHostWindow | None:
        projected = self._windows.get(window_addr)
        return projected.host_window if projected is not None else None
