# amiga-ui

This repository is being set up to develop a Python-based compatibility layer for classic Amiga Workbench applications.

## Installation

The project uses `uv` for Python environment and dependency management and assumes Python 3.12 or newer.

```bash
uv sync
```

This creates a local virtual environment in `.venv/` and installs the project dependencies, including `amitools` with its `vamos` support extra.

For headless GUI work on Linux, install `Xvfb` on the host. On Ubuntu:

```bash
sudo apt install xvfb
```

To use all of the resource download scripts install `7z` with:

```
sudo apt install p7zip-full
```

You can then confirm the optional host-side tools are available with:

```bash
./check_optional_deps.sh
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

### Bootstrap Note

The `amitools` checkout currently present in the repository root is only a bootstrap analysis aid. Once the dependency-based workflow is verified, the project should rely on the `uv`-managed installation instead of that in-tree copy.

## Documentation Sources

The external source registry for this project lives in [docs/sources.md](docs/sources.md).
