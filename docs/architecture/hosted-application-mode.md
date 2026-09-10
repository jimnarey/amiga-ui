---
title: "Hosted Application Mode"
status: draft
depends_on:
  - "gui-strategy.md"
  - "translation-pipeline.md"
  - "../host-gui/README.md"
citations_used:
  - "S26"
  - "S57"
---

# Hosted Application Mode

Purpose: Record the default host presentation model for Amiga GUI applications.

Needed for:
- Preventing agents from inventing a visible Workbench desktop canvas.
- Giving host-window, menu, and event-loop work one settled target.

Notes:
- This is a project architecture decision, not a claim that classic Intuition
  behaves exactly like a modern desktop toolkit.

## Summary

The default runtime presentation is **hosted application mode**. The project keeps
a notional default public Workbench screen internally because Amiga APIs need a
screen, windows belong to screens, and Intuition owns concepts such as windows,
menus, gadgets, and requesters [S26 §Components of Intuition tbl.1]. That screen
is not rendered as a visible desktop canvas.

To the host user, each app-facing Amiga window should appear as an ordinary host
desktop window, similar to opening a Windows application under Wine. The user
should not see Workbench wallpaper, desktop icons, a screen title bar, or a
separate Workbench canvas unless a later feature explicitly introduces a classic
desktop mode.

## Public Screen Model

`LockPubScreen(NULL)` and related public-screen behavior still resolve to a
repo-owned default public screen. The screen is real in the compatibility layer:
it has Amiga-shaped state, it owns windows, and it remains the place where
screen-scoped Intuition semantics are coordinated.

The screen is invisible by default. Opening a normal application window must not
force the host to display a Workbench background or a containing desktop surface.
Helper, backdrop, or setup windows that exist only because a target expects a
Workbench-like environment should be represented internally unless they contain
real application UI that the user needs to see.

## Window Projection

Each app-facing Amiga `Window` maps to its own host top-level Qt window. The
Amiga `Window` struct remains authoritative for Amiga-side behavior:

- `WScreen` points at the notional public screen.
- `RPort` identifies the drawing target for recorded or rendered operations.
  Each opened app-facing window owns its **own** `RastPort` (a distinct
  allocation, not the public screen's embedded RPort). `OpenWindow`/
  `OpenWindowTagList` allocate it, initialize it to the documented standard
  values, copy the font/text metrics from the screen RPort explicitly, and store
  the pointer at `Window.RPort`. This guarantees two windows' drawing can never
  be replayed into the wrong host window.
- `UserPort` remains the IDCMP event-delivery path.
- `IDCMPFlags` determine which host-originated events may be delivered.

The host window is a projection of that Amiga state, not a replacement for it.
Host close, resize, menu, and input actions should be translated back into
Amiga-shaped messages for the owning window whenever the target requested those
events.

## Menu Projection

Classic Amiga applications attach menu strips to windows, while the visible menu
area belongs to the screen presentation. Hosted application mode deliberately
projects that into normal host-window behavior:

- A host window gets a menu bar only when its Amiga window has a menu strip.
- A host window without an Amiga menu strip has no host menu bar.
- The host menu bar is always-visible, ordinary desktop UI.
- Right-click menu activation is not part of the default mode.
- Host menu actions generate `IDCMP_MENUPICK` messages for the owning Amiga
  window's `UserPort`.

This preserves the important ownership rule for the target application: menu
selection belongs to one Amiga window at a time. The project does not merge
Workbench menus with application menus, and it does not expose a host-global
desktop menu for the invisible screen.

## Requesters And Modal UI

Requesters and modal child windows should also be backed by Amiga-side state and
message flow. They may project as host modal dialogs or host child windows when
that preserves the user's experience, but their results still need to return to
the target as Amiga-shaped memory updates, return values, or IDCMP messages.

## Implementation Consequences

This decision allows early GUI work to proceed in two layers:

1. non-rendering compatibility behavior that records windows, menus, drawing,
   text, and refresh operations in Amiga-shaped state; and
2. host projection code that turns that state into Qt Widgets when the project is
   ready to display it.

Drawing state is unified per window: the launcher installs one run-wide
`RastPortRegistry` on every library context (`ctx.rastports`), so `graphics.library`
(`Text`) and `intuition.library` (`PrintIText`) record into the *same* ordered
per-RastPort op log. A window's drawing — whether issued through graphics or
Intuition — is one chronological stream the projection layer can replay, rather
than per-library fragments.

Window-owned RastPorts close the loop: `OpenWindow`/`OpenWindowTagList` allocate
a window RPort, register it up-front in the run-wide registry (keyed by its
address), and point `Window.RPort` at it; `CloseWindow` unregisters and frees
that window's RPort (and the window) without touching any other window's state.
Because every RastPort is a distinct, registered address, per-window op-stream
isolation is structural rather than a matter of shared mutable state. The public
screen keeps its own embedded RastPort for screen-level drawing and for
`GetScreenDrawInfo`, which is a different target from any window's RPort.

Qt Widgets remain the host GUI toolkit for this mode because they provide normal
desktop windows, menu bars, dialogs, actions, widgets, and custom painting hooks
without requiring a browser or scene-graph UI [S57 §Qt Widgets User Interfaces ¶1-2].

## Launching From The Command Line

`amiga-ui run <path-to-amiga-binary>` is the supported, user-invokable launch
path for this mode. It reuses the probe's target resolution and prepared runtime
(the same `-V`/`-a`/`--cwd` vamos arguments — no divergent second preparation),
installs the real Qt host-window projection (rather than the probe's null
projection), and runs the target in-process on the GUI thread. When the target
run ends, the host shell stays open so the projected window(s) can be inspected;
the shell exits when the last projected window is closed, or after
`--auto-close-after <seconds>` for automation. `--timeout` bounds the target run
phase. With no usable display the command fails clearly (exit 2) rather than
aborting.

This keeps the two launch paths distinct and honest: `probe` stays
headless/null-projected and Qt-free, while `run` is the graphical,
user-facing path. The target reaching its `WaitPort`-on-empty-queue boundary
and the host shell exiting are separate, reported events — the run phase ends at
the boundary, and the shell stays open afterwards for inspection.

The static post-run shell is not the final interactive lifecycle. Live hosted
interaction uses the single-active-context cooperative design in
`cooperative-host-scheduler.md`: a supported blocking Amiga call yields to a
Qt-free host scheduler boundary, the Qt backend services events, and target
execution resumes only after the corresponding real Amiga-side condition is
true.

## Non-Goals

Hosted application mode does not require:

- a visible Workbench desktop;
- a visible screen title/menu strip area separate from app windows;
- right-click menu activation;
- desktop icons or Workbench backdrop rendering;
- full multi-screen Workbench emulation;
- or a host-global menu bar shared between applications.

Those may be revisited later as optional compatibility modes. They are not the
default path for first-wave Workbench utility support.

## Working Rule

When implementing visible UI behavior, keep the Amiga-side screen and window
model honest, but project user-facing application windows as normal host desktop
windows. Menus belong to the host window that represents the Amiga window whose
menu strip is set.
