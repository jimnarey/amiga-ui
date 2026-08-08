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
uv run vamos --help
uv run xdftool --help
```

### Bootstrap Note

The `amitools` checkout currently present in the repository root is only a bootstrap analysis aid. Once the dependency-based workflow is verified, the project should rely on the `uv`-managed installation instead of that in-tree copy.

## Documentation Sources

The external source registry for this project lives in [docs/sources.md](docs/sources.md).
