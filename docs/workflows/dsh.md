---
title: "DeepSeek Harness Workflow"
status: draft
depends_on:
  - "bootstrap-environment.md"
  - "agent-tool-contract.md"
  - "error-driven-porting.md"
  - "branching-and-merging.md"
  - "asset-acquisition.md"
  - "../host-gui/translation-obligations.md"
citations_used:
  - "S67"
  - "S68"
  - "S69"
---

# DeepSeek Harness Workflow

Purpose: Define the current preferred autonomous-agent workflow for this repository when using DeepSeek Harness.

Needed for:
- Giving DSH a short, active starting path.
- Keeping legacy OpenHands, Goose, and bespoke local-agent instructions out of the model's way while preserving them for reference.
- Making bootstrap, asset acquisition, and missing-function research explicit enough for long autonomous runs.

## DSH Role

DSH is the preferred general-purpose autonomous harness for this repository at the moment. Its CLI supports a `headless` profile for one-shot tasks, a `web` profile for browser sessions, and profile configuration inspection with `--dump-default-config` and `--dump-config` [S67 §Entry modes] [S68 §Profile boot]. The invoking directory becomes the default workspace root, so start DSH from the repository root or set the container working directory to `/workspace/amiga-ui` [S67 §Entry modes] [S68 §Profile boot].

DSH loads repo instructions from `AGENTS.md` and related project instruction files into session context, with a bounded render budget and `.git` as the default project-root marker [S69 §Lifecycle] [S69 §Configuration]. Keep durable repo-wide rules in `AGENTS.md`; keep the longer DSH procedure here.

## Ignore Legacy Harness Material

The old OpenHands and Goose prompts, hooks, recipes, helper scripts, and bespoke local-agent code are preserved under `.deprecated/`. They are not active instructions for DSH sessions. Ignore `.deprecated/` unless the user explicitly asks about legacy harness behavior.

## Starting A DSH Run

Start from the repository root. In the current container setup, the expected working directory is `/workspace/amiga-ui`.

For a headless run, use the prompt in [../prompts/dsh-autonomous-dev.md](../prompts/dsh-autonomous-dev.md). A typical command from the container stack is:

```bash
docker compose exec -u runuser -w /workspace/amiga-ui deepseek \
  sh -lc 'dsh --profile headless "$(cat docs/prompts/dsh-autonomous-dev.md)"'
```

For Web UI sessions, paste the same prompt into a new session after selecting the repository workspace.

## Bootstrap Checklist

At the beginning of a run, DSH should establish the repository baseline before fixing code:

1. Read `AGENTS.md` and this document.
2. Run `bash tools/bootstrap.sh` unless the user has already bootstrapped the environment.
3. Run `uv run python tools/docs_triage.py` to choose a small, relevant doc set.
4. Run `uv run amiga-ui check` before making behavior changes unless an earlier dependency/bootstrap failure blocks it.
5. Run `uv run python tools/generate_api_index.py` when the generated API index is missing or stale.
6. Run `uv run python tools/analyze_target_failure.py --latest` after each probe failure to identify the defaulted API calls, missing paths, and any UI obligation attached to the blocker.
7. Use `UV_CACHE_DIR=/tmp/uv-cache`, `UV_LINK_MODE=copy`, and `PRE_COMMIT_HOME=/tmp/pre-commit-home` if container cache ownership or cross-filesystem hardlinking prevents `uv` or `pre-commit` from writing cleanly under the default home directory.

The bootstrap script intentionally prints the next recommended checks instead of running every expensive command itself.

## Asset And Reference Setup

Do not invent binary assets or commit copyrighted payloads. When a task needs reference material that is absent from the working tree, use the repo-owned acquisition scripts and then inspect the generated files:

```bash
assets/docs/download_required_docs.sh
assets/libs/download_classact33.sh
uv run python tools/extract_adfs.py --force
uv run python tools/generate_api_index.py
```

These scripts are not required for every run. Use them when `docs/assets/`, `amiga_apps/`, or the current blocker shows that the reference material is missing. `extract_adfs.py` uses `amitools`/`xdftool` to unpack operator-supplied ADFs from `assets/adf/` into ignored local reference trees under `assets/extracted/adf/`. `generate_api_index.py` combines FD tables, fetched AutoDocs, and repo implementation status into ignored local files under `assets/generated/`.

## Missing Amiga Function Workflow

When `vamos` reports a missing library function, do not implement from the function name alone.

1. Inspect the latest `artifacts/runs/` entry, including stdout, stderr, `vamos.log`, and result JSON.
2. Identify the library, vector/bias, function name, register contract, and call site using FD/proto files, generated stubs, app source, and AutoDocs.
3. Search the local docs tree and fetched documentation cache before looking elsewhere.
4. For `iTidy`, inspect the upstream source under `amiga_apps/itidy1classic/source/` to understand why the app calls the function.
5. Use decompiled ROM or ADF-contained code only as a fallback when redistributable docs and available source do not explain behavior well enough.
6. Implement the smallest repo-owned compatibility behavior that gets the real app to the next meaningful state.
7. Rerun the same probe command immediately, then document the new stopping point in `docs/apps/<app>/run-log.md`.

AutoDocs fit between FD/proto discovery and implementation: FD files identify which function is being called and how `vamos` dispatches it; AutoDocs explain the expected AmigaOS API behavior and edge cases. Decompiled code is evidence of last resort, not the default design source.

## Tool Behavior Expectations

Follow [agent-tool-contract.md](agent-tool-contract.md). In particular:

- use only tools exposed by the current DSH session;
- treat `rg`, `find`, `sed`, `cat`, and `ls` as shell commands;
- inspect command output before retrying failed commands;
- install small missing packages with passwordless `sudo` when the container policy allows it;
- never modify `.git/`, `.deprecated/`, editor settings, credentials, or agent config directories unless the user explicitly asks for that exact change.

## Completion Shape

A DSH run should leave the repository in a rational state: code changed only where needed, checks run or clearly blocked, run findings documented, and remaining work named concretely. If the task is too large for one context window, summarize the current blocker, exact commands run, files changed, and next command to run before stopping.
