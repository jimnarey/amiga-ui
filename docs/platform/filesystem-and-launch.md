---
title: "Filesystem And Launch"
status: draft
depends_on:
  - "amiga-primer.md"
citations_used:
  - "S2"
  - "S5"
---

# Filesystem And Launch

Purpose: Explain Amiga paths, volumes, assigns, locks, and launch modes.

Needed for:
- Correct path mapping and startup behavior under `vamos`.

Depends on:
- `amiga-primer.md`

Status: Draft.

Notes:
- Cover CLI vs Workbench launch, current directory rules, and `CON:` behavior.

## Summary

For this project, the most important difference between Amiga Shell launch and Workbench launch is that Workbench does not hand an application a normal `argc`/`argv` list or a ready-made console environment. Workbench-started programs receive a `WBStartup` message instead, and by default they also lack valid `stdin`, `stdout`, and `stderr` file handles unless a console is explicitly set up [S2 §Launching ¶1-5] [S2 §WBStartup Message ¶1-2].

## Path Model

AmigaDOS path handling is volume-oriented rather than POSIX-root-oriented. The `dos.library` overview describes path names as having a device part and a path part, with `:` marking the device or volume boundary [S5 §Path names and current directories ¶1-5]. The same overview also explains that:

- an empty string refers to the current directory,
- a leading `:` refers to the root directory of the current volume,
- and a leading `/` refers to a parent directory relative to the current directory [S5 §Path names and current directories ¶6-9].

This matters because the project is translating between Amiga path semantics and host filesystem semantics. A host path mapping that only reproduces file names but not current-directory behavior will still be wrong.

## Current Directory

The current directory of an Amiga process is represented by a lock, not by a string path. `dos.library` documents that the current directory is changed with `CurrentDir()` and that `Lock()` plus `CurrentDir()` are the standard way to access deeply nested directories [S5 §Path names and current directories ¶6-8]. That is the key reason Workbench argument handling cannot be reduced to string concatenation alone.

## Launch Modes

### Shell Launch

Shell launch is the simpler case conceptually. The application gets normal CLI-style arguments and a CLI-style process environment. For compatibility work, this mode is useful when we want to test a binary in isolation or compare CLI and Workbench behavior.

### Workbench Launch

Workbench launch is the behavior that matters more for the current target class. The Workbench documentation states that applications started from Workbench receive a `WBStartup` structure rather than normal CLI arguments, and that compiler startup code often places a pointer to this message in `argv` while setting `argc` to zero [S2 §Argument Passing in Workbench ¶1-4] [S2 §WBStartup Message ¶1-2].

That means the project should assume that a GUI utility may inspect its startup mode and behave differently when launched from Workbench.

## Console And `CON:`

Workbench-started applications do not automatically have legal standard I/O handles. The Workbench documentation explicitly warns that `stdio` functions such as `printf()` are not safe by default in that environment unless a `stdio` window is first established [S2 §Launching ¶2-4]. It also gives a concrete pattern for opening an auto console window through:

`CON:0/0/640/200/auto/close/wait` [S2 §Launching ¶4]

For this project, that means "the program wrote nothing" and "the program had nowhere valid to write" are different states. A compatibility layer must preserve that distinction.

## Why This Matters To The Project

The project is trying to support Workbench-oriented applications rather than just command-line tools. That means accurate support for:

- current-directory locks,
- Workbench argument passing,
- relative path behavior,
- and optional Workbench console setup

is part of baseline correctness, not an edge-case refinement.
