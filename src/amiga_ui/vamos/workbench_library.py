"""Repo‑owned minimal ``workbench.library`` implementation for vamos."""

from __future__ import annotations

from amitools.vamos.libcore import LibImpl


class WorkbenchLibrary(LibImpl):
    """Stub implementation enabling ``workbench.library`` to load."""

    def get_version(self) -> int:
        return 40

