---
title: "GUI Strategy"
status: draft
depends_on:
  - "compatibility-scope.md"
  - "../platform/gui-stack.md"
  - "../runtime/headless-gui.md"
citations_used:
  - "S11"
  - "S18"
  - "S19"
  - "S20"
  - "S31"
---

# GUI Strategy

Purpose: Record the intended host GUI approach and its tradeoffs.

Needed for:
- Deciding when native widgets are enough and when custom drawing is required.

Depends on:
- `compatibility-scope.md`
- `../platform/gui-stack.md`
- `../runtime/headless-gui.md`

Status: Draft.

Notes:
- Start from PySide6/Qt Widgets, document expected threading model, and note where custom drawing is likely.

## Summary

The project-standard host GUI approach is PySide6 with Qt Widgets and not a browser-like UI layer. This choice fits the current target class because the first real applications are native Workbench utilities with menus, gadgets, requesters, and occasional custom drawing rather than highly animated scenes or direct hardware rendering [S11 L107-L112] [S31 L103-L142]. For automated runs, the same Qt Widgets layer is exercised under `Xvfb` using Qt's `xcb` platform plugin on X11 [S18 §Platform Plugin Dependencies tbl.1] [S19 §Selecting a QPA plugin ¶1-2] [S20 §Description ¶1-2].

## Primary Design Choice

The host UI should be built from ordinary Qt Widgets primitives first:

- `QMainWindow`, `QWidget`, `QDialog`
- standard menus and actions
- list, text, and selection widgets
- layout managers for resize behavior

The guiding rule is: use normal host widgets where the Amiga-side behavior is mostly semantic, and reserve custom painting for the smaller subset of places where the original app is expressing a specific visual or geometric intent.

## Expected Division Of Labor

### Use Standard Qt Widgets By Default

Use ordinary Qt controls when the Amiga-side concept is basically a conventional desktop control:

- buttons
- checkboxes
- string or integer entry
- list-style views
- menus
- file or folder selection dialogs

This should cover a large share of first-wave `iTidy`-class behavior.

### Use Custom Painting Selectively

Use custom painting only where the app's meaning depends on geometry or presentation details that a standard host widget would erase or distort. Likely examples include:

- custom group boxes or bevels
- progress surfaces with Amiga-specific visual rules
- icon-layout previews
- translated Workbench-like canvas areas

This is important because the current target class does sometimes mix standard GadTools controls with small amounts of direct drawing [S31 L1795-L1860].

## Threading Model

The host GUI must follow the normal Qt rule: UI objects live on the main GUI thread, and host-side rendering or widget mutation should not happen from arbitrary worker threads. For this project, that implies a conservative architecture:

1. `vamos` and the compatibility layer detect or synthesize an Amiga-side action.
2. Project-owned translation code turns that into a host-side state update or UI intent.
3. The Qt layer applies the visible change on the GUI thread.

If background work is needed later, it should feed results back into the GUI thread rather than directly mutating widgets.

## Human And Headless Modes

The same Qt Widgets code should run in both normal and automated modes. The difference should only be the outer display environment:

- human testing uses a normal Linux desktop session
- automated testing uses the project `Xvfb` wrapper and `QT_QPA_PLATFORM=xcb`

That keeps smoke tests honest and reduces the risk that automation and manual use silently diverge.

## Working Rule

When choosing how to represent an Amiga GUI behavior on the host:

1. prefer a standard Qt Widget if it preserves the semantics,
2. add a thin translation layer before inventing a custom surface,
3. use custom painting only when behavior or geometry truly requires it,
4. keep all host-widget mutation on the Qt GUI thread.
