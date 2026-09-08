"""Repo-owned ``iffparse.library`` implementation for vamos.

Only the ``AllocIFF``/``FreeIFF`` handle lifecycle is implemented with real
semantics. Classic ``AllocIFF`` returns a pointer to an ``IFFparse`` control
block that the caller writes through (e.g. ``iff->iff_Stream``), so the handle
is a real allocation in the emulated address space; ``FreeIFF`` releases only a
handle this library actually handed out and ignores anything else.

The observed iTidy path (``window_management.c`` / ``Settings/IControlPrefs.c``)
allocates a parser, fails to open an absent ``ENV:sys/*.prefs`` file, and frees
the parser, so no chunk parsing is exercised. The remaining traps in this file
are pre-existing no-ops that the target never reaches in this path; they are
deliberately not expanded into a general IFF parser and are documented here as
the implementation boundary.
"""

from __future__ import annotations

from amitools.vamos.machine.regs import REG_A0

from .base_library import BaseLibrary

# Room for the classic ``IFFparse`` control block plus the single pointer the
# target writes through it (``iff_Stream``) before any parsing is attempted.
_IFF_STRUCT_SIZE = 256


class IffParseLibrary(BaseLibrary):
    """Real ``AllocIFF``/``FreeIFF`` handle lifecycle over a stubbed parser.

    ``AllocIFF`` allocates a tracked block in the emulated address space and
    returns its address as the handle; ``FreeIFF`` releases exactly the handles
    this instance allocated. Everything else in the iffparse table remains a
    pre-existing no-op boundary (not a full IFF parser).
    """

    def __init__(self) -> None:
        # Live IFF handles: handle value (emulated address) -> allocated memory.
        self._iff_handles: dict[int, object] = {}

    def AllocIFF(self, ctx):
        """Allocate a new IFF parser handle and return its address.

        ``AllocIFF()()`` takes no arguments and returns a pointer to a new
        ``IFFparse`` structure. The handle is a real emulated-memory allocation
        so the caller can write through it, and it is tracked so ``FreeIFF`` can
        release exactly the handles this library created. Returns 0 (NULL) if
        no allocator is available or the allocation fails.

        Args:
            ctx: library call context.
        """
        alloc = getattr(ctx, "alloc", None)
        if alloc is None:
            return 0
        mem = alloc.alloc_memory(_IFF_STRUCT_SIZE, label="IFFParse.IFF")
        handle = getattr(mem, "addr", 0)
        if not handle:
            return 0
        self._iff_handles[handle] = mem
        return handle

    def FreeIFF(self, ctx):
        """Release a previously allocated IFF parser handle.

        ``FreeIFF(iff)(a0)`` takes the handle in ``A0``. Only a handle this
        library allocated is released; unknown or already-freed handles are
        ignored (honest no-op) rather than treated as success.

        Args:
            ctx: library call context.
        """
        handle = ctx.cpu.r_reg(REG_A0)
        mem = self._iff_handles.pop(handle, None)
        if mem is None:
            return 0
        alloc = getattr(ctx, "alloc", None)
        if alloc is not None and hasattr(alloc, "free_memory"):
            alloc.free_memory(mem)
        return 0

    def OpenIFF(self, iff, rwMode):
        """Open an IFF IFF handle.

        Args:
            iff: IFF handle (a0 register)
            rwMode: read/write mode (d0 register)
        """
        return 0

    def CloseIFF(self, iff):
        """Close an IFF handle.

        Args:
            iff: IFF handle (a0 register)
        """
        return None

    def ParseIFF(self, iff, control):
        """Parse an IFF file.

        Args:
            iff: IFF handle (a0 register)
            control: parse control flags (d0 register)
        """
        return 0

    def ReadChunkBytes(self, iff, buf, numBytes):
        """Read chunk bytes from IFF file.

        Args:
            iff: IFF handle (a0 register)
            buf: data buffer (a1 register)
            numBytes: number of bytes to read (d0 register)
        """
        return 0

    def WriteChunkBytes(self, iff, buf, numBytes):
        """Write chunk bytes to IFF file.

        Args:
            iff: IFF handle (a0 register)
            buf: data buffer (a1 register)
            numBytes: number of bytes to write (d0 register)
        """
        return 0

    def ReadChunkRecords(self, iff, buf, bytesPerRecord, numRecords):
        """Read chunk records from IFF file.

        Args:
            iff: IFF handle (a0 register)
            buf: data buffer (a1 register)
            bytesPerRecord: bytes per record (d1 register)
            numRecords: number of records (d0 register)
        """
        return 0

    def WriteChunkRecords(self, iff, buf, bytesPerRecord, numRecords):
        """Write chunk records to IFF file.

        Args:
            iff: IFF handle (a0 register)
            buf: data buffer (a1 register)
            bytesPerRecord: bytes per record (d1 register)
            numRecords: number of records (d0 register)
        """
        return 0

    def PushChunk(self, iff, chunkType, chunkId, size):
        """Push a chunk onto the IFF chunk stack.

        Args:
            iff: IFF handle (a0 register)
            chunkType: chunk type (d0 register)
            chunkId: chunk ID (d1 register)
            size: chunk size (d2 register)
        """
        return 0

    def PopChunk(self, iff):
        """Pop a chunk from the IFF chunk stack.

        Args:
            iff: IFF handle (a0 register)
        """
        return None

    def EntryHandler(self, iff, chunkType, chunkId, position, handler, object):
        """Set entry handler for IFF chunk.

        Args:
            iff: IFF handle (a0 register)
            chunkType: chunk type (d0 register)
            chunkId: chunk ID (d1 register)
            position: chunk position (d2 register)
            handler: handler routine address (a1 register)
            object: object data pointer (a2 register)
        """
        return None

    def ExitHandler(self, iff, chunkType, chunkId, position, handler, object):
        """Set exit handler for IFF chunk.

        Args:
            iff: IFF handle (a0 register)
            chunkType: chunk type (d0 register)
            chunkId: chunk ID (d1 register)
            position: chunk position (d2 register)
            handler: handler routine address (a1 register)
            object: object data pointer (a2 register)
        """
        return None

    def PropChunk(self, iff, chunkType, chunkId):
        """Process a property chunk.

        Args:
            iff: IFF handle (a0 register)
            chunkType: chunk type (d0 register)
            chunkId: chunk ID (d1 register)
        """
        return None

    def PropChunks(self, iff, propArray, numPairs):
        """Process property chunks.

        Args:
            iff: IFF handle (a0 register)
            propArray: property array (a1 register)
            numPairs: number of property pairs (d0 register)
        """
        return None

    def StopChunk(self, iff, chunkType, chunkId):
        """Stop processing at a chunk.

        Args:
            iff: IFF handle (a0 register)
            chunkType: chunk type (d0 register)
            chunkId: chunk ID (d1 register)
        """
        return None

    def StopChunks(self, iff, propArray, numPairs):
        """Stop processing property chunks.

        Args:
            iff: IFF handle (a0 register)
            propArray: property array (a1 register)
            numPairs: number of property pairs (d0 register)
        """
        return None

    def CollectionChunk(self, iff, chunkType, chunkId):
        """Process a collection chunk.

        Args:
            iff: IFF handle (a0 register)
            chunkType: chunk type (d0 register)
            chunkId: chunk ID (d1 register)
        """
        return None

    def CollectionChunks(self, iff, propArray, numPairs):
        """Process collection chunks.

        Args:
            iff: IFF handle (a0 register)
            propArray: property array (a1 register)
            numPairs: number of property pairs (d0 register)
        """
        return None

    def StopOnExit(self, iff, chunkType, chunkId):
        """Stop parsing on exit marker.

        Args:
            iff: IFF handle (a0 register)
            chunkType: chunk type (d0 register)
            chunkId: chunk ID (d1 register)
        """
        return None

    def FindProp(self, iff, chunkType, chunkId):
        """Find a property in a chunk.

        Args:
            iff: IFF handle (a0 register)
            chunkType: chunk type (d0 register)
            chunkId: chunk ID (d1 register)
        """
        return None

    def FindCollection(self, iff, chunkType, chunkId):
        """Find a collection in a chunk.

        Args:
            iff: IFF handle (a0 register)
            chunkType: chunk type (d0 register)
            chunkId: chunk ID (d1 register)
        """
        return None

    def FindPropContext(self, iff):
        """Find property context.

        Args:
            iff: IFF handle (a0 register)
        """
        return None

    def CurrentChunk(self, iff):
        """Get current chunk.

        Args:
            iff: IFF handle (a0 register)
        """
        return None

    def FindLocalItem(self, iff, chunkType, chunkId, ident):
        """Find a local item in a chunk.

        Args:
            iff: IFF handle (a0 register)
            chunkType: chunk type (d0 register)
            chunkId: chunk ID (d1 register)
            ident: item identifier (d2 register)
        """
        return None

    def StoreLocalItem(self, localItem, position):
        """Store a local item at a position.

        Args:
            localItem: local item data (a0 register)
            position: position (d0 register)
        """
        return None

    def StoreItemInContext(self, localItem, contextNode):
        """Store item in context node.

        Args:
            localItem: local item data (a0 register)
            contextNode: context node pointer (a1 register)
        """
        return None

    def InitIFF(self, iff, flags, streamHook):
        """Initialize IFF handle.

        Args:
            iff: IFF handle (a0 register)
            flags: initialization flags (d0 register)
            streamHook: stream hook routine address (a1 register)
        """
        return None
