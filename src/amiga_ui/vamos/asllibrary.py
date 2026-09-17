"""Repo‑owned ``asl.library`` implementation.

Implements the classic Workbench-era ASL requester API for file/directory
selection: ``AllocAslRequest`` (requester allocation), ``AslRequestTags``
(varargs stub for AslRequest, the actual blocking call), and
``FreeAslRequest`` (requester deallocation). The implementation is host-backed
by a real ``QFileDialog`` when the app is running in the projected GUI mode
(hosted application mode); for headless (null-projected) probes, it fails
honestly with ``UnsupportedFeatureError``.
"""

from __future__ import annotations

from typing import Any

from amitools.vamos.error import UnsupportedFeatureError

from .base_library import BaseLibrary

# --- ASL request types ------------------------------------------------------
# Classic Amiga ASL request types (from <libraries/asl.h>, V36+).
# Only ASL_FileRequest is implemented for this increment.
ASL_FileRequest = 0  # File requester


# --- struct FileRequester (classic Workbench-era layout) ---------------------
# Classic layout (pre-ASLv4, no fr_Pattern): see
# docs/platform/library-cards/asl.library.md.
# The target (iTidy) uses this layout, so we mirror it exactly.
_FILE_REQUESTER_SIZE = 0x50  # classic size without fr_Pattern field

# Offsets per the classic structure.
_FR_OFF_RESERVED0 = 0x00
_FR_OFF_FILE = 0x04  # Contents of File gadget on exit (str pointer)
_FR_OFF_DRAWER = 0x08  # Contents of Drawer gadget on exit (str pointer)
_FR_OFF_RESERVED1 = 0x0C
_FR_OFF_LEFT = 0x16  # Suggested left edge
_FR_OFF_TOP = 0x18  # Suggested top edge
_FR_OFF_WIDTH = 0x1A  # Suggested width
_FR_OFF_HEIGHT = 0x1C  # Suggested height
_FR_OFF_RESERVED2 = 0x1E
_FR_OFF_NUM_ARGS = 0x20  # Number of files selected
_FR_OFF_ARG_LIST = 0x24  # List of files selected (struct WBArg *)
_FR_OFF_USER_DATA = 0x28  # Application-provided data
_FR_OFF_RESERVED3 = 0x2C  # Padding to reach fr_Pattern in newer versions


# --- File requester tag values (classic Workbench-era) ----------------------
# Tag values from <libraries/asl.h>, V36+.
# Only the subset used by the accepted target (iTidy's directory picker) are
# implemented here.
ASL_TB = 0x8000
ASLFR_TitleText = ASL_TB + 1  # Title of requester
ASLFR_PositiveText = ASL_TB + 18  # Positive gadget text (not used for dir picker)
ASLFR_NegativeText = ASL_TB + 19  # Negative gadget text (not used for dir picker)
ASLFR_Window = ASL_TB + 2  # Parent window
ASLFR_InitialLeftEdge = ASL_TB + 3  # Initial requester coordinates
ASLFR_InitialTopEdge = ASL_TB + 4  # Initial requester coordinates
ASLFR_InitialWidth = ASL_TB + 5  # Initial requester coordinates
ASLFR_InitialHeight = ASL_TB + 6  # Initial requester coordinates
ASLFR_InitialFile = ASL_TB + 8  # Initial contents of File gadget
ASLFR_InitialDrawer = ASL_TB + 9  # Initial contents of Drawer gadget
ASLFR_InitialPattern = ASL_TB + 10  # Initial contents of Pattern gadget
ASLFR_DoPatterns = ASL_TB + 46  # Display a Pattern gadget?
ASLFR_DrawersOnly = ASL_TB + 47  # Don't display files (directory-only picker)
# Tag values from <libraries/asl.h>, V36+.
# Only the subset used by the accepted target (iTidy's directory picker) are
# implemented here.
ASL_TB = 0x8000
ASLFR_TitleText = ASL_TB + 1  # Title of requester
ASLFR_PositiveText = ASL_TB + 18  # Positive gadget text (not used for dir picker)
ASLFR_NegativeText = ASL_TB + 19  # Negative gadget text (not used for dir picker)
ASLFR_InitialLeftEdge = ASL_TB + 3  # Initial requester coordinates
ASLFR_InitialTopEdge = ASL_TB + 4  # Initial requester coordinates
ASLFR_InitialWidth = ASL_TB + 5  # Initial requester coordinates
ASLFR_InitialHeight = ASL_TB + 6  # Initial requester coordinates
ASLFR_InitialFile = ASL_TB + 8  # Initial contents of File gadget
ASLFR_InitialDrawer = ASL_TB + 9  # Initial contents of Drawer gadget
ASLFR_InitialPattern = ASL_TB + 10  # Initial contents of Pattern gadget
ASLFR_DoPatterns = ASL_TB + 46  # Display a Pattern gadget?
ASLFR_DrawersOnly = ASL_TB + 47  # Don't display files (directory-only picker)


class ASLLibrary(BaseLibrary):
    """Real ``asl.library`` implementation with host-backed file/directory requesters.

    Implements ``AllocAslRequest``, ``AslRequestTags`` (the varargs stub), and
    ``FreeAslRequest`` for the classic Workbench-era ASL API.

    The host-side file/directory selection is driven by ``QFileDialog`` (see
    :mod:`~amiga_ui.host.qt_projection`). When the app is running with a host
    projection (the GUI mode), the blocking ``AslRequestTags`` call shows a real
    ``QFileDialog``, waits for the user's actual choice, and returns the real
    selected path. For headless (null-projected) probes, it raises
    ``UnsupportedFeatureError`` (honest failure rather than a fabricated path).

    This is a *Qt-free* library: it does not import PySide6, Qt, or any display
    APIs. The host projection is injected through the context.
    """

    # LVOs for classic ASL functions (from <libraries/asl.h>, V36).
    # These are the entry points the app actually calls.
    _LVO_ALLOC_ASL_REQUEST = 0x24  # AllocAslRequest (32-bit)
    _LVO_FREE_ASL_REQUEST = 0x30  # FreeAslRequest (48-bit)
    _LVO_ASL_REQUEST = 0x60  # AslRequest (96-bit) - the non-varargs entry point
    _LVO_ASL_REQUEST_TAGS = 0x66  # AslRequestTags (102-bit) - the varargs entry point

    @staticmethod
    def _tag_to_int(tag: int) -> int:
        """Tag values are UWORDs, stored in low 16 bits of the 32-bit argument.

        This helper extracts the tag value from the 32-bit argument slot.
        """
        return tag & 0xFFFF

    @staticmethod
    def _data_to_ptr(data: int) -> int:
        """Tag data values are STRPTRs, stored in low 32 bits of the 64-bit argument.

        This helper extracts the pointer from the 64-bit argument slot.
        """
        return data & 0xFFFFFFFF

    def AllocAslRequest(self, ctx: Any, reqType: int, tagList: Any) -> int:
        """Allocate an ASL file requester.

        Args:
            ctx: The emulation context (alloc, mem, host_projection).
            reqType: ASL request type (ASL_FileRequest = 0 for file/dir requester).
            tagList: Optional tag list for requester options (ignored for now).

        Returns:
            int: The emulated ``struct FileRequester *`` address (non-NULL on success),
                 or 0 on allocation failure.

        Raises:
            UnsupportedFeatureError: If ``reqType`` is not ``ASL_FileRequest``.
        """
        alloc = ctx.alloc
        mem = ctx.mem

        if reqType != ASL_FileRequest:
            raise UnsupportedFeatureError(f"ASL request type {reqType:#x} not implemented (only ASL_FileRequest)")

        # Allocate the classic FileRequester struct (0x50 bytes).
        # We use the classic layout without the fr_Pattern field.
        fr = alloc.alloc_memory(_FILE_REQUESTER_SIZE, label="ASL.FileRequester")

        # Initialize the struct to zero.
        fr_addr = fr.addr
        for i in range(_FILE_REQUESTER_SIZE):
            mem.w8(fr_addr + i, 0)

        # Set up default fields:
        # - fr_File = NULL (no file selected by default)
        # - fr_Drawer = NULL (no drawer selected by default)
        mem.w32(fr_addr + _FR_OFF_FILE, 0)
        mem.w32(fr_addr + _FR_OFF_DRAWER, 0)

        # Initial position (default: center of screen).
        mem.w16(fr_addr + _FR_OFF_LEFT, 0x0000)
        mem.w16(fr_addr + _FR_OFF_TOP, 0x0000)
        mem.w16(fr_addr + _FR_OFF_WIDTH, 0x480)  # 1152 / 2.4 ≈ 480
        mem.w16(fr_addr + _FR_OFF_HEIGHT, 0x280)  # 640 / 2.4 ≈ 280

        # Initialize tag list processing (apply initial settings, if any).
        # Only the tags used by the accepted target are decoded here.
        if tagList:
            off = 0
            for _ in range(0x100):  # bounded: max 256 tags
                item = mem.r32(tagList + off)
                data = mem.r32(tagList + off + 4)
                off += 8
                if item == 0:  # TAG_END
                    break

                tag = self._tag_to_int(item)

                if tag == ASLFR_InitialDrawer:
                    # Set initial drawer (directory) path.
                    drawer_ptr = self._data_to_ptr(data)
                    mem.w32(fr_addr + _FR_OFF_DRAWER, drawer_ptr)

                elif tag == ASLFR_InitialFile:
                    # Set initial file path (not used for directory-only picker,
                    # but we store it in fr_File for completeness).
                    file_ptr = self._data_to_ptr(data)
                    mem.w32(fr_addr + _FR_OFF_FILE, file_ptr)

                elif tag == ASLFR_DoPatterns:
                    # fr_Pattern is not part of the classic structure, so we ignore this tag.
                    # The target (iTidy) uses ASLFR_DoPatterns = FALSE for directory-only mode.
                    pass  # pragma: no cover: this tag is ignored for the classic struct

            # Note: ASLFR_DrawersOnly is an *option* that changes the host dialog behavior,
            # not a struct field. We decode it in AslRequestTags and pass it to the host.
            # ASLFR_TitleText is also an option (host dialog title).

        # Return the requester address.
        return fr_addr

    def FreeAslRequest(self, ctx: Any, requester: int) -> None:
        """Free an ASL file requester.

        Args:
            ctx: The emulation context (alloc, mem, host_projection).
            requester: The ``struct FileRequester *`` address returned by
                       ``AllocAslRequest`` (may be NULL).

        The requester must have been allocated with ``AllocAslRequest``.
        """
        alloc = ctx.alloc
        mem = ctx.mem  # noqa: F841

        if not requester:
            return  # idempotent: NULL is a no-op

        # Free the FileRequester block.
        alloc.free_memory(requester, label="ASL.FileRequester")

    def AslRequestTags(self, ctx: Any, requester: int, tagList: Any) -> bool:
        """Get user input from an ASL file/directory requester (blocking call).

        Args:
            ctx: The emulation context (alloc, mem, host_projection).
            requester: The ``struct FileRequester *`` address returned by
                       ``AllocAslRequest`` (must be non-NULL).
            tagList: Tag list for requester options (ASLFR_* tags).

        Returns:
            bool: ``TRUE`` if the user confirmed the selection (selected a drawer),
                 ``FALSE`` if the user cancelled or the dialog was aborted.

        Raises:
            UnsupportedFeatureError: If the app is running in a headless
                (null-projected) mode without a host projection.
            ValueError: If ``requester`` is NULL.

        This is the Qt-free seam: it decodes the tag list, passes the relevant
        options (title, drawers-only, initial drawer, do-patterns) to the host
        projection's ``show_file_dialog`` method, and returns the classic result
        (TRUE for confirmed, FALSE for cancelled).
        """
        mem = ctx.mem

        if not requester:
            # AllocAslRequest(NULL) should return FALSE with IoErr = ERROR_NO_FREE_STORE.
            raise UnsupportedFeatureError("ASL: AllocAslRequest(NULL) should return FALSE")

        # Decode the tag list.
        title: str | None = None
        drawers_only = False
        initial_drawer: str | None = None
        do_patterns = False
        initial_file: str | None = None

        if tagList:
            off = 0
            for _ in range(0x100):  # bounded: max 256 tags
                item = mem.r32(tagList + off)
                data = mem.r32(tagList + off + 4)
                off += 8
                if item == 0:  # TAG_END
                    break

                tag = self._tag_to_int(item)

                if tag == ASLFR_TitleText:
                    title_ptr = self._data_to_ptr(data)
                    title = self._read_cstr(ctx, title_ptr, max_len=256)

                elif tag == ASLFR_DrawersOnly:
                    drawers_only = bool(data)

                elif tag == ASLFR_DoPatterns:
                    do_patterns = bool(data)

                elif tag == ASLFR_InitialDrawer:
                    drawer_ptr = self._data_to_ptr(data)
                    initial_drawer = self._read_cstr(ctx, drawer_ptr, max_len=256)

                elif tag == ASLFR_InitialFile:
                    file_ptr = self._data_to_ptr(data)
                    initial_file = self._read_cstr(ctx, file_ptr, max_len=256)

        # Get the window the app expects the dialog to be parented to (if any).
        # The host projection needs this to parent the QFileDialog.
        window_addr: int | None = None
        if tagList:
            off = 0
            for _ in range(0x100):  # bounded: max 256 tags
                item = mem.r32(tagList + off)
                data = mem.r32(tagList + off + 4)
                off += 8
                if item == 0:  # TAG_END
                    break

                tag = self._tag_to_int(item)

                if tag == ASLFR_Window:
                    # ASLFR_Window is a struct Window *.
                    window_addr = data & 0xFFFFFFFF

        # Get the host projection and show the real file dialog.
        projection = getattr(ctx, "host_projection", None)
        if projection is None:
            raise UnsupportedFeatureError("ASL: headless mode does not support file/directory requesters")

        # Show the dialog and get the selected path (or an empty path if cancelled).
        selected_path = projection.show_file_dialog(
            window_addr=window_addr,
            title=title or "",
            initial_directory=initial_drawer or "",
            file_only=not drawers_only,
            directories_only=drawers_only,
            allow_patterns=do_patterns,
            initial_file=initial_file or "",
        )

        # Update the requester struct with the user's selection.
        # The target (iTidy) reads ``freq->fr_Drawer`` for the selected directory.
        mem.w32(requester + _FR_OFF_DRAWER, selected_path or 0)

        # Return TRUE if the user selected a directory (path != 0), FALSE if cancelled.
        return bool(selected_path)

    # For completeness, we also expose the non-varargs AslRequest entry point.
    # It's just a thin wrapper around AslRequestTags.
    def AslRequest(self, ctx: Any, requester: int, tagList: Any) -> bool:
        """Wrapper around AslRequestTags for the non-varargs entry point."""
        return self.AslRequestTags(ctx, requester, tagList)

    @staticmethod
    def _read_cstr(ctx: Any, ptr: int, max_len: int = 256) -> str:
        """Read a bounded NUL-terminated C string from 68k memory.

        Args:
            ctx: The emulation context (has mem.r8).
            ptr: The address of the C string in emulated memory.
            max_len: Maximum length to read (prevents infinite loops).

        Returns:
            str: The decoded C string (decoded from UTF-8 guest bytes).
        """
        mem = ctx.mem
        out = bytearray()
        for i in range(max_len):
            byte = mem.r8(ptr + i)
            if byte == 0:
                break
            out.append(byte)
        return out.decode("latin-1")
