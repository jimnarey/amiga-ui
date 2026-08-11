---
title: "asl.library"
status: draft
depends_on:
  - "../gui-stack.md"
  - "../structs/wbarg.md"
citations_used:
  - "S1"
  - "S31"
---

# asl.library

Purpose: Summarize Amiga requester APIs.

Needed for:
- Supporting file and directory requesters in target apps.

Notes:
- Track whether `iTidy` or later apps actually rely on ASL.

## Summary

`asl.library` is the standard requester library used for file, font, and screen-mode dialogs. For this project, its most immediate importance is not "general dialogs" in the abstract, but the concrete requester path that real Workbench utilities use to ask the user for drawers, files, and related selections [S1 Include_H/libraries/asl.h L46-L60].

## Requester Types

The NDK header defines three standard requester families:

- `ASL_FileRequest`
- `ASL_FontRequest`
- `ASL_ScreenModeRequest` [S1 Include_H/libraries/asl.h L46-L49]

The current target app uses file requesters directly. `iTidy` allocates an `ASL_FileRequest`, then opens it with tags such as `ASLFR_TitleText`, `ASLFR_DrawersOnly`, and `ASLFR_InitialDrawer` to let the user choose a folder to process [S31 L470-L518].

## File Requester Data Model

The `FileRequester` structure is explicitly library-owned and read-only to callers. The header states that it must only be allocated by `asl.library`, and that callers control it through tags passed to `AllocAslRequest()` and `AslRequest()` rather than by mutating fields directly [S1 Include_H/libraries/asl.h L52-L60].

The fields most relevant to this repository are:

- `fr_File`
- `fr_Drawer`
- `fr_NumArgs`
- `fr_ArgList`
- `fr_UserData` [S1 Include_H/libraries/asl.h L61-L77]

The presence of `fr_ArgList` is especially useful context because it means ASL selection can flow back into Workbench-style `WBArg` data rather than only raw strings [S1 Include_H/libraries/asl.h L72-L74].

## Tag-Driven Configuration

The highest-value file-requester tags for the current project are:

- parent/screen attachment: `ASLFR_Window`, `ASLFR_Screen`, `ASLFR_PubScreenName`
- initial state: `ASLFR_InitialFile`, `ASLFR_InitialDrawer`
- behavior flags: `ASLFR_DoMultiSelect`, `ASLFR_DoPatterns`
- filtering: `ASLFR_DrawersOnly`, `ASLFR_RejectIcons`, `ASLFR_AcceptPattern` [S1 Include_H/libraries/asl.h L81-L126]

These matter because early compatibility bugs are likely to show up as the wrong requester type, the wrong filtering behavior, or missing attachment to the right public screen.

## Why It Matters To The Project

ASL is one of the points where GUI behavior, path semantics, and Workbench-style argument handling meet. If a target app cannot open a drawer-only requester, return a selected drawer correctly, or respect the expected public-screen context, the result will feel broken to the user even if the lower-level DOS path handling is otherwise fine.

## Working Rule

For this project, `asl.library` support should first preserve:

1. correct requester allocation and lifetime,
2. tag-driven configuration rather than ad hoc field mutation,
3. correct drawer/file selection return values,
4. correct parent-window or public-screen attachment.
