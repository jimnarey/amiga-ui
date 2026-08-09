---
title: "intuition.library"
status: draft
depends_on:
  - "../gui-stack.md"
citations_used:
  - "S1"
  - "S26"
  - "S27"
  - "S28"
---

# intuition.library

Purpose: Summarize the core Amiga windowing and event model.

Needed for:
- Translating GUI event flow into host-side behavior.

Depends on:
- `../gui-stack.md`

Status: Draft.

Notes:
- Focus on windows, IDCMP events, gadgets, and message processing.

## Summary

`intuition.library` is the core native GUI layer beneath Workbench. The official Intuition overview describes it as the library and data-structure collection used to open windows, manage menus, monitor gadgets, read mouse position, and perform other user-interface work for Amiga applications [S26 §Intuition and the Amiga Graphical User Interface ¶1-3].

## What It Owns

The Intuition docs group its main GUI objects into:

- screens,
- windows,
- menus,
- gadgets,
- requesters [S26 §Components of Intuition tbl.1]

For this project, the highest-value subset is windows plus gadgets plus event delivery, because that is the minimum needed to translate many Workbench utility interactions into host-side behavior.

## High-Value APIs

The Intuition prototype surface makes the first implementation wave fairly clear:

- `OpenWindowTagList()`, `OpenWindowTags()`, and `CloseWindow()` for window lifetime [S1 Include_H/clib/intuition_protos.h L145-L148] [S1 Include_H/clib/intuition_protos.h L37-L38]
- `LockPubScreen()` and `UnlockPubScreen()` for Workbench or named public-screen attachment [S1 Include_H/clib/intuition_protos.h L126-L134]
- `ModifyIDCMP()` for selecting which events a window receives [S1 Include_H/clib/intuition_protos.h L50-L52]
- `SetMenuStrip()` and `ClearMenuStrip()` for menu attachment [S1 Include_H/clib/intuition_protos.h L35-L35] [S1 Include_H/clib/intuition_protos.h L73-L74]
- `Request()`, `AutoRequest()`, `EasyRequest()`, and `BuildEasyRequest()` for requester behavior [S1 Include_H/clib/intuition_protos.h L70-L74] [S1 Include_H/clib/intuition_protos.h L91-L95] [S1 Include_H/clib/intuition_protos.h L140-L144]

That list is not exhaustive, but it covers most of the Intuition calls a normal Workbench utility reaches before it gets into more specialized behavior.

## Window Event Flow

The Window Communication docs explain that Intuition notifies applications of user activity primarily through the IDCMP message-port mechanism, where input events arrive as Exec messages associated with a window [S27 §Communicating with Intuition ¶1-4] [S27 §The IDCMP ¶1-3]. This is a crucial architectural clue for the host translation layer: native Amiga GUI logic is fundamentally message-driven.

## Gadgets

The Intuition gadget docs describe gadgets as the Amiga equivalent of buttons, knobs, and similar controls, and distinguish between:

- system gadgets managed by Intuition,
- application gadgets managed by the application [S28 §Intuition Gadgets ¶1-3] [S28 §About Gadgets ¶1-4]

They also note that GadTools exists specifically to make gadget programming easier [S28 §Intuition Gadgets ¶3] [S28 §About Gadgets ¶3].

## Close And Resize Semantics

The Window Communication docs emphasize a subtle but important behavior: system gadgets for size, position, and depth are mostly managed directly by Intuition, but the close gadget is different. Selecting it sends a message to the application, and the application is responsible for actually closing the window [S27 §System Gadgets ¶1-3].

That distinction matters because a host-side compatibility layer should not collapse every visible window control into immediate host-native behavior if the original Amiga model expected application-level confirmation or processing first.

## Working Rule

For this project, `intuition.library` support should first aim to preserve:

1. message-driven window input,
2. gadget activation semantics,
3. application responsibility for handling close and related events,
4. the distinction between system-managed and application-managed controls.
