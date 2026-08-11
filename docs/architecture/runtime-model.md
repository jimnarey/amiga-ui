---
title: "Runtime Model"
status: draft
depends_on:
  - "overview.md"
  - "../runtime/vamos-overview.md"
  - "../runtime/headless-gui.md"
citations_used:
  - "S7"
---

# Runtime Model

Purpose: Explain the moving pieces involved when an Amiga program runs under this project.

Needed for:
- Understanding failure points and implementation boundaries.

## Layers

When a supported Amiga application runs in this project, the runtime should be thought of as a stack of cooperating layers:

1. The original m68k program binary.
2. `vamos`, which executes the binary and provides low-level AmigaOS-shaped services such as memory structures, path mapping, and library dispatch [S7 L21-L31] [S7 L64-L77].
3. Project-owned compatibility code, which fills in missing semantics one function or feature at a time.
4. The host GUI toolkit, currently assumed to be Qt Widgets via PySide6.
5. The host display environment, either a real Linux desktop session or the project-standard `Xvfb` wrapper.

## Failure Boundaries

This layered view matters because not every failure means the same thing:

- A `vamos` trap or library failure usually points to missing Amiga-side semantics.
- A Qt exception or windowing failure usually points to host-side GUI code.
- A display connection failure usually points to the desktop or `Xvfb` environment rather than the Amiga compatibility layer itself.

The project should preserve those boundaries in both documentation and debugging workflow.

## Headless And Interactive Modes

The application logic should be the same in both modes. The only intended difference is the outer display environment:

- interactive mode uses a normal Linux desktop session;
- headless mode uses `uv run amiga-ui-xvfb -- <command>`.

That keeps smoke tests close to real execution while still making automation possible.
