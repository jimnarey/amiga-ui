"""Repo‑owned minimal ``gadtools.library`` implementation for vamos."""

from __future__ import annotations

from .base_library import BaseLibrary


class GadToolsLibrary(BaseLibrary):
    """Stub implementation enabling ``gadtools.library`` to load."""

    def get_version(self) -> int:
        """Return a plausible library version (non‑zero)."""
        return 40
