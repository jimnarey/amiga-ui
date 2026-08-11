---
name: itidy-target
description: >
  Work effectively on the current primary target application, iTidy. Use when a
  task is specific to iTidy's binary, source tree, expected behavior, or
  milestones.
---

# ITidy Target

## Use This Skill When
- The task is about `iTidy` specifically.
- You need the current target's source, binary, or milestone context.
- You are interpreting an `iTidy` probe failure.

## Canonical Locations
- Binary payload:
  - `amiga_apps/itidy1classic/binary/extracted/`
- Original binary archive:
  - `amiga_apps/itidy1classic/binary/iTidy.lha`
- Source tree for inspection:
  - `amiga_apps/itidy1classic/source/`
- Target-specific docs:
  - `docs/apps/itidy/`

## Ground Truth
- Treat the shipped binary as the runtime truth.
- Use the source tree for diagnosis and implementation clues.
- Do not assume source and shipped binary are perfectly identical in behavior.

## Default Commands
- `uv run amiga-ui probe amiga_apps/itidy1classic/binary/extracted/iTidy`
- `PYTHONPATH=src .venv/bin/python -m amiga_ui probe amiga_apps/itidy1classic/binary/extracted/iTidy --direct --timeout 5`

## Milestone Order
1. Binary loads under the launcher.
2. Prepared runtime and assigns are accepted.
3. The next missing library or API is identified honestly.
4. The app progresses through startup.
5. GUI and Workbench-specific expectations become the active blocker. At this point, switch to the `qt-widgets-and-host-gui` skill and `docs/host-gui/` for host UI rules, and check `docs/runtime/workbench-integration-boundaries.md` for what counts as first-wave Workbench support.

## Guardrails
- Prefer the first blocker in the current artifact set, not a later desired feature.
- Do not rewrite the target-specific workflow as if it were a generic app if the behavior is clearly `iTidy`-specific.
- Keep target-specific logic separate from generic launcher logic when possible.

## Key Repo Files
- `docs/apps/itidy/runbook.md`
- `docs/apps/itidy/compatibility-notes.md`
- `docs/apps/itidy/run-log.md`
- `docs/apps/itidy/dependencies.md`
- `docs/apps/itidy/observed-behavior.md`
- `docs/host-gui/README.md`
- `docs/runtime/workbench-integration-boundaries.md`
- `docs/workflows/external-helpers-and-shellouts.md`
