"""Repo-owned minimal ``iffparse.library`` implementation for vamos."""

from __future__ import annotations

from amitools.vamos.libcore import LibImpl


class IffParseLibrary(LibImpl):
    """Stub implementation to satisfy the first ``iffparse.library`` load."""

    def get_version(self) -> int:
        """Report a baseline library version.

        The exact value is not critical for initial loading; Workbench expects
        a non‑zero value.  Returning 40 mirrors the baseline used for
        icon.library.
        """
        return 40

