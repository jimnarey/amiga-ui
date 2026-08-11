---
title: "dos.library"
status: draft
depends_on:
  - "../filesystem-and-launch.md"
citations_used:
  - "S5"
  - "S1"
  - "S53"
---

# dos.library

Purpose: Summarize the file, path, CLI, and process-facing parts of `dos.library`.

Needed for:
- Most filesystem and program startup work in this project.

## Summary

`dos.library` is the main API surface for Amiga path handling, filesystem access, current-directory state, and process-facing I/O conventions. For this project, it is second only to `exec.library` in practical importance because Workbench utilities tend to spend most of their time navigating paths, opening files, switching directories, and reporting results through DOS-facing abstractions [S5 §Path names and current directories ¶1-9].

## High-Priority Semantics

The highest-priority `dos.library` areas for this repository are:

- path parsing rules,
- `Lock()` / `UnLock()` behavior,
- `CurrentDir()` behavior,
- file handle access,
- CLI versus Workbench stream assumptions,
- and helper functions such as `NameFromLock()` and `AddPart()`.

Those areas are the ones that most directly influence Workbench launch, `WBArg` interpretation, and `.info`-oriented utilities.

## High-Value APIs

The prototype surface confirms the practical first-wave API groups:

- `Open()`, `Close()`, `Read()`, `Write()`, `Seek()` for file-handle operations [S1 Include_H/clib/dos_protos.h L44-L50]
- `Lock()`, `UnLock()`, `DupLock()`, `CurrentDir()`, `ParentDir()` for directory-context handling [S1 Include_H/clib/dos_protos.h L53-L60] [S1 Include_H/clib/dos_protos.h L71-L74]
- `NameFromLock()` and `NameFromFH()` for turning DOS context back into readable paths [S1 Include_H/clib/dos_protos.h L114-L120]
- `Execute()`, `SystemTagList()`, and related command-launch helpers for shell-like behavior from within a process [S1 Include_H/clib/dos_protos.h L74-L75] [S1 Include_H/clib/dos_protos.h L157-L159]
- `LoadSeg()`, `UnLoadSeg()`, `CreateProc()`, and `RunCommand()` for loading and launching code [S1 Include_H/clib/dos_protos.h L62-L65] [S1 Include_H/clib/dos_protos.h L135-L139] [S53 §FUNCTION ¶1-4]

These are the APIs most likely to matter before the project ever needs deeper packet-level DOS behavior.

## Path And Directory Rules

The official `dos.library` overview explains that paths are split into device and path parts, that the current directory is represented by a lock, and that `CurrentDir()` is the supported way to change directory context [S5 §Path names and current directories ¶1-9]. It also documents the 255-character path limitation and notes that `Lock()` plus `CurrentDir()` are the normal workaround for deeply nested paths [S5 §Path names will be silently truncated if too long, bugs included ¶1-7].

This is directly relevant to the project because a host translation layer that always collapses paths into long absolute strings can miss how Amiga applications actually avoid path-length issues.

## File And Console Context

The Workbench launch model means a program may not start with valid standard I/O file handles even though it still expects DOS semantics elsewhere. So `dos.library` support here is not just about opening files; it is also about correctly modeling when file-handle-style I/O is and is not available.

## Loading And Running Programs

`dos.library` also owns a large part of the executable-loading story. The prototype surface includes `LoadSeg()`, `UnLoadSeg()`, `CreateProc()`, and `RunCommand()` directly [S1 Include_H/clib/dos_protos.h L62-L65] [S1 Include_H/clib/dos_protos.h L135-L139]. The `LoadSeg()` autodoc explains that a load file becomes a relocatable load module made of CODE, DATA, and BSS segments connected into a seglist [S53 §FUNCTION ¶1-4] [S53 §NOTES ¶4-8].

That is a useful reminder that DOS responsibilities here extend beyond filenames and streams into actual process launch mechanics.

## Return-Value Caution

The `dos.library` overview warns that DOS truth values follow the Tripos/BCPL convention, where `DOSFALSE` is `0` and success may be reported as `DOSTRUE == -1`, not `1` [S5 §Boolean values ¶1-8]. For a Python compatibility layer, that matters whenever low-level DOS success/failure values are surfaced directly rather than being normalized too early.

## Working Rule

When implementing or debugging `dos.library` behavior for this project, prefer faithful semantics in these areas before chasing breadth:

1. lock and current-directory correctness,
2. path resolution correctness,
3. file-handle correctness,
4. DOS-style return-value correctness.
