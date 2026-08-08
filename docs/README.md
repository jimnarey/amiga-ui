# Documentation

This directory contains the project-authored documentation intended to be read before raw upstream material in the fetched documentation cache.

## Read First

1. `architecture/overview.md`
2. `architecture/compatibility-scope.md`
3. `platform/amiga-primer.md`
4. `runtime/vamos-overview.md`
5. `workflows/error-driven-porting.md`
6. Relevant app notes in `apps/`

## Sections

- `architecture/`: project goals, boundaries, and high-level design.
- `platform/`: AmigaOS concepts, libraries, and structures relevant to this project.
- `runtime/`: how `vamos` fits into the implementation and debugging loop.
- `workflows/`: repeatable setup, porting, and regression routines.
- `assets/`: the resource inventory section explaining what resource classes exist and why they matter to the project.
- `apps/`: app-specific notes, beginning with `iTidy`.
- `research/`: open questions, deferred decisions, and source priorities.

## Status

This tree currently contains stubs. Each file should be expanded from the fetched upstream documentation, inspected source trees, and verified runtime behavior.
