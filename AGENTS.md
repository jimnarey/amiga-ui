# Repository Guidance

This repository develops a Python-based compatibility layer for selected classic Amiga Workbench applications.

Read `openhands-onboarding.md` first for the standard bootstrap and autonomous development loop.

## Core Rules
- Use `uv` for Python commands and dependency management.
- Treat the repo-owned in-process `vamos` launcher as the standard execution path.
- Prefer one real blocker at a time: run, inspect artifacts, make the smallest useful fix, rerun.
- Keep compatibility changes in the repository, not in `.venv/` or other installed-package locations.
- Prefer subclassing or explicit extension points over monkey patching. If a patch is necessary, keep it narrow and local.

## Git Workflow
- `main` is not the working branch for routine OpenHands development.
- OpenHands should start on `development`.
- Each distinct feature, fix, or doc task should use its own branch created from `development`.
- Do not commit directly on `main` or `development`.
- Do not merge routine work into `main`.
- Merge feature branches into `development` only after the repo quality gates pass.
- Do not delete branches after merge.

## Runtime And GUI
- Use `uv run amiga-ui probe <path-to-amiga-binary>` for target probing.
- Use `uv run python tests/run_gui_smoke_test.py` for the headless GUI smoke test.
- Use `uv run amiga-ui smoke-gui --direct` for manual desktop smoke testing.
- Use `uv run amiga-ui-xvfb -- <command>` for ad hoc headless GUI commands.

## Assets And Scope
- Do not commit copyrighted binary assets unless the repo already treats them as allowed.
- Maintain placeholder files and download scripts consistently when binary resources cannot live in source control.
- Stay within API-level compatibility scope. Direct hardware access and full-system emulation are out of scope.

## Verification And Docs
- Run the smallest relevant verification set for each change and report what you actually ran.
- Treat `pre-commit`, relevant tests, and any higher-value smoke or probe checks as the minimum merge gate.
- Keep documentation authoritative for settled project decisions.
- When editing technical docs, keep citations and source references aligned with `docs/sources.md`.

## Optional Skills
- Use the on-demand skills in `.agents/skills/` for specialized workflows such as error-driven porting, launcher work, code style, committing, assets, and documentation.
