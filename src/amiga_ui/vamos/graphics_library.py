"""Repo-owned minimal ``graphics.library`` implementation for vamos."""

from __future__ import annotations

from amitools.vamos.libcore import LibImpl


class GraphicsLibrary(LibImpl):
    """Provide the first project-owned ``graphics.library`` implementation seam."""

    def get_version(self) -> int:
        """Report a plausible baseline library version for Workbench 3.x startup."""
        # Use the same baseline as icon.library for consistency.
        return 40

