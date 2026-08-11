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

## Out Of Scope
- Direct hardware access workloads.
- Full UAE-style machine or chipset emulation.
- Treating ROM boot, full desktop session emulation, or custom hardware behavior as the main implementation goal.

## Decision Rule
If a blocker is fundamentally about hardware registers, chipset behavior, or another full-emulator concern, stop and record that clearly instead of building misleading partial abstractions on top.

## Guardrails
- Prefer honest boundaries over fake progress.
- Do not solve a scope problem by quietly depending on more copyrighted system payload than the project intends to require.
- Keep the repo focused on a small number of real Workbench-class targets, not broad unsupported software classes.

## Key Repo Files
- `PROJECT_BRIEF.md`
- `docs/architecture/compatibility-scope.md`
- `docs/research/deferred-decisions.md`
