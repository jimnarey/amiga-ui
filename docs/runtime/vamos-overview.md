---
title: "Vamos Overview"
status: draft
depends_on:
  - "vamos-library-modes.md"
  - "vamos-path-mapping.md"
citations_used:
  - "S7"
  - "S8"
  - "S9"
---

# Vamos Overview

Purpose: Summarize what `vamos` already provides for this project.

Needed for:
- Avoiding duplicate implementation effort.

Depends on:
- `vamos-library-modes.md`
- `vamos-path-mapping.md`

Status: Draft.

Notes:
- Distinguish clearly between what is emulated in Python and what still needs new work.

## Summary

`Vamos` is the runtime substrate for this project. It already provides the core machinery needed to execute m68k binaries, expose Amiga memory structures, map host files into an Amiga-style filesystem view, and intercept many library calls into Python implementations [S7 L21-L31] [S7 L64-L77]. The project should therefore treat `vamos` as the execution and low-level OS bridge, not as something to replace.

At the same time, `vamos` documents its main focus as CLI-oriented software and explicitly says it does not aim to be a full system emulator or the right tool for direct hardware-access workloads [S7 L5-L17]. That gap is exactly where this project begins.

## What Vamos Already Gives Us

### m68k Program Execution

`Vamos` already solves the hardest low-level problem: it can execute AmigaOS m68k binaries on the host by combining Musashi CPU emulation with a memory model and Python-visible traps for library behavior [S7 L21-L31]. This means the compatibility layer can focus on semantics rather than instruction execution.

### Core AmigaOS Structure Emulation

The runtime also provides public in-memory structures such as `ExecBase` and a memory handler for heap allocations and library data exchange [S7 L29-L31]. That is essential because many Amiga programs expect not just function calls but also a plausible OS-shaped memory environment.

### Filesystem Mapping And Launch Environment

`Vamos` already has a configurable DOS environment consisting of:

- volume mappings
- assigns
- command path
- library settings
- memory and CPU settings
- tracing and emulation options [S7 L64-L77]

It supports mapping host directories as Amiga volumes, creating assigns, and setting up a default `root:` view over the host filesystem [S7 L100-L148] [S7 L150-L198]. It also documents auto-assign behavior for unresolved Amiga path prefixes [S7 L199-L220]. All of that is directly useful for mounting the project tree, test assets, and extracted application files in a predictable way.

### Library Management

`Vamos` has a library manager that can load different classes of libraries and handle them in several modes [S8 L16-L55]. The three important categories are:

- original Amiga libraries
- Python-implemented `vamos` libraries
- fake libraries with dummy functions [S8 L18-L32]

That flexibility matters because Workbench-class application support will almost certainly involve a mix of:

- existing `vamos` implementations
- native Amiga libraries loaded from reference media
- temporary fake implementations used to expose the next real missing behavior

### Tracing And Test Harness Patterns

The existing `amitools` test helper code shows a practical execution pattern for running a program through `vamos`, inserting `--` before the Amiga binary, capturing stdout/stderr, and optionally writing a `vamos.log` file for later inspection [S9 L149-L247]. That is a good model for the project’s own debug loop.

## What Vamos Does Not Already Solve

### Full Workbench GUI Behavior

`Vamos` says plainly that its main focus is console binaries that do not depend on Intuition or graphics [S7 L5-L10]. The project therefore should not assume that “the binary runs under `vamos`” is equivalent to “the Workbench application behaves correctly.”

### Full-System Emulation

`Vamos` is an API-level emulator and “never will be” a full Amiga system emulator in the UAE sense [S7 L16-L17]. This is not a limitation to work around; it is a design boundary to respect.

### Direct Hardware Workloads

Software that depends on direct hardware register access is explicitly outside `vamos`’s intended use case [S7 L12-L14]. The project should preserve that boundary in its own target selection.

### Broad Subsystem Emulation

`Vamos` documents CPU execution, memory structures, path modeling, configurable libraries, and some hardware-access handling modes, but it does not present itself as a broad audio, peripheral, or desktop-session emulation layer [S7 L64-L77] [S7 L282-L288] [S7 L467-L488]. The project should therefore be careful not to infer support for whole subsystems from the mere fact that some feature can be named through an API boundary.

## Why Vamos Is Still The Right Base

Although `vamos` is not enough by itself for Workbench GUI compatibility, it is still the correct foundation because it already provides:

- stable binary execution
- core OS memory structures
- path and assign modeling
- configurable library loading
- testable host-side interception points

The project’s job is therefore not to build “another emulator,” but to incrementally expand the semantics available on top of `vamos` until selected Workbench applications can run usefully.

## Working Rule

If a missing behavior can be implemented as:

- a better `vamos` library implementation,
- a small amount of native-library handling,
- a path/layout/metadata fix,
- or a host-side translation layer,

then it belongs in this project. If solving it would require the project to become a full machine emulator, it probably does not.
