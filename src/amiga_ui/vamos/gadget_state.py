"""Host-side registry of decoded GadTools gadget descriptions.

The ``gadtools.library`` implementation decodes each created gadget — the 68k
``struct Gadget`` geometry and kind, the ``NewGadget`` label, and the GadTools
tag-list state (cycle labels / active index, checkbox flag, text display) —
*while emulated memory is still valid*, and records the result here as an
immutable, host-safe :class:`~amiga_ui.host.projection.GadgetDescription`.

This registry is the run-wide association between an emulated ``struct Gadget *``
address and its decoded description. It is Qt-free: it stores only copied
host-safe values (strings, ints, bools), never a live emulated pointer, so the
Qt projection can later read a description and build a widget without ever
dereferencing emulated memory.

The registry is deliberately small and dumb (record / get / release): the 68k
interpretation (which fields to read, how to walk the tag list, how to walk the
gadget chain) lives in the ``vamos`` compatibility layer, not here. See
``docs/architecture/translation-pipeline.md``.
"""

from __future__ import annotations

from typing import Any

from ..host.projection import GadgetDescription


class GadgetDescriptionRegistry:
    """One shared host-side map of emulated gadget address -> decoded description.

    A single run-wide registry (installed on the library context as
    ``ctx.gadget_descriptions``) so the GadTools library (which creates and
    decodes the gadgets) and the Intuition library (which resolves a window's
    ``FirstGadget`` chain at ``OpenWindow`` time) can share the decoded state
    without either importing the other.
    """

    def __init__(self) -> None:
        # gadget addr (emulated ``struct Gadget *``) -> GadgetDescription
        self._descriptions: dict[int, GadgetDescription] = {}

    def record(self, description: GadgetDescription) -> None:
        """Record one decoded description keyed by its gadget address.

        Re-recording the same address replaces the previous description
        (``GT_SetGadgetAttrs`` can update a live gadget's state in place).
        """

        if description.gadget_addr:
            self._descriptions[description.gadget_addr] = description

    def get(self, gadget_addr: int) -> GadgetDescription | None:
        """Return the decoded description for ``gadget_addr`` (or ``None``)."""

        return self._descriptions.get(gadget_addr)

    def release(self, gadget_addr: int) -> GadgetDescription | None:
        """Remove and return the description for ``gadget_addr`` (idempotent)."""

        return self._descriptions.pop(gadget_addr, None)

    def release_all(self) -> None:
        """Drop every recorded description."""

        self._descriptions.clear()

    def all(self) -> list[GadgetDescription]:
        """All decoded descriptions, in first-recorded (insertion) order."""

        return list(self._descriptions.values())

    def __len__(self) -> int:
        return len(self._descriptions)

    def __contains__(self, gadget_addr: int) -> bool:  # type: ignore[override]
        return gadget_addr in self._descriptions


def gadget_registry_from_ctx(ctx: Any) -> GadgetDescriptionRegistry | None:
    """Return the gadget-description registry installed on ``ctx`` (or ``None``).

    The compatibility layer uses this helper so it degrades to no-op when no
    registry is installed (e.g. a library invoked outside the launcher) rather
    than importing the registry module directly.
    """

    return getattr(ctx, "gadget_descriptions", None)
