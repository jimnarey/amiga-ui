---
title: "utility.library"
status: draft
depends_on:
  - "../data-types-and-conventions.md"
citations_used:
  - "S1"
  - "S45"
  - "S36"
  - "S44"
---

# utility.library

Purpose: Summarize general support functions, especially tags and helper routines.

Needed for:
- Interpreting API signatures and message construction.

## Summary

`utility.library` matters to this repository mainly because the Amiga tag system runs through so many other APIs. The utility autodocs index includes functions such as `FindTagItem`, `GetTagData`, `NextTagItem`, `AllocateTagItems`, `CloneTagItems`, `ApplyTagChanges`, and `MapTags` [S44 item 1]. In practice, that makes `utility.library` part of the connective tissue between higher-level libraries rather than a standalone subsystem.

## TagItem Basics

The NDK header defines:

- `typedef ULONG Tag;`
- `struct TagItem { Tag ti_Tag; ULONG ti_Data; }` [S1 Include_H/utility/tagitem.h L29-L35]

The Tags documentation explains the model directly: tags are attribute/value pairs collected into tag lists, and they exist specifically to extend APIs without breaking older call signatures [S36 §Introduction ¶1-3] [S36 §Tag Structures ¶1-4].

## Control Tags

The control tags defined in the header are:

- `TAG_DONE` or `TAG_END`
- `TAG_IGNORE`
- `TAG_MORE`
- `TAG_SKIP` [S1 Include_H/utility/tagitem.h L37-L45]

The Tags page explains their operational meaning in prose and clarifies that `TAG_MORE` chains another list while `TAG_SKIP` skips a specified number of items [S36 §Simple Tag Usage ¶2-4].

## Why `TAG_USER` Matters

The header defines `TAG_USER` as the high-bit separator between utility control tags and subsystem-specific tags [S1 Include_H/utility/tagitem.h L46-L54]. The Tags page then explains the practical consequence: Intuition, Graphics, ASL, and other subsystems each define their own tag spaces above that control layer [S36 §Simple Tag Usage ¶2-6].

That is important because many compatibility bugs will not be in "utility.library" code as such, but in how a target library interprets or forwards tag lists.

## Concrete Relevance In `iTidy`

The current target app already uses small explicit `TagItem` arrays when talking to icon-related APIs, for example to set the frameless flag and to request Workbench notification on save [S45 L189-L223]. That is a good reminder that even app-local code often uses raw tag arrays directly rather than only varargs wrappers.

## Working Rule

For this project, `utility.library` support should initially prioritize:

1. correct `TagItem` representation,
2. correct control-tag traversal semantics,
3. correct pointer-versus-integer handling in `ti_Data`,
4. faithful passing-through of tag lists between higher-level libraries.
