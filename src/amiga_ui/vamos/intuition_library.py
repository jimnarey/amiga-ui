"""Minimal Intuition.library implementation (stub)."""

from __future__ import annotations

from .base_library import BaseLibrary


class IntuitionLibrary(BaseLibrary):
    def get_version(self) -> int:
        """Report a plausible baseline library version for Workbench 3.x startup."""
        return 39

    def LockPubScreen(self, ctx, name):
        """Minimal stub: return a plausible public screen pointer.
        iTidy expects a handle and will proceed once it gets one.

        The scanner expects (self, ctx, name) signature for proper function dispatch.
        ctx: library context pointer
        name: screen name to lock
        """
        # Return a non-None value to indicate success.
        # The actual screen pointer value isn't critical for iTidy's
        # basic operation - it just needs a truthy handle.
        return 0x10000

    def UnlockPubScreen(self, ctx, name, screen):
        """No-op unlock."""
        return None

    def OpenWindowTagList(self, ctx, newWindow, tagList):
        """Stub for OpenWindowTagList - returns a default window pointer.

        iTidy calls OpenWindowTagList to create a window during GUI initialization.
        This stub returns a default window handle to allow further initialization.
        """
        # Return a default window pointer to allow further GUI initialization
        return 0x20000

    def SetDefaultPubScreen(self, ctx, name):
        """Stub for SetDefaultPubScreen - returns success.

        iTidy calls SetDefaultPubScreen during GUI initialization.
        This stub indicates success and allows further initialization.
        """
        # Indicate success
        return 0

    def EraseImage(self, ctx, rp, image, leftOffset, topOffset):
        """Stub for EraseImage - clears a rectangle in the render pattern.

        iTidy calls EraseImage during GUI initialization.
        This stub accepts the parameters but does nothing.
        """
        # No-op stub - iTidy just needs the function to exist
        pass

    def OpenWindow(self, ctx, newWindow):
        """Stub for the classic OpenWindow entry point; iTidy uses OpenWindowTagList."""
        pass

    def CloseWindow(self, ctx, window):
        """Stub for the classic CloseWindow entry point."""
        pass
