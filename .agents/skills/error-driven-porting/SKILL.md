---
name: error-driven-porting
description: >
  Triage probe failures and advance compatibility one blocker at a time. Use
  when running a target under amiga-ui probe or deciding the next
  implementation step.
---

# Error-Driven Porting

## Use This Skill When
- A real app run has failed and you need to choose the next fix.
- You are about to change runtime behavior, library behavior, or prepared-path setup.
- You need to avoid mixing several speculative fixes into one step.

## Goal
Move the target app forward by fixing the earliest meaningful blocker, then rerun immediately.

## Workflow
1. Start from a real run, not a hypothetical failure.
2. Prefer the project probe entrypoint over ad hoc commands.
3. Read the latest run artifacts before changing code:
   - `artifacts/runs/.../result.json`
   - `artifacts/runs/.../stderr.txt`
   - `artifacts/runs/.../vamos.log`
   - `artifacts/runs/.../invocation.json`
4. Classify the first blocker honestly:
   - host setup problem
   - path/runtime-tree problem
   - missing library or missing function
   - launcher or bridge problem
   - helper-command or optional dependency problem
   - out-of-scope hardware/full-emulator/subsystem problem
5. Implement the smallest repo-owned change that addresses that blocker.
6. Rerun the same probe as soon as the change is in place.
7. Stop once the app advances to a new blocker or the current blocker is resolved.

## Guardrails
- Do not bundle multiple unrelated fixes into one change.
- Do not hide a real failure behind a broad fake unless the fake is explicitly temporary and documented.
- Do not treat a later symptom as the target if an earlier blocker is already visible.
- Do not patch installed packages under `.venv/`; keep changes in the repository.
- If the failure points to direct hardware access, broad audio/peripheral/device emulation, or another full-system concern, stop and mark it clearly.
- If the failure should produce visible UI behavior, do not bypass it with an invented success result.

## Preferred Commands
- `uv run amiga-ui probe amiga_apps/itidy1classic/binary/extracted/iTidy`
- `PYTHONPATH=src .venv/bin/python -m amiga_ui probe amiga_apps/itidy1classic/binary/extracted/iTidy --direct --timeout 5`
- `PYTHONPATH=src .venv/bin/python -m unittest tests.test_vamos_launcher`

## Key Repo Files
- `src/amiga_ui/cli.py`
- `src/amiga_ui/vamos/launcher.py`
- `src/amiga_ui/vamos/extensions.py`
- `docs/workflows/error-driven-porting.md`
- `docs/workflows/fake-and-deferred-implementations.md`
- `docs/workflows/external-helpers-and-shellouts.md`
- `docs/runtime/subsystem-stop-rules.md`
- `docs/apps/itidy/runbook.md`
