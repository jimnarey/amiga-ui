---
title: "Library Cards"
status: index
depends_on:
  - "../amiga-primer.md"
citations_used: []
---

# Library Cards

Purpose: Provide one short file per important Amiga library.

Needed for:
- Looking up project-relevant behavior without opening full autodocs.

Depends on:
- `../amiga-primer.md`

Status: Index.

Notes:
- Each card should eventually include role, key types, key functions, and project relevance.

## Purpose Of This Section

These files are the short-form lookup cards for Amiga libraries that keep showing up in source code, logs, and compatibility discussions. The goal is not to replace full autodocs. It is to give a small-context model or a human reviewer the project-relevant meaning of a library quickly.

## Highest-Priority Cards

For the current project scope, these are the key cards to read first:

- [dos.library](./dos.library.md)
- [exec.library](./exec.library.md)
- [workbench.library](./workbench.library.md)
- [icon.library](./icon.library.md)
- [intuition.library](./intuition.library.md)
- [gadtools.library](./gadtools.library.md)
- [asl.library](./asl.library.md)

These map directly onto the current `iTidy` target and the present `vamos` integration work.

## Secondary Cards

These are important, but usually after the core set above:

- [graphics.library](./graphics.library.md)
- [utility.library](./utility.library.md)

## Lower-Priority Card

- [iffparse.library](./iffparse.library.md)

This is still a lower-priority card than the core GUI and DOS libraries, but it is no longer purely hypothetical because the current `iTidy` source reads Workbench preference files through `iffparse.library`.
