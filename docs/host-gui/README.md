---
title: "Host GUI"
status: index
depends_on:
  - "../architecture/gui-strategy.md"
  - "../runtime/headless-gui.md"
citations_used:
  - "S57"
  - "S58"
---

# Host GUI

This section records the project's host-side GUI implementation rules for PySide6 and Qt Widgets.

Qt Widgets are the project-standard host GUI technology. The Qt docs describe them as the classic desktop-style UI toolkit in Qt, and the broader Qt UI overview positions them as the mature, feature-rich choice for traditional desktop interfaces rather than for fluid, touch-centric scenes [S57 §Qt Widgets User Interfaces ¶1-2] [S57 §Comparison of UI Technologies tbl.1]. The PySide6 module overview matches that: widgets are the core UI elements, layouts are the standard arrangement mechanism, and custom widgets are created by subclassing `QWidget` or a suitable subclass [S58 §Detailed Description ¶1-4] [S58 §Widgets ¶1-3] [S58 §Layouts ¶1-2].

## Read First

1. `qt-widgets-primer.md`
2. `widget-mapping.md`
3. `translation-obligations.md`
4. `component-implementation-standard.md`
5. `menus-dialogs-and-requesters.md`
6. `painting-styling-and-layout.md`
7. `threading-and-desktop-boundaries.md`
8. `testing-host-ui.md`

## Project Rules

- Use Qt Widgets, not Qt Quick or QML, for normal host GUI work.
- Prefer built-in widgets and layouts first.
- Translate visible Amiga UI behavior into real host UI behavior or fail honestly; do not satisfy it with fabricated success values by default.
- Use custom `QWidget` painting only when standard widgets would erase required Workbench semantics.
- Keep menus inside the app window rather than treating Workbench's screen-top menu bar as a desktop-global integration point.
- Keep GUI code simple enough to run consistently both in a normal Linux desktop session and under the project `Xvfb` path.
