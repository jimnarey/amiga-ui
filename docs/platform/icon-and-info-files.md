---
title: "Icon And Info Files"
status: draft
depends_on:
  - "workbench-model.md"
citations_used:
  - "S2"
  - "S24"
  - "S25"
---

# Icon And Info Files

Purpose: Document `.info` files and the metadata they carry.

Needed for:
- Apps like `iTidy` that operate directly on Workbench layout data.

Depends on:
- `workbench-model.md`

Status: Draft.

Notes:
- Explain icon types, drawer state, and file naming conventions.

## Summary

Workbench represents visible files, directories, and disks through `.info` files. The Workbench library documentation describes the `.info` file as the mechanism that stores the icon imagery and other metadata needed by Workbench, and states that icons are associated with files or directories by matching name in the same location [S2 §The Info File ¶1-3]. The icon library docs go further and call the `.info` file the center of interaction between applications and Workbench [S24 L7-L14].

## Naming Rules

The basic naming convention is simple:

- a file `myapp` uses `myapp.info` as its icon metadata file,
- a directory uses a same-named `.info` file at the level where that directory name appears,
- and a disk icon uses `disk.info` at the root of the disk [S2 §The Info File ¶1-6].

This distinction matters because a drawer icon is not stored inside the drawer it represents. A compatibility layer that only looks inside directories for their icon metadata will miss legitimate Workbench state.

## What The `.info` File Carries

The icon library documentation explains that the data in a `.info` file is organized as a `DiskObject` and includes:

- icon type,
- default tool,
- Tool Types,
- current icon position,
- optional drawer data,
- optional tool window,
- optional stack size [S24 L13-L29] [S24 L48-L75]

For this project, that means `.info` files are both visual and behavioral artifacts. They are not just decoration.

## Icon Types

Workbench fundamentals describes the main visible icon types as disk, drawer, tool, project, and Trashcan, plus pseudo-icon cases for objects without explicit icon files [S25 §Icons ¶1-6]. The lower-level icon library documentation and NDK headers add `WBKICK` and `WBAPPICON` to the broader technical model [S24 L38-L47].

The practical project takeaway is:

- `tool` and `project` icons affect launch behavior,
- `drawer` and `disk` icons affect navigation and stored layout,
- `AppIcon` behavior matters for running-app integration later.

## Layout And Drawer State

The icon library docs explain that `do_CurrentX` and `do_CurrentY` store icon position in a drawer's virtual coordinate system, while `do_DrawerData` stores the window position and size used when the drawer reopens [S24 L54-L67]. That makes icon and drawer handling directly relevant to `iTidy`-class tools that arrange icons and window layout.

## Why Shell And Workbench Differ

The `.info` file model is Workbench-centric. Shell tools operate on raw files and paths, but Workbench associates launch behavior and visual state with matching `.info` files [S2 §The Info File ¶1-6]. A compatibility layer therefore needs to preserve the difference between:

- a file existing,
- a file having an associated icon,
- and a file's icon carrying launch or layout metadata.
