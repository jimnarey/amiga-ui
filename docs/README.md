---
title: "Documentation"
status: index
depends_on: []
citations_used: []
---

# Documentation

This directory contains the project-authored documentation intended to be read before raw upstream material in the fetched documentation cache.

## Read First

1. `architecture/overview.md`
2. `architecture/compatibility-scope.md`
3. `platform/amiga-primer.md`
4. `runtime/vamos-overview.md`
5. `runtime/headless-gui.md`
6. `workflows/branching-and-merging.md`
7. `workflows/error-driven-porting.md`
8. Relevant app notes in `apps/`

## Sections

- `archive`: information on how this repository was set up and unlikely to be relevant
- `architecture/`: project goals, boundaries, and high-level design.
- `platform/`: AmigaOS concepts, libraries, and structures relevant to this project.
- `runtime/`: how `vamos` fits into the implementation and debugging loop.
- `workflows/`: repeatable setup, porting, and regression routines.
- `assets/`: the resource inventory section explaining what resource classes exist and why they matter to the project.
- `apps/`: app-specific notes, beginning with `iTidy`.
- `research/`: open questions, deferred decisions, and source priorities.

## Sources

Use the numbered inline reference system defined in [sources.md](sources.md) when citing external material.

## Status

This tree is a mix of filled-in draft pages and stubs. Expand the remaining stubs from the fetched upstream documentation, inspected source trees, and verified runtime behavior.
