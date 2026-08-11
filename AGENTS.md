# Repository Guidance

This repository develops a Python-based compatibility layer for selected classic Amiga Workbench applications.

## Core Rules
- Use `uv` for Python commands and dependency management.
- Treat the repo-owned in-process `vamos` launcher as the standard execution path.
- Prefer one real blocker at a time: run, inspect artifacts, make the smallest useful fix, rerun.
- Keep compatibility changes in the repository, not in `.venv/` or other installed-package locations.
- Prefer subclassing or explicit extension points over monkey patching. If a patch is necessary, keep it narrow and local.

## Runtime And GUI
- Use `uv run amiga-ui probe <target>` for target probing.
- Use `uv run python tests/run_gui_smoke_test.py` for the headless GUI smoke test.
- Use `uv run amiga-ui smoke-gui --direct` for manual desktop smoke testing.
- Use `uv run amiga-ui-xvfb -- <command>` for ad hoc headless GUI commands.

## Assets And Scope
- Do not commit copyrighted binary assets unless the repo already treats them as allowed.
- Maintain placeholder files and download scripts consistently when binary resources cannot live in source control.
- Stay within API-level compatibility scope. Direct hardware access and full-system emulation are out of scope.

## Verification And Docs
- Run the smallest relevant verification set for each change and report what you actually ran.
- Keep documentation authoritative for settled project decisions.
- When editing technical docs, keep citations and source references aligned with `docs/sources.md`.

## Optional Skills
- Use the on-demand skills in `.agents/skills/` for specialized workflows such as error-driven porting, launcher work, code style, committing, assets, and documentation.
