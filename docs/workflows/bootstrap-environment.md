---
title: "Bootstrap Environment"
status: draft
depends_on:
  - "asset-acquisition.md"
  - "../runtime/vamos-configuration.md"
  - "../runtime/headless-gui.md"
citations_used:
  - "S20"
---

# Bootstrap Environment

Purpose: Define the minimum setup path for a fresh Linux or local-agent machine.

Needed for:
- Reproducible onboarding and recovery.

## Minimum Setup

On a fresh Linux machine or agent container, the shared project bootstrap path is:

1. Acquire the project tree and required copyrighted assets.
2. Run `bash tools/bootstrap.sh` from the repository root.
3. Use `uv run amiga-ui-xvfb -- <command>` for headless GUI checks when no desktop session is available.

The bootstrap script runs `uv sync --group dev`, verifies required host tools with `./check_dependencies.sh`, reports the current branch, and prints the next recommended validation commands. The default platform target is recorded in `docs/architecture/platform-target.md`; read it before interpreting NDK, AutoDoc, or `vamos` library-vector evidence. It does not change branches. It also uses `/tmp/uv-cache` as the default `uv` cache location so container users are less likely to hit read-only or cross-user cache ownership problems.

The project currently requires `Xvfb` for headless GUI execution and `7z` for archive and asset handling. `Xvfb` is the project-standard virtual display server because it provides a real X11 environment for machines with no physical display hardware [S20 §Description ¶1-2].

## One Environment Per Side

The project directory is bind-mounted into the DSH container (host `/mnt/work/projects/amiga-ui` is container `/workspace/amiga-ui`), so a single `.venv` cannot serve both sides. A `uv` virtual environment records absolute paths: `.venv/bin/python` is a symlink to the interpreter that created it, console-script shebangs and the editable-install `.pth` name the project path, and the host and the container differ in all three (host uv-managed Python 3.12.x vs the container's `/usr/bin/python3.12`, and `/mnt/work/projects/...` vs `/workspace/...`). When `uv` finds the other side's `.venv`, it reports "linked to non-existent Python interpreter", deletes it, and rebuilds it, so alternating host and container runs repeatedly wipe each other's environment and re-download dependencies.

The convention is:

- The host uses the default `.venv`, which IDEs and Pyright discover on their own.
- The DSH container sets `UV_PROJECT_ENVIRONMENT=.venv-container` in its service environment (`compose.ai.yml`, outside this repository). The value is relative, so it resolves per project root and the container never touches the host's `.venv`. `.venv-container/` is gitignored.
- Because the container's environment is not at `.venv`, commands in docs and skills must go through `uv run python ...` rather than `.venv/bin/python`. Pyright is not pinned to a `venv` in `pyrightconfig.json` for the same reason: it uses the interpreter of whichever environment `uv run` selected.

## First GUI Validation

After Python dependencies are installed, validate the host GUI path with:

```bash
uv run python tests/run_gui_smoke_test.py
```

This confirms that:

- the Python environment is usable,
- PySide6 imports cleanly,
- Qt can connect to the temporary X server,
- and a trivial Widgets window can be shown and closed.

## Interactive Versus Headless Use

If a normal Linux desktop session is available, developers should use it for exploratory manual work. If the project is being run in a local-agent or other non-desktop environment, use the `Xvfb` wrapper by default.
