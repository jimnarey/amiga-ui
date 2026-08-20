"""Minimal Intuition.library implementation (stub)."""

from __future__ import annotations

from amitools.vamos.libcore import LibImpl

class IntuitionLibrary(LibImpl):
    def get_version(self) -> int:
        """Report a plausible baseline library version for Workbench 3.x startup."""
        return 39

    # Placeholder
    def OpenWindow(self):
        pass

    def CloseWindow(self):
        pass