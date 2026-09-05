#!/usr/bin/env python3
# pyright: reportMissingImports=false
"""Disassemble Motorola 68k bytes from a file or a vamos run artifact.

The default mode reads raw bytes from a file. Use ``--base`` when the file is a
memory dump or relocated segment and you want printed addresses to match the
runtime address space seen in ``vamos.log``.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from capstone import CS_ARCH_M68K, CS_MODE_BIG_ENDIAN, CS_MODE_M68K_000, Cs


def parse_int(value: str) -> int:
    """Parse decimal or 0x-prefixed integers for CLI offsets and addresses."""
    return int(value, 0)


def read_bytes(path: Path, offset: int, size: int | None) -> bytes:
    with path.open("rb") as f:
        if offset:
            f.seek(offset)
        return f.read() if size is None else f.read(size)


def disassemble(data: bytes, address: int, count: int | None) -> None:
    md = Cs(CS_ARCH_M68K, CS_MODE_M68K_000 | CS_MODE_BIG_ENDIAN)
    for index, insn in enumerate(md.disasm(data, address)):
        if count is not None and index >= count:
            break
        raw = " ".join(f"{b:02x}" for b in insn.bytes)
        print(f"{insn.address:08x}: {raw:<18} {insn.mnemonic} {insn.op_str}".rstrip())


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Disassemble Motorola 68k code with Capstone.",
    )
    parser.add_argument("path", type=Path, help="binary, segment, or memory dump to read")
    parser.add_argument(
        "--offset",
        type=parse_int,
        default=0,
        help="file offset to start reading, decimal or 0x-prefixed",
    )
    parser.add_argument(
        "--size",
        type=parse_int,
        default=None,
        help="number of bytes to read; defaults to the rest of the file",
    )
    parser.add_argument(
        "--base",
        type=parse_int,
        default=0,
        help="runtime address corresponding to file offset 0",
    )
    parser.add_argument(
        "--address",
        type=parse_int,
        default=None,
        help="runtime address to print for the first decoded byte; overrides base+offset",
    )
    parser.add_argument(
        "--count",
        type=parse_int,
        default=None,
        help="maximum number of instructions to print",
    )
    args = parser.parse_args()

    start_address = args.address if args.address is not None else args.base + args.offset
    data = read_bytes(args.path, args.offset, args.size)
    disassemble(data, start_address, args.count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
