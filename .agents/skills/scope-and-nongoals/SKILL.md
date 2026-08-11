---
name: scope-and-nongoals
description: >
  Keep work aligned with the repository's intended scope and explicit
  exclusions. Use when evaluating targets, deciding whether to emulate a
  behavior, or checking for drift toward full-system emulation.
---

# Scope And Nongoals

## Use This Skill When
- A proposed fix may push the project beyond API-level compatibility.
- You need to decide whether a target or behavior is in scope.
- A failure may actually require a full machine emulator.

## In Scope
- Classic Amiga Workbench applications that mainly depend on operating-system services.
- API-level compatibility work on top of `vamos`.
- Host-side runtime, library, and GUI behavior needed to advance selected desktop apps.
- Narrow secondary OS features reached through documented APIs when they are not the app's main value.

## Out Of Scope
- Direct hardware access workloads.
- Full UAE-style machine or chipset emulation.
- Treating ROM boot, full desktop session emulation, or custom hardware behavior as the main implementation goal.
- Broad subsystem emulation for audio, peripherals, or desktop integration when that becomes the real implementation burden.

## Decision Rule
If a blocker is fundamentally about hardware registers, chipset behavior, or another full-emulator concern, stop and record that clearly instead of building misleading partial abstractions on top.

Do not treat every sound- or device-related API name as out of scope automatically. The key distinction is:
- narrow API-level behavior that is secondary to the app's value may still be in scope
- broad hardware-facing or subsystem-emulation work is not

## Guardrails
- Prefer honest boundaries over fake progress.
- Do not solve a scope problem by quietly depending on more copyrighted system payload than the project intends to require.
- Keep the repo focused on a small number of real Workbench-class targets, not broad unsupported software classes.
- If a blocker points to a broad peripheral, audio, or desktop-session subsystem, stop and consult the subsystem stop-rules docs before widening support.

## Key Repo Files
- `docs/architecture/compatibility-scope.md`
- `docs/runtime/subsystem-stop-rules.md`
- `docs/runtime/workbench-integration-boundaries.md`
- `docs/research/deferred-decisions.md`

`docs/archive/PROJECT_BRIEF.md` is historical bootstrap material, not a current scope reference. Do not treat it as authoritative; use the files above instead.
