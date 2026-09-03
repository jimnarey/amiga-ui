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
