# amiga-ui

`amiga-ui` is a Python-based compatibility-layer project for running selected classic Amiga Workbench GUI applications on Linux by extending the `vamos` runtime from [amitools](https://github.com/cnvogelg/amitools).

This README is the human entrypoint. For the OpenHands-specific autonomous workflow, start with [openhands-onboarding.md](openhands-onboarding.md).

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
- `uv run amiga-ui probe itidy`

For ad hoc commands under a temporary headless X11 server, use:

```bash
uv run amiga-ui-xvfb -- <command> [args...]
```

Examples:

```bash
uv run amiga-ui check
uv run amiga-ui smoke-gui
uv run amiga-ui probe itidy
uv run amiga-ui-xvfb -- python -c 'print("hello from xvfb")'
uv run vamos --help
uv run xdftool --help
```

For the full autonomous development loop and recommended command order, see [openhands-onboarding.md](openhands-onboarding.md).

## Development Workflow

Routine development should flow through `development`, not `main`.

- Start from `development`
- Create a task-specific branch for each feature, fix, or docs change
- Merge accepted branches back into `development`
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

The `probe` subcommand writes run artifacts under `artifacts/runs/`, including the exact invocation, stdout, stderr, a `vamos` log, and a JSON result summary. This is the main handoff point for an automated OpenHands loop that fixes one issue and reruns the target.

## Documentation Sources

The external source registry for this project lives in [docs/sources.md](docs/sources.md).
