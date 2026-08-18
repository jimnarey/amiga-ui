"""Repo-owned minimal ``iffparse.library`` implementation for vamos."""

from __future__ import annotations

from amitools.vamos.libcore import LibImpl


class IffParseLibrary(LibImpl):
    """Stub implementation to satisfy the first ``iffparse.library`` load."""

    def AllocIFF(self, *args, **kwargs):
        """Return a dummy IFF handle.

        The iTidy binary merely checks for a non‑NULL handle.
        """
        return 1
    def FreeIFF(self, *args, **kwargs):
        """No‑op free.
        """
        return None

