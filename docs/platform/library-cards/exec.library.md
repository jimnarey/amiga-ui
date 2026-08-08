---
title: "exec.library"
status: draft
depends_on:
  - "../structs/process-and-task.md"
citations_used:
  - "S1"
  - "S8"
  - "S30"
  - "S37"
  - "S38"
  - "S39"
  - "S40"
  - "S41"
---

# exec.library

Purpose: Summarize the core task, memory, and messaging services exposed by `exec.library`.

Needed for:
- Process execution, task behavior, and message-passing analysis.

Depends on:
- `../structs/process-and-task.md`

Status: Draft.

Notes:
- Focus on what `vamos` already replaces and what target apps still assume.

## Summary

`exec.library` is the kernel-level substrate beneath the rest of AmigaOS. For this repository it matters for four reasons above all others:

- task and process identity,
- message ports and message delivery,
- signals and wait behavior,
- memory ownership and cleanup.

It also matters operationally because `vamos` itself requires `exec.library` to be handled as a `vamos` library rather than as an original Amiga library [S8 L48-L52] [S8 L151-L163].

## Why It Matters To This Project

Many compatibility problems that first look like GUI or Workbench issues are actually Exec-shape issues underneath. Workbench startup messages are Exec messages. IDCMP traffic is delivered through ports owned by tasks or processes. Request loops depend on waiting for and draining ports correctly. And resource lifetime often follows task lifetime rather than Python object lifetime.

## High-Value Service Areas

The `exec.library` autodocs index shows just how broad the surface is, but the highest-value subset for this project is smaller: task/process discovery, message passing, signals, library opening, and memory management [S37 item 1].

### Message Ports And Messages

`GetMsg()` removes the next message from a port but does not wait, while `WaitPort()` waits until a port becomes non-empty and then still expects the caller to drain messages in a loop [S40 §FUNCTION ¶1-5] [S41 §FUNCTION ¶1-5]. That distinction is core to GUI compatibility because a correct event loop is not "wait once, process once." It is "wait, then drain."

The current `iTidy` source shows exactly that pattern around GadTools windows: `WaitPort(window->UserPort)` followed by a loop over `GT_GetIMsg()` and later reply handling [S31 L1308-L1319].

### Tasks Versus DOS-Capable Processes

The `AddTask()` autodoc is blunt that tasks are low-level building blocks and generally cannot call `dos.library` functions, while DOS-capable work should use processes instead [S39 §WARNING ¶1-2]. That rule is one of the most important architectural guardrails in this codebase because many library and filesystem operations are only safe in a process context.

### Library Opening

`OpenLibrary()` historically carries a task-versus-process caveat too. The autodoc notes that only processes are allowed to call it in the fully general case because disk-backed library opening may require DOS involvement, even though later systems added more protection for tasks [S38 §FUNCTION ¶1-3] [S38 §NOTES ¶1-3].

## Concrete Relevance In `iTidy`

The current target app uses `exec.library` behavior directly and indirectly:

- it checks `SysBase->LibNode.lib_Version` at startup to enforce a Workbench 3.0 floor [S30 L121-L128] [S30 L136-L176]
- it relies on automatic Workbench-startup handling through the C runtime and then exits with `RemTask(NULL)` in the Amiga path [S30 L623-L687] [S30 L880-L886]

That makes `exec.library` support part of basic process correctness, not just an implementation detail hidden below the app.

## Working Rule

For this project, `exec.library` work should initially prioritize:

1. correct task/process identity,
2. correct port, signal, and message semantics,
3. correct library-open assumptions,
4. predictable memory and shutdown behavior.
