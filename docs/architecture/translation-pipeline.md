---
title: "Translation Pipeline"
status: draft
depends_on:
  - "runtime-model.md"
  - "../platform/library-cards/README.md"
  - "gui-strategy.md"
citations_used:
  - "S7"
  - "S8"
  - "S9"
  - "S30"
  - "S31"
  - "S40"
  - "S41"
---

# Translation Pipeline

Purpose: Show how one Amiga-side action becomes one host-side effect.

Needed for:
- Designing small, testable implementation steps.

Depends on:
- `runtime-model.md`
- `../platform/library-cards/README.md`
- `gui-strategy.md`

Status: Draft.

Notes:
- Include API interception, state translation, host rendering, and result propagation.

## Summary

The core implementation pattern for this project is not "run an Amiga app and magically mirror it." It is a translation pipeline: `vamos` executes m68k code, intercepted library behavior is turned into project-owned semantic events, those events update host-side state or UI, and results are then propagated back in the Amiga-shaped form the program expects [S7 L21-L31] [S8 L18-L32].

## Pipeline Stages

### 1. Amiga Code Executes Under `vamos`

The original binary runs as m68k code under `vamos`, with configured volumes, assigns, memory, and library dispatch [S7 L21-L31] [S7 L64-L77]. This stage is responsible for CPU execution and the low-level Amiga memory model, not for deciding what the host GUI should look like.

### 2. Library Call Or Message Boundary Is Reached

The next useful boundary is usually a trapped library call, a Workbench startup structure, or a message-port event. `Vamos` can route library behavior through Python-owned implementations or other configured library modes [S8 L40-L55]. That is the moment where project code gets a stable place to intervene.

Typical first-wave boundaries include:

- opening libraries
- handling Workbench launch data
- resolving paths and locks
- loading or saving icon metadata
- opening windows, gadgets, or requesters

### 3. Compatibility Layer Interprets Intent

Project-owned code should then translate the low-level call into a higher-level project intent. Examples:

- "open the main iTidy window"
- "show a drawer requester"
- "update this icon's default tool"
- "persist this drawer geometry"

This is the critical anti-spaghetti step. It keeps the project from hardwiring every Amiga-side call directly to a Qt widget mutation.

### 4. Host State Is Updated

The interpreted intent updates a host-side model or state object. Not every action should repaint a window immediately. Some actions should only update:

- path state
- icon metadata state
- request/response state
- pending GUI state
- cached Workbench-like objects

This stage is what makes small, testable fixes possible: state changes are easier to inspect and validate than one giant "UI did something" side effect.

### 5. Host GUI Or Filesystem Effect Occurs

Once the translated state is ready, the host layer performs the visible or persistent effect:

- a Qt dialog opens
- a widget label changes
- a list refreshes
- a `.info`-backed state object is written back to disk
- a log or trace artifact is emitted

The GUI strategy doc defines the main rule here: standard Qt Widgets first, custom painting only where needed.

### 6. Result Is Converted Back To Amiga-Side Form

The project must then turn the host outcome back into the kind of result the Amiga program expects:

- return values
- updated in-memory structs
- a filled requester result
- a changed current-directory or lock context
- a message arrival on a port

This stage matters because the app is still speaking Amiga semantics even when the host effect was implemented through Qt or POSIX.

## Example: Main Window Startup

`iTidy` provides a useful example. The binary starts under `vamos`, checks Workbench-era assumptions, distinguishes CLI from Workbench launch, and then proceeds toward main-window setup [S30 L598-L687]. Later it locks the Workbench screen, obtains `VisualInfo`, creates GadTools gadgets and menus, opens the window, and enters a request loop driven by the window's user port [S31 L1006-L1107] [S31 L1308-L1319].

In project terms, that should be modeled as:

1. Amiga startup and launch-mode detection,
2. semantic request for main-window creation,
3. host-side window/controller creation,
4. event loop bridging between Qt and Amiga-style message flow.

## Example: Event Loop Translation

The Amiga-side event pattern is explicit waiting plus message draining. `WaitPort()` waits for a port signal, and `GetMsg()`-style processing must then drain queued messages rather than assuming exactly one event per wakeup [S41 §FUNCTION ¶1-5] [S40 §FUNCTION ¶1-5]. `iTidy` follows the same pattern around its GadTools windows [S31 L1308-L1319].

The host-side translation should preserve that meaning even if Qt delivers the originating interaction through its own signal or event system.

## Design Rules

### Keep Boundaries Visible

Do not blur together:

- CPU execution,
- library semantics,
- project translation logic,
- host rendering,
- and persistence.

If a bug appears, those boundaries should make it obvious which layer is the likely culprit.

### Prefer Semantic Adapters Over One-Off Hooks

If several low-level calls all mean "update the current window model," route them through one adapter or state transition rather than several unrelated widget mutations.

### Make Return Paths Explicit

Every translated action should define not only the host-side effect but also what Amiga-side observable result is produced. Otherwise the program will get visually plausible behavior with logically broken state.

## Working Rule

When implementing a new compatibility feature, aim to add exactly one clear path through this pipeline:

1. identify the Amiga-side boundary,
2. interpret the intent,
3. update host state,
4. produce the host effect,
5. propagate the result back in Amiga form.
