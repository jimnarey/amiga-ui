---
name: vamos-launcher-and-overrides
description: >
  Work on the repo-owned in-process vamos launcher and local override points.
  Use when adding library behavior, adjusting launcher flow, or deciding
  between subclassing and patching.
---

# Vamos Launcher And Overrides

## Use This Skill When
- You need to extend how `vamos` is launched from this repo.
- You need to add or override library behavior.
- You are deciding where a compatibility fix should live.

## Goal
Keep `vamos` integration reviewable, repo-owned, and easy to rerun.

## Default Architecture
- The app should run through `run_vamos_in_process()`.
- Session orchestration lives in `src/amiga_ui/vamos/launcher.py`.
- Library override registration lives in `src/amiga_ui/vamos/extensions.py`.
- Temporary last-resort monkey patches live in `src/amiga_ui/vamos/bootstrap.py`.

## Preferred Extension Order
1. Change repo-owned runtime preparation or probe arguments if the problem is environmental.
2. Use subclassing or composition in the launcher if the problem is session setup.
3. Add a repo-owned library implementation and register it in `get_library_impl_overrides()` if the problem is library behavior.
4. Use a narrowly-scoped bootstrap patch only if upstream offers no clean seam.

## Hard Rules
- Do not edit files under `.venv/`.
- Do not fork or vendor `amitools` unless explicitly asked.
- Prefer subclassing over monkey patching.
- If a patch is necessary, keep it local, reversible, and documented in code.
- Keep launcher responsibilities separate from app-specific behavior where practical.

## When Adding A Library Override
1. Identify the exact Amiga library name.
2. Create the smallest repo-owned implementation that moves the app forward.
3. Register it in `src/amiga_ui/vamos/extensions.py`.
4. Rerun `tests.test_vamos_launcher` and the relevant probe.
5. Confirm the first blocker has changed for the right reason.

## Verification
- `PYTHONPATH=src .venv/bin/python -m unittest tests.test_vamos_launcher`
- `PYTHONPATH=src .venv/bin/python -m amiga_ui probe itidy --direct --timeout 5`
