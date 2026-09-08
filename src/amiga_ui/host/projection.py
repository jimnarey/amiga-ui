"""Qt-independent host window-projection boundary.

This is the seam through which the compatibility layer (``intuition.library``
and ``gadtools.library``) expresses *intent* about app-facing Amiga windows:

- a window was opened (with its title, initial geometry, RastPort and IDCMP
  flags),
- a window should be repainted (the ``GT_RefreshWindow`` boundary),
- a window was closed.

The compatibility layer never imports or constructs Qt widgets: it calls these
semantic methods on whatever projection the launcher installed on the library
context (``ctx.host_projection``). The concrete projection decides how to turn
the intent into host effects.

Two concrete projections exist:

- :class:`NullHostWindowProjection` — the default for plain (non-GUI) probes.
  It records the intents (so the boundary is observable) but never touches Qt,
  so ordinary headless probes never require a display.
- ``QtHostWindowProjection`` (``amiga_ui.host.qt_projection``) — the real
  PySide6-backed projection that creates one host top-level window per
  app-facing Amiga window and replays the recorded RastPort op stream onto a
  focused custom drawing surface.

Keeping this module free of any Qt import is what lets the low-level Amiga
library implementations stay Qt-free: they duck-type ``ctx.host_projection``
and never see the Qt implementation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class OpenWindowIntent:
    """One window-open intent as expressed by the compatibility layer.

    ``title`` is the decoded window title (empty string when the Amiga window
    has no title). ``rport_addr`` is the emulated ``Window.RPort`` address the
    app draws through; the projection later uses it to find the RastPort op
    stream to replay. ``idcmp`` is the window's IDCMP flag word; ``has_menu_strip``
    is true only when an Amiga menu strip has actually been attached.
    """

    window_addr: int
    title: str
    left: int
    top: int
    width: int
    height: int
    rport_addr: int
    idcmp: int = 0
    has_menu_strip: bool = False

    @property
    def is_app_facing(self) -> bool:
        """Whether this is a real application window the user should see.

        A window is app-facing when it carries a title, requests input
        (non-zero IDCMP), or has a menu strip attached. Helper / backdrop
        windows (no title, no IDCMP, no menu) stay internal / notional.
        """

        return bool(self.title) or self.idcmp != 0 or self.has_menu_strip


class HostWindowProjection(Protocol):
    """Semantic intent interface for projecting app-facing Amiga windows.

    Implementations must be callable from the library context (i.e. created and
    mutated only on the GUI thread in a real Qt-backed run). All methods are
    no-ops for unknown window addresses and idempotent for close.
    """

    def open_window(self, intent: OpenWindowIntent) -> None:
        """Project (or keep internal) one newly opened Amiga window."""

    def refresh_window(self, window_addr: int) -> None:
        """Repaint the projection for ``window_addr`` from its RastPort ops."""

    def close_window(self, window_addr: int) -> None:
        """Remove the projection for ``window_addr``. Idempotent."""

    def bind_registry(self, registry: Any) -> None:
        """Attach the run-wide RastPort op registry used to resolve replay ops."""


class NullHostWindowProjection:
    """Default no-GUI projection used by plain (headless) probes.

    Records the intents in plain lists (so the boundary is exercised and
    observable without Qt) but performs no host effect and never imports Qt.
    """

    def __init__(self) -> None:
        self.opened: list[OpenWindowIntent] = []
        self.refreshed: list[int] = []
        self.closed: list[int] = []
        self._registry: Any = None
        self._known: set[int] = set()

    def open_window(self, intent: OpenWindowIntent) -> None:
        self.opened.append(intent)
        self._known.add(intent.window_addr)

    def refresh_window(self, window_addr: int) -> None:
        # Only refresh windows that were actually opened (mirrors the real
        # projection, which has no surface for unknown windows).
        if window_addr in self._known:
            self.refreshed.append(window_addr)

    def close_window(self, window_addr: int) -> None:
        self._known.discard(window_addr)
        if window_addr not in self.closed:
            self.closed.append(window_addr)

    def bind_registry(self, registry: Any) -> None:
        self._registry = registry


def projection_from_ctx(ctx: Any) -> HostWindowProjection | None:
    """Return the host projection installed on ``ctx`` (or ``None``).

    The compatibility layer uses this helper so it never imports the
    projection module directly and degrades to no-op when no projection is
    installed (e.g. a library invoked outside the launcher).
    """

    return getattr(ctx, "host_projection", None)
