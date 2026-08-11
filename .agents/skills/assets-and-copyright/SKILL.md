---
name: assets-and-copyright
description: >
  Manage binary assets, placeholders, provenance, and copyright boundaries. Use
  when adding ADFs, ROMs, archives, or other non-source resources.
---

# Assets And Copyright

## Use This Skill When
- Adding or renaming binary assets.
- Creating or updating placeholder files.
- Deciding whether a resource belongs in source control.

## Goal
Keep the repo legally and operationally clean while making required resources discoverable.

## Default Rules
- Commit redistributable source, docs, and scripts.
- Do not commit copyrighted binaries unless the project has already decided they are safe to keep.
- Use `.placeholder` files for copyrighted resources that must exist conceptually but cannot be committed.
- Keep naming consistent between real files and placeholder files.

## Current Asset Areas
- `assets/adf/`
- `assets/roms/`
- `assets/libs/`
- `assets/system/`
- `assets/docs/`
- `amiga_apps/itidy1classic/`

## Workflow
1. Decide whether the resource is redistributable.
2. If not redistributable, create or maintain a `.placeholder` file instead.
3. Record provenance through filenames, scripts, README notes, or upstream metadata.
4. Keep download/extraction logic in source-controlled scripts when appropriate.
5. Do not change asset naming casually; consistency helps probes, docs, and future automation.

## Guardrails
- Do not invent provenance.
- Do not hide copyrighted payloads in archives or unexpected paths.
- Do not mix prepared runtime trees with long-term reference media.
- Keep the repo's placeholders authoritative about what is expected.

## Key Repo Files
- `assets/`
- `docs/assets/`
- `docs/workflows/asset-acquisition.md`
