---
title: "Amiga Primer"
status: draft
depends_on: []
citations_used:
  - "S2"
  - "S3"
  - "S5"
  - "S25"
---

# Amiga Primer

Purpose: Give a minimal orientation to AmigaOS concepts used throughout the project.

Needed for:
- Contributors who know Python/Linux better than AmigaOS.

Depends on:

Status: Draft.

Notes:
- Keep this short and cross-link to more specific documents instead of becoming a manual.

## Summary

For this project, the fastest way to think about classic AmigaOS is: it is a message-driven operating system with a DOS-style filesystem layer and an icon-driven desktop called Workbench layered on top. Programs may run from the Shell, but many GUI utilities are really designed around Workbench concepts such as icons, drawers, default tools, public screens, and startup messages rather than around plain command-line arguments [S3 §Welcome ¶2-5] [S2 §Workbench Library ¶1-4].

## Five Core Ideas

### 1. Workbench Is Not Just A File Browser

Workbench is the normal desktop environment. It represents disks, drawers, tools, projects, and trash through icons, menus, windows, and requesters [S3 §Welcome ¶2-5] [S25 §Icons ¶1-6]. If a program is written as a Workbench utility, it is usually interacting with that icon-and-window model rather than with raw filenames alone.

### 2. `.info` Files Carry Real Behavior

On AmigaOS, visible objects in Workbench usually have matching `.info` files. Those files carry not only icon imagery but also launch and layout metadata such as default tools, Tool Types, and stored drawer positions [S2 §The Info File ¶1-6]. For this repository, that is why icon handling is central rather than cosmetic.

### 3. Paths Are Volume-Oriented

AmigaDOS paths do not start from a UNIX-style `/`. They are volume-oriented, use `:` to separate the device or volume name from the path, and treat the current directory as an important part of path interpretation [S5 §Path names and current directories ¶1-9]. That is why `sys:`, `c:`, and other assigns matter so much in `vamos` setups.

### 4. Workbench Launch Differs From Shell Launch

Shell-launched programs get ordinary CLI-style arguments. Workbench-launched programs receive a `WBStartup` message instead, and may not have valid standard input/output file handles unless they explicitly create a console window [S2 §Launching ¶1-5] [S2 §WBStartup Message ¶1-2]. This distinction is fundamental for the current target class.

### 5. GUI Code Is Message-Driven

Classic Amiga GUI code is built around libraries such as Intuition, GadTools, ASL, and Graphics. Windows and gadgets are not "declarative widgets" in the modern web sense; they are objects that participate in explicit message loops and stateful library calls. That shapes both the runtime model and the way compatibility bugs appear.

## What To Read Next

Use this file as orientation only. The more detailed follow-on pages are:

- [Filesystem And Launch](/home/jimnarey/projects/amiga-ui/docs/platform/filesystem-and-launch.md) for path and startup behavior
- [Workbench Model](/home/jimnarey/projects/amiga-ui/docs/platform/workbench-model.md) for the desktop-side object model
- [Icon And Info Files](/home/jimnarey/projects/amiga-ui/docs/platform/icon-and-info-files.md) for `.info` files and icon metadata
- [Data Types And Conventions](/home/jimnarey/projects/amiga-ui/docs/platform/data-types-and-conventions.md) for BPTRs, tag lists, and other low-level calling conventions

## Working Rule

When in doubt, assume that a Workbench-class program is not asking for "an Amiga machine" in the abstract. It is usually asking for a specific combination of:

- AmigaDOS path and lock semantics,
- Workbench icon metadata,
- message-driven GUI behavior,
- and a believable process environment.
