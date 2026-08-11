---
name: runtime-tree-and-paths
description: >
  Prepare and debug the host runtime tree, volumes, assigns, and cwd used by
  probes. Use when a run fails during path setup, file lookup, or process
  startup.
---

# Runtime Tree And Paths

## Use This Skill When
- A probe fails in path setup or early process creation.
- A binary cannot find a file, library, assign, or startup path.
- You need to change the prepared runtime tree under `artifacts/runs/.../runtime/`.

## Goal
Make the host filesystem view explicit, minimal, and reproducible.

## Standard Probe Shape
- Explicit volumes:
  - `root:/`
  - `app:<target-binary-dir>`
  - `sys:<prepared-runtime-dir>`
  - `work:<scratch-dir>`
- Explicit assigns:
  - `c:sys:C`
  - `libs:sys:Libs`
  - `s:sys:S`
  - `l:sys:L`
  - `devs:sys:Devs`
  - `t:sys:T`
- Explicit cwd:
  - `sys:T`

## Required `sys:` Layout
- `C/`
- `S/`
- `Libs/`
- `Devs/`
- `L/`
- `T/`
- `S/startup-sequence`

## Guardrails
- Map host directories, not raw ADF files, into `vamos` volumes.
- Prefer explicit volumes and assigns over hidden defaults.
- Keep path decisions in repo code, not in ambient user config.
- When debugging, inspect `invocation.json` and `vamos.log` before changing mappings.

## Common Failure Types
- `path config failed!`: invalid config shape or invalid mapping syntax.
- `path setup failed!`: unusable volume/assign/runtime dir.
- missing cwd or lock creation failures: runtime tree exists, but a required location is absent or badly mapped.

## Key Repo Files
- `src/amiga_ui/cli.py`
- `docs/runtime/vamos-path-mapping.md`
- `docs/runtime/vamos-configuration.md`
