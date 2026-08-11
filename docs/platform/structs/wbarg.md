---
title: "WBArg"
status: draft
depends_on:
  - "../filesystem-and-launch.md"
  - "wbstartup.md"
citations_used:
  - "S1"
  - "S2"
---

# WBArg

Purpose: Explain how Workbench passes file and directory arguments.

Needed for:
- Correct interpretation of Workbench selection and launch context.

## Summary

`WBArg` is the unit Workbench uses to describe one launched or selected object. The NDK header defines it as a pair:

- `wa_Lock`
- `wa_Name` [S1 Include_H/workbench/startup.h L30-L33]

That pair matters because a Workbench argument is not simply a path string. It is a directory lock plus a name relative to that lock.

## Meaning Of The Fields

The Workbench documentation describes `wa_Name` as the name of an AmigaDOS filesystem object, and `wa_Lock` as a lock on the directory or object context associated with that name [S2 §WBStartup Message ¶11-13].

In practical terms:

- for the first argument, `wa_Name` is the program name and `wa_Lock` refers to the program's directory [S2 §WBStartup Message ¶11]
- for a launched project, `wa_Name` is the project filename and `wa_Lock` refers to the directory containing that file [S2 §WBStartup Message ¶12]

## Null Cases

The Workbench docs also spell out an important edge case: for directory, disk, or Trashcan icons, `wa_Name` may be `NULL`, and in some icon types `wa_Lock` may also be `NULL` if locks are not supported [S2 §WBStartup Message ¶13].

That means the project must not assume that every `WBArg` can be converted into a normal filename by blindly concatenating lock and name.

## Typical Usage Pattern

The standard Amiga pattern is:

1. turn the lock into a directory context,
2. use `wa_Name` relative to that context,
3. restore the old current directory afterwards.

The Workbench docs describe this explicitly through `CurrentDir(wa_Lock)` plus `wa_Name` access [S2 §WBStartup Message ¶16]. The NDK examples show the same pattern in real code, either by using `NameFromLock()` plus `AddPart()` to build a full path or by switching the current directory before opening `wa_Name` [S1 Examples/Backfill/Backfill.c L85-L93] [S1 DAControl+trackfile/DAControl/start.c L183-L195].

## Working Rule

Treat `WBArg` as structured location data, not as a filename string. Any host-side translation layer that flattens it too early risks getting:

- relative-path behavior wrong,
- directory selection semantics wrong,
- or lock ownership wrong.
