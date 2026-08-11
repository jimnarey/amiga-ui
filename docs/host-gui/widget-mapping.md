---
title: "Widget Mapping"
status: draft
depends_on:
  - "qt-widgets-primer.md"
  - "../platform/gui-stack.md"
citations_used:
  - "S26"
  - "S28"
  - "S58"
  - "S59"
  - "S63"
---

# Widget Mapping

Purpose: Record the default host-widget choices for common Workbench and GadTools UI elements.

Needed for:
- Keeping host GUI implementations consistent.
- Avoiding repeated ad hoc widget selection.

## Summary

Workbench and GadTools apps are built around windows, menus, gadgets, and requesters [S26 §Components of Intuition tbl.1] [S28 §Intuition Gadgets ¶1-3]. Qt Widgets provides the standard desktop widget families needed to express those concepts on the host side [S58 §Detailed Description ¶1-4] [S59] [S63]. The mapping below is therefore a project decision about default translation choices.

## Default Mapping

| Amiga-side concept | Default Qt choice | Project note |
| --- | --- | --- |
| main application window | `QMainWindow` | Default when a menu bar and central content are present. |
| simple secondary panel | `QWidget` child inside a layout | Prefer a plain widget container unless dialog semantics are needed. |
| modal requester | `QDialog` | Use for small focused interactions. |
| simple info/confirm requester | `QMessageBox` | Acceptable for straightforward yes/no/info flows. |
| drawer or file requester | `QFileDialog` or a small custom `QDialog` | Start with `QFileDialog`; switch to a custom dialog if Workbench semantics do not fit cleanly. |
| button gadget | `QPushButton` | Default push action. |
| checkbox gadget | `QCheckBox` | Default boolean option. |
| radio/mutually-exclusive gadget group | `QRadioButton` with `QButtonGroup` | Use when one of a small fixed set must be selected. |
| cycle gadget | `QComboBox` | Default for choosing one value from a compact list. |
| string gadget | `QLineEdit` | Default single-line text input. |
| integer field | `QLineEdit` plus validator | Prefer this by default; use `QSpinBox` only when stepper semantics are genuinely wanted. |
| static text label | `QLabel` | Default caption or short status text. |
| framed group or boxed settings area | `QGroupBox` or `QFrame` | Use `QGroupBox` when it needs a title. |
| simple list | `QListWidget` | Good default for small first-wave lists. |
| structured or scalable list/tree | `QListView` or `QTreeView` with a model | Use when data/view separation genuinely pays off. |
| read-only log or report text | `QPlainTextEdit` | Prefer over richer text widgets for plain logs. |
| custom-drawn control or preview | focused `QWidget` subclass | Only when semantics or visuals require it. |

## Working Rule

Choose the smallest built-in Qt widget that preserves the Amiga-side semantics. Only step up to:

1. model/view classes,
2. custom dialogs,
3. or custom-painted widgets

when the simpler built-in choice is no longer a good fit.
