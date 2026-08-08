---
title: "Process And Task"
status: draft
depends_on:
  - "../library-cards/exec.library.md"
  - "../library-cards/dos.library.md"
citations_used:
  - "S1"
  - "S30"
  - "S34"
  - "S38"
  - "S39"
---

# Process And Task

Purpose: Explain the difference between Amiga tasks and DOS processes at the level this repo needs.

Needed for:
- Startup behavior, message handling, and execution flow analysis.

Depends on:
- `../library-cards/exec.library.md`
- `../library-cards/dos.library.md`

Status: Draft.

Notes:
- Keep the focus on practical consequences for app execution, not full kernel internals.

## Summary

On AmigaOS, every process is built on the lower-level Exec task model, but not every task is a DOS-capable process. The NDK headers show this relationship directly: `struct Process` begins with an embedded `struct Task` and then adds DOS-specific fields such as current directory, CLI streams, CLI pointer, error window pointer, and startup arguments [S1 Include_H/exec/tasks.h L24-L47] [S1 Include_H/dos/dosextens.h L36-L69].

## `Task`

The base `Task` structure contains scheduling, signal, trap, stack, and cleanup-related fields:

- `tc_Node`
- `tc_State`
- signal fields such as `tc_SigWait` and `tc_SigRecvd`
- stack fields such as `tc_SPReg`, `tc_SPLower`, `tc_SPUpper`
- `tc_MemEntry` for memory freed by `RemTask()` [S1 Include_H/exec/tasks.h L24-L47]

This is the right model for raw scheduling and message-port ownership, but not for ordinary filesystem work.

## `Process`

The DOS `Process` extension adds the fields that matter most for this repo:

- `pr_CurrentDir`
- `pr_CIS`
- `pr_COS`
- `pr_CLI`
- `pr_WindowPtr`
- `pr_Arguments`
- `pr_Result2` [S1 Include_H/dos/dosextens.h L44-L69]

These are the fields that bridge the Exec task world into DOS- and Workbench-facing behavior.

## Why The Distinction Matters

The `AddTask()` autodoc explicitly warns that tasks are low-level building blocks and are generally unable to call `dos.library` functions or anything that may indirectly require DOS, pointing developers toward DOS process APIs instead [S39 §WARNING ¶1-2]. The `OpenLibrary()` autodoc adds a closely related warning: library opening that may touch disk is fundamentally process-oriented [S38 §FUNCTION ¶1-3] [S38 §NOTES ¶1-3].

For this repository, the practical consequence is simple: if a piece of host emulation needs current-directory state, file handles, startup arguments, or DOS request-window behavior, it should be thinking in terms of `Process`, not just `Task`.

## Concrete Relevance In `iTidy`

`iTidy` uses this distinction directly. During default-tool validation it calls `FindTask(NULL)`, casts the result to `struct Process *`, saves `pr_WindowPtr`, and temporarily sets `pr_WindowPtr` to `-1` to suppress DOS volume requesters while probing missing paths [S34 L1032-L1063]. That is a precise example of why process-level fields matter for realistic app compatibility.

The app also relies on task-level lifetime cleanup when exiting through `RemTask(NULL)` on the Amiga path [S30 L880-L886].

## Working Rule

For this project, use this mental model:

1. `Task` owns scheduling, signals, ports, and low-level lifetime.
2. `Process` adds DOS context, streams, current directory, and requester policy.
3. Workbench utilities almost always need process semantics even when the code also touches task semantics underneath.
