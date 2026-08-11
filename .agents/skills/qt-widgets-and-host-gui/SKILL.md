---
name: qt-widgets-and-host-gui
description: >
  Implement host-side GUI code with PySide6 Qt Widgets using the repository's
  widget, menu, threading, and testing rules. Use when adding or editing host
  windows, dialogs, menus, custom widgets, or host GUI tests.
---

# Qt Widgets And Host GUI

## Use This Skill When
- You are adding or editing host-side GUI code in PySide6.
- You need to choose between a built-in widget and a custom widget.
- You are implementing menus, dialogs, or requesters.
- You are writing or updating tests for host UI code.

## Goal
Keep host GUI work simple, consistent, and within the project's chosen Qt Widgets boundaries.

## Read These Docs First
- `docs/host-gui/qt-widgets-primer.md`
- `docs/host-gui/widget-mapping.md`
- `docs/host-gui/menus-dialogs-and-requesters.md`
- `docs/host-gui/painting-styling-and-layout.md`
- `docs/host-gui/threading-and-desktop-boundaries.md`
- `docs/host-gui/testing-host-ui.md`

## Default Rules
- Use Qt Widgets, not Qt Quick or QML.
- Prefer built-in widgets first.
- Use layouts before manual geometry.
- Keep menus inside the app window.
- Use `QAction` as the command layer for menus.
- Set `menu_bar.setNativeMenuBar(False)` by default.
- Use custom `QWidget` painting only when a built-in widget would lose needed Workbench semantics.
- Keep all widget creation and mutation on the GUI thread.

## Avoid By Default
- `QGraphicsView`
- `QQuickWidget`
- toolbars, dock widgets, and status bars
- system tray or desktop-shell integration
- new thread architectures for UI work
- heavy GUI testing frameworks or screenshot-diff suites

## Testing Rules
- Use `unittest`.
- Prefer direct widget inspection and direct action triggering.
- Test construction, state, labels, enabled/disabled logic, and narrow interactions.
- For custom-painted widgets, test state and geometry logic first.
- Keep the broad host sanity check in `tests/run_gui_smoke_test.py`; do not rebuild a giant UI harness in unit tests.

## Key Repo Files
- `src/amiga_ui/host/gui_smoke.py`
- `src/amiga_ui/host/xvfb.py`
- `docs/host-gui/`
