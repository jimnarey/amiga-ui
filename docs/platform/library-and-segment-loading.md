---
title: "Library And Segment Loading"
status: draft
depends_on:
  - "memory-model-and-address-space.md"
  - "data-types-and-conventions.md"
  - "structs/process-and-task.md"
citations_used:
  - "S1"
  - "S50"
  - "S51"
  - "S52"
  - "S53"
  - "S54"
  - "S55"
---

# Library And Segment Loading

Purpose: Explain how classic Amiga libraries and load modules enter memory and are used by applications.

Needed for:
- Understanding library bases, shared code, seglists, and process launch state.

Depends on:
- `memory-model-and-address-space.md`
- `data-types-and-conventions.md`
- `structs/process-and-task.md`

Status: Draft.

Notes:
- Focus on the classic model relevant to Workbench applications, not later OS4 interface details.

## Summary

Classic Amiga applications do not generally carry private in-process copies of operating-system libraries. The official libraries overview says that AmigaOS libraries are shared libraries and that only one copy of a shared library exists in memory no matter how many programs are using it [S52 §Introduction ¶2-4]. Applications open those libraries, receive library-base pointers, and then call through library vectors rather than directly embedding separate copies of the OS code [S50 §Libraries of functions ¶1-7] [S54 §What is a Library? ¶1-4].

## Runtime Libraries Are Shared System Modules

The programming guide distinguishes Amiga run-time libraries from link libraries. A run-time library lives in ROM or on disk, must be opened before use, and can be used by many programs at once even though only one copy exists in memory [S50 §Another Kind of Function Library ¶1-8]. If the library is disk-based, it may be loaded on demand and later flushed when no longer needed [S50 §Another Kind of Function Library ¶4-6].

That is much closer to "shared OS module with explicit open/close discipline" than to a modern per-process `dlopen()` mental model.

## The Library Base Is Real Data In Memory

The NDK `Library` structure defines the standard library base fields:

- version and revision,
- ID string,
- negative and positive size,
- checksum fields,
- and `lib_OpenCnt` for the number of current opens [S1 Include_H/exec/libraries.h L17-L50].

The Exec libraries overview describes the same model in prose: a library consists of functions, a vector table, and a `Library` structure, and the base pointer returned by `OpenLibrary()` points to that structure [S54 §What is a Library? ¶1-5].

For this project, two consequences matter immediately:

1. a library base is part of the emulated memory model, not just a token,
2. many apps read at least version information from those bases directly.

## Vectors And Negative Offsets Matter

The NDK header defines the standard library entry offsets `LIB_OPEN`, `LIB_CLOSE`, `LIB_EXPUNGE`, and `LIB_EXTFUNC`, as well as the negative-space layout used around a library base [S1 Include_H/exec/libraries.h L18-L28]. The Exec libraries overview explains why: library calls are reached through a vector table associated with the base structure [S54 §What is a Library? ¶1-5].

The programming guide makes the dynamic-loading consequence explicit. Because library code can live anywhere in memory, the system creates a vector table dynamically and preserves vector order across versions even when function bodies move [S50 §Dynamic memory architecture ¶3-7] [S51 §Libraries and Devices ¶17-19].

This is one of the most characteristically Amiga parts of the runtime model.

## Open, Close, And Delayed Expunge

The minimum library vector set includes OPEN, CLOSE, and EXPUNGE. The Exec libraries overview says OPEN usually increments `lib_OpenCnt`, CLOSE decrements it, and EXPUNGE may be delayed if someone still has the library open [S54 §Minimum Subset of Library Vectors ¶1-6]. The `LIBF_DELEXP` flag in the NDK header names that delayed-expunge state directly [S1 Include_H/exec/libraries.h L46-L50].

For compatibility work, that means:

- library lifetime is shared rather than per-app private,
- open count is part of the real behavior,
- and unloading is not just "free everything when this process exits."

## Resident Modules And Initialization

The NDK `Resident` structure is the OS-level metadata used to identify and initialize code modules, with fields for flags, version, type, priority, name, ID string, and init pointer [S1 Include_H/exec/resident.h L17-L35]. The Exec proto surface includes `FindResident()`, `InitResident()`, and `MakeLibrary()` as part of module and library creation machinery [S1 Include_H/clib/exec_protos.h L48-L53].

This is a lower-level implementation detail than most applications need, but it matters for understanding why library loading is an OS concern rather than a simple file-open operation.

## Executables Load As Segment Lists

Amiga executables and similar load files are brought into memory through `LoadSeg()`. The `LoadSeg()` autodoc says it allocates memory for CODE, DATA, and BSS segments, connects them into a segment list or "seglist," and returns a BPTR to that seglist [S53 §FUNCTION ¶1-4] [S53 §RESULT ¶1]. It also says the resulting load module may later be unloaded with `UnLoadSeg()` [S53 §FUNCTION ¶2-3].

The same autodoc explains the classic scatter-loading model: segments are not loaded to predefined addresses. They are dynamically allocated, relocated, and scattered through memory as needed [S53 §NOTES ¶4-8].

That behavior lines up directly with the soft-machine memory model described elsewhere in the docs.

## Processes Remember Their Loaded Program

The AmigaDOS data-structures guide explains that a process carries the state associated with its loaded program and stack, and that cleanup behavior is tied to process lifetime [S55 §CLI process ¶1-4]. Combined with the `CreateProc()` and `LoadSeg()` proto surfaces [S1 Include_H/clib/dos_protos.h L62-L65], the practical point is that a launched program is not just a naked instruction pointer. It is a process plus a load module plus DOS-side execution context.

## Practical Consequences For This Repository

For this repo, the most useful implementation consequences are:

- library bases must look like real in-memory objects,
- version checks against those bases are normal and expected,
- shared library lifetime is separate from one app's lifetime,
- executable code and data arrive as relocatable load modules, not fixed-address blobs,
- and process startup must preserve enough launch state that seglists, current directories, and Workbench arguments still make sense together.

## Working Rule

When an Amiga app "opens a library" or "loads a program," think in terms of shared OS-managed in-memory objects:

1. library base plus vectors plus open count,
2. load module plus seglist plus relocation,
3. process context wrapped around both.
