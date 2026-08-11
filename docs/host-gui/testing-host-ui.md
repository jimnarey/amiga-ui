---
title: "Testing Host UI Code"
status: draft
depends_on:
  - "threading-and-desktop-boundaries.md"
  - "../workflows/regression-checks.md"
citations_used:
  - "S58"
  - "S61"
  - "S64"
---

# Testing Host UI Code

Purpose: Define the default test strategy for host-side Qt Widgets code.

Needed for:
- Keeping host GUI tests useful, cheap, and reviewable.

Depends on:
- `threading-and-desktop-boundaries.md`
- `../workflows/regression-checks.md`

Status: Draft.

Notes:
- The goal is confidence, not a huge GUI-test framework.

## Summary

Qt Widgets code is event-driven and GUI-thread-bound [S61 §Per-Thread Event Loop ¶1-4]. Widgets are ordinary Python objects in a parent/child tree with event handlers and paint hooks [S58 §Widgets ¶1-3] [S64]. That means the project can get good coverage from simple construction, state, and interaction tests without adopting a heavy UI-testing stack.

## What To Test

Prefer tests that answer these questions:

- can the widget or dialog be constructed successfully under the project test environment?
- are the expected child widgets, actions, or layouts present?
- do important actions start enabled or disabled correctly?
- does a small direct interaction update the visible or exported state correctly?
- does a custom widget's state or geometry logic behave correctly?
- can the paint path run without crashing when the widget is shown or updated?

For menus and dialogs, it is usually more valuable to test:

- which `QAction` objects exist,
- what labels and enabled states they have,
- which callbacks or state changes they trigger,

than to test every possible user click sequence.

## What Not To Test Aggressively

Do not default to testing:

- Qt's own built-in behavior in depth
- pixel-perfect screenshots
- broad visual snapshot comparison
- long timing-sensitive event scripts
- complex GUI robot frameworks
- every permutation of widget focus and input order

Those tend to be brittle, expensive, and low-signal for this repository.

## Project Testing Style

Default testing style:

- use `unittest`
- create the smallest widget tree needed
- inspect widget properties directly
- call methods or trigger `QAction` objects directly when possible
- use `processEvents()` only when genuinely needed

Prefer ordinary Python assertions over a large Qt-specific test DSL.

## Custom Widget Tests

For custom-painted widgets, focus on:

- state transitions,
- geometry calculations,
- any mapping between compatibility-layer state and host widget state,
- and a minimal smoke path that shows or repaints the widget without failure.

Do not make screenshot-diff testing the default answer to every custom-drawing problem.

## Existing Smoke Test Role

The existing headless smoke test is the broad host-GUI sanity check. It proves that the project can create and close a minimal Qt Widgets window under `Xvfb`. Individual feature tests should stay narrower than that and should not try to recreate a full desktop-session integration harness inside the unit-test suite.
