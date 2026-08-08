---
title: "Regression Checks"
status: draft
depends_on:
  - "error-driven-porting.md"
  - "../runtime/headless-gui.md"
citations_used: []
---

# Regression Checks

Purpose: Record how to make sure new fixes do not break earlier app behavior.

Needed for:
- Maintaining steady progress as compatibility grows.

Depends on:
- `error-driven-porting.md`
- `../runtime/headless-gui.md`

Status: Draft.

Notes:
- Start with manual smoke checks, then add scripted checks as the project matures.

## Baseline Checks

Run these checks before and after a compatibility change:

```bash
./.venv/bin/python -m unittest tests.test_helper tests.test_docs_metadata
./tests/run_gui_smoke_test.sh
```

The first command protects the documentation metadata conventions. The second proves that the host-side Qt Widgets path can still create and close a window under the project-standard headless display server.

## App-Focused Checks

When working on one Amiga application, keep the regression loop layered:

1. Re-run the generic GUI smoke test.
2. Re-run the app-specific launch command under the same headless wrapper.
3. Inspect logs and captured errors before implementing the next missing behavior.

This sequence helps separate:

- environment breakage,
- host GUI breakage,
- and app-specific compatibility regressions.
