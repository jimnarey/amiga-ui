"""Repo‑owned minimal ``asl.library`` implementation for vamos."""

from __future__ import annotations

from .base_library import BaseLibrary


class ASLLibrary(BaseLibrary):
    """Stub implementation enabling ``asl.library`` to load.

    This allows the app to advance past library startup without
    actually implementing the full file requester API.  When asl.library
    is loaded it returns a non-zero version that lets the next probe
    discover what specific ASL calls are actually needed by the target
    application.
    """

    def get_version(self) -> int:
        """Return a plausible library version for Workbench 3.x."""
        # Use the same baseline as other stub libraries for consistency.
        return 40
