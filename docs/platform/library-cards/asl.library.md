---
title: "asl.library"
status: draft
depends_on:
  - "../gui-stack.md"
  - "../structs/wbarg.md"
citations_used:
  - "S1"
  - "S31"
  - "S63"
  - "S71"
---

# asl.library

Purpose: Summarize Amiga requester APIs.

Needed for:
- Supporting file and directory requesters in target apps.

## Summary

`asl.library` is the standard requester library used for file, font, and screen-mode dialogs. For this project, its most immediate importance is not "general dialogs" in the abstract, but the concrete requester path that real Workbench utilities use to ask the user for drawers, files, and related selections [S71 §AllocAslRequest].

## Requester Types

The header defines three standard requester families:

- `ASL_FileRequest`
- `ASL_FontRequest`
- `ASL_ScreenModeRequest` [S1 Include_H/libraries/asl.h L45-L48]

The current target app uses file requesters directly. `iTidy` allocates an `ASL_FileRequest` (via the `AllocAslRequestTags` inline wrapper) and opens it with tags such as `ASLFR_TitleText`, `ASLFR_DrawersOnly`, and `ASLFR_InitialDrawer` to let the user choose a folder to process [S31 L470-L518], and reads `fr_Drawer`/`fr_File` back on accept [S31 L495-L500, L2430-L2433].

## File Requester Data Model

The `FileRequester` structure is library-owned and read-only to callers: it must only be allocated by `asl.library`, and callers control it through tags passed to `AllocAslRequest()` and `AslRequest()` rather than by mutating fields directly [S1 Include_H/libraries/asl.h L52-L60] [S71 §AllocAslRequest]. The fields most relevant to this repository are:

- `fr_File`
- `fr_Drawer`
- `fr_NumArgs`
- `fr_ArgList`
- `fr_UserData`
- `fr_Pattern` [S1 Include_H/libraries/asl.h L61-L77]

The `rf_File`/`rf_Dir`/`rf_Pat` aliases are pre-V38 spellings of the same fields [S1 Include_H/libraries/asl.h L477-L486]. `fr_ArgList` means ASL selection can flow back into Workbench-style `WBArg` data rather than only raw strings [S1 Include_H/libraries/asl.h L72-L74].

**NDK provenance caveat.** The header copy under `assets/docs/ndk/NDK3.2/` identifies itself as a later V47-era NDK, and `docs/sources.md` [S1] warns against citing that cache path as classic 3.0-3.1 evidence without independent verification. For this library the risk is small and was checked: the tag base `ASL_TB = TAG_USER+0x80000` [S1 Include_H/libraries/asl.h L40] and the file-requester tag numbers are documented for the classic API [S71 §AslRequest], and `iTidy` reads only `fr_File`/`fr_Drawer` — fields in the stable head of the structure that both the classic and the cached layout agree on (the app's `rf_Dir` usage [S31 L495-L500, tool_cache_window.c L160] and `fr_Drawer + fr_File → AddPart` usage [S31 L2430-L2433] are grep-verified).

## Tag-Driven Configuration

The highest-value file-requester tags for the current project are:

- parent/screen attachment: `ASLFR_Window`, `ASLFR_Screen`, `ASLFR_PubScreenName`
- initial state: `ASLFR_InitialFile` (TB+8), `ASLFR_InitialDrawer` (TB+9), `ASLFR_InitialPattern` (TB+10)
- behavior flags: `ASLFR_DoSaveMode` (TB+44), `ASLFR_DoMultiSelect`, `ASLFR_DoPatterns` (TB+46)
- filtering: `ASLFR_DrawersOnly` (TB+47), `ASLFR_RejectIcons` (TB+60)
- text: `ASLFR_TitleText` (TB+1), `ASLFR_PositiveText` (TB+18), `ASLFR_NegativeText` (TB+19)
- storage: `ASLFR_UserData` (TB+52) [S1 Include_H/libraries/asl.h L88-L122]

Tag-list parsing follows the Exec protocol flat: `TAG_DONE` terminates, `TAG_IGNORE` skips the pair, `TAG_MORE` switches to a successor tag array, `TAG_SKIP` advances the current array by a number of entries [S71 §AslRequest].

These matter because early compatibility bugs show up as the wrong requester type, the wrong filtering behavior, or missing attachment to the right parent window.

## Repo Implementation Status

`src/amiga_ui/vamos/asllibrary.py` (`ASLLibrary`, registered in `extensions.py`) implements the three public FD functions the app uses, as genuine traps dispatched at their real LVIs (`AllocAslRequest` −48, `FreeAslRequest` −54, `AslRequest` −60 [S71]):

- **`AllocAslRequest(reqType, tagList)`** allocates a zeroed `FileRequester` block in emulated memory, decodes any alloc-time tag list, *copies* string tag values (`InitialDrawer`/`InitialFile`/`InitialPattern`) into ASL-owned memory (matching the library-owned-strings contract), and records the requester's options in a host-side per-address record. Only `ASL_FileRequest` is supported; other requester types raise an honest `UnsupportedFeatureError`.
- **Tag persistence.** Options set at allocation time (the `AllocAslRequestTags` + `AslRequest(freq, NULL)` pattern the app uses for its save/open requesters) stay in effect until the request, with request-time tags overriding — mirroring the documented "tag values stay in effect for each use of the requester" behavior [S71 §AslRequest].
- **`AslRequest(requester, tagList)`** presents the request through the host projection: a real, blocking, non-native `QFileDialog` carrying the app's own title and mode (`DrawersOnly` → `Directory`, `DoSaveMode` → `AnyFile` without overwrite confirmation [S63]) parented to the projected `ASLFR_Window` when one was given. Cancel returns FALSE with the structure untouched; accept writes the chosen drawer (and file part, when not drawer-only) into `fr_Drawer`/`fr_File` as ASL-owned strings and returns TRUE — exactly the contract the autodocs describe [S71 §AslRequest]. Strings cross the guest boundary as latin-1, the repo-wide `_read_cstr` convention.
- **`FreeAslRequest(requester)`** releases the struct and every ASL-owned string it handed out; double-free and unknown addresses are handled without corrupting the allocator.
- **`AslRequestTags`/`AllocAslRequestTags` are not LVIs.** They are `static __inline__` varargs wrappers in the SDK headers that compile into the app and JSR to the three real functions; the app never dispatches those names. (`AslRequestTags` exists in the class only as a delegating alias for direct host-side calls.)
- **Known gaps.** `AbortAslRequest`/`ActivateAslRequest` (async requester control) are unimplemented — no target calls them. The installed PySide6 has no public "show hidden files" option, so the classic requester's dot-file visibility is not translated; `ASLFR_DoPatterns` patterns are carried in the projection request but not yet applied as dialog name filters (known translation gaps under the rule in `docs/host-gui/translation-obligations.md`).

Verified by `tests/test_asl_library.py` (Qt-free tag decode/struct write-back), `tests/test_qt_asl_dialog.py` (offscreen `QFileDialog` round trip driven through `exec()`), and `tests/run_interactive_asl_smoke_test.py --branch {accept,cancel}` (real `iTidy` Browse button → real dialog → the app's own redraw of the chosen path observed in the live RastPort op log).

## Why It Matters To The Project

ASL is one of the points where GUI behavior, path semantics, and Workbench-style argument handling meet. If a target app cannot open a drawer-only requester, return a selected drawer correctly, or respect the expected parent-window context, the result will feel broken to the user even if the lower-level DOS path handling is otherwise fine.

## Working Rule

For this project, `asl.library` support should first preserve:

1. correct requester allocation and lifetime,
2. tag-driven configuration rather than ad hoc field mutation,
3. correct drawer/file selection return values,
4. correct parent-window attachment.
