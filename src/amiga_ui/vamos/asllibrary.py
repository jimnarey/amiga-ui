"""Repo-owned ``asl.library`` implementation.

Implements the classic Workbench-era ASL file-requester API:

- ``AllocAslRequest`` (LVO -48) — allocate a ``struct FileRequester`` and
  apply its initialization tags,
- ``FreeAslRequest`` (LVO -54) — release a requester,
- ``AslRequest`` (LVO -60) — the blocking "show the requester, wait for the
  user's choice" call.

The LVO values above are taken from ``FD/asl_lib.fd`` and
``Include_H/inline/asl.h`` of the repo-local NDK (see ``docs/sources.md``).
The ``AllocAslRequestTags`` / ``AslRequestTags`` spellings the app source uses
are *not* library entry points: they are inline varargs wrappers compiled into
the app (``Include_H/inline/asl.h``) that build a tag list on the stack and
call ``AllocAslRequest`` / ``AslRequest``. At the vamos seam only the three
FD symbols above arrive. (``AslRequestTags`` is kept below as a thin alias of
``AslRequest`` for callers that resolve it by name; it delegates, it does not
duplicate behavior.)

The implementation is host-backed by a real ``QFileDialog`` when the app runs
in projected GUI mode (hosted application mode): the dialog is the user's
actual choice point, and the returned result is the user's actual answer. For
headless (null-projected) probes it fails honestly with
``UnsupportedFeatureError`` — never a fabricated path or default answer.

Strings crossing the seam use Latin-1, the classic Amiga 8-bit byte
encoding — the same encoding every other repo library implementation uses for
guest-memory C strings. Host paths outside Latin-1 are transliterated with
``?`` on the way into guest memory (an explicit, visible loss, not a silent
one).
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from amitools.vamos.error import UnsupportedFeatureError

from .base_library import BaseLibrary

# --- ASL request types ------------------------------------------------------
# From <libraries/asl.h> (NDK). Only ASL_FileRequest is implemented.
ASL_FileRequest = 0  # file/directory requester
ASL_FontRequest = 1  # (not implemented)
ASL_ScreenModeRequest = 2  # (not implemented)


# --- TagItem control values ---------------------------------------------------
# From <utility/tagitem.h> (NDK). These are *positive* small values; user tags
# carry the TAG_USER bit. Treating them as negative (or masking tags down to
# 16 bits) silently mis-parses every real tag list.
TAG_DONE = 0x00000000  # end of this tag list
TAG_IGNORE = 0x00000001  # this item is to be ignored
TAG_MORE = 0x00000002  # data is a pointer to another tag item list
TAG_SKIP = 0x00000003  # skip <data> tag items
TAG_USER = 0x80000000  # (1UL << 31)


# --- File requester tag values -------------------------------------------------
# <libraries/asl.h>: ``#define ASL_TB (TAG_USER+0x80000)`` — the full 32-bit
# tag base is 0x80080000. Tag items store the full 32-bit tag in the item
# field; there is no 16-bit masking anywhere in the classic tag protocol.
ASL_TB = TAG_USER + 0x80000  # 0x80080000

# Window control
ASLFR_TitleText = ASL_TB + 1  # STRPTR: title of requester
ASLFR_Window = ASL_TB + 2  # struct Window *: parent window
ASLFR_InitialLeftEdge = ASL_TB + 3  # initial requester coordinates
ASLFR_InitialTopEdge = ASL_TB + 4
ASLFR_InitialWidth = ASL_TB + 5  # initial requester dimensions
ASLFR_InitialHeight = ASL_TB + 6
ASLFR_InitialFile = ASL_TB + 8  # STRPTR: initial contents of File gadget
ASLFR_InitialDrawer = ASL_TB + 9  # STRPTR: initial contents of Drawer gadget
ASLFR_InitialPattern = ASL_TB + 10  # STRPTR: initial contents of Pattern gadget
ASLFR_PositiveText = ASL_TB + 18  # STRPTR: positive gadget text
ASLFR_NegativeText = ASL_TB + 19  # STRPTR: negative gadget text

# Options and filtering
ASLFR_DoSaveMode = ASL_TB + 44  # BOOL: requester used for saving
ASLFR_DoPatterns = ASL_TB + 46  # BOOL: display a Pattern gadget
ASLFR_DrawersOnly = ASL_TB + 47  # BOOL: don't display files (dir-only picker)
ASLFR_RejectIcons = ASL_TB + 60  # BOOL: hide .info icon files
ASLFR_UserData = ASL_TB + 52  # APTR: value to place in fr_UserData


# --- struct FileRequester layout -----------------------------------------------
# Layout per <libraries/asl.h> (NDK 3.2, the only FileRequester header in the
# repo): fr_Reserved0[4], fr_File (0x04), fr_Drawer (0x08), fr_Reserved1[10],
# fr_LeftEdge (0x16), fr_TopEdge (0x18), fr_Width (0x1A), fr_Height (0x1C),
# fr_Reserved2[2], fr_NumArgs (0x20), fr_ArgList (0x24), fr_UserData (0x28),
# fr_Reserved3[8], fr_Pattern (0x34) — size 0x38.
#
# Provenance caveat (see docs/sources.md): the NDK 3.2 header documents ASL
# 3.9; the OS 3.0-3.1 era (V36) header lacks the trailing fr_Pattern field
# (size 0x34). Every field *before* fr_Pattern is byte-identical between the
# two, and the accepted target (iTidy) only reads fr_File/fr_Drawer, both in
# the shared prefix. Allocating the larger documented size keeps reads safe
# under either header generation.
_FILE_REQUESTER_SIZE = 0x38

_FR_OFF_FILE = 0x04  # STRPTR: contents of File gadget on exit
_FR_OFF_DRAWER = 0x08  # STRPTR: contents of Drawer gadget on exit
_FR_OFF_LEFT = 0x16  # WORD: requester left edge on exit
_FR_OFF_TOP = 0x18  # WORD: requester top edge on exit
_FR_OFF_WIDTH = 0x1A  # WORD: requester width on exit
_FR_OFF_HEIGHT = 0x1C  # WORD: requester height on exit
_FR_OFF_NUM_ARGS = 0x20  # LONG: number of files selected
_FR_OFF_ARG_LIST = 0x24  # struct WBArg *: list of files selected
_FR_OFF_USER_DATA = 0x28  # APTR: application data
_FR_OFF_PATTERN = 0x34  # STRPTR: contents of Pattern gadget on exit


def _iter_tag_items(mem: Any, tag_list: int, max_items: int = 0x100) -> Iterator[tuple[int, int]]:
    """Walk a classic tag list once, yielding ``(tag, data)`` pairs.

    Implements the ``TagItem`` protocol from <utility/tagitem.h>:

    - ``TAG_DONE`` ends the traversal,
    - ``TAG_IGNORE`` skips one item,
    - ``TAG_MORE`` chains to the tag list whose address is the item's data,
    - ``TAG_SKIP`` skips ``data`` further items.

    ``max_items`` bounds the walk so a malformed (unterminated) list cannot
    loop forever. This single scan serves every consumer; callers must not
    re-walk the list per tag.
    """
    if not tag_list:
        return
    addr = tag_list
    seen = 0
    while addr:
        while True:
            if seen >= max_items:
                return
            tag = mem.r32(addr)
            data = mem.r32(addr + 4)
            addr += 8
            seen += 1
            if tag == TAG_DONE:
                return
            if tag == TAG_IGNORE:
                continue
            if tag == TAG_MORE:
                addr = data  # chain to the next list
                break
            if tag == TAG_SKIP:
                skip = data & 0xFFFFFFFF
                if skip >= max_items or seen + skip >= max_items:
                    return
                addr += skip * 8
                seen += skip
                continue
            yield tag, data


@dataclass
class _RequesterRecord:
    """Library-side state of one allocated ``struct FileRequester``.

    ASL owns the requester across ``AllocAslRequest`` → ``AslRequest`` →
    ``FreeAslRequest``: tags passed at *alloc* time initialize it, tags
    passed at *request* time override them, and the strings ASL allocates
    (copies of the initial values, and the selection result) stay owned by
    ASL until ``FreeAslRequest`` releases the whole record. Keeping this
    bookkeeping per-requester also means ``AslRequest(freq, NULL)`` — the way
    iTidy's Open/Save menu handlers call it after
    ``AllocAslRequestTags`` — sees the options the app passed at alloc time.
    """

    block: Any  # the Memory object backing the struct
    title: str | None = None
    positive_text: str | None = None
    negative_text: str | None = None
    initial_drawer: str | None = None
    initial_file: str | None = None
    pattern: str | None = None
    window_addr: int = 0
    drawers_only: bool = False
    do_patterns: bool = False
    save_mode: bool = False
    reject_icons: bool = False
    user_data: int = 0
    # Strings allocated by ASL (initial-value copies and result strings);
    # freed with the requester.
    owned_strings: list[Any] = field(default_factory=list)


class ASLLibrary(BaseLibrary):
    """Real ``asl.library`` implementation with host-backed file requesters.

    The host-side selection is driven by ``QFileDialog`` through the
    projection's ``show_file_dialog`` seam (see
    :mod:`amiga_ui.host.qt_projection`). In GUI (projected) mode the blocking
    ``AslRequest`` shows a real ``QFileDialog``, waits for the user's real
    choice, writes the real selection into ``fr_Drawer``/``fr_File``, and
    returns TRUE — or leaves the struct untouched and returns FALSE on
    cancel. In headless (null-projected) mode the projection raises
    ``UnsupportedFeatureError``; nothing is fabricated.

    This is a *Qt-free* library: it never imports PySide6 or any display API.
    The projection arrives through the context (``ctx.host_projection``), and
    only host-safe values (strings, ints, bools) cross the seam in either
    direction — the projection never touches emulated memory, and the string
    allocation for the selection result happens here, in the library.
    """

    def __init__(self) -> None:
        # requester address -> _RequesterRecord for every live requester.
        self._requesters: dict[int, _RequesterRecord] = {}

    # -- string helpers (Latin-1: the classic Amiga 8-bit byte encoding) -----

    @staticmethod
    def _read_cstr(ctx: Any, ptr: int, max_len: int = 1024) -> str:
        """Read a bounded NUL-terminated C string from guest memory.

        Bytes are decoded as Latin-1 — the same encoding every other repo
        library implementation uses for guest C strings (the classic Amiga
        character set is 8-bit; see ``docs/sources.md``).

        Args:
            ctx: The emulation context (provides ``mem.r8``).
            ptr: Address of the C string in emulated memory.
            max_len: Read bound (a runaway/unterminated string cannot hang us).

        Returns:
            str: The decoded string (empty for a NULL pointer).
        """
        if not ptr:
            return ""
        mem = ctx.mem
        out = bytearray()
        for i in range(max_len):
            byte = mem.r8(ptr + i)
            if byte == 0:
                break
            out.append(byte)
        return out.decode("latin-1")

    def _alloc_cstring(self, ctx: Any, record: _RequesterRecord, text: str, label: str) -> int:
        """Copy ``text`` into ASL-owned emulated memory; return its address.

        Encodes as Latin-1 (the counterpart of :meth:`_read_cstr`); host
        characters outside Latin-1 degrade to ``?`` — the same lossy
        narrowing a classic 8-bit filesystem path would apply. The allocated
        block is tracked in ``record.owned_strings`` and released by
        :meth:`FreeAslRequest`.
        """
        raw = text.encode("latin-1", errors="replace")
        block = ctx.alloc.alloc_memory(len(raw) + 1, label=label)
        mem = ctx.mem
        for i, byte in enumerate(raw):
            mem.w8(block.addr + i, byte)
        mem.w8(block.addr + len(raw), 0)
        record.owned_strings.append(block)
        return block.addr

    # -- LVO AllocAslRequest (-48) ---------------------------------------------

    def AllocAslRequest(self, ctx, reqType, tagList):
        """``AllocAslRequest(reqType, tagList)`` (LVO -48).

        Allocates a zero-initialized ``struct FileRequester`` (the real ASL
        allocates it ``MEMF_CLEAR``) and applies the initialization tags.
        Geometry fields (fr_LeftEdge/Top/Width/Height) stay 0 until the
        requester has actually been opened — we never invent screen geometry.

        Tags whose data is a string (``ASLFR_InitialDrawer``,
        ``ASLFR_InitialFile``) are *copied* into ASL-owned memory, mirroring
        the real requester, which owns its gadget buffers; the app's own
        pointers may dangle once the app's stack frame goes away, so aliasing
        them into the struct would be wrong.

        Returns:
            int: The emulated ``struct FileRequester *`` (never NULL here —
            allocation failure would raise, not return 0 silently).

        Raises:
            UnsupportedFeatureError: If ``reqType`` is not ``ASL_FileRequest``.
        """
        if reqType != ASL_FileRequest:
            raise UnsupportedFeatureError(
                f"ASL: request type {reqType} not implemented (only ASL_FileRequest is supported)"
            )

        alloc = ctx.alloc
        mem = ctx.mem

        block = alloc.alloc_memory(_FILE_REQUESTER_SIZE, label="ASL.FileRequester")
        fr_addr = block.addr

        # struct FileRequester * is READ-ONLY for the app (ASL owns it); start
        # fully cleared like the real MEMF_CLEAR allocation.
        for i in range(_FILE_REQUESTER_SIZE):
            mem.w8(fr_addr + i, 0)

        record = _RequesterRecord(block=block)
        self._requesters[fr_addr] = record

        # Single scan: apply every initialization tag from the list.
        for tag, data in _iter_tag_items(mem, tagList or 0):
            if tag == ASLFR_TitleText:
                record.title = self._read_cstr(ctx, data)
            elif tag == ASLFR_PositiveText:
                record.positive_text = self._read_cstr(ctx, data)
            elif tag == ASLFR_NegativeText:
                record.negative_text = self._read_cstr(ctx, data)
            elif tag == ASLFR_InitialDrawer:
                record.initial_drawer = self._read_cstr(ctx, data)
                if record.initial_drawer is not None:
                    mem.w32(
                        fr_addr + _FR_OFF_DRAWER,
                        self._alloc_cstring(ctx, record, record.initial_drawer, "ASL.InitialDrawer"),
                    )
            elif tag == ASLFR_InitialFile:
                record.initial_file = self._read_cstr(ctx, data)
                if record.initial_file is not None:
                    mem.w32(
                        fr_addr + _FR_OFF_FILE, self._alloc_cstring(ctx, record, record.initial_file, "ASL.InitialFile")
                    )
            elif tag == ASLFR_InitialPattern:
                record.pattern = self._read_cstr(ctx, data)
                if record.pattern is not None:
                    mem.w32(
                        fr_addr + _FR_OFF_PATTERN,
                        self._alloc_cstring(ctx, record, record.pattern, "ASL.InitialPattern"),
                    )
            elif tag == ASLFR_Window:
                record.window_addr = data
            elif tag == ASLFR_DrawersOnly:
                record.drawers_only = bool(data)
            elif tag == ASLFR_DoPatterns:
                record.do_patterns = bool(data)
            elif tag == ASLFR_DoSaveMode:
                record.save_mode = bool(data)
            elif tag == ASLFR_RejectIcons:
                record.reject_icons = bool(data)
            elif tag == ASLFR_UserData:
                record.user_data = data
                mem.w32(fr_addr + _FR_OFF_USER_DATA, data)
            # Other ASLFR_* tags (fonts, sort order, multi-select, filter
            # hooks, V44+ extensions) are accepted-and-ignored at this seam;
            # they only affect classic requester presentation.

        return fr_addr

    # -- LVO FreeAslRequest (-54) -------------------------------------------------

    def FreeAslRequest(self, ctx, requester):
        """``FreeAslRequest(requester)`` (LVO -54).

        Releases the requester struct and every string ASL allocated for it
        (initial-value copies and selection results). A NULL requester is a
        no-op, matching the classic API; freeing an unknown address is
        likewise a no-op rather than a crash (the app may double-free after
        an allocation-failure path).
        """
        if not requester:
            return  # classic: NULL is a legal, ignored argument

        record = self._requesters.pop(requester, None)
        alloc = ctx.alloc

        if record is not None:
            for block in record.owned_strings:
                alloc.free_memory(block)
            record.owned_strings.clear()
            alloc.free_memory(record.block)
            return

        # Unknown address: still try to release a tracked block (e.g. a
        # requester allocated before this library instance existed), but a
        # double-free must not crash the app.
        block = alloc.get_memory(requester)
        if block is not None:
            alloc.free_memory(block)

    # -- LVO AslRequest (-60) --------------------------------------------------------

    def AslRequest(self, ctx, requester, tagList):
        """``AslRequest(requester, tagList)`` (LVO -60) — the blocking call.

        Merges the request-time tags over the requester's alloc-time state,
        presents the app's requester as a real host file dialog through the
        projection's ``show_file_dialog`` seam, waits for the user's real
        choice, and maps it to the classic result:

        - confirmed: the selected path is split into drawer/file parts,
          copied into ASL-owned emulated memory, written to
          ``fr_Drawer``/``fr_File``, and TRUE is returned;
        - cancelled: the struct is left untouched (the classic requester
          does not rewrite its gadgets on cancel) and FALSE is returned.

        Args:
            ctx: The emulation context (provides ``alloc``, ``mem``,
                ``host_projection``).
            requester: The ``struct FileRequester *`` from AllocAslRequest.
            tagList: Request-time tags (may be NULL — the app may pass all
                options at ``AllocAslRequestTags`` time and call
                ``AslRequest(freq, NULL)``, as iTidy's menu handlers do).

        Returns:
            bool: TRUE on confirmed selection, FALSE on cancel. A NULL
                requester always yields FALSE, per the documented contract
                ("If this parameter is NULL, this function will always return
                FALSE") [S71 AslRequest]; the IoErr detail is not emulated.

        Raises:
            ValueError: If ``requester`` is a non-NULL address that was not
                allocated by us — writing into arbitrary guest memory is not
                an option, and failing loudly beats corrupting the app.
            UnsupportedFeatureError: If no host projection can present the
                requester (the null projection raises it on its side).
        """
        if not requester:
            # Documented behavior: NULL requester -> FALSE, never a crash.
            return False

        record = self._requesters.get(requester)
        if record is None:
            # The pointer did not come from our AllocAslRequest; we cannot
            # know its state, and writing into arbitrary memory is not an
            # option. Fail loudly instead of guessing.
            raise ValueError(f"AslRequest: {requester:#010x} was not allocated by AllocAslRequest")

        mem = ctx.mem

        # Request-time tags override the alloc-time state; single scan.
        title = record.title
        initial_drawer = record.initial_drawer
        initial_file = record.initial_file
        window_addr = record.window_addr
        drawers_only = record.drawers_only
        do_patterns = record.do_patterns
        save_mode = record.save_mode
        for tag, data in _iter_tag_items(mem, tagList or 0):
            if tag == ASLFR_TitleText:
                title = self._read_cstr(ctx, data)
            elif tag == ASLFR_InitialDrawer:
                initial_drawer = self._read_cstr(ctx, data)
            elif tag == ASLFR_InitialFile:
                initial_file = self._read_cstr(ctx, data)
            elif tag == ASLFR_Window:
                window_addr = data
            elif tag == ASLFR_DrawersOnly:
                drawers_only = bool(data)
            elif tag == ASLFR_DoPatterns:
                do_patterns = bool(data)
            elif tag == ASLFR_DoSaveMode:
                save_mode = bool(data)

        projection = getattr(ctx, "host_projection", None)
        if projection is None:
            # Honest headless boundary: there is no host surface to present
            # the requester on. Failing beats fabricating a selection the app
            # would branch on. (The launcher always installs a projection;
            # the *null* projection raises UnsupportedFeatureError itself —
            # see NullHostWindowProjection.show_file_dialog.)
            raise UnsupportedFeatureError("ASL: no host projection to present the requester on")

        selected = projection.show_file_dialog(
            window_addr=window_addr or None,
            title=title or "",
            initial_directory=initial_drawer or "",
            directories_only=drawers_only,
            save_mode=save_mode,
            allow_patterns=do_patterns,
            initial_file=initial_file or "",
        )

        if selected is None:
            # Cancelled: the classic requester leaves fr_File/fr_Drawer as they
            # were; the app branches on our FALSE.
            return False

        # Confirmed. Split the host path the way ASL fills its two gadgets:
        # a drawer-only picker yields the whole choice as the drawer; a file
        # picker yields the containing directory and the file name.
        if drawers_only:
            drawer, file_part = selected, ""
        else:
            drawer, file_part = os.path.split(selected)

        mem.w32(requester + _FR_OFF_DRAWER, self._alloc_cstring(ctx, record, drawer, "ASL.ResultDrawer"))
        mem.w32(requester + _FR_OFF_FILE, self._alloc_cstring(ctx, record, file_part, "ASL.ResultFile"))
        return True

    # ``AslRequestTags`` is not an asl.library LVO: it is the app-side inline
    # varargs wrapper from Include_H/inline/asl.h. It is kept only as an
    # alias so any caller resolving the wrapper's name lands on the real
    # entry point; behavior (and documentation) live on AslRequest.
    def AslRequestTags(self, ctx, requester, tagList):
        """Alias of :meth:`AslRequest` (see the note above)."""
        return self.AslRequest(ctx, requester, tagList)
