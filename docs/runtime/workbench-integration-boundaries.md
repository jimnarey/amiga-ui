---
title: "Workbench Integration Boundaries"
status: draft
depends_on:
  - "../platform/library-cards/workbench.library.md"
  - "../apps/itidy/runbook.md"
citations_used:
  - "S1"
  - "S2"
  - "S30"
---

# Workbench Integration Boundaries

Purpose: Distinguish first-wave Workbench launch support from later running-app Workbench integration features.

Needed for:
- Preventing premature expansion into richer Workbench desktop behavior.

Depends on:
- `../platform/library-cards/workbench.library.md`
- `../apps/itidy/runbook.md`

Status: Draft.

Notes:
- This document narrows priorities rather than claiming later Workbench APIs are unimportant forever.

## Summary

Workbench-facing support is not one single feature. The official Workbench APIs distinguish between startup semantics such as `WBStartup` and later running-application behaviors such as `AppWindow`, `AppIcon`, and `AppMenuItem` messaging [S2 §WBStartup Message ¶1-16] [S2 §The AppMessage Structure ¶1-9] [S1 Include_H/clib/wb_protos.h L36-L49]. The current target app's immediate pressure is startup and normal window/requester behavior, not rich running-app Workbench integration [S30 L277-L389] [S30 L623-L687].

## First-Wave Workbench Support

Treat these as first-wave Workbench obligations:

- `WBStartup` launch semantics
- `WBArg` interpretation
- current-directory behavior during Workbench launch
- tooltype lookup through the program icon
- normal Workbench-oriented window, requester, and menu behavior inside the application

These are directly relevant to `iTidy`.

## Later-Phase Workbench Integration

Treat these as later-phase by default:

- `AppWindow`
- `AppIcon`
- `AppMenuItem`
- richer running-app Workbench message delivery
- drag-and-drop from Workbench into a running app
- desktop-level integration behaviors beyond launch

They matter, but they should not silently become part of the first milestone unless a real target forces them.

## Stop Rule

If a blocker is really about running-app Workbench integration rather than launch-time Workbench semantics or ordinary in-window UI, stop and document that boundary before widening the implementation target.

## Working Rule

Support Workbench as an application-launch and application-usage context first. Treat running-app desktop integration as a separate later subsystem, not as something to absorb accidentally while chasing an unrelated blocker.
