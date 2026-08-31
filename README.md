# amiga-ui

`amiga-ui` is a Python-based compatibility-layer project for running selected classic Amiga Workbench GUI applications on Linux by extending the `vamos` runtime from [amitools](https://github.com/cnvogelg/amitools).

This README is the human entrypoint. For the OpenHands-specific autonomous workflow, start with [.openhands/onboarding.md](.openhands/onboarding.md).

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

If you are working through OpenHands, the repo-local setup entrypoint is:

```bash
bash .openhands/setup.sh
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

For the full autonomous development loop and recommended command order, see [.openhands/onboarding.md](.openhands/onboarding.md).

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

## Bespoke Porting Agent (experimental)

`agent/` is a separate, minimal driver for this repo's error-driven-porting loop, built on [PydanticAI](https://pydantic.dev/docs/ai/overview/) against local models. Unlike the OpenHands/Goose/OpenCode harnesses, the LLM is only called for two narrow, validated judgment calls — classify the blocker, propose a fix as a diff — while a plain Python driver owns the loop itself, including deciding whether a fix actually worked.

```bash
uv sync --group agent --group dev
uv run python -m agent amiga_apps/itidy1classic/binary/extracted/iTidy
```

It runs exactly one unit of work per invocation and exits; call it again to pick up the next blocker. See [agent/README.md](agent/README.md) for the design — including how it restricts blocker categories to what the launcher's own probe output actually supports — and [docs/research/local-agent-performance.md](docs/research/local-agent-performance.md) for the research behind it.

The `agent` dependency group is optional: without it, the agent's unit tests (`tests.test_agent_driver`, `tests.test_agent_llm`) skip with a reason instead of failing to import, so the standard quality gate stays green on the dev-only bootstrap.

## Documentation Sources

The external source registry for this project lives in [docs/sources.md](docs/sources.md).
