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

Purpose: Define the minimum setup path for a fresh Linux/OpenHands machine.

Needed for:
- Reproducible onboarding and recovery.

Depends on:
- `asset-acquisition.md`
- `../runtime/vamos-configuration.md`
- `../runtime/headless-gui.md`

Status: Draft.

Notes:
- Reference helper scripts instead of embedding long setup steps here.

## Minimum Setup

On a fresh Linux machine, the project bootstrap path is:

1. Acquire the project tree and required copyrighted assets.
2. Run `uv sync` to install the Python dependencies.
3. Run `./check_optional_deps.sh` to confirm optional external tools are available.
4. Use `./tools/run_with_xvfb.sh` for headless GUI checks when no desktop session is available.

The only optional non-distro dependency currently checked for headless GUI work is `Xvfb`. It is the project-standard virtual display server because it provides a real X11 environment for machines with no physical display hardware [S20 §Description ¶1-2].

## First GUI Validation

After Python dependencies are installed, validate the host GUI path with:

```bash
./tests/run_gui_smoke_test.sh
```

This confirms that:

- the Python environment is usable,
- PySide6 imports cleanly,
- Qt can connect to the temporary X server,
- and a trivial Widgets window can be shown and closed.

## Interactive Versus Headless Use

If a normal Linux desktop session is available, developers should use it for exploratory manual work. If the project is being run in OpenHands or another non-desktop environment, use the `Xvfb` wrapper by default.
