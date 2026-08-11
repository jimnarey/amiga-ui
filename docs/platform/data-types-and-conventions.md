---
title: "Data Types And Conventions"
status: draft
depends_on:
  - "amiga-primer.md"
citations_used:
  - "S1"
  - "S5"
  - "S36"
---

# Data Types And Conventions

Purpose: Record Amiga-specific data rules that affect implementation.

Needed for:
- Avoiding repeated confusion about pointers, strings, tags, and handles.

## Summary

The Amiga APIs used by this project rely on a handful of conventions that are easy to flatten away accidentally in Python: relative pointers, BCPL strings, small fixed-size integer types, DOS truth values, and tag lists. These conventions are not historical trivia. They directly affect filesystem access, Workbench argument handling, icon APIs, and many GUI calls.

## Fixed-Size Scalar Types

The NDK `exec/types.h` header defines the core scalar vocabulary used across the OS:

- `LONG` and `ULONG` are 32-bit values
- `WORD` and `UWORD` are 16-bit values
- `BYTE` and `UBYTE` are 8-bit values
- `BOOL` is a 16-bit field-oriented boolean type
- `STRPTR` is a pointer to a NUL-terminated string
- `APTR` is an untyped absolute pointer [S1 Include_H/exec/types.h L70-L82] [S1 Include_H/exec/types.h L113-L170]

Two practical cautions matter here:

- `APTR` is an untyped pointer, not a "do anything safely" pointer type [S1 Include_H/exec/types.h L70-L77]
- `BOOL` is a structure-compatibility type, not the same thing as modern language-level booleans [S1 Include_H/exec/types.h L160-L170]

## BPTR And BSTR

AmigaDOS uses BCPL-derived pointer conventions in some core structures:

- `BPTR` is a longword pointer
- `BSTR` is a longword pointer to a BCPL string [S1 Include_H/dos/dos.h L130-L143]

The same header explains the key rule: BCPL pointers store the byte address divided by four, and `BADDR(x)` converts a `BPTR` back into a normal address [S1 Include_H/dos/dos.h L130-L143].

This matters because code that treats every pointer-like field as an ordinary byte-addressed pointer will misread important DOS and Workbench structures.

## DOS Truth Values

The DOS layer uses `DOSTRUE == -1` and `DOSFALSE == 0` [S1 Include_H/dos/dos.h L20-L24]. The `dos.library` overview makes the same semantic warning in prose: DOS truth values follow the older BCPL/Tripos style rather than the modern "1 means true" assumption [S5 §Boolean values ¶1-8].

In practice, that means return-value handling should not silently normalize all non-zero results to `1` if exact behavior is being modeled or forwarded.

## Locks And Current Directories

The Amiga path model relies heavily on locks rather than just path strings. The `dos.library` overview states that the current directory is itself represented by a lock, and that `Lock()` plus `CurrentDir()` are central path-handling operations [S5 §Path names and current directories ¶6-8].

For this repository, a lock is therefore not "just an opaque handle." It is often part of the actual meaning of a Workbench argument or a process's directory context.

## TagItem Conventions

Many Amiga APIs use extensible tag lists instead of long fixed parameter lists. The NDK defines:

- `struct TagItem { Tag ti_Tag; ULONG ti_Data; }`
- control tags such as `TAG_DONE`, `TAG_IGNORE`, `TAG_MORE`, and `TAG_SKIP`
- `TAG_USER` as the separator between control tags and subsystem tag spaces [S1 Include_H/utility/tagitem.h L29-L54]

The Tags documentation explains the same model in human terms: tags are attribute/value pairs collected into arrays or chained arrays, and they are the standard way to extend APIs without breaking older call sites [S36 §Introduction ¶1-3] [S36 §Simple Tag Usage ¶1-6].

## Alignment And Structure Fidelity

Several Amiga structures carry explicit layout assumptions. The DOS headers note, for example, that BCPL data is longword-aligned and that certain returned structures must be on 4-byte boundaries [S1 Include_H/dos/dos.h L60-L61] [S1 Include_H/dos/dos.h L130-L143].

For a Python compatibility layer, the main consequence is that "logically equivalent fields" are not enough if binary-facing code reads or writes structure layouts directly.

## Working Rule

When implementing or debugging compatibility behavior, preserve these conventions until there is a deliberate reason to abstract them away:

1. respect fixed field sizes,
2. distinguish `APTR` from `BPTR`,
3. preserve DOS truth-value conventions,
4. treat tag lists as structured input rather than as arbitrary kwargs,
5. keep lock-bearing structures semantically intact.
