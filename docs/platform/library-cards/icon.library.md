---
title: "icon.library"
status: draft
depends_on:
  - "../icon-and-info-files.md"
citations_used:
  - "S1"
  - "S24"
---

# icon.library

Purpose: Summarize icon loading, saving, and icon metadata operations.

Needed for:
- Workbench icon compatibility and `iTidy` behavior.

## Summary

`icon.library` is the main API surface for reading, writing, creating, and inspecting Workbench icon metadata. The official icon library docs describe it as the support library for managing `.info` files and `DiskObject` data [S24 L7-L14] [S24 L98-L117].

## Core Data Model

At the data-structure level, icon handling revolves around `DiskObject`, defined in `<workbench/workbench.h>` [S24 L13-L29]. The NDK header shows the fields most relevant to this project:

- `do_Type`
- `do_DefaultTool`
- `do_ToolTypes`
- `do_CurrentX`
- `do_CurrentY`
- `do_DrawerData`
- `do_ToolWindow`
- `do_StackSize` [S1 Include_H/workbench/workbench.h L82-L95]

## Core Operations

The icon library docs list the central functions as:

- `GetDiskObject()`
- `GetDiskObjectNew()`
- `PutDiskObject()`
- `FreeDiskObject()`
- `DeleteDiskObject()`
- `FindToolType()`
- `MatchToolValue()`
- `GetDefDiskObjectNew()`
- `PutDefDiskObject()` [S24 L98-L117]

For project purposes, these divide into three groups:

1. load/save/delete icon files,
2. inspect and modify icon metadata,
3. work with default icon templates and Tool Types.

## Tool Types And Default Tools

The icon library documentation explains that Tool Types are free-format strings stored in `do_ToolTypes`, while `do_DefaultTool` controls which application Workbench launches for a project icon [S24 L48-L53] [S24 L118-L130]. That is exactly the kind of metadata `iTidy`-class tools may need to read, preserve, or validate.

It also notes a subtle but important rule: when a tool is started through a project's default-tool mechanism, Workbench uses the stack size from the project's `.info` file and ignores the tool icon's stack size [S24 L70-L75]. That is a compatibility detail worth preserving.

## Memory Ownership

The icon library docs warn that `GetDiskObject()` allocates a `DiskObject` in memory and that callers who replace pointers inside it must restore the old pointers before `FreeDiskObject()` so the correct allocations are released [S24 L113-L117]. In other words, host-side emulation of icon operations needs to care about structure ownership, not just field values.

## Working Rule

For this project, `icon.library` support should initially prioritize:

1. loading real icon metadata correctly,
2. preserving fields the app did not intend to change,
3. writing back layout/default-tool/Tool Type changes without corrupting unrelated icon state.
