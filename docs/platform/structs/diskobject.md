---
title: "DiskObject"
status: draft
depends_on:
  - "../icon-and-info-files.md"
  - "../library-cards/icon.library.md"
citations_used:
  - "S1"
  - "S24"
  - "S34"
---

# DiskObject

Purpose: Explain the icon metadata structure used by `icon.library`.

Needed for:
- Workbench icon persistence and `iTidy`-style editing behavior.

## Summary

`DiskObject` is the in-memory representation of a Workbench `.info` file. The icon-library docs identify it as the core icon data structure, and the NDK header shows the fields that store icon type, layout, drawer data, default-tool behavior, and other metadata [S24 L13-L29] [S1 Include_H/workbench/workbench.h L82-L95].

## Structure Fields

The NDK definition includes:

- `do_Magic`
- `do_Version`
- `do_Gadget`
- `do_Type`
- `do_DefaultTool`
- `do_ToolTypes`
- `do_CurrentX`
- `do_CurrentY`
- `do_DrawerData`
- `do_ToolWindow`
- `do_StackSize` [S1 Include_H/workbench/workbench.h L82-L95]

The same header also defines `WB_DISKMAGIC`, version constants, and `NO_ICON_POSITION` for icons that do not live at a normal drawer coordinate [S1 Include_H/workbench/workbench.h L97-L121].

## Fields That Matter Most Here

### Type And Launch Metadata

`do_Type`, `do_DefaultTool`, `do_ToolTypes`, `do_ToolWindow`, and `do_StackSize` drive how Workbench interprets the icon as a tool, project, drawer, or other object, and how launching behavior is configured [S24 L48-L53] [S24 L70-L75].

### Layout Metadata

`do_CurrentX` and `do_CurrentY` store icon position, while `do_DrawerData` carries drawer-window geometry and related drawer-view information [S24 L54-L67].

### Gadget/Image Payload

`do_Gadget` is the reason a `DiskObject` is more than "metadata with a couple of strings." It carries the gadget/image payload that influences how the icon is rendered and measured in memory [S1 Include_H/workbench/workbench.h L82-L89].

## Concrete Relevance In `iTidy`

`iTidy` reads `DiskObject` data repeatedly through `GetDiskObject()`, extracts default-tool information, and uses the loaded icon object to determine icon type and display-size details before laying icons out [S34 L760-L801]. That makes `DiskObject` correctness central to the current app, not just a future concern.

## Working Rule

For this project, a compatible `DiskObject` implementation must first preserve:

1. launch metadata fields such as default tool and tooltypes,
2. layout fields such as current position and drawer data,
3. enough gadget/image state for measurement-sensitive tools,
4. memory ownership rules when fields are edited and written back.
