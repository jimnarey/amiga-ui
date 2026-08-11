---
title: "Headless GUI Runtime"
status: draft
depends_on:
  - "vamos-overview.md"
  - "../architecture/runtime-model.md"
citations_used:
  - "S18"
  - "S19"
  - "S20"
  - "S21"
  - "S22"
  - "S23"
---

# Headless GUI Runtime

Purpose: Define the standard headless display environment for Linux and OpenHands runs.

Needed for:
- Reproducible GUI smoke tests.
- Running Qt Widgets code without assuming a real desktop session.

## Standard Choice

The project-standard headless display server is `Xvfb`, not a headless Wayland compositor. On Linux, Qt uses the `xcb` QPA plugin to run Qt GUI and Qt Widgets applications against X11 [S18 §Platform Plugin Dependencies tbl.1]. `Xvfb` exists specifically to run an X server on machines with no display hardware or physical input devices, and it is explicitly described as useful for testing clients and running applications that insist on having an X server [S20 §Description ¶1-2].

That makes `Xvfb` the lowest-friction way to give the project a real window-system target inside OpenHands while keeping the runtime model close to ordinary Qt Widgets usage.

## Project Rule

Use `uv run amiga-ui-xvfb -- <command>` as the default headless launcher for GUI smoke tests and scripted app runs. The Python wrapper starts a temporary `Xvfb` instance, exports `DISPLAY`, and defaults `QT_QPA_PLATFORM` to `xcb`. Qt documents `QT_QPA_PLATFORM` as the mechanism for selecting a specific platform plugin [S19 §Selecting a QPA plugin ¶1-2].

The canonical virtual screen configuration is:

- one screen
- `1280x1024x24`
- `QT_QPA_PLATFORM=xcb`

The fixed screen geometry is a project decision for reproducibility. It is not meant to model any one Amiga display exactly.

## Why Not `qminimal`

Qt documents the `qminimal` platform plugin as being for tools that link against Qt GUI but do not require window-system integration [S19 §Writing a QPA plugin ¶1-2]. That is too narrow for this project. We want to exercise a real desktop-style widget stack, not just create GUI objects in a display-less diagnostic mode.

## Local Interactive Development

When a developer has a normal Linux desktop session, they should run the host GUI directly in that session for exploratory work. The `Xvfb` wrapper is mainly for:

- OpenHands execution
- repeatable smoke tests
- automated regression checks

This split keeps interactive debugging pleasant while preserving a deterministic headless path.

## Deferred Wayland Path

Native Wayland coverage is deferred, not rejected. Qt supports Wayland clients through the `wayland` platform plugin [S23 §The Role of Wayland ¶1-4]. Weston also provides a `headless` backend intended for testing client applications, and can optionally host X11 clients through Xwayland [S21 §Available back-ends item 5] [S22 §BACKENDS ¶1-8].

The project should only add a Wayland-specific headless path when there is a concrete reason to test:

- Wayland-only behavior
- X11 versus Wayland differences
- Xwayland hosting scenarios

Until then, `Xvfb` remains the standard headless runtime.
