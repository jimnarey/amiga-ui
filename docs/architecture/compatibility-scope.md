# Compatibility Scope

Purpose: State exactly what software this project targets and excludes.

Needed for:
- Avoiding wasted effort on unsupported app classes.

Depends on:
- `overview.md`

Status: Draft.

Notes:
- Include Workbench GUI apps, exclude direct hardware access, and define how toolkit dependencies affect scope.

## Summary

This project targets classic Amiga Workbench applications whose value primarily comes from filesystem, icon, configuration, requester, and window-management behavior. It does not target applications whose core behavior depends on direct chipset access, cycle-accurate timing, custom blitters, audio hardware, or a full emulated Amiga desktop.

## In Scope

### Workbench-Oriented Utility Applications

The primary target class is desktop software that behaves like a normal Workbench tool: it launches from Workbench, works with Amiga paths and icons, opens standard windows, and relies on OS libraries rather than direct hardware pokes. This is deliberately narrower than “all Amiga GUI software” and is meant to keep the early project tractable.

`iTidy` is the model example for this class. Its upstream documentation states that it is a Workbench utility for AmigaOS 3.x, requires Workbench 3.0 or newer, uses native GadTools, and focuses on arranging icon layouts and drawer windows rather than touching user data [S11 L9-L21] [S11 L42-L48] [S11 L107-L112] [S11 L150-L153].

### Standard AmigaOS Library Use

Software is in scope when it mainly expects documented operating-system services: path handling, locks, file I/O, message passing, Workbench startup, standard requesters, and common GUI libraries. `Vamos` already provides an API-level execution environment built around library trapping and emulated public system structures, which makes this kind of software a realistic target class [S7 L21-L31] [S8 L18-L32].

### Workbench Metadata and Layout Behavior

The project explicitly includes software that reads or writes:

- `.info` files
- default tool metadata
- drawer window sizing and placement
- Workbench argument structures
- path and assign-driven file access

This matters because these behaviors are central to `iTidy` and likely to other filesystem-oriented tools in the same family [S12 L5-L8] [S12 L43-L50].

## Out Of Scope

### Direct Hardware Access

Applications or games that depend on direct hardware register access are out of scope. `Vamos` itself documents this as a non-goal and points users toward full machine emulators for that class of software [S7 L12-L17]. The project follows that boundary rather than trying to erode it.

### Full-System Desktop Emulation

The project is not trying to reproduce an entire Amiga desktop session, ROM boot process, chipset model, or display pipeline. `Vamos` is explicitly described as an API-level emulator rather than a full system emulator [S7 L16-L17]. The project builds on that model instead of competing with UAE-class emulators.

### Demo, Game, And Custom Rendering Workloads

Software whose main value depends on custom graphics pipelines, direct audio hardware use, or timing-sensitive rendering is out of scope for the same reason. Even if such software presents a window or menu, it is not the project’s intended class unless its core behavior is still expressible through Workbench- and library-level semantics.

## Conditional Scope

### Add-On GUI Toolkits

Add-on GUI layers such as ClassAct are conditionally in scope. They are not part of the project’s minimum promise, but they become relevant if a real target application requires them and the dependency can be documented and acquired cleanly. The presence of ClassAct in the project assets is therefore best understood as preparatory support, not as a commitment to broad toolkit compatibility from day one.

### Later AmigaOS Releases

Workbench 3.0 and 3.1 behavior form the default baseline. Later media such as 3.1.4 are retained as reference and comparison material, especially where they clarify library or layout behavior, but the project should not silently drift into “supports every 3.x variation” unless a later doc explicitly widens the contract.

## Acceptance Test For New Targets

A new application is a good fit for the project if most of the following are true:

1. It is useful from Workbench rather than from direct hardware control.
2. It uses standard or at least documentable library calls.
3. Its missing behavior can plausibly be added one function or feature at a time.
4. Its correctness can be validated through logs, metadata changes, and observable UI behavior.
5. Failure to support it does not imply that the project must become a full machine emulator.

If those conditions are not met, the software is probably better treated as a reference curiosity or as a job for FS-UAE/UAE rather than as a primary compatibility target.
