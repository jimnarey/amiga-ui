---
title: "iTidy Compatibility Notes"
status: draft
depends_on:
  - "runbook.md"
  - "../../runtime/vamos-gaps.md"
  - "run-log.md"
  - "../../runtime/workbench-integration-boundaries.md"
  - "../../host-gui/README.md"
  - "../../workflows/external-helpers-and-shellouts.md"
citations_used:
  - "S11"
  - "S12"
  - "S29"
  - "S30"
  - "S31"
  - "S32"
  - "S33"
  - "S34"
  - "S35"
---

# iTidy Compatibility Notes

Purpose: Track the current support state of `iTidy` under the project runtime.

Needed for:
- Preventing repeated investigation of the same failures.

Depends on:
- `runbook.md`
- `../../runtime/vamos-gaps.md`
- `run-log.md`
- `../../runtime/workbench-integration-boundaries.md`
- `../../host-gui/README.md`
- `../../workflows/external-helpers-and-shellouts.md`

Status: Draft.

Notes:
- Organize by working, partially working, blocked, and deferred behavior.

## Current Status

Trust `run-log.md` over any status claim in the sections below. The log is the append-only, dated record of what has actually been run and observed; the sections below are forward-looking triage guidance written before most of that evidence existed, and can go stale as the log advances. Read the log's most recent entry first, then use the rest of this file to interpret it.

## Compatibility Frontier

The purpose of the sections below is to define the expected compatibility frontier clearly enough that new runs can be classified quickly instead of re-arguing the target every time.

## Likely Earliest Wins

These are the behaviors most likely to become usable first:

- binary loading under `vamos` with explicit volumes, assigns, and command path
- basic `.info` discovery in a small test drawer
- non-recursive icon layout over real icon files
- visible progress to main-window creation

Those are the most realistic early wins because the app's core scope is Workbench metadata rather than direct graphics hardware or undocumented devices [S11 L150-L153] [S12 L5-L8].

## Behaviors That Clearly Need Workbench-Class Support

The following areas should be treated as blocked until the runtime can supply genuine Workbench semantics:

- launch via `WBStartup` rather than only CLI argv [S30 L623-L687]
- reading program-icon tooltypes at startup [S30 L277-L380]
- correct current-directory behavior during Workbench launch [S30 L330-L335]
- stable use of Workbench/public-screen UI resources, menus, and requesters [S31 L174-L227] [S31 L470-L518]

If an investigation is still at plain Shell launch, failures in these areas are expected rather than surprising. See `../../runtime/workbench-integration-boundaries.md` for which of these are first-wave versus later-phase, and `../../host-gui/README.md` for how the UI-facing items should be implemented on the host side.

## Behaviors That Are Probably Optional Or Second-Phase

These features matter, but they should not be allowed to block the very first runnable milestone:

- default-tool validation using PATH parsed from startup scripts [S12 L244-L250] [S34 L1275-L1310]
- LhA backup and restore [S12 L256-L299] [S32 L93-L119] [S32 L201-L249]
- higher-fidelity icon handling that depends on icon-library v44 features [S12 L207-L209] [S34 L803-L825]
- scan-time exclusions such as left-out icons and disk icons [S35 L366-L395]

They are important compatibility targets, but they sit behind "the app launches and can inspect a small test folder" in the delivery order. See `../../workflows/external-helpers-and-shellouts.md` for how to triage the `LhA` dependency specifically.

## Source-Release Drift To Keep In Mind

The user-facing docs identify the application as version 1.0, but the current source comments describe a GUI migration and refer to a GUI version 2.0.0 [S12 L382-L386] [S30 L1-L9]. Treat this as a standing caution:

- the released binary and published manual define the baseline behavior we are trying to reproduce;
- the source tree is excellent for understanding dependencies and likely failure modes;
- but a source-only feature should not be marked as "required for compatibility" until a real run or release artifact confirms it.

## Likely Failure Buckets

When `iTidy` fails under the project runtime, the most probable first buckets are:

- missing or inaccurate Workbench launch semantics
- incomplete `dos.library` path and lock behavior
- incomplete `icon.library` load/save/default-tool behavior
- missing Intuition or requester behavior
- missing command execution support for `LhA`

This ordering comes directly from the published feature set and the current source structure, which bundles GUI, icon, scan, default-tool, and backup subsystems into one executable [S11 L15-L26] [S29 L38-L116].
