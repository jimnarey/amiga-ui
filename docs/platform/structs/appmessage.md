---
title: "AppMessage"
status: draft
depends_on:
  - "wbarg.md"
  - "../library-cards/workbench.library.md"
citations_used:
  - "S1"
  - "S2"
---

# AppMessage

Purpose: Explain the structure Workbench uses for AppIcon, AppWindow, and AppMenuItem notifications.

Needed for:
- Any later support for drag and drop or Workbench app objects.

## Summary

`AppMessage` is the Workbench message structure used after application startup for running-app interactions such as AppIcons, AppWindows, and AppMenuItems. The NDK header defines it as an Exec `Message` plus app-object type, user data, ID, argument list, class, mouse coordinates, and timestamps [S1 Include_H/workbench/workbench.h L131-L147]. The Workbench docs explain that it is the vehicle Workbench uses to notify an application about those running-app events [S2 §The AppMessage Structure ¶1-9].

## Fields That Matter First

The highest-priority fields for this repository are:

- `am_Message`
- `am_Type`
- `am_UserData`
- `am_ID`
- `am_NumArgs`
- `am_ArgList` [S1 Include_H/workbench/workbench.h L133-L140]

These are the fields that determine what kind of Workbench event happened and what Workbench objects were attached to it.

## Type And Class

The header defines the core app-object message types as:

- `AMTYPE_APPWINDOW`
- `AMTYPE_APPICON`
- `AMTYPE_APPMENUITEM`
- `AMTYPE_APPWINDOWZONE` [S1 Include_H/workbench/workbench.h L149-L153]

For AppIcons, the same header also defines higher-level classes such as open, copy, rename, snapshot, leave-out, put-away, delete, and related actions [S1 Include_H/workbench/workbench.h L155-L170]. That means `am_Type` and `am_Class` together describe more than "some Workbench event happened." They identify the channel and often the user action.

## `WBArg` Reuse

The most important design fact is that `am_ArgList` uses `WBArg` entries just like `WBStartup` does [S2 §The AppMessage Structure ¶5-9]. For the project, that is excellent news: once `WBArg` handling is correct, later AppMessage support can reuse the same lock-plus-name translation model rather than inventing a separate path-passing scheme.

## What Can Wait

The remaining fields are real, but not first-wave priorities:

- mouse coordinates,
- timestamps,
- version/compatibility padding,
- reserved fields for later expansion [S1 Include_H/workbench/workbench.h L140-L146]

They matter once the project reaches drag-and-drop and richer running-app integration, but they do not need to block early Workbench-launch compatibility.

## Working Rule

If the project later adds AppIcon or AppWindow support, treat `AppMessage` as:

1. an Exec message envelope,
2. plus a typed Workbench event,
3. plus a reused `WBArg` payload,
4. not as a plain filename callback.
