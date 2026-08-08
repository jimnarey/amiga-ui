---
title: "Vamos Configuration"
status: draft
depends_on:
  - "vamos-overview.md"
  - "vamos-path-mapping.md"
  - "vamos-library-modes.md"
citations_used:
  - "S7"
  - "S8"
  - "S10"
---

# Vamos Configuration

Purpose: Document the repo-specific `vamos` configuration conventions.

Needed for:
- Repeatable runs and consistent debugging output.

Depends on:
- `vamos-overview.md`
- `vamos-path-mapping.md`
- `vamos-library-modes.md`

Status: Draft.

Notes:
- Include volumes, assigns, library sections, CPU choice, and hardware access policy.

## Summary

`Vamos` can be configured partly on the command line and partly through `.vamosrc` files, and command-line settings override file settings [S7 L79-L94]. For this project, that flexibility is useful but also dangerous: hidden per-user configuration would make OpenHands runs harder to reproduce. The project should therefore prefer explicit repo-owned settings and should avoid depending on ambient `~/.vamosrc` state.

## Configuration Sources

`Vamos` documents three important rules:

1. it looks for `.vamosrc` in `$HOME` and then the current directory,
2. `-c` can select a specific config file,
3. `-S` disables implicit `.vamosrc` loading entirely [S7 L81-L94]

The project convention should be:

1. assume automation should not inherit a developer's personal `~/.vamosrc`;
2. use an explicit config path or explicit command-line options for important runs;
3. use `-S` for debugging sessions where hidden config would make diagnosis ambiguous.

## What Must Be Controlled

The upstream `vamos` docs divide configuration into DOS setup, library settings, hardware settings, and tracing/emulation options [S7 L64-L77]. For this project, the important configurable areas are:

- volume mappings
- assigns
- command path
- current working directory
- library modes and versions
- CPU choice
- RAM size
- hardware-access policy
- logging and tracing

## Project Rules

### 1. Prefer Explicit Path Setup

The project should treat volume and assign mappings as part of the test fixture, not as incidental shell state. If a run depends on files under `amiga_apps/` or `assets/`, those mappings should be explicit in the command or config used for that run.

### 2. Keep Library Policy Visible

Library mode choices should live in explicit config sections rather than being buried in ad hoc launch scripts. `Vamos` library configuration is part of the main `.vamosrc` structure and supports per-library sections plus a default `*.library` section [S8 L117-L163].

### 3. Fail Fast On Hardware Access

`Vamos` supports several hardware-access handling modes, including `emu`, `ignore`, `abort`, and `disable` [S7 L334-L365]. Because this project excludes direct-hardware workloads, the normal policy should be to fail fast rather than quietly emulate or ignore such access. In practice, that means treating `abort` as the safer default for exploratory compatibility work.

### 4. Prefer Pure Amiga Paths In Serious Runs

`Vamos` can fall back from host paths to Amiga paths unless `pure_ami_paths=True` is set [S7 L254-L270] [S7 L438-L444]. For serious debugging and automation, the project should prefer pure Amiga-path launches so that path resolution errors stay visible.

## Sample Baseline Shape

The sample `test.vamosrc` bundled with `amitools` is intentionally small: it defines volumes, defines a `sys:` assign, adds a command path, and sets a small amount of main-memory configuration [S10 L1-L14]. That is the right design lesson even though the project's eventual config will be larger. The baseline shape should remain:

1. explicit volumes
2. explicit assigns
3. explicit path
4. explicit library policy where needed
5. explicit memory and debugging choices where relevant

## What This Doc Does Not Promise Yet

This document does not claim that one final committed `.vamosrc` already exists for every use case. The authoritative rule is simpler: every important run should be reproducible from repo-visible configuration, not from developer-local defaults.
