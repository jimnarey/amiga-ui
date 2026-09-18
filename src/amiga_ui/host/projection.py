"""Qt-independent host window- and gadget-projection boundary.

This is the seam through which the compatibility layer (``intuition.library``
and ``gadtools.library``) expresses *intent* about app-facing Amiga windows:

- a window was opened (with its title, initial geometry, RastPort and IDCMP
  flags, and the immutable, host-safe descriptions of the GadTools gadgets the
  window owns),
- a window should be repainted (the ``GT_RefreshWindow`` boundary),
- a menu strip was attached to (``SetMenuStrip``) or detached from
  (``ClearMenuStrip``) a window,
- a window was closed.

Gadget intent is carried as :class:`GadgetDescription` values — immutable,
host-safe records of one gadget's decoded state (kind, geometry, label, and
kind-specific state such as cycle labels / active index or the checkbox flag).
Menu-strip intent is carried as :class:`MenuStripDescription` — the decoded
titles, entries, and the packed classic ``MenuNumber`` a host pick must deliver
for each entry. The compatibility layer decodes the 68k ``struct Gadget`` /
``NewGadget`` and the ``struct Menu`` / ``struct MenuItem`` chains *while
emulated memory is still valid* and hands the projection only these copied
values; the Qt projection never dereferences emulated memory. The invisible
``CreateContext``/``GContext`` gadget is carried with :data:`KIND_CONTEXT` and
is never projected.

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

from amitools.vamos.error import UnsupportedFeatureError

# --- GadTools gadget kind names (host-safe) ----------------------------------
# The compatibility layer maps the numeric GadTools ``GadgetType`` (NDK 3.2
# ``libraries/gadtools.h``: BUTTON_KIND=1, CHECKBOX_KIND=2, INTEGER_KIND=3,
# LISTVIEW_KIND=4, MX_KIND=5, NUMBER_KIND=6, CYCLE_KIND=7, PALETTE_KIND=8,
# SCROLLER_KIND=9, SLIDER_KIND=11, STRING_KIND=12, TEXT_KIND=13) to one of these
# stable names. The projection switches on the name, so the numeric-to-name
# mapping stays in the Qt-free compatibility layer.
KIND_GENERIC = "generic"
KIND_BUTTON = "button"
KIND_CHECKBOX = "checkbox"
KIND_INTEGER = "integer"
KIND_LISTVIEW = "listview"
KIND_MX = "mx"
KIND_NUMBER = "number"
KIND_CYCLE = "cycle"
KIND_PALETTE = "palette"
KIND_SCROLLER = "scroller"
KIND_SLIDER = "slider"
KIND_STRING = "string"
KIND_TEXT = "text"
#: The invisible ``CreateContext``/``GContext`` gadget that heads every
#: GadTools gadget list. It is real (it owns the list and the GadTools
#: rendering context) but is never a visible control, so it is never projected.
KIND_CONTEXT = "context"
#: A gadget whose ``GadgetType`` is not one this increment decodes.
KIND_UNSUPPORTED = "unsupported"

#: The kinds the host projection renders as widgets in this increment. Every
#: other kind name (including :data:`KIND_CONTEXT`) is recorded but not
#: projected.
PROJECTABLE_KINDS: frozenset[str] = frozenset({KIND_BUTTON, KIND_TEXT, KIND_CYCLE, KIND_CHECKBOX})


@dataclass(frozen=True)
class GadgetDescription:
    """Immutable, host-safe description of one Amiga gadget.

    Decoded by the compatibility layer (``gadtools.library``) while emulated
    memory is still valid. It carries only host-safe values (strings, ints,
    bools) — never a raw emulated-memory pointer — so the Qt projection can
    build its widgets without dereferencing emulated memory after the target
    phase.

    ``gadget_addr`` is the emulated ``struct Gadget *`` retained purely as an
    identity key for window association and per-window release; the host never
    dereferences it. ``kind`` is the raw numeric ``GadgetType`` (retained for
    fidelity); ``kind_name`` is the host-safe name the projection switches on.

    Kind-specific fields are ``None``/empty for kinds that do not use them:
    ``checked`` for :data:`KIND_CHECKBOX`, ``cycle_labels``/``cycle_active``
    for :data:`KIND_CYCLE`, and ``text``/``text_border`` for :data:`KIND_TEXT`.
    """

    gadget_addr: int
    gadget_id: int
    kind_name: str
    kind: int
    left: int
    top: int
    width: int
    height: int
    label: str
    enabled: bool = True
    # CHECKBOX_KIND:
    checked: bool | None = None
    # CYCLE_KIND:
    cycle_labels: tuple[str, ...] = ()
    cycle_active: int = 0
    # TEXT_KIND:
    text: str | None = None
    text_border: bool | None = None

    @property
    def is_projectable(self) -> bool:
        """Whether the host projection renders this kind as a widget.

        The context gadget and any kind outside :data:`PROJECTABLE_KINDS` are
        recorded (so the boundary is honest) but never projected.
        """

        return self.kind_name in PROJECTABLE_KINDS


@dataclass(frozen=True)
class MenuEntryDescription:
    """Immutable, host-safe description of one entry of an Amiga menu.

    Decoded by the compatibility layer (``gadtools.library``, which created the
    real ``struct MenuItem``) while emulated memory is still valid.

    ``code`` is the packed classic ``MenuNumber`` Intuition would deliver for
    this entry — the value a host menu pick must carry in ``IntuiMessage.Code``
    so the app's own ``ItemAddress(strip, Code)`` resolves back to this very
    item. ``item_data`` is what the app reads back through
    ``GTMENUITEM_USERDATA(item)``; it is carried for observation only, never
    interpreted by the host. ``item_addr`` is the emulated ``struct MenuItem *``
    kept purely as an identity key.

    A classic separator bar (``NM_BARLABEL``) has an empty ``label`` and
    :attr:`is_separator` set; it is projected as a separator, never as a
    triggerable action. ``sub_items`` carries the optional third level
    (``NM_SUB`` entries): each sub-entry has its own packed ``code`` — with the
    sub-item field set — and is projected as a nested host menu.
    """

    item_addr: int
    code: int
    label: str = ""
    is_separator: bool = False
    command_key: str = ""
    item_data: int = 0
    sub_items: tuple[MenuEntryDescription, ...] = ()

    @property
    def is_selectable(self) -> bool:
        """Whether picking this entry is an action the app can be told about.

        A separator bar is never an action, and neither is a plain title that
        only opens a sub-menu — only a leaf entry with a label is.
        """

        return not self.is_separator and bool(self.label) and not self.sub_items


@dataclass(frozen=True)
class MenuTitleDescription:
    """One top-level menu of a strip: its decoded title and its entries."""

    title: str
    items: tuple[MenuEntryDescription, ...] = ()


@dataclass(frozen=True)
class MenuStripDescription:
    """Immutable, host-safe description of a whole ``struct Menu`` strip.

    ``strip_addr`` is the emulated ``struct Menu *`` (identity key only).
    ``entry_count`` is the total number of decoded entries — separators
    included — so a host can report what it attached without re-walking
    anything.
    """

    strip_addr: int = 0
    menus: tuple[MenuTitleDescription, ...] = ()
    entry_count: int = 0


@dataclass
class OpenWindowIntent:
    """One window-open intent as expressed by the compatibility layer.

    ``title`` is the decoded window title (empty string when the Amiga window
    has no title). ``rport_addr`` is the emulated ``Window.RPort`` address the
    app draws through; the projection later uses it to find the RastPort op
    stream to replay. ``idcmp`` is the window's IDCMP flag word; ``has_menu_strip``
    is true only when an Amiga menu strip has actually been attached.

    ``gadgets`` carries the immutable, host-safe descriptions of the GadTools
    gadgets this window owns (resolved from the window's real
    ``FirstGadget`` chain). Only projectable kinds are expected here — the
    invisible context gadget and any unsupported kind are excluded by the
    compatibility layer before the intent is expressed — but the projection
    double-checks :meth:`GadgetDescription.is_projectable` before building a
    widget. Each window receives only its own gadgets.
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
    gadgets: tuple[GadgetDescription, ...] = ()

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

    def set_menu_strip(self, window_addr: int, strip: MenuStripDescription) -> None:
        """Attach a decoded Amiga menu strip to ``window_addr``'s projection.

        Called by ``intuition.library`` from ``SetMenuStrip``, i.e. usually
        *after* the window was opened. A projection that has no host window for
        ``window_addr`` records nothing and returns; a real projection shows the
        strip as the host window's menu bar (the Amiga menu bar belongs to its
        window, never to a shared/native application menu bar).
        """

    def clear_menu_strip(self, window_addr: int) -> None:
        """Detach the menu strip of ``window_addr``'s projection. Idempotent."""

    def bind_registry(self, registry: Any) -> None:
        """Attach the run-wide RastPort op registry used to resolve replay ops."""

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
        """Present the app's ASL file/directory requester and await the user's choice.

        The host half of ``asl.library``'s blocking ``AslRequest``: the caller
        (the Qt-free ASL library) has already decoded the app's tag list into
        host-safe values; the projection presents a real picker carrying them
        and returns the user's actual selection as a host path, or ``None``
        if the user cancelled. Implementations without a host dialog surface
        must raise :class:`UnsupportedFeatureError` rather than invent an
        answer the app would branch on.
        """


class NullHostWindowProjection:
    """Default no-GUI projection used by plain (headless) probes.

    Records the intents in plain lists (so the boundary is exercised and
    observable without Qt) but performs no host effect and never imports Qt.
    """

    def __init__(self) -> None:
        self.opened: list[OpenWindowIntent] = []
        self.refreshed: list[int] = []
        self.closed: list[int] = []
        # window addr -> the decoded strip last attached to it (only known
        # windows can hold one; a clear removes it and is recorded).
        self.strips: dict[int, MenuStripDescription] = {}
        self.strips_cleared: list[int] = []
        # the decoded file-requester intents seen (so the boundary is
        # observable even though a headless run cannot present one; see
        # show_file_dialog).
        self.file_dialog_requests: list[dict[str, Any]] = []
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
        self.strips.pop(window_addr, None)
        if window_addr not in self.closed:
            self.closed.append(window_addr)

    def set_menu_strip(self, window_addr: int, strip: MenuStripDescription) -> None:
        # Mirrors the real projection: a strip only attaches to a window that
        # was actually opened here.
        if window_addr in self._known:
            self.strips[window_addr] = strip

    def clear_menu_strip(self, window_addr: int) -> None:
        if self.strips.pop(window_addr, None) is not None and window_addr not in self.strips_cleared:
            self.strips_cleared.append(window_addr)

    def bind_registry(self, registry: Any) -> None:
        self._registry = registry

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
        """Record the requester intent, then fail honestly — there is no host dialog.

        A headless run has no user to answer the requester. Returning
        ``None`` here would *fabricate* a cancel the user never made and let
        the app silently take its cancel branch, so the documented boundary
        is the error: :class:`UnsupportedFeatureError`, not a bare
        ``AttributeError`` from a missing method. The decoded intent is still
        recorded first, so probes can observe exactly what the app asked for.
        """
        self.file_dialog_requests.append(
            {
                "window_addr": window_addr,
                "title": title,
                "initial_directory": initial_directory,
                "directories_only": directories_only,
                "save_mode": save_mode,
                "allow_patterns": allow_patterns,
                "initial_file": initial_file,
            }
        )
        raise UnsupportedFeatureError(
            f"NullHostWindowProjection: no host dialog to present the app's file requester {title!r} on"
        )


def projection_from_ctx(ctx: Any) -> HostWindowProjection | None:
    """Return the host projection installed on ``ctx`` (or ``None``).

    The compatibility layer uses this helper so it never imports the
    projection module directly and degrades to no-op when no projection is
    installed (e.g. a library invoked outside the launcher).
    """

    return getattr(ctx, "host_projection", None)
