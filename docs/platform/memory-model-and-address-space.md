---
title: "Memory Model And Address Space"
status: draft
depends_on:
  - "amiga-primer.md"
  - "data-types-and-conventions.md"
  - "structs/process-and-task.md"
citations_used:
  - "S1"
  - "S50"
  - "S51"
  - "S56"
---

# Memory Model And Address Space

Purpose: Explain the Amiga memory model the project is actually trying to emulate around.

Needed for:
- Avoiding Unix-shaped assumptions about process isolation and allocation.

## Summary

Classic AmigaOS is a multitasking system without hardware memory protection. The official programming overview says this directly and warns that an errant task can overwrite another task's code or data [S50 §What the System Doesn't Do For You ¶1-4]. For this project, that means the right mental model is not "many isolated Unix processes" but "many tasks sharing one machine-wide address space under OS-managed coordination."

## Shared Address Space, Not Process Isolation

The official Amiga programming overview describes the platform as multitasking without memory protection [S50 §Programming in the Amiga Environment ¶1-1]. It also explains the practical consequence: the operating system arbitrates access to shared resources, but it does not stop a task from touching memory it did not legally acquire [S50 §What the System Doesn't Do For You ¶1-4].

That distinction matters a great deal here:

- shared use of a library does not imply separate per-process copies,
- a bad pointer can damage unrelated program state,
- and allocation and cleanup discipline are part of normal application correctness rather than optional hardening.

## Dynamic Memory, Not Fixed Load Addresses

The official Exec introduction describes the Amiga as having a soft-machine architecture in which tasks do not use fixed memory addresses and must obtain memory from the operating system [S51 §Dynamic Memory Allocation ¶1-5]. The broader programming guide makes the same point at a higher level by calling out a dynamic memory architecture with no fixed memory map [S50 §Programming in the Amiga Environment ¶1-1].

This is one reason the current project can sensibly build on `vamos`: many important Amiga behaviors are already phrased in terms of dynamic OS-mediated structures rather than in terms of hard-coded physical addresses.

## Exec Owns The Memory Inventory

The NDK `ExecBase` definition shows that Exec keeps global memory bookkeeping as part of its own base structure, including a `MemList` alongside the system's library, device, port, and task lists [S1 Include_H/exec/execbase.h L81-L90]. The NDK memory headers then define:

- `MemHeader` for a managed memory region,
- `MemChunk` for free chunks,
- `MemList` and `MemEntry` for tracked allocations and cleanup [S1 Include_H/exec/memory.h L19-L59].

This is the concrete shape behind the high-level rule that "you must ask the system for memory." Memory on AmigaOS is not just raw bytes. It is part of a global Exec-managed resource model.

## Allocation Is A Task-Or-Process Activity

The `AllocVec()` autodoc states two especially relevant rules:

1. every allocation must be checked for failure,
2. memory allocation, deallocation, and availability queries require a task or process context and are not safe from interrupt code [S56 §WARNING ¶1-2].

That pairs neatly with the shared-address-space model: the system centralizes allocation, but it still expects callers to behave responsibly and to be in a valid execution context.

## Memory Types Still Matter

The programming guide also reminds classic developers that there are two important memory classes on old hardware: Chip memory and Fast memory [S50 §Two Kinds of Memory ¶1-6]. That distinction is mostly out of scope for the project's target app class, but it still matters as background because:

- it explains why some classic software cares deeply about allocation flags,
- and it reinforces that Amiga memory semantics are more explicit than a generic "heap" abstraction.

For Workbench-class utilities, the first-order concern is usually not Chip-versus-Fast placement, but correct allocation, lifetime, and visibility.

## Practical Consequences For This Repository

For the repo's compatibility layer, the most important implications are:

- structure pointers and library bases refer into a shared Amiga-shaped memory world,
- ownership errors can create cross-component corruption rather than neat per-process failure,
- task/process context matters when calling Exec and DOS services,
- and "works under one run" is not enough if lifetime and cleanup are wrong.

This is also why so many docs in the repo emphasize exact struct shapes, lock ownership, and cleanup rules. In a shared address-space model, those details are architectural, not cosmetic.

## Working Rule

When designing host-side behavior, do not assume Amiga tasks have the safety boundaries of modern desktop processes. Prefer models that preserve:

1. shared visibility of OS-managed structures,
2. explicit allocation and cleanup,
3. task/process context requirements,
4. and the possibility that one bad memory decision can have system-wide effects.
