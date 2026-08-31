"""Repo‑owned minimal ``workbench.library`` implementation for vamos."""

from __future__ import annotations

from .base_library import BaseLibrary


class WorkbenchLibrary(BaseLibrary):
    """Stub implementation enabling ``workbench.library`` to load."""

    def get_version(self) -> int:
        return 40

    def LockPubScreen(self, name):
        """Minimal stub: return `None` to indicate failure.
        iTidy expects a handle, but we just simulate failure.
        """
        return None

    def UnlockPubScreen(self, screen):
        """No-op unlock."""
        return None
