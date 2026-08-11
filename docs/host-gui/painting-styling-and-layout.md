---
title: "Painting, Styling, And Layout"
status: draft
depends_on:
  - "qt-widgets-primer.md"
  - "../architecture/gui-strategy.md"
citations_used:
  - "S58"
  - "S62"
  - "S64"
  - "S65"
---

# Painting, Styling, And Layout

Purpose: Define the default rules for host widget layout, styling, and custom drawing.

Needed for:
- Building maintainable host widgets.
- Avoiding unnecessary rendering complexity.

Notes:
- This is where the project draws the line between normal widget use and custom rendering.

## Layout First

Qt Widgets already provides a standard layout system, and the module overview treats layouts as the normal arrangement mechanism for child widgets [S58 §Layouts ¶1-2]. Project rule:

- use layouts by default
- use size policies and container widgets before manual geometry
- only use fixed geometry when the geometry itself is part of the compatibility behavior

## Styling First Choice

Default styling order:

1. built-in widget appearance and ordinary properties
2. restrained style sheets
3. style-aware custom painting

Qt's style-sheet overview says style sheets layer on top of the current widget style and take precedence when they conflict with functions such as `setFont()` or `setBackground()` [S62 §Overview ¶1-4]. So the project should use style sheets sparingly and intentionally rather than piling them on until the widget tree becomes hard to reason about.

## Custom Painting Rule

When built-in widgets are not enough, create a focused `QWidget` subclass and implement the smallest painting surface needed. The `QtWidgets` overview and `QWidget` docs both position subclassing and event-handler reimplementation as the normal path for custom widget behavior [S58 §Widgets ¶1-3] [S64].

Typical justified uses in this repo include:

- a Workbench-flavored custom preview
- a small custom-drawn status surface
- a geometry-sensitive translated control that no built-in widget expresses cleanly

## Style-Aware Drawing

The style-reference docs explain that style-aware widgets should draw through `QStyle` with `QStyleOption` data rather than assuming raw platform geometry or hard-coding all visuals [S65 §QStyle Functions ¶1-4]. Project rule:

- if a custom widget is still fundamentally "button-like", "frame-like", or otherwise close to a normal control, prefer style-aware drawing over fully bespoke pixel art
- only drop to entirely custom drawing when the control really is project-specific

## Framework Features Ruled Out By Default

Do not introduce these by default for host UI implementation:

- Qt Quick or QML
- `QQuickWidget`
- `QGraphicsView`
- OpenGL-driven widget rendering
- application-wide custom `QStyle` replacement

If one of those becomes necessary, the change should be justified in docs before it quietly spreads through the codebase.

## Designer Files

Prefer hand-written Python widget and layout code over `.ui` Designer files. The project is intentionally optimized for small-context local LLMs and straightforward diffs; hand-written code is easier to inspect, patch, and discuss than generated or tool-owned UI assets.
