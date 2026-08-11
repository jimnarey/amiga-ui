---
title: "Key Structs"
status: index
depends_on:
  - "../data-types-and-conventions.md"
citations_used: []
---

# Key Structs

Purpose: Provide short notes for the structures this project must understand correctly.

Needed for:
- Fast lookup when a log or source file names a core Amiga struct.

Depends on:
- `../data-types-and-conventions.md`

Status: Index.

Notes:
- Keep each struct note compact and project-focused.

## Purpose Of This Section

These files capture the structures that the project most needs to model correctly. They are deliberately narrower than a general Amiga reference. The emphasis is on structs that appear in Workbench launch, icon handling, GUI integration, or DOS-facing runtime behavior.

## Read First

For the current target class, the most important struct notes are:

- [WBStartup](./wbstartup.md)
- [WBArg](./wbarg.md)
- [Locks And Filehandles](./locks-and-filehandles.md)
- [DiskObject](./diskobject.md)
- [Process And Task](./process-and-task.md)

## Later-Phase Struct

- [AppMessage](./appmessage.md)

This one is already important conceptually, but it is more likely to become an active implementation target after basic Workbench launch and icon behavior are in place.
