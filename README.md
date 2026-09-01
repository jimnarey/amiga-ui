# amiga-ui

`amiga-ui` is a Python-based compatibility-layer project for running selected classic Amiga Workbench GUI applications on Linux by extending the `vamos` runtime from [amitools](https://github.com/cnvogelg/amitools).

This README is the human entrypoint. Autonomous agents should start with [AGENTS.md](AGENTS.md); the current preferred DeepSeek Harness workflow is in [docs/workflows/dsh.md](docs/workflows/dsh.md), with a copy-paste task prompt in [docs/prompts/dsh-autonomous-dev.md](docs/prompts/dsh-autonomous-dev.md).

## Harness Status

DeepSeek Harness is the active local autonomous workflow for this repository. Previous OpenHands, Goose, and bespoke local-agent experiments have been preserved under `.deprecated/` for reference, but they are no longer active instructions. Agents should ignore `.deprecated/` unless specifically asked to inspect the legacy setup.

## Installation

The project uses `uv` for Python environment and dependency management and assumes Python 3.12 or newer.

```bash
uv sync --group dev
```

This creates a local virtual environment in `.venv/` and installs the project dependencies, including `amitools` with its `vamos` support extra.

The project also requires two host tools:

- `Xvfb` for headless GUI execution
- `7z` for archive and asset handling

On Ubuntu:

```bash
sudo apt install xvfb
sudo apt install p7zip-full
```

You can then confirm the required host-side tools are available with:

```bash
./check_dependencies.sh
```

For local agent containers, the shared repo bootstrap entrypoint is:

```bash
bash tools/bootstrap.sh
```

## Usage

The main project command is:

```bash
uv run amiga-ui check
```

Current subcommands:

- `uv run amiga-ui check`
- `uv run amiga-ui smoke-gui`
- `uv run amiga-ui probe <path-to-amiga-binary>`, for example `uv run amiga-ui probe amiga_apps/itidy1classic/binary/extracted/iTidy`

For ad hoc commands under a temporary headless X11 server, use:

```bash
uv run amiga-ui-xvfb -- <command> [args...]
```

Examples:

```bash
uv run amiga-ui check
uv run amiga-ui smoke-gui
uv run amiga-ui probe amiga_apps/itidy1classic/binary/extracted/iTidy
uv run amiga-ui-xvfb -- python -c 'print("hello from xvfb")'
uv run vamos --help
uv run xdftool --help
```

For the autonomous development loop and recommended command order, see [docs/workflows/dsh.md](docs/workflows/dsh.md) and [docs/workflows/error-driven-porting.md](docs/workflows/error-driven-porting.md).

## Reference Tooling

Local agents can regenerate the non-committed reference material used for API-aware porting:

```bash
assets/docs/download_required_docs.sh
assets/libs/download_classact33.sh
uv run python tools/extract_adfs.py --force
uv run python tools/generate_api_index.py
uv run python tools/analyze_target_failure.py --latest
```

The generated/extracted outputs live under ignored `assets/` paths. The scripts and placeholder contracts are the committed part.

## Development Workflow

Routine development should flow through `development`, not `main`.

- Start from `development`
- Create a task-specific branch for each feature, fix, docs change, or blocker-fix iteration
- Keep one coherent blocker or decision per branch
- Merge accepted branches back into `development` when the quality gates pass
- Start the next blocker from a fresh branch created from the updated `development`
- Keep branches after merge

The authoritative branch policy lives in [docs/workflows/branching-and-merging.md](docs/workflows/branching-and-merging.md).

## Headless GUI Smoke Test

The smoke test creates a minimal Qt Widgets window and is useful as a host-side sanity check before involving `vamos`.

Run it with:

```bash
uv run python tests/run_gui_smoke_test.py
```

If you want to run the same minimal Qt window directly in your normal desktop session instead of under `Xvfb`, use:

```bash
uv run amiga-ui smoke-gui --direct
```

### Probe Artifacts

The `probe` subcommand writes local run artifacts under `artifacts/runs/`, including the exact invocation, stdout, stderr, a `vamos` log, and a JSON result summary. These files are for recent-run inspection, not long-term project history. Important findings from a run should be carried forward into the relevant documentation, especially the app run log.

`artifacts/runs/` is gitignored and grows by one directory per run. Prune older runs once their findings have been carried forward:

```bash
./tools/prune_run_artifacts.sh        # keep the most recent 20 runs
./tools/prune_run_artifacts.sh 50     # or keep a different number
```

## Deprecated Local Agent Experiments

Earlier local-agent experiments, including the bespoke PydanticAI porting driver, are preserved under `.deprecated/` for reference. They are no longer part of the active workflow, package checks, or pre-commit scope.

## Documentation Sources

The external source registry for this project lives in [docs/sources.md](docs/sources.md).
