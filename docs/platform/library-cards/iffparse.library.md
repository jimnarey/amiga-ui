---
title: "iffparse.library"
status: draft
depends_on:
  - "../data-types-and-conventions.md"
  - "../../apps/itidy/dependencies.md"
citations_used:
  - "S46"
  - "S47"
  - "S48"
  - "S49"
---

# iffparse.library

Purpose: Summarize structured IFF parsing support relevant to target apps.

Needed for:
- Preference-file parsing and later metadata-oriented app support.

Notes:
- Keep lower priority than the core GUI stack, but document the current `iTidy` touchpoints honestly.

## Summary

`iffparse.library` is the standard AmigaOS helper for reading and writing structured IFF data without hard-coding one specific file format. The official overview describes it as a general parser built around an `IFFHandle`, stream initialization, and context-aware chunk traversal rather than around one fixed document type [S46 §IFFParse Library ¶1-4] [S46 §Basic Functions and Structures of IFFParse Library ¶1-3].

For this project, `iffparse.library` is not part of the first minimal Workbench contract in the same way as `dos.library`, `intuition.library`, or `icon.library`. However, it is no longer accurate to treat it as purely hypothetical. The current `iTidy` source uses it to read Workbench preference files such as `ENV:sys/icontrol.prefs` and `ENV:sys/font.prefs` [S48 L212-L266] [S49 L297-L347].

## Core Model

The key public object is `IFFHandle`. Applications allocate it with `AllocIFF()`, free it with `FreeIFF()`, attach a stream, initialize stream handling, and then open the parser in read or write mode [S46 §Basic Functions and Structures of IFFParse Library ¶1-3] [S46 §Initialization ¶1-9].

For DOS-file usage, the normal pattern is:

1. open the file with AmigaDOS,
2. store the file handle in `iff->iff_Stream`,
3. call `InitIFFasDOS()`,
4. call `OpenIFF()`,
5. parse or read chunks,
6. call `CloseIFF()`,
7. close the underlying file yourself [S46 §Initialization ¶4-9] [S46 §Termination ¶1-4].

That ownership split matters to the project because it means a compatibility layer must preserve both parser lifetime and the separate lifetime of the underlying DOS file handle.

## High-Value Functions

The project does not need the full library surface memorized up front. The highest-value functions for current analysis are:

- `AllocIFF()` / `FreeIFF()` for parser lifetime [S46 §Basic Functions and Structures of IFFParse Library ¶1-3]
- `InitIFFasDOS()` for ordinary file-backed parsing [S46 §Initialization ¶4-6]
- `OpenIFF()` / `CloseIFF()` for starting and ending a parser transaction [S46 §Initialization ¶9-10] [S46 §Termination ¶1-4]
- `ParseIFF()` for stepping through chunks [S47 §Parsing ¶1-3]
- `PropChunk()` / `FindProp()` for collecting property chunks by type and id [S47 §PropChunk()/FindProp() ¶1-6]
- `CurrentChunk()` and `ReadChunkBytes()` when the caller wants explicit chunk inspection or direct reads [S47 §Controlling Parsing ¶1-3] [S47 §Reading Chunk Data ¶1-2]

The official parsing guide also distinguishes `IFFPARSE_SCAN`, `IFFPARSE_STEP`, and `IFFPARSE_RAWSTEP`, with `STEP` returning control chunk by chunk while still invoking installed handlers [S47 §Other Parsing Modes ¶1-6] [S47 §IFFPARSE_STEP ¶1-1].

## Concrete Relevance In `iTidy`

`iTidy` currently uses `iffparse.library` in at least two practical places.

First, `fetchIControlSettings()` opens `ENV:sys/icontrol.prefs`, initializes an `IFFHandle` as a DOS stream, registers `PropChunk()` for `ID_PREF` and `ID_ICTL`, and then walks the file with `ParseIFF(IFFPARSE_STEP)` until it can `FindProp()` and copy the preference payload [S48 L203-L266]. This is a real dependency, but it is also somewhat forgiving: the code seeds default values before opening the file and falls back to those defaults if the prefs file is absent [S48 L214-L223] [S48 L262-L265].

Second, `GetWorkbenchIconFont()` allocates an `IFFHandle`, opens `ENV:sys/font.prefs`, and scans chunks until it finds `ID_FONT` data for the Workbench font [S49 L297-L347]. That path is also tolerant of failure because it defaults to `topaz.font` at size 8 before parsing begins [S49 L293-L295] [S49 L305-L311].

Those two facts together shape the implementation priority:

- `iffparse.library` is not safely ignorable forever,
- but missing support here is more likely to degrade polish than to block the first crude window from opening.

## Priority Rule

Treat `iffparse.library` as a second-wave compatibility target:

1. after core launch, DOS, icon, and window/event behavior,
2. before declaring preference-driven Workbench fidelity "done",
3. and earlier only if a real run shows that prefs parsing is the first blocker rather than a later enhancement.
