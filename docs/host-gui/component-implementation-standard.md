---
title: "Host UI Component Standard"
status: draft
depends_on:
  - "translation-obligations.md"
  - "menus-dialogs-and-requesters.md"
  - "testing-host-ui.md"
citations_used:
  - "S58"
  - "S59"
  - "S61"
  - "S64"
---

# Host UI Component Standard

Purpose: Define the default structure and implementation rules for host UI components.

Needed for:
- Keeping host GUI code consistent.
- Discouraging short-term widget code that is hard to extend or test.

Depends on:
- `translation-obligations.md`
- `menus-dialogs-and-requesters.md`
- `testing-host-ui.md`

Status: Draft.

Notes:
- This is a repository engineering standard, not a claim about the only valid Qt architecture.

## Summary

Qt Widgets are normal `QWidget`-based object trees with event handlers, parent-child ownership, and main-window support through classes like `QMainWindow` [S58 §Widgets ¶1-3] [S59] [S64]. The project should therefore implement host UI elements as small, explicit, testable widget classes rather than as one-off procedural UI effects embedded directly in translation code.

## Standard Shape

Default component shape:

1. one focused widget or dialog class,
2. one small project-owned adapter/controller path that feeds it semantic state,
3. explicit signals, methods, or return values for outward communication,
4. tests aimed at construction, state, and narrow interactions.

This keeps the translation pipeline visible instead of blending `vamos`, compatibility logic, and Qt mutation into one place.

## Separation Rules

### Widget Classes

Widget and dialog classes should be responsible for:

- constructing host controls
- arranging layouts
- reflecting state visibly
- emitting user-driven actions outward

They should not be responsible for:

- talking directly to `vamos`
- reading or mutating Amiga memory structures
- deciding broad compatibility policy
- inventing fake results to keep the app moving

### Translation Or Adapter Code

Compatibility-layer code outside the widget should be responsible for:

- interpreting Amiga-side intent
- preparing host-side state
- deciding when a widget should open, close, or refresh
- translating the host result back into Amiga-facing semantics

That boundary follows the existing translation-pipeline design rather than bypassing it through direct ad hoc widget mutation.

## Window And Dialog Defaults

Default choices remain:

- `QMainWindow` for main application windows [S59]
- `QDialog` for modal requesters
- focused `QWidget` subclasses for custom panels or controls [S64]

Do not start from giant all-purpose base classes "just in case" later apps need more features.

## Command And Event Standard

For menu and command-style UI:

- model commands as `QAction` objects
- connect them to small explicit handlers
- have those handlers emit a signal or call a narrow adapter method

For ordinary widgets:

- connect built-in widget signals directly
- keep handlers short
- move nontrivial translation work out of the widget class

## State Standard

A host UI component should have a small explicit state surface. That does not require a heavyweight framework, but it does mean:

- avoid hidden global state
- avoid spreading one logical UI state across many unrelated helper functions
- prefer one obvious place where current visible state is applied

If a widget is so tangled that a small unit test cannot assert its visible state after one interaction, the design is probably too implicit.

## Threading Standard

Widget creation and mutation stay on the GUI thread [S61 §QObject Reentrancy ¶1-3] [S61 §Signals and Slots Across Threads ¶1-5]. Do not hide concurrency inside a component just to make it feel self-contained.

## Testing Consequence

The component should be simple enough that tests can usually verify:

- it can be constructed,
- it exposes the expected controls or actions,
- one interaction changes one visible or exported state as expected.

If a component design requires a large UI robot harness to verify basic correctness, it is too complex for the repository's default style.
