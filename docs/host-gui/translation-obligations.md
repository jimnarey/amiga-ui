---
title: "UI Translation Obligations"
status: draft
depends_on:
  - "widget-mapping.md"
  - "../architecture/translation-pipeline.md"
  - "../apps/itidy/runbook.md"
citations_used:
  - "S26"
  - "S31"
  - "S57"
  - "S58"
---

# UI Translation Obligations

Purpose: Define when visible Amiga GUI behavior must be translated into host UI behavior rather than satisfied by a stub or fabricated result.

Needed for:
- Preventing fake progress during compatibility work.
- Making the error-driven porting loop produce real UI capability.

Notes:
- This document records a project implementation rule, not an external framework requirement.

## Summary

Workbench applications are fundamentally about windows, menus, gadgets, and requesters [S26 §Components of Intuition tbl.1]. Qt Widgets is the chosen host toolkit precisely because it provides real desktop widgets for those kinds of interactions [S57 §Qt Widgets User Interfaces ¶1-2] [S58 §Detailed Description ¶1-4]. Therefore, when an intercepted Amiga-side behavior is supposed to create, update, or depend on visible UI, the default obligation is to translate it into host UI behavior rather than to return plausible values from a stub.

The current `iTidy` target already puts real pressure on this rule because it constructs menus, requesters, and a main window as part of its normal behavior [S31 L174-L227] [S31 L470-L518] [S31 L1006-L1085].

The generated API index from `uv run python tools/generate_api_index.py` adds a mechanical first pass over this rule. Entries marked `host-ui-required`, `workbench-visible-state`, or `likely-ui-support` should send an agent to this page before it writes a stub. The marker is not a complete design decision, but it is a warning that a fake pointer or no-op return probably hides the real compatibility work.

## The Main Rule

If the Amiga-side operation would normally produce a visible UI element, change visible UI state, or wait for a user-facing interaction, then the compatibility layer should normally do one of two things:

1. implement a real host-side translation for that behavior, or
2. fail honestly and record the missing capability.

It should not silently "solve" the blocker by fabricating a success result that bypasses the missing UI.

## Cases Where UI Translation Is Normally Required

Translation is normally required when the behavior would:

- open a window
- attach or update a menu
- create or refresh a gadget/control
- open a requester or dialog
- change visible text, selection, or enabled state
- wait for user input through a UI event path
- return data that should come from a user interaction

In those cases, a fake return value is usually the wrong shape of progress because it teaches the repo to skip the host GUI layer instead of building it.

## Shortcuts That Are Not Acceptable By Default

Do not treat these as valid default fixes:

- returning success from a window-open path without creating a host window
- pretending a requester was confirmed without showing a translated dialog
- inventing a directory or file choice that should have come from the user
- claiming a menu action happened without a host-side command path
- returning "reasonable" geometry, state, or text while the visible widget layer is still missing

Those approaches may move the program further on one run, but they make the resulting compatibility layer dishonest and harder to repair later.

## What Is Acceptable Instead

If the right UI translation is not ready yet, acceptable interim behavior is:

- fail clearly with a documented missing capability
- stop at an earlier honest blocker
- add narrow non-visual scaffolding that enables the real UI translation to be implemented next

The project wants scaffolding that leads into real translation, not stubs that become a parallel fake UI semantics layer.

## Narrow Exceptions

A temporary shortcut is only acceptable when all of the following are true:

1. the missing behavior is not the current user-visible blocker,
2. the shortcut does not fake a completed visible interaction,
3. the shortcut is explicitly documented as temporary,
4. and the next step remains the real UI translation rather than indefinite reliance on the shortcut.

This should be rare.

## Working Rule

When deciding whether to implement host UI now, ask:

1. would the original app expect the user to see or interact with something here?
2. is the program's next state supposed to depend on that visible interaction?

If the answer is yes, the default action is to build the host UI path or fail honestly, not to synthesize a plausible result.
