---
title: "iTidy Dependencies"
status: draft
depends_on:
  - "overview.md"
  - "../../platform/library-cards/dos.library.md"
  - "../../platform/library-cards/icon.library.md"
  - "../../platform/library-cards/intuition.library.md"
  - "../../platform/library-cards/workbench.library.md"
  - "../../host-gui/README.md"
  - "../../workflows/external-helpers-and-shellouts.md"
citations_used:
  - "S11"
  - "S12"
  - "S29"
  - "S30"
  - "S31"
  - "S32"
  - "S33"
  - "S34"
  - "S35"
---

# iTidy Dependencies

Purpose: Record the libraries, files, and Workbench features that `iTidy` relies on.

Needed for:
- Triage when `vamos` fails to run the app.

Depends on:
- `overview.md`
- `../../platform/library-cards/dos.library.md`
- `../../platform/library-cards/icon.library.md`
- `../../platform/library-cards/intuition.library.md`
- `../../platform/library-cards/workbench.library.md`
- `../../host-gui/README.md`
- `../../workflows/external-helpers-and-shellouts.md`

Status: Draft.

Notes:
- Include both compile-time and runtime dependencies.

## Runtime Minimum

The upstream manual says `iTidy` requires Workbench 3.0 or newer, at least 1 MB of RAM, at least 1 MB of free storage, and `LhA` in `SYS:C` if backup and restore features are to work [S12 L24-L33]. The program enforces the Workbench-floor requirement in code by checking for Exec version 39 or later before continuing [S30 L115-L129] [S30 L598-L605].

## Launch And Environment Dependencies

`iTidy` is most naturally a Workbench-launched program. On startup it looks for `_WBenchMsg`, treats `argc == 0` as Workbench launch, and reads tooltypes from its own icon only in that mode [S30 L277-L380] [S30 L623-L687]. That means a serious compatibility run eventually needs:

- believable `WBStartup` data,
- a real current-directory lock for the program location,
- and access to the program icon as a `DiskObject`.

Shell launch is still useful for early loader and path debugging, but it is not behaviorally equivalent.

## Core Amiga Libraries And Services

### `dos.library`

The app depends heavily on DOS-facing services:

- `CurrentDir()` during Workbench startup handling [S30 L330-L335]
- `MatchFirst()` and `MatchNext()` for `.info` discovery and fast folder pre-scan [S33 L59-L121] [S35 L306-L346]
- startup-script parsing for PATH discovery in `S:Startup-Sequence` and `S:User-Startup` [S12 L250-L250] [S34 L1275-L1310]
- `Execute()` plus `NIL:` handles for running `LhA` commands [S32 L162-L195]

This makes `dos.library` one of the highest-priority dependencies for getting the app meaningfully past startup.

### `icon.library`

`iTidy` uses `icon.library` in several different ways:

- opening the library to read tooltypes from the program icon at startup [S30 L314-L350]
- loading icon metadata with `GetDiskObject()` [S34 L760-L779]
- reading and updating default-tool data [S34 L760-L779] [S34 L889-L927]
- using icon-library v44 functionality for frameless-icon detection and related higher-fidelity behavior [S34 L803-L825]

The manual also ties some visible behavior to newer icon-library support, especially for OS3.5+ color-icon fidelity and NewIcon border stripping [S12 L207-L209] [S12 L314-L320].

### Intuition, GadTools, And ASL

The main window is built directly on native UI libraries rather than on MUI or a custom renderer. The source includes Intuition, GadTools, and ASL headers and uses them for menus, the folder requester, and Workbench-screen attachment [S31 L7-L17] [S31 L174-L227] [S31 L470-L518]. In practice, that means compatibility work must cover:

- opening and managing standard windows,
- menu creation and event handling,
- public-screen access,
- and drawer-only file requesters.

See `../../host-gui/README.md` for how these map onto the host-side Qt Widgets implementation.

### Workbench Services

The app is deeply Workbench-oriented even when it is not calling `workbench.library` functions directly. It expects Workbench startup data, Workbench screen naming, and Workbench-style icon semantics throughout the run [S30 L108-L109] [S30 L623-L687] [S31 L177-L227].

## File And Path Dependencies

At runtime, `iTidy` expects several concrete path classes to exist:

- real icon files, because the tool operates on `.info` files rather than Workbench's temporary "All Files" pseudo-icons [S12 L348-L352]
- startup scripts in `S:` for PATH parsing and default-tool lookup [S12 L250-L250] [S34 L1304-L1310]
- an installed `LhA` command in one of the expected locations if backup or restore is used [S32 L98-L118]
- writable storage under `PROGDIR:` for logs and backup archives [S12 L294-L299] [S32 L217-L247]

The recursive pre-scan also depends on folder icons being present if the "skip hidden folders" behavior is left enabled, because hidden folders are identified by the absence of the folder's own `.info` file [S12 L354-L358] [S33 L198-L214].

See `../../workflows/external-helpers-and-shellouts.md` for how to triage the `LhA` dependency specifically.

## Build-Time Dependencies

The source tree currently builds with VBCC for `+aos68k`, targets a 68000 CPU for maximum compatibility, and links against the standard Amiga runtime libraries rather than against MUI or ClassAct [S29 L4-L30]. The source list also shows that backup, default-tool, restore, DOS, settings, and GUI subsystems are all part of the program rather than optional plugins [S29 L38-L116].
