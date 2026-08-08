---
title: "GUI Stack"
status: draft
depends_on:
  - "workbench-model.md"
  - "library-cards/gadtools.library.md"
  - "library-cards/intuition.library.md"
citations_used:
  - "S16"
  - "S26"
  - "S28"
---

# GUI Stack

Purpose: Describe the layers of Amiga GUI software relevant to target apps.

Needed for:
- Understanding what an app expects when it says Intuition, GadTools, or ClassAct.

Depends on:
- `workbench-model.md`
- `library-cards/gadtools.library.md`
- `library-cards/intuition.library.md`

Status: Draft.

Notes:
- Clarify the relationship between native system GUI APIs and add-on widget toolkits.

## Summary

The Amiga GUI stack relevant to this project is layered rather than monolithic. At the base of the native GUI model is `intuition.library`, which provides the fundamental screens, windows, menus, gadgets, and requesters used by applications [S26 §Components of Intuition tbl.1]. On top of that, higher-level helper layers exist to make common UI construction easier.

## Native Base Layer: Intuition

Intuition is the core GUI substrate. It provides the windowing and event model and the base gadget concepts [S26 §Intuition and the Amiga Graphical User Interface ¶1-3] [S28 §Intuition Gadgets ¶1-3].

For compatibility work, this is the layer that defines:

- what a window is,
- how input events arrive,
- and what basic user-interface controls mean.

## Convenience Layer: GadTools

The Intuition gadget documentation explicitly describes GadTools as a library that makes gadget programming easier and provides prefabricated application gadgets [S28 §Intuition Gadgets ¶3] [S28 §About Gadgets ¶3-4].

That makes GadTools a convenience layer above raw Intuition, not a separate window system. A GadTools-based application is still fundamentally an Intuition application.

## Add-On Toolkit Layer: ClassAct

ClassAct is an additional GUI toolkit rather than part of the minimal built-in system API. The presence of the `classact33` development package in the project assets reflects this distinction: it is relevant because real applications may depend on it, not because it defines the baseline Workbench GUI contract [S16].

For this project, ClassAct should therefore be treated as:

- conditionally in scope when a target app needs it,
- layered above the native GUI base rather than replacing it.

## Workbench Relationship

Workbench itself sits above these native GUI layers as the user's icon-driven desktop environment. It is not the same thing as Intuition, but it relies on the lower GUI stack while adding icon, drawer, and desktop integration behavior on top.

## Working Rule

When diagnosing a GUI compatibility failure, first ask which layer the app is actually depending on:

1. raw Intuition behavior,
2. GadTools convenience behavior,
3. higher-level toolkit behavior such as ClassAct,
4. or Workbench desktop integration behavior.

That question usually determines where the next fix belongs.
