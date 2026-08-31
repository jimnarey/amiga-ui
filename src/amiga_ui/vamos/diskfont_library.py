"""Repo‑owned minimal ``diskfont.library`` implementation for vamos."""

from __future__ import annotations

from .base_library import BaseLibrary


class DiskFontLibrary(BaseLibrary):
    """Stub implementation enabling ``diskfont.library`` to load."""

    def get_version(self) -> int:
        """Return a plausible library version.

        The concrete value is not crucial; a non‑zero value suffices for
        loading.  Using the historic Workbench baseline of 40 keeps the
        implementation simple and consistent with previous libraries.
        """
        return 40
