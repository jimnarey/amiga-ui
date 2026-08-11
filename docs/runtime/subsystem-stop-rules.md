---
title: "Subsystem Stop Rules"
status: draft
depends_on:
  - "vamos-overview.md"
  - "../architecture/compatibility-scope.md"
citations_used:
  - "S7"
  - "S8"
---

# Subsystem Stop Rules

Purpose: Define when the agent should stop rather than widening the project into subsystems that `vamos` and the repository do not naturally target.

Needed for:
- Honest triage.
- Preventing scope creep by subsystem.

Depends on:
- `vamos-overview.md`
- `../architecture/compatibility-scope.md`

Status: Draft.

Notes:
- These are project stop-rules layered on top of upstream `vamos` boundaries.

## Summary

`Vamos` describes itself as an API-level AmigaOS runtime focused on CLI-oriented software, not a full system emulator, and not the right tool for direct hardware-access programs [S7 L5-L17]. It also allows mixed library strategies rather than claiming to emulate every subsystem uniformly [S8 L18-L32] [S8 L40-L55]. The project therefore needs explicit rules for when a blocker should be treated as a stop signal rather than as an invitation to invent a new emulation layer.

## Main Rule

When a blocker points primarily to a hardware-facing subsystem, a broad peripheral-emulation problem, or a full-desktop behavior outside normal Workbench/library semantics, the default action is:

1. stop,
2. document the boundary,
3. and avoid building a misleading partial abstraction.

## Subsystems That Trigger A Stop By Default

The following should be treated as stop-sign subsystems unless a later doc narrows the requirement to a small API-level slice:

- custom-chip or CIA behavior as a real feature dependency
- audio playback or capture as a central app feature
- printer workflows as a primary supported behavior
- serial, MIDI, joystick, or other external-peripheral workflows as a primary supported behavior
- timing-sensitive rendering or device polling loops
- broad desktop/session behavior beyond the app's own Workbench-facing window and message semantics

## What Does Not Automatically Trigger A Stop

Do not stop merely because a symbol or API name sounds adjacent to one of those areas. A feature may still be in scope if it is:

- reached through documented OS/library APIs,
- secondary rather than central to the application,
- and narrow enough to implement honestly without dragging the project toward full subsystem emulation.

That means a small API-level alert or helper-device path is a different kind of problem from implementing "sound support" or "device support" in the abstract.

## Triage Questions

Before widening support for a new subsystem, ask:

1. Is the feature part of the app's core value or just a secondary edge?
2. Is the dependency API-level or hardware-facing?
3. Would supporting it require broad subsystem emulation rather than one narrow compatibility feature?
4. Would a truthful implementation still fit the repository's stated target class?

If the answers point toward broad subsystem work, stop and record the boundary.

## Working Rule

Prefer one honest "out of scope because this has become a subsystem problem" note over several speculative fixes that accidentally teach the repo to emulate a new machine feature one symptom at a time.
