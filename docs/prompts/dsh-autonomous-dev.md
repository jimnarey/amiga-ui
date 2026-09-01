---
title: "DSH Autonomous Development Prompt"
status: prompt
depends_on:
  - "../workflows/dsh.md"
  - "../workflows/agent-tool-contract.md"
  - "../workflows/error-driven-porting.md"
  - "../workflows/branching-and-merging.md"
citations_used: []
---

# DeepSeek Harness Autonomous Development Prompt

Work autonomously in the `amiga-ui` repository.

Use `AGENTS.md` as the repo-wide authority. Use `docs/workflows/dsh.md`, `docs/workflows/agent-tool-contract.md`, `docs/workflows/error-driven-porting.md`, and `docs/workflows/branching-and-merging.md` for the active workflow. Ignore `.deprecated/` unless explicitly asked to inspect legacy OpenHands, Goose, or bespoke local-agent material.

First establish the baseline. If the environment has not already been bootstrapped, run:

```bash
bash tools/bootstrap.sh
```

Then run or confirm these checks before making behavior changes, unless an earlier setup failure blocks them:

```bash
./check_dependencies.sh
uv run python tools/docs_triage.py
uv run amiga-ui check
uv run python tools/generate_api_index.py
```

If `uv` or `pre-commit` hits a cache ownership problem, use writable temporary caches, for example:

```bash
export UV_CACHE_DIR=/tmp/uv-cache
export PRE_COMMIT_HOME=/tmp/pre-commit-home
export UV_LINK_MODE=copy
```

If required reference docs, ClassAct files, ADF-derived files, or ROM-derived files are missing, use the repo-owned scripts and documented asset workflow. Do not invent binary assets and do not commit copyrighted payloads. Use these only when the current blocker actually needs them:

```bash
assets/docs/download_required_docs.sh
assets/libs/download_classact33.sh
uv run python tools/extract_adfs.py --force
uv run python tools/generate_api_index.py
```

Advance by the error-driven porting loop: run the real target under the repo `vamos` launcher, capture the first actionable failure, classify it, make the smallest useful repo-owned fix, rerun the same command, and record the result in the relevant app run log.

For missing Amiga library functions, inspect the latest run artifact, run `uv run python tools/analyze_target_failure.py --latest`, identify the library/vector/function/register contract from local FD/proto/stub material, read the relevant AutoDocs, and inspect the target app source to understand why the function is being called. Do not implement from a function name alone. Use decompiled ROM or ADF-contained code only when redistributable docs and available source do not provide enough evidence.

For UI-related functions, correctness means useful host-side behavior, not just returning a value that lets the binary proceed. If the API index or failure analyser marks a function as `host-ui-required`, `workbench-visible-state`, or `likely-ui-support`, read `docs/host-gui/translation-obligations.md` and either implement real Qt-backed window/menu/gadget/requester/font/drawing state or stop at an honest documented boundary. Do not count a fake window pointer, fake visual-info pointer, fake requester result, or no-op drawing call as success by itself.

Use only tools that DSH exposes in this session. Treat `rg`, `find`, `sed`, `cat`, `ls`, and `git grep` as shell commands. If a command fails, inspect the full output before retrying, and change approach when the error shows the command was wrong. If a small command-line dependency is missing and passwordless `sudo` is available, install the package rather than repeatedly working around the missing tool.

Keep changes scoped to the current blocker. Do not modify `.git/`, `.deprecated/`, editor config, credentials, cache directories, or harness configuration unless the user explicitly asks for that exact change. Before stopping, report files changed, checks run, current app/runtime status, and the next concrete blocker.
