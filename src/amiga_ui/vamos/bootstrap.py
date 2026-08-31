"""Bootstrap hooks for repo-owned vamos customisation."""

from __future__ import annotations

import importlib
from contextlib import AbstractContextManager, nullcontext


def apply_runtime_patches() -> AbstractContextManager[None]:
    """Return a context manager for temporary monkey patches.

    Prefer subclassing and registry-based overrides first. This hook exists so
    the project can add narrowly-scoped runtime patches later if vamos exposes
    no cleaner seam for a specific need.
    """

    # Monkey‑patch ExecLibrary.FreeVec to swallow unknown pointers that
    # usually arise when the iTidy binary uses a different memory model.
    try:
        exec_lib_mod = importlib.import_module("amitools.vamos.lib.ExecLibrary")
        ExecLibrary = exec_lib_mod.ExecLibrary
        original_free_vec = ExecLibrary.FreeVec

        def patched_free_vec(self, ctx):
            try:
                return original_free_vec(self, ctx)
            except Exception as e:
                msg = str(e)
                if "Unknown memory to free" in msg:
                    return None
                raise

        ExecLibrary.FreeVec = patched_free_vec
    except Exception:
        pass

    # Monkey‑patch WorkbenchLibrary for minimal screen handling
    try:
        wb_mod = importlib.import_module("amiga_ui.vamos.workbench_library")
        WorkbenchLibrary = wb_mod.WorkbenchLibrary

        # Simple dummy screen object
        class DummyScreen:
            pass

        WorkbenchLibrary.LockPubScreen = lambda self, name: DummyScreen()
        WorkbenchLibrary.UnlockPubScreen = lambda self, screen: None
        WorkbenchLibrary.OpenScreen = lambda self, *args, **kwargs: DummyScreen()
    except Exception:
        pass

    return nullcontext()
