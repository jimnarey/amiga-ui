---
title: "Workbench Model"
status: draft
depends_on:
  - "amiga-primer.md"
  - "icon-and-info-files.md"
  - "structs/wbstartup.md"
citations_used:
  - "S1"
  - "S2"
  - "S3"
---

# Workbench Model

Purpose: Explain how Workbench thinks about files, icons, tools, projects, and user interaction.

Needed for:
- Reproducing Workbench-facing behavior instead of only CLI behavior.

Depends on:
- `amiga-primer.md`
- `icon-and-info-files.md`
- `structs/wbstartup.md`

Status: Draft.

Notes:
- Focus on the subset that real target apps rely on.

## Summary

Workbench is not just a file browser. The Workbench manual presents it as the user's main icon-driven environment, built around icons, menus, windows, and requesters rather than typed commands [S3 §Welcome ¶2-5]. For this project, the important consequence is that a Workbench utility is typically operating on icon-represented objects and Workbench state, not just on filenames.

## Object Types

The NDK `workbench.h` header defines the canonical Workbench object types used in icon metadata:

- `WBDISK`
- `WBDRAWER`
- `WBTOOL`
- `WBPROJECT`
- `WBGARBAGE`
- `WBDEVICE`
- `WBKICK`
- `WBAPPICON` [S1 Include_H/workbench/workbench.h L36-L43]

That list is a useful scope reminder. A Workbench-facing compatibility layer needs to understand not just tools and projects, but also drawers, disks, and AppIcons because those affect launch behavior and user interaction.

## Tools, Projects, And Default Tools

The Workbench library documentation explains the core model clearly:

- activating a tool icon launches the tool itself,
- activating a project icon launches the project's default tool,
- and the project becomes an additional Workbench argument passed to that tool [S2 §Argument Passing in Workbench ¶2-4].

This is especially relevant for the current project because `iTidy` and similar utilities are defined by how they interact with Workbench files, icons, and default-tool metadata rather than by custom rendering hardware.

## Icons Carry Behavior

The NDK `DiskObject` definition shows why icons matter so much. A `DiskObject` includes:

- `do_Type`
- `do_DefaultTool`
- `do_ToolTypes`
- `do_CurrentX`
- `do_CurrentY`
- optional drawer data
- optional tool window and stack size fields [S1 Include_H/workbench/workbench.h L82-L95]

In other words, Workbench icons are not just pictures. They are a bundle of launch, configuration, and layout metadata. That makes icon handling a first-class compatibility problem for this project.

## Running Applications Can Still Receive Workbench Input

Workbench interaction does not end at process startup. The Workbench library documentation describes `AppWindow`, `AppIcon`, and `AppMenuItem` as ways for a running application to receive more Workbench-driven input after launch [S2 §The AppMessage Structure ¶1-9].

This matters architecturally because the project cannot model Workbench support as a one-time "launch translation" only. Some applications participate in an ongoing Workbench message loop.

## Working Rule

When designing or debugging compatibility behavior, assume that Workbench is an object-and-message environment with icon metadata at its center. If a tool behaves strangely, the problem may be in:

- icon metadata,
- default-tool resolution,
- drawer/layout state,
- or Workbench message handling

and not only in raw file I/O.
