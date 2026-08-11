---
name: headless-gui-and-xvfb
description: >
  Run and debug the project's headless GUI path using the Python-managed Xvfb
  wrapper. Use when smoke tests, Qt startup, or display configuration are the
  current blocker.
---

# Headless GUI And Xvfb

## Use This Skill When
- A GUI smoke test is failing.
- A headless run needs a temporary display.
- You need to decide whether to use desktop or Xvfb execution.

## Goal
Separate host-display problems from Amiga compatibility problems.

## Preferred Commands
- Headless smoke test:
  - `uv run python tests/run_gui_smoke_test.py`
- Ad hoc headless command:
  - `uv run amiga-ui-xvfb -- <command> [args...]`
- Direct desktop smoke test:
  - `uv run amiga-ui smoke-gui --direct`

## Workflow
1. Run the smoke test before blaming `vamos` or app-specific code.
2. If the smoke test fails, fix the host GUI path first.
3. Use the Python Xvfb wrapper for automated and ad hoc headless runs.
4. Use the direct desktop subcommand when a human is testing on a normal Linux session.

## Guardrails
- Do not keep re-probing an Amiga app if the host Qt smoke test is already broken.
- If `/tmp/.X11-unix` ownership or mode is wrong, report the exact problem and stop.
- Keep `QT_QPA_PLATFORM` explicit when needed; the wrapper defaults it to `xcb`.
- Prefer the Python module and `uv run` entrypoint over deleted shell-script workflows.

## Key Repo Files
- `src/amiga_ui/host/xvfb.py`
- `src/amiga_ui/host/gui_smoke.py`
- `tests/run_gui_smoke_test.py`
- `docs/runtime/headless-gui.md`
