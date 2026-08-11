---
title: "Qt Widgets Primer"
status: draft
depends_on:
  - "../architecture/gui-strategy.md"
  - "README.md"
citations_used:
  - "S57"
  - "S58"
  - "S59"
  - "S61"
  - "S64"
  - "S66"
---

# Qt Widgets Primer

Purpose: Provide the minimum Qt Widgets concepts needed to work on the host GUI layer sensibly.

Needed for:
- Reading and editing host GUI code.
- Avoiding unnecessary framework sprawl.

Depends on:
- `../architecture/gui-strategy.md`
- `README.md`

Status: Draft.

Notes:
- This is a project primer, not a general Qt textbook.

## Summary

The host GUI layer should be written as ordinary PySide6 Qt Widgets code. Qt's own UI overview describes Widgets as the traditional desktop UI stack, while the PySide6 `QtWidgets` module overview describes widgets, layouts, model/view classes, and custom widget subclassing as the main building blocks for classic desktop interfaces [S57 §Qt Widgets User Interfaces ¶1-2] [S58 §Detailed Description ¶1-4].

## Core Model

The minimum mental model is:

1. create `QApplication` first;
2. build a tree of `QWidget` objects;
3. arrange child widgets with layouts;
4. connect user actions to project logic through signals and slots;
5. enter the event loop.

The Qt threading overview explicitly warns that creating `QObject` instances before the application object is not supported, and the `QWidget` docs position widgets as the basic renderable and interactive UI elements in that object tree [S61 §QObject Reentrancy ¶1-3] [S64].

## Top-Level Window Defaults

Use these default top-level classes:

- `QMainWindow` for the main application window with a menu bar and central content [S59]
- `QDialog` for modal requesters and small secondary dialogs
- plain `QWidget` for custom panels or custom controls that do not need `QMainWindow` features

`QMainWindow` has built-in support for a menu bar, status bar, dock widgets, and toolbars [S59]. For this project, that matters mainly because it gives us the correct window-local menu-bar structure; it does not mean all of those extra features are wanted.

## Layouts Before Geometry

Qt Widgets already have a standard layout system, and the module overview presents layouts as the normal way to arrange child widgets automatically [S58 §Layouts ¶1-2]. Project default:

- use layouts and size policies by default
- avoid hard-coded pixel geometry unless compatibility semantics genuinely depend on it

## Signals, Slots, And Simple UI Logic

Keep the first wave of host GUI logic simple:

- widget emits a signal
- project-owned adapter/controller code updates state
- widget state refresh follows from that state

Do not make local LLMs invent an elaborate framework on top of Qt just to avoid calling `connect()`.

## Custom Widgets

The PySide6 docs describe custom widgets as subclasses of `QWidget` or a suitable subclass, with behavior implemented by reimplementing event handlers [S58 §Widgets ¶1-3]. When a built-in widget is close enough, prefer the built-in widget. When a Workbench behavior really needs custom presentation, create a small focused `QWidget` subclass rather than switching to a whole different scene system.

## Framework Choices Settled Now

The following choices are project policy:

- use Qt Widgets, not Qt Quick or QML, for normal host GUI work
- prefer hand-written Python widget code over `.ui` Designer files
- do not introduce `QQuickWidget` or hybrid Widgets/QML stacks by default

Those are local design decisions. The reason is repository clarity and predictability, not a claim that Qt's other UI technologies are bad.

## Official Entry Points

The most useful official Qt references for this repository are:

- the Qt Widgets overview and UI comparison pages [S57] [S58]
- the `QMainWindow` and `QWidget` API pages [S59] [S64]
- the threading overview for `QObject` rules [S61]
- the tutorials index when a basic example is genuinely helpful [S66]
