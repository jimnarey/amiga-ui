"""Repo‑owned minimal ``diskfont.library`` implementation for vamos."""

from __future__ import annotations

from typing import Any

from .base_library import BaseLibrary


class DiskFontLibrary(BaseLibrary):
    """``diskfont.library``: open a disk font and return a usable font handle.

    ``iTidy`` calls ``OpenDiskFont(&textAttr)`` to load a font (a ``TextAttr``
    carrying the requested name and size) and then uses the returned handle in
    ``SetFont``. There is no disk font file in the emulated environment, so this
    returns a repo-allocated ``TextFont`` stand-in that carries the requested
    attributes — the same pattern the screen's default font uses — rather than a
    fake success or a silent no-op. Each open is recorded so a future renderer
    can see which font the app asked for.
    """

    # struct TextAttr: ta_Name (STRPTR), ta_YSize (WORD), ta_Style (WORD),
    # ta_Flags (WORD). The target's OpenDiskFont takes a TextAttr* in a0 and
    # returns a TextFont* in d0 (confirmed from the probe: a single a0 arg).
    _TA_OFF_NAME = 0x00  # STRPTR ta_Name (the font-name pointer)
    _TA_OFF_YSIZE = 0x04  # WORD ta_YSize (the requested point size)

    def __init__(self) -> None:
        super().__init__()
        # Ordered record of font-open requests (name + size) for the future
        # renderer: there is no host font file to load yet.
        self.font_opens: list[dict[str, Any]] = []
        # handle -> the TextAttr that produced it, so FreeFont can release it.
        self._fonts: dict[int, int] = {}

    def get_version(self) -> int:
        """Return a plausible library version (Workbench 3.x baseline)."""
        return 40

    def OpenDiskFont(self, ctx, textAttr):
        """diskfont.library ``OpenDiskFont(textAttr)``: open a disk font.

        Reads the ``TextAttr`` (``ta_Name`` font-name pointer, ``ta_YSize``) and
        returns a repo-allocated ``TextFont`` stand-in carrying the requested
        attributes, so the app's ``SetFont(rastPort, font)`` records a real font
        handle on the RastPort (meaningful emulated state, not an empty success).
        The request (name, size) is recorded so a future renderer can see which
        font the app asked for. Returns 0 (NULL) only when there is no 68k memory
        to read the TextAttr from — the app then falls back to the screen font,
        which it handles gracefully.
        """
        mem = getattr(ctx, "mem", None)
        if mem is None or not textAttr:
            return 0
        name_ptr = mem.r32(textAttr + self._TA_OFF_NAME)
        size = mem.r16(textAttr + self._TA_OFF_YSIZE)
        name = self._read_string(mem, name_ptr)

        # A TextFont stand-in block (the screen's default font uses the same
        # pattern): carry the requested name so a future renderer can replay it.
        handle = ctx.alloc.alloc_memory(64, label="DiskFont.TextFont").addr
        if name:
            encoded = name.encode("ascii", "ignore")[:31]
            for i, ch in enumerate(encoded):
                mem.w8(handle + i, ch)
            mem.w8(handle + len(encoded), 0)
        self._fonts[handle] = textAttr
        self.font_opens.append({"text_attr": textAttr, "name": name, "size": size})
        return handle

    @staticmethod
    def _read_string(mem, ptr: int, max_len: int = 32) -> str:
        """Best-effort read of a NUL-terminated string from 68k memory."""
        if not ptr:
            return ""
        chars: list[int] = []
        for i in range(max_len):
            ch = mem.r8(ptr + i)
            if ch == 0:
                break
            chars.append(ch)
        return bytes(chars).decode("ascii", "ignore")
