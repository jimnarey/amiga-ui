"""Registry for repo-owned vamos library implementations."""

from __future__ import annotations

from .icon_library import IconLibrary


def get_library_impl_overrides() -> dict[str, type]:
    """Return local vamos library implementations keyed by Amiga library name.

    Once a library implementation exists, register it here, for example:
        return {"icon.library": IconLibrary}

    See docs/runtime/writing-a-library-impl.md for how to write one.
    """

    return {"icon.library": IconLibrary}
