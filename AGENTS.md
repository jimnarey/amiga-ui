# Repository Guidance

This repository develops a Python-based compatibility layer for selected classic Amiga Workbench applications.

Read `docs/README.md` for the documentation map, then `docs/workflows/dsh.md` for the current DeepSeek Harness autonomous workflow. Older OpenHands, Goose, and bespoke local-agent material is preserved under `.deprecated/`; ignore that directory unless the user explicitly asks you to inspect or revive legacy harness behavior.

## Core Rules
- Use `uv` for Python commands and dependency management.
- Treat the repo-owned in-process `vamos` launcher as the standard execution path.
- Prefer one real blocker at a time: run, inspect artifacts, make the smallest useful fix, rerun.
- Keep compatibility changes in the repository, not in `.venv/` or other installed-package locations.
- Prefer subclassing or explicit extension points over monkey patching. If a patch is necessary, keep it narrow and local.
- Before substantial work, assess the docs tree cheaply with `uv run python tools/docs_triage.py` or a filename-only scan, then read in full only the docs relevant to the immediate task.
- Use `bash tools/bootstrap.sh` as the shared bootstrap entrypoint for local agent containers unless the environment has already been bootstrapped.
- Use `uv run python tools/generate_api_index.py` and `uv run python tools/analyze_target_failure.py --latest` to connect probe failures to FD tables, AutoDocs, implementation status, and UI obligations before adding library methods.

## Tool Use And Safety
Every harness working in this repository must follow the shared rules in [docs/workflows/agent-tool-contract.md](docs/workflows/agent-tool-contract.md): tool discipline, protected directories, image-tool handling, and narration/stop discipline. Harness-specific tool names and invocation mechanics belong in harness-specific instructions, not in shared policy. Current DSH instructions live in [docs/workflows/dsh.md](docs/workflows/dsh.md).

## Git Workflow
- `main` is not the working branch for routine autonomous development.
- Start routine autonomous work from `development` when that branch exists and the user has not requested a different branch.
- Each distinct feature, fix, doc task, or blocker-fix iteration should use its own branch created from `development`.
- Do not commit directly on `main` or `development`.
- Do not merge routine work into `main`.
- Merge feature branches into `development` only after the repo quality gates pass.
- If a feature branch satisfies the merge conditions and the user has not asked to keep it unmerged, merge it into `development` before finishing the task.
- After a blocker-level branch has been merged, start the next blocker from a fresh branch created from the updated `development` branch rather than continuing on the old branch.
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
- When implementing missing Amiga library functions, use local FD/proto files, AutoDocs, app source, generated API indexes, and recorded run artifacts before inferring behavior from a function name. Decompile ROMs or ADF-contained binaries only when the task genuinely needs implementation evidence that is not available from redistributable documentation or source.
- Do not treat fake UI handles or no-op drawing/requester/menu/gadget functions as complete fixes. If an Amiga API creates or changes visible UI, the repo implementation should connect it to Qt-backed host behavior or record an honest missing capability.

## Verification And Docs
- Run the smallest relevant verification set for each change and report what you actually ran.
- Treat `pre-commit`, relevant tests, and any higher-value smoke or probe checks as the minimum merge gate.
- Keep documentation authoritative for settled project decisions.
- When editing technical docs, keep citations and source references aligned with `docs/sources.md`.

## Optional Skills
- Use the on-demand skills in `.agents/skills/` for specialized workflows such as error-driven porting, launcher work, host GUI implementation, scope and boundary triage, code style, committing, assets, and documentation.
