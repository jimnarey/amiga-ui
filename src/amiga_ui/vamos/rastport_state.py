"""Host-side RastPort drawing-state model for the repo ``graphics.library``.

The target app drives all window drawing through ``graphics.library``
(``SetFont``/``SetAPen``/``SetBPen``/``SetDrMd``/``Move``/``Draw``/``RectFill``).
On real AmigaOS these calls mutate an in-memory ``struct RastPort`` and then
rasterise into the screen ``BitMap``. This project has no host window yet, so
instead of silently no-op'ing the calls (a fake "success" that records nothing),
we record the drawing *state* and the ordered *sequence of drawing operations*
in a host-side model keyed by the emulated RastPort pointer.

This is a genuine, inspectable record of what the app drew:

- a later host-side renderer can replay ``ops`` to reconstruct the window;
- text-metrics work (``TextLength``/``PrintIText``/``IntuiTextLength``) can read
  the RastPort font/pen/draw-mode state the app actually configured;
- a probe can assert "the app set pen 7 and drew a line from (a,b) to (c,d)"
  without needing a display.

The model is deliberately *not* tied to any particular ``struct RastPort`` byte
layout: it stores the values the app passed to the library entry points, so it
stays correct regardless of the on-memory struct offsets (which are tracked
separately in ``docs/platform/structs/``). See
``docs/architecture/platform-target.md``: default target is classic m68k
AmigaOS 3.0-3.1; no OS4/PPC assumptions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Default draw mode: DM_COPY (the classic RastPort default per the NDK).
_DEFAULT_DRAW_MODE = 0x8C


@dataclass
class RastPortState:
    """Host-side drawing state for one emulated RastPort.

    ``ops`` is the ordered log of drawing operations the app issued against this
    RastPort. Each entry is a dict with at least an ``op`` key plus the
    operation's parameters and the pen/draw-mode state in effect when it ran.
    """

    rp: int = 0
    apen: int = 0
    bpen: int = 0
    draw_mode: int = _DEFAULT_DRAW_MODE
    maxpen: int = 0
    outline_pen: int = 0
    font: int = 0  # emulated TextFont pointer from SetFont
    x: int = 0  # current pen position (Move/AreaMove/Draw)
    y: int = 0
    ops: list[dict[str, Any]] = field(default_factory=list)

    # -- state mutation + op recording -------------------------------------
    def _record(self, op: str, **fields: Any) -> dict[str, Any]:
        """Append an op entry carrying the pen/draw-mode state in effect."""
        entry: dict[str, Any] = {
            "op": op,
            "apen": self.apen,
            "bpen": self.bpen,
            "draw_mode": self.draw_mode,
        }
        entry.update(fields)
        self.ops.append(entry)
        return entry

    def set_font(self, font: int) -> int:
        """Record SetFont; return the previous font pointer (classic contract)."""
        previous = self.font
        self.font = font
        self._record("SetFont", font=font)
        return previous

    def set_apen(self, pen: int) -> None:
        self.apen = pen
        self._record("SetAPen", pen=pen)

    def set_bpen(self, pen: int) -> None:
        self.bpen = pen
        self._record("SetBPen", pen=pen)

    def set_dr_md(self, draw_mode: int) -> None:
        self.draw_mode = draw_mode
        self._record("SetDrMd", draw_mode=draw_mode)

    def set_ab_pen_dr_md(self, apen: int, bpen: int, draw_mode: int) -> None:
        self.apen = apen
        self.bpen = bpen
        self.draw_mode = draw_mode
        self._record("SetABPenDrMd", apen=apen, bpen=bpen, draw_mode=draw_mode)

    def set_max_pen(self, maxpen: int) -> int:
        """Record SetMaxPen; return the previous maximum pen (classic contract)."""
        previous = self.maxpen
        self.maxpen = maxpen
        self._record("SetMaxPen", maxpen=maxpen)
        return previous

    def set_outline_pen(self, pen: int) -> int:
        """Record SetOutlinePen; return the previous outline pen (classic)."""
        previous = self.outline_pen
        self.outline_pen = pen
        self._record("SetOutlinePen", pen=pen)
        return previous

    def move(self, x: int, y: int) -> None:
        self.x = x
        self.y = y
        self._record("Move", x=x, y=y)

    def area_move(self, x: int, y: int) -> None:
        self.x = x
        self.y = y
        self._record("AreaMove", x=x, y=y)

    def draw(self, x: int, y: int) -> None:
        """Record Draw (line from the current position to (x, y))."""
        self._record("Draw", from_x=self.x, from_y=self.y, x=x, y=y)
        self.x = x
        self.y = y

    def area_draw(self, x: int, y: int) -> None:
        self._record("AreaDraw", from_x=self.x, from_y=self.y, x=x, y=y)
        self.x = x
        self.y = y

    def rect_fill(self, x_min: int, y_min: int, x_max: int, y_max: int) -> None:
        self._record("RectFill", x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max)

    def record_text_length(self, string: int, count: int, length: int) -> None:
        """Record a ``TextLength`` measurement.

        ``string`` is the emulated string pointer the app passed, ``count`` the
        character count measured, and ``length`` the pixel width the library
        returned. A later renderer/replayer can see what the app measured and
        how wide it was told the text was.
        """
        self._record("TextLength", string=string, count=count, length=length)

    def record_text(self, string: int, count: int, width: int, text: str = "") -> None:
        """Record a ``Text`` draw at the current pen position.

        ``string`` is the emulated string pointer, ``count`` the number of
        characters drawn, ``width`` the pixel width the draw advances the pen
        by, and ``text`` the decoded string content (best-effort, for a future
        renderer/replayer). Classic ``Text`` draws at the RastPort's current
        origin and then advances it, so this records the draw position and
        moves the pen forward by ``width``.
        """
        self._record("Text", string=string, count=count, width=width, x=self.x, y=self.y, text=text)
        self.x += width

    def print_itext(
        self, string: int, count: int, width: int, x: int, y: int, front_pen: int = 0, font: int = 0, text: str = ""
    ) -> None:
        """Record an ``Intuition`` ``PrintIText`` draw at an explicit position.

        Unlike graphics ``Text`` (which draws at the RastPort origin and then
        advances it), ``PrintIText(rp, iText, left, top)`` draws the IntuiText's
        string at the explicit ``(left, top)`` in the IntuiText's own front pen
        and font, so this records the explicit draw position and the IntuiText
        front pen *without* moving the RastPort origin. A future renderer can
        replay the group-box / requester titles from this op.
        """
        self._record(
            "PrintIText",
            string=string,
            count=count,
            width=width,
            x=x,
            y=y,
            front_pen=front_pen,
            font=font,
            text=text,
        )

    def draw_bevel_box(
        self, left: int, top: int, width: int, height: int, recessed: bool = False, visual_info: int = 0
    ) -> None:
        """Record a GadTools ``DrawBevelBox(A)`` bevel-box draw.

        The group-box / frame bevel the app draws around its gadgets. Draws at
        the explicit ``(left, top)`` bounds (not the RastPort origin) and records
        the size plus the ``GTBB_Recessed`` flag and the ``GT_VisualInfo``
        pointer, so a future renderer can replay the bevel frame in the window's
        op log alongside the ``PrintIText`` titles.
        """
        self._record(
            "DrawBevelBox",
            left=left,
            top=top,
            width=width,
            height=height,
            recessed=recessed,
            visual_info=visual_info,
        )

    def init(self) -> None:
        """Record InitRastPort (resets the drawing state for this RastPort)."""
        self.apen = 0
        self.bpen = 0
        self.draw_mode = _DEFAULT_DRAW_MODE
        self.maxpen = 0
        self.outline_pen = 0
        self.font = 0
        self.x = 0
        self.y = 0
        self.ops.clear()
        self._record("InitRastPort")


class RastPortRegistry:
    """Map emulated RastPort pointers to their host-side drawing state.

    The launcher creates ONE registry per vamos session and exposes it on every
    library context (``ctx.rastports``), so ``graphics.library`` (Text) and
    ``intuition.library`` (PrintIText) draw into the same per-RastPort op log in
    chronological order. Library instances keep a private fallback registry for
    unit tests where no shared registry is on the context, so drawing state
    never leaks across probe runs either way.
    """

    def __init__(self) -> None:
        self._states: dict[int, RastPortState] = {}

    def get_or_create(self, rp: int) -> RastPortState:
        state = self._states.get(rp)
        if state is None:
            state = RastPortState(rp=rp)
            self._states[rp] = state
        return state

    def state(self, rp: int) -> RastPortState | None:
        """Return the state for ``rp`` if one exists, else ``None``."""
        return self._states.get(rp)

    def all_states(self) -> list[RastPortState]:
        """All tracked RastPorts, in first-seen (insertion) order."""
        return list(self._states.values())

    def total_ops(self) -> int:
        return sum(len(state.ops) for state in self._states.values())
