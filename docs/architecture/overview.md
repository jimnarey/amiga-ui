---
title: "Architecture Overview"
status: draft
depends_on:
  - "compatibility-scope.md"
  - "runtime-model.md"
citations_used:
  - "S7"
  - "S8"
  - "S11"
  - "S12"
---

# Architecture Overview

Purpose: Describe the whole project in one short pass.

Needed for:
- Understanding what the Python compatibility layer is meant to do.

## Summary

This project is a Python compatibility layer for classic Amiga Workbench applications. It is not trying to replace a full machine emulator. Instead, it uses `vamos` as the execution substrate for m68k code and then adds the missing Workbench- and GUI-facing behavior needed to make selected desktop applications usable on a modern host.

The immediate target is software in the same general class as `iTidy`: a Workbench utility that targets AmigaOS 3.x, uses native GadTools for its interface, and operates on Workbench metadata such as `.info` files and drawer window layout rather than on custom graphics hardware or game-style rendering [S11 L42-L48] [S11 L107-L112] [S11 L150-L153].

## Architectural Layers

### 1. Target Application Layer

At the top of the stack is the original Amiga application binary plus any required supporting assets such as icons, Workbench files, optional add-on libraries, and documentation. In the first phase, the main reference application is `iTidy`, which is explicitly described by its upstream docs as a Workbench utility for AmigaOS 3.x with recursive directory processing, backup support, and default-tool validation features [S11 L9-L21] [S12 L39-L50].

### 2. Execution Layer

The execution layer is provided by `vamos`. `Vamos` is an API-level emulator, not a full Amiga machine emulator, and it is designed to execute AmigaOS m68k binaries by emulating the CPU and trapping library calls into host-side implementations [S7 L5-L17] [S7 L21-L31]. This means the project does not need to begin by writing its own m68k interpreter or object loader. Instead, it can build on top of an existing runtime that already knows how to execute code, expose core public structures in emulated memory, and intercept API calls [S7 L21-L31].

### 3. Compatibility Layer

The compatibility layer is the main body of this project. Its job is to bridge the gap between what `vamos` already supports and what Workbench GUI applications actually expect. `Vamos` is already strong enough to run many CLI-oriented tools, and its own docs describe its current focus as console binaries that do not rely on Intuition or graphics [S7 L5-L10]. This project extends that foundation toward Workbench-class software.

The compatibility layer will therefore concentrate on:

- additional library behavior not yet covered well enough by `vamos`
- Workbench launch semantics and message formats
- icon and `.info` handling
- drawer/window layout persistence
- path, assign, and environment behavior that GUI apps assume
- translation of GUI-facing Amiga operations into host-side behavior

### 4. Host UI Layer

The host UI layer is where Amiga-facing GUI intent becomes a Linux desktop interface. The current project decision is to use Python with PySide6 and Qt Widgets as the first host GUI implementation. This layer should remain conceptually separate from the emulation layer: it is not responsible for executing m68k code, only for representing the resulting interface and interactions in a host-native way. Automated GUI checks should use the project `Xvfb` wrapper, while human testing should use a normal Linux desktop session.

### 5. Validation Layer

The validation layer exists to keep progress incremental and testable. It combines:

- controlled runs under `vamos`
- captured stdout/stderr and runtime logs
- side-by-side inspection of affected Workbench files and layout metadata
- comparison against real documentation and, where useful later, fuller emulation environments

This layer is especially important because `vamos` can run binaries without needing a real Kickstart ROM or Workbench disk when Python-side library implementations are sufficient [S8 L9-L15]. That makes it a strong development base, but also means the project must be disciplined about checking whether its behavior still matches what real Workbench software expects.

## Design Consequences

Several design consequences follow from this architecture:

1. The project should add behavior at the highest useful level.
   If a missing feature can be implemented as a library call or message-translation fix, that is preferable to growing the project toward whole-machine emulation.

2. Real applications drive scope.
   New compatibility work should normally be justified by a concrete target application rather than by trying to model the entire Amiga desktop in advance.

3. Documentation is part of the architecture.
   Since the project depends on small-context models, the explanatory documentation in `docs/` is not supplementary. It is part of the system that makes iterative development possible.

4. Host behavior should be explicit.
   Where the Amiga API and a Linux desktop model differ, the project should document the translation choice rather than letting it emerge accidentally from implementation details.
