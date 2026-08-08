---
title: "Vamos Path Mapping"
status: draft
depends_on:
  - "vamos-overview.md"
  - "../platform/filesystem-and-launch.md"
citations_used:
  - "S7"
  - "S10"
---

# Vamos Path Mapping

Purpose: Explain how host paths are exposed as Amiga volumes and assigns.

Needed for:
- Correct asset layout and reproducible app runs.

Depends on:
- `vamos-overview.md`
- `../platform/filesystem-and-launch.md`

Status: Draft.

Notes:
- Include `sys:` expectations and any repo-specific mapping conventions.

## Summary

`Vamos` exposes host directories as Amiga volumes, then uses assigns and command-path settings to make those directories look like an Amiga filesystem environment [S7 L100-L237]. That means raw ADF files and ROM images are not, by themselves, a runnable filesystem view. A volume mapping needs a host directory, not a disk-image filename [S7 L102-L117].

## Core Upstream Behavior

The upstream rules that matter most here are:

- a volume maps an Amiga volume name to a host directory [S7 L102-L117]
- `root:` is created automatically and maps to the host filesystem root [S7 L118-L125]
- assigns map Amiga names to absolute Amiga paths, not to host paths [S7 L150-L169]
- command search uses the configured Amiga `path` list [S7 L222-L237]
- the current working directory is derived from the launch directory unless overridden [S7 L238-L253]
- auto-assign can create implicit mappings for unknown names, but only under a chosen prefix [S7 L199-L220]

## Project Conventions

### Do Not Depend On `root:`

Even though `vamos` automatically provides `root:` [S7 L118-L125], the project should not depend on it for serious automation runs. Explicit custom volumes are easier to review, easier to diff, and less likely to hide host-environment mistakes.

### Separate Repo Data From Runtime System Trees

The repository already contains several classes of files:

- Amiga application packages under `amiga_apps/`
- copyrighted media and placeholders under `assets/`
- documentation under `docs/`

Those are not all the same thing from `vamos`'s point of view. In particular, the AmigaOS ADF collection is reference media, not a ready-to-run `sys:` tree. A serious Workbench-style run will usually need a prepared host directory representing the Amiga-side runtime tree that `sys:` and related assigns can point at.

### Use Narrow, Named Volumes

The default project mapping style should be to define narrow, purpose-specific volumes, for example:

- one volume for the repo root when needed
- one volume for application files
- one volume for prepared runtime-system content
- one volume for scratch or generated output if needed

This keeps the Amiga-visible filesystem legible and reduces accidental coupling to unrelated host files.

## `sys:` Expectations

The upstream docs explicitly note that defining a `sys:` volume makes sense because some AmigaOS calls default to it [S7 L136-L148]. The project should therefore assume that any realistic Workbench-oriented run needs a meaningful `sys:` target, even if that target is only a minimal prepared runtime tree rather than a full extracted operating-system installation.

The `amitools` sample config takes a small but important step in this direction by explicitly defining `sys=ram:` rather than leaving the name unresolved [S10 L5-L10].

## Assign Policy

Assigns should be used for Amiga-side structure, not as a substitute for volume design. Useful project examples include:

- `c:` for command search paths under `sys:`
- `libs:` for library discovery
- app-specific assigns when a target application expects an installation name

Multi-assigns are supported by `vamos` [S7 L182-L198], but the project should treat them as a compatibility tool, not as a default. They make lookup behavior less obvious, which is usually the opposite of what debugging needs.

## Auto-Assign Policy

Auto-assign is useful for exploratory sessions, but it can also hide missing environment declarations by inventing mappings for unknown names [S7 L199-L220]. The project should therefore leave auto-assign disabled by default in repeatable runs and only enable it deliberately when probing how an unfamiliar app searches for resources.
