---
title: "Menus, Dialogs, And Requesters"
status: draft
depends_on:
  - "widget-mapping.md"
  - "../apps/itidy/dependencies.md"
citations_used:
  - "S31"
  - "S59"
  - "S60"
  - "S63"
---

# Menus, Dialogs, And Requesters

Purpose: Define how Workbench menus and requesters should be represented in the host GUI.

Needed for:
- Main-window construction.
- Requester behavior.

Notes:
- This document settles project policy on menu-bar placement and dialog defaults.

## Window Menu Bars

The Workbench menu bar sits at the top of the screen, but the project should represent application menus as part of the host app window, not as desktop-global menu integration. `QMainWindow` is the standard Qt Widgets main-window class and holds menus through `QMenuBar`, while `QMenuBar` exposes the `nativeMenuBar` property when platforms offer special native handling [S59] [S60].

Project rule:

- use a window-local `QMenuBar`
- use `QMenu` and `QAction` for menu structure and commands
- call `menu_bar.setNativeMenuBar(False)` by default

That gives the project deterministic in-window behavior across normal Linux sessions and the headless `Xvfb` path.

## QAction As The Command Layer

Represent user-invokable commands as `QAction` objects first and then attach them to menus or other widgets as needed. This keeps menu state, enable/disable logic, labels, and shortcuts in one place instead of scattering them across individual controls.

## Dialog Defaults

Use these defaults:

- `QDialog` for custom modal requesters
- `QMessageBox` for simple confirm/error/info flows
- `QFileDialog` for ordinary file or directory picking [S63]

Parent dialogs to the relevant top-level window so modality and focus behavior stay local and predictable.

## Directory And File Requesters

Qt provides `QFileDialog` as the standard file-selection dialog type [S63]. Project rule:

- start with `QFileDialog` for basic file or directory selection
- prefer Qt-managed behavior over platform-native dialog integration
- if the Workbench semantics are awkward enough that the dialog becomes a pile of options and workarounds, replace it with a small explicit `QDialog`

For consistency and testability, prefer setting `DontUseNativeDialog` when the implementation needs deterministic widget behavior rather than host-desktop special cases.

## Features We Are Not Using By Default

`QMainWindow` can also host toolbars, dock widgets, and status bars [S59]. Those are not part of the first-wave host GUI contract. Default rule:

- no toolbars by default
- no dock widgets by default
- no `QStatusBar` by default

Use a normal central widget plus menu bar unless a concrete target app proves that something richer is needed.

## Current Pressure From `iTidy`

The current target app builds a classic menu and requester path around native Amiga GUI libraries [S31 L174-L227] [S31 L470-L518]. That means the highest-value first host path is not "all Qt features" but:

1. one main window,
2. one in-window menu bar,
3. and straightforward modal requesters.
