---
title: "Threading And Desktop Boundaries"
status: draft
depends_on:
  - "qt-widgets-primer.md"
  - "../architecture/compatibility-scope.md"
citations_used:
  - "S61"
---

# Threading And Desktop Boundaries

Purpose: Record the default concurrency and desktop-integration boundaries for host GUI work.

Needed for:
- Preventing local LLMs from making costly framework decisions implicitly.

Notes:
- This document intentionally settles several framework choices early.

## GUI Thread Rule

Qt's threading overview says that `QObject` instances live in the thread where they are created, that cross-thread access is constrained, and that signals and queued delivery are the normal way to communicate across threads when multiple threads exist at all [S61 §QObject Reentrancy ¶1-3] [S61 §Per-Thread Event Loop ¶1-4] [S61 §Signals and Slots Across Threads ¶1-5].

Project rule:

- create and mutate widgets on the GUI thread
- do not update widgets directly from worker threads
- keep first-wave host GUI code single-threaded unless a concrete problem proves otherwise

## Concurrency Defaults

Local LLMs should not introduce any of the following by default:

- `QThread` worker architectures
- `moveToThread()`
- thread pools for host GUI logic
- multiprocessing for UI work
- background timers or polling loops that exist only to "make the GUI feel live"

If background work later becomes necessary, the default pattern should still be conservative:

1. do the non-UI work off the GUI thread,
2. send back a result or intent,
3. apply visible widget changes on the GUI thread.

## Desktop Interoperability Boundaries

Local LLMs should not make new interoperability decisions with the surrounding desktop environment unless the repo docs explicitly require them. That includes:

- system tray integration
- desktop notifications
- DBus or portal integration
- file-association registration
- global menu-bar integration
- drag and drop involving other apps or the desktop shell
- global hotkeys

Normal in-window widget behavior is fine. New cross-application or desktop-shell integration is not a default feature.

## Clipboard And Similar Features

Do not add explicit clipboard, selection-manager, or other desktop-sharing behavior unless a real target app requires it and the requirement is documented first. Normal Qt widget defaults are acceptable; new project-owned clipboard behavior is not a casual addition.
