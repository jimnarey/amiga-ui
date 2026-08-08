---
title: "workbench.library"
status: draft
depends_on:
  - "../workbench-model.md"
  - "../structs/wbstartup.md"
citations_used:
  - "S1"
  - "S2"
---

# workbench.library

Purpose: Summarize the Workbench-specific APIs and startup conventions.

Needed for:
- App arguments, AppIcon/AppWindow/AppMenuItem, and Workbench integration.

Depends on:
- `../workbench-model.md`
- `../structs/wbstartup.md`

Status: Draft.

Notes:
- This is one of the highest-priority cards for this repo.

## Summary

For this project, `workbench.library` matters less as a bag of miscellaneous API calls and more as the center of Workbench-specific application integration. The key areas are:

- startup argument conventions,
- AppWindow/AppIcon/AppMenuItem messaging,
- and the reuse of `WBArg`-style arguments after startup [S2 §WBStartup Message ¶1-16] [S2 §The AppMessage Structure ¶1-9].

## Why It Matters

The target application class is Workbench-oriented software. That means correctness depends on more than opening DOS files and libraries. A realistic compatibility layer eventually needs to support the parts of Workbench integration that let an application:

- understand how it was launched,
- receive Workbench objects as arguments,
- and possibly continue receiving Workbench-driven messages while already running.

## AppMessage

The NDK `workbench.h` header defines `AppMessage` with:

- `am_Type`
- `am_UserData`
- `am_ID`
- `am_NumArgs`
- `am_ArgList`
- version, class, mouse-position, and timestamp fields [S1 Include_H/workbench/workbench.h L131-L147]

The Workbench docs explain that this message is used when Workbench notifies an application about `AppWindow`, `AppIcon`, or `AppMenuItem` activity [S2 §The AppMessage Structure ¶1-9].

## AppObject Types

The header defines these core AppMessage types:

- `AMTYPE_APPWINDOW`
- `AMTYPE_APPICON`
- `AMTYPE_APPMENUITEM`
- `AMTYPE_APPWINDOWZONE` [S1 Include_H/workbench/workbench.h L149-L154]

The Workbench docs describe the first three as follows:

- an AppWindow accepts dropped icons through a window,
- an AppIcon accepts dropped icons through an icon,
- an AppMenuItem lets a running application add a Workbench menu action [S2 §The AppMessage Structure ¶1-5]

## Argument Reuse

One of the most important design facts is that `AppMessage.am_ArgList` uses the same `WBArg` format as `WBStartup.sm_ArgList` [S2 §The AppMessage Structure ¶5-9]. That is very helpful for the project because it means one compatible host-side representation of `WBArg` semantics can serve both:

- startup-time argument delivery,
- and later Workbench message delivery.

## Working Rule

If the project reaches the point of supporting drag-and-drop or running-app Workbench integration, it should model `workbench.library` behavior as an extension of the same argument-and-lock semantics already needed for `WBStartup`, not as a separate ad hoc subsystem.
