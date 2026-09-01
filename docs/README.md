---
title: "Documentation"
status: index
depends_on: []
citations_used: []
---

# Documentation

This directory contains the project-authored documentation intended to be read before raw upstream material in the fetched documentation cache.

## Triage First

Before reading many docs in full, take a lightweight inventory pass so you can choose the relevant small set first.

Preferred commands:

```bash
uv run python tools/docs_triage.py
uv run python tools/docs_triage.py --section runtime
uv run python tools/docs_triage.py --suggest launcher probe
find docs -type f -name '*.md' | sort
```

The helper inspects markdown paths and front matter only. Use it to discover what exists and then open only the docs that match the immediate task.

## Read First

1. `../AGENTS.md`
2. `workflows/dsh.md` for DeepSeek Harness sessions
3. `workflows/bootstrap-environment.md`
4. `architecture/overview.md`
5. `architecture/compatibility-scope.md`
6. `architecture/gui-strategy.md`
7. `platform/amiga-primer.md`
8. `runtime/vamos-overview.md`
9. `runtime/headless-gui.md`
10. `runtime/subsystem-stop-rules.md`
11. `host-gui/README.md`
12. `workflows/agent-tool-contract.md`
13. `workflows/fake-and-deferred-implementations.md`
14. `workflows/branching-and-merging.md`
15. `workflows/error-driven-porting.md`
16. `apps/itidy/runbook.md` for the current target application, then other relevant notes under `apps/` as more targets are added

## Sections

- `archive`: information on how this repository was set up and unlikely to be relevant
- `architecture/`: project goals, boundaries, and high-level design.
- `platform/`: AmigaOS concepts, libraries, and structures relevant to this project.
- `runtime/`: how `vamos` fits into the implementation and debugging loop.
- `host-gui/`: host-side PySide6/Qt Widgets design rules and testing guidance.
- `workflows/`: repeatable setup, porting, regression, and implementation-boundary routines.
- `assets/`: the resource inventory section explaining what resource classes exist and why they matter to the project.
- `apps/`: app-specific notes, beginning with `iTidy`.
- `prompts/`: copy-paste prompts for supported autonomous harnesses.
- `research/`: open questions, deferred decisions, and source priorities.

## Sources

Use the numbered inline reference system defined in [sources.md](sources.md) when citing external material.

## Workfiles

Temporary, gitignored working state does not live under `docs/`:

- `artifacts/runs/` for probe and run artifacts.
- `.deprecated/` for preserved legacy harness configuration that is no longer active.

## Status

This tree is a mix of filled-in draft pages and stubs. Expand the remaining stubs from the fetched upstream documentation, inspected source trees, and verified runtime behavior.
