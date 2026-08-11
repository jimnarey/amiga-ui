"""Repo-owned minimal ``icon.library`` implementation for vamos."""

from __future__ import annotations

from amitools.vamos.libcore import LibImpl


class IconLibrary(LibImpl):
    """Provide the first project-owned ``icon.library`` implementation seam."""

    def get_version(self) -> int:
        """Report a plausible baseline library version for Workbench 3.1-era startup."""

        return 40
