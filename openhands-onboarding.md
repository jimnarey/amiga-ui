# OpenHands Onboarding

This file is the repository starting point for OpenHands-style autonomous work. It is not the main user README.

## Purpose

This repository is building a Python-based compatibility layer for selected classic Amiga Workbench GUI applications. The first real target is `iTidy`.

The working model is:

1. run a real Amiga GUI app under the repo-owned `vamos` launcher;
2. capture the first meaningful failure;
3. implement one missing function, behavior, or runtime mapping in repo code;
4. rerun immediately and move to the next blocker.

## First Actions

On a fresh clone:

```bash
bash .openhands/setup.sh
```

Required host tools:

- `Xvfb` for headless GUI execution
- `7z` for required archive and asset handling

If the repo check reports missing required binary assets, stop and ask for them rather than guessing replacements.

The setup script is intended to leave the repository on `development`. Before making a real change, create or switch to a task-specific feature branch from there.

## Canonical Commands

Use these commands by default:

```bash
uv run amiga-ui check
uv run amiga-ui smoke-gui
uv run amiga-ui smoke-gui --direct
uv run amiga-ui probe amiga_apps/itidy1classic/binary/extracted/iTidy
uv run amiga-ui probe amiga_apps/itidy1classic/binary/extracted/iTidy --direct
uv run amiga-ui-xvfb -- <command> [args...]
```

`probe` is the main autonomous loop entrypoint. Prefer it over ad hoc `vamos` invocations.

## Branch Strategy

Treat Git workflow as part of the development loop, not as cleanup at the end.

- `main` is the protected history branch.
- `development` is the long-lived integration branch for accepted work.
- Each new feature, fix, documentation task, or blocker-fix iteration should use its own branch created from `development`.
- Do not commit directly on `main` or `development`.
- Do not merge routine work into `main`.
- Do not delete branches after merge.

Recommended branch shapes:

- `feature/<short-topic>`
- `fix/<short-topic>`
- `docs/<short-topic>`

Typical sequence:

```bash
git checkout development
git checkout -b feature/<short-topic>
```

See `docs/workflows/branching-and-merging.md` for the authoritative policy.

## Standard Development Loop

1. Run `uv run amiga-ui probe amiga_apps/itidy1classic/binary/extracted/iTidy`.
2. Read the latest local run artifacts under `artifacts/runs/`.
3. Classify the first blocker honestly:
   - host dependency or setup issue
   - path/runtime-tree issue
   - missing library or function
   - struct or message translation issue
   - GUI/requester/layout behavior issue
   - out-of-scope hardware/full-emulation issue
4. Make the smallest repo-owned change that addresses that blocker.
5. Rerun the same probe immediately.
6. If the app advances to a new blocker and the current branch now represents one coherent completed fix, run the quality gates, commit it, merge it into `development`, and record the result.
7. Start the next blocker from a fresh feature branch created from the updated `development` branch. Do not continue working on a branch that has already been merged; treat it as completed history, not a rolling workspace.
8. Stop without merging only when the blocker is out of scope, the work is intentionally draft, the user asked to leave it unmerged, or a merge issue needs human input.

Do not patch installed packages inside `.venv/`. Keep project behavior in this repository.

There is a concrete example of this loop producing one completed unit of work in commit `c097fbb` on the `development` branch (`Add minimal icon.library override`) — a useful reference for the expected size and shape of one blocker-level iteration: narrow code change, focused verification, docs update, and merge-ready branch closure.

## Commit And Merge Conditions

Do not commit or merge merely because a run produced some improvement. A branch is ready to commit when:

1. it addresses one coherent problem;
2. the changes are limited to that problem;
3. the relevant tests or checks exist;
4. the relevant tests or checks have been run and have passed;
5. the required docs updates are already included.

Do not merge a feature branch back into `development` unless all of the following are true:

1. `uv run pre-commit run --all-files` passes;
2. the relevant test suite passes;
3. new or changed behavior is covered by tests where sensible;
4. any required smoke or probe checks have passed;
5. the branch remains within project scope.

The repository stop hook is intended to enforce the minimum quality gate automatically before OpenHands finishes a task.

## Where To Read Next

Start with `AGENTS.md`, then follow the reading order in `docs/README.md`. Do not duplicate that order here; keep `docs/README.md` as the single canonical list so it only needs updating in one place.

Use `.agents/skills/` for focused guidance on launcher work, path setup, host GUI implementation, scope and boundary triage, testing, assets, citations, and the error-driven porting loop.

## Important Repo Rules

- Use `uv` for Python commands and dependency management.
- Treat the repo-owned in-process `vamos` launcher as the standard execution path.
- Prefer subclassing and explicit extension points over monkey patching.
- Keep compatibility logic in `src/amiga_ui/`, not in downloaded upstream code or local environment state.
- Use `Xvfb` for automated and headless GUI runs; use a normal Linux desktop session for human exploratory testing.
- Do not treat `docs/archive/PROJECT_BRIEF.md` as the current source of truth. It is historical bootstrap material.
- Keep `.openhands/setup.sh` and `.openhands/hooks.json` aligned with the actual repository workflow.

## Key Code And Data Locations

- `src/amiga_ui/cli.py`: main project entrypoint
- `src/amiga_ui/vamos/launcher.py`: in-process `vamos` launch path
- `src/amiga_ui/host/xvfb.py`: Python-managed `Xvfb` wrapper
- `amiga_apps/itidy1classic/`: first real target app and source tree
- `assets/`: required copyrighted assets, placeholders, and download scripts
- `artifacts/runs/`: transient local probe outputs and logs from recent runs

## Verification

After making changes, run the smallest relevant checks and report exactly what ran. Common commands:

```bash
uv run ruff check .
uv run pyright
uv run python -m unittest
uv run amiga-ui probe amiga_apps/itidy1classic/binary/extracted/iTidy --direct
uv run python tests/run_gui_smoke_test.py
```
