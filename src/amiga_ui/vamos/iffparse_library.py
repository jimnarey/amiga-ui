"""Repo-owned minimal ``iffparse.library`` implementation for vamos."""

from __future__ import annotations

from .base_library import BaseLibrary


class IffParseLibrary(BaseLibrary):
    """Stub implementation to satisfy the first ``iffparse.library`` load."""

    def AllocIFF(self, ctx):
        """Return a dummy IFF handle.

        The iTidy binary merely checks for a non-NULL handle.

        Args:
            ctx: library context pointer (d0 register)
        """
        return 1

    def FreeIFF(self, iff):
        """No-op free.

        Args:
            iff: IFF handle (d0 register)
        """
        return None

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
