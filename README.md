# amiga-ui

This repository is being set up to develop a Python-based compatibility layer for classic Amiga Workbench applications.

## Python Setup

The project uses `uv` for Python environment and dependency management and assumes Python 3.12 or newer.

### Initial Setup

```bash
uv sync
```

This creates a local virtual environment in `.venv/` and installs the project dependencies, including `amitools` with its `vamos` support extra.

### Running Tools

Examples:

```bash
uv run amiga-ui check
uv run amiga-ui smoke-gui
uv run amiga-ui probe itidy
uv run vamos --help
uv run xdftool --help
```

The `amiga-ui` command is the main project entrypoint. It currently provides:

- `check` for host and asset preflight checks
- `smoke-gui` for a minimal Qt Widgets window test
- `probe <target>` for a first `vamos` launch with captured artifacts

## Headless GUI Smoke Test

For headless GUI work on Linux, install `Xvfb` and use the project wrapper:

```bash
./check_optional_deps.sh
./tests/run_gui_smoke_test.sh
```

The smoke-test launcher starts a temporary X11 server via the project `Xvfb` wrapper, exports `DISPLAY`, and defaults `QT_QPA_PLATFORM` to `xcb` so Qt Widgets runs in a predictable mode.

### Probe Artifacts

The `probe` subcommand writes run artifacts under `artifacts/runs/`, including the exact invocation, stdout, stderr, a `vamos` log, and a JSON result summary. This is the main handoff point for an automated OpenHands loop that fixes one issue and reruns the target.

### Bootstrap Note

The `amitools` checkout currently present in the repository root is only a bootstrap analysis aid. Once the dependency-based workflow is verified, the project should rely on the `uv`-managed installation instead of that in-tree copy.

## Documentation Sources

The external source registry for this project lives in [docs/sources.md](docs/sources.md).
