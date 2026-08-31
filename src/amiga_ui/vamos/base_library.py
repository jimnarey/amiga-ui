"""Repo-owned base class for ``vamos`` library implementations."""

from __future__ import annotations

from amitools.vamos.libcore import LibImpl


class BaseLibrary(LibImpl):
    """Base for repo-owned ``vamos`` library implementations.

    Upstream ``LibImpl.get_version`` carries no return annotation, so the
    type checker infers a literal return type from its body and rejects a
    plain ``-> int`` override on a direct ``LibImpl`` subclass. Re-announcing
    the method here — with a single documented suppression for the upstream
    mismatch — lets every repo library override ``get_version`` with an
    ordinary ``int``.
    """

    def get_version(self) -> int:  # pyright: ignore[reportIncompatibleMethodOverride]
        """Report the historic Workbench 3.x baseline library version."""
        return 40
