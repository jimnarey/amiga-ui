---
title: "iTidy Overview"
status: draft
depends_on:
  - "../../architecture/compatibility-scope.md"
  - "../../platform/workbench-model.md"
citations_used:
  - "S11"
  - "S12"
  - "S30"
  - "S31"
---

# iTidy Overview

Purpose: Explain what `iTidy` is and why it is the first real compatibility target.

Needed for:
- Framing the app-specific docs that follow.

Depends on:
- `../../architecture/compatibility-scope.md`
- `../../platform/workbench-model.md`

Status: Draft.

Notes:
- Keep this focused on why `iTidy` is useful pressure for the project.

## Summary

`iTidy` is a Workbench utility for AmigaOS 3.x that rearranges icon layouts, resizes drawer windows, scans recursively through folder trees, validates default-tool paths, and can create LhA-based backups before making changes [S11 L9-L32] [S12 L43-L50]. It is a strong first target because it is unmistakably a real GUI application, but its value lives in Workbench-facing behavior rather than in custom graphics or hardware tricks [S11 L107-L112] [S12 L5-L8].

## Why It Is A Good First Target

### It Exercises Workbench Launch Semantics

The source does not treat Shell and Workbench launch as equivalent. It checks for `argc == 0`, reads `_WBenchMsg`, and parses tooltypes from its own program icon only when Workbench startup data is present [S30 L277-L380] [S30 L623-L687]. That makes `iTidy` useful for forcing the project to handle real Workbench startup behavior rather than only CLI-style process launch.

### It Exercises Native Amiga GUI Layers

The upstream docs describe the program as using native GadTools on Workbench 3.x [S11 L107-L112]. The main-window code backs that up with direct use of Intuition, GadTools, and ASL requesters for menus, windows, and folder selection [S31 L7-L17] [S31 L103-L142] [S31 L470-L518].

### It Exercises Workbench Metadata Rather Than User Data

The manual is explicit that `iTidy` updates `.info` files and drawer/window layout information only, rather than modifying ordinary user files [S12 L5-L8]. That is ideal for the project's error-driven workflow because visible success can be measured through icon positions, window geometry, and default-tool metadata without risking broad data corruption.

### It Stays Within The Project Scope

The app works in the exact area the repository is trying to support first: path handling, `.info` files, Workbench startup, requesters, standard windows, and optional helper commands like `LhA` [S11 L15-L26] [S12 L215-L250]. If `iTidy` fails, the failure is likely to reveal a missing OS-level behavior that other Workbench utilities will need too.

## Source-Of-Truth Rule

There is one important caution during analysis: the published user docs present `iTidy` as version 1.0, while the current source comments describe an in-progress GUI migration and label the main program as a GUI version 2.0.0 [S12 L382-L386] [S30 L1-L9]. For this project, that means:

- the released behavior described by the README and manual is the baseline compatibility target;
- the checked-in source is still valuable for identifying dependencies and likely failure points;
- but source comments should not silently override observed release behavior.
