---
name: testing-and-regression
description: >
  Choose and run the smallest meaningful verification set after a change. Use
  when code, docs, launcher behavior, or headless GUI support has been edited.
---

# Testing And Regression

## Use This Skill When
- You have changed code or docs and need to verify the result.
- You need to decide which tests are mandatory for the current change.
- You need to report what was and was not verified.

## Goal
Run the smallest set of checks that gives honest confidence for the change.

## Default Verification Rules
- Always prefer targeted checks over a vague claim of correctness.
- Match the verification to the change surface.
- If a higher-value runtime check is available, use it in addition to unit tests.

## Common Command Set
- Docs metadata:
  - `PYTHONPATH=src .venv/bin/python -m unittest tests.test_helper tests.test_docs_metadata`
- Launcher and probe integration:
  - `PYTHONPATH=src .venv/bin/python -m unittest tests.test_vamos_launcher`
  - `PYTHONPATH=src .venv/bin/python -m amiga_ui probe amiga_apps/itidy1classic/binary/extracted/iTidy --direct --timeout 5`
- Xvfb wrapper and smoke helpers:
  - `PYTHONPATH=src .venv/bin/python -m unittest tests.test_xvfb`
  - `uv run python tests/run_gui_smoke_test.py`
- Syntax sanity for edited Python modules:
  - `python -m py_compile <files>`

## Guardrails
- If a test could not be run, say so plainly.
- Do not claim the desktop GUI path was tested if only Xvfb was used.
- Do not skip the direct probe when changing launcher or path behavior.
- Prefer one extra relevant check over a long unrelated test sweep.

## Output Expectations
Report:
- what was run
- what passed
- what could not be run
- what risk remains
