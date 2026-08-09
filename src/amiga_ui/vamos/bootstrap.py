"""Bootstrap hooks for repo-owned vamos customisation."""

from __future__ import annotations

from contextlib import nullcontext
from typing import ContextManager


def apply_runtime_patches() -> ContextManager[None]:
    """Return a context manager for temporary monkey patches.

    Prefer subclassing and registry-based overrides first. This hook exists so
    the project can add narrowly-scoped runtime patches later if vamos exposes
    no cleaner seam for a specific need.
    """

    return nullcontext()

