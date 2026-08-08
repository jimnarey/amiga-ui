---
title: "dos.library"
status: draft
depends_on:
  - "../filesystem-and-launch.md"
citations_used:
  - "S5"
---

# dos.library

Purpose: Summarize the file, path, CLI, and process-facing parts of `dos.library`.

Needed for:
- Most filesystem and program startup work in this project.

Depends on:
- `../filesystem-and-launch.md`

Status: Draft.

Notes:
- Prioritize locks, file handles, path functions, startup rules, and console behavior.

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

## Path And Directory Rules

The official `dos.library` overview explains that paths are split into device and path parts, that the current directory is represented by a lock, and that `CurrentDir()` is the supported way to change directory context [S5 §Path names and current directories ¶1-9]. It also documents the 255-character path limitation and notes that `Lock()` plus `CurrentDir()` are the normal workaround for deeply nested paths [S5 §Path names will be silently truncated if too long, bugs included ¶1-7].

This is directly relevant to the project because a host translation layer that always collapses paths into long absolute strings can miss how Amiga applications actually avoid path-length issues.

## File And Console Context

The Workbench launch model means a program may not start with valid standard I/O file handles even though it still expects DOS semantics elsewhere. So `dos.library` support here is not just about opening files; it is also about correctly modeling when file-handle-style I/O is and is not available.

## Return-Value Caution

The `dos.library` overview warns that DOS truth values follow the Tripos/BCPL convention, where `DOSFALSE` is `0` and success may be reported as `DOSTRUE == -1`, not `1` [S5 §Boolean values ¶1-8]. For a Python compatibility layer, that matters whenever low-level DOS success/failure values are surfaced directly rather than being normalized too early.

## Working Rule

When implementing or debugging `dos.library` behavior for this project, prefer faithful semantics in these areas before chasing breadth:

1. lock and current-directory correctness,
2. path resolution correctness,
3. file-handle correctness,
4. DOS-style return-value correctness.
