---
title: "Assets Index"
status: draft
depends_on:
  - "adf-sets.md"
  - "rom-sets.md"
  - "libraries-and-toolkits.md"
  - "documentation-sources.md"
citations_used:
  - "S7"
  - "S8"
  - "S16"
---

# Assets Index

Purpose: Provide one map of all resource classes used by the project.

Needed for:
- Understanding what resource groups exist and why.

Depends on:
- `adf-sets.md`
- `rom-sets.md`
- `libraries-and-toolkits.md`
- `documentation-sources.md`

Status: Draft.

Notes:
- Distinguish between committed helpers, placeholders, ignored payloads, and fetched raw docs.

## Summary

The `assets/` tree is the repository's resource staging area. It is intentionally mixed-purpose:

- some entries are committed helper scripts or placeholder markers,
- some are optional local binary payloads added by the operator,
- some are extracted local reference trees,
- and some are fetched raw documentation caches.

The key rule is that the project docs are authoritative for how these resources are used, while the placeholder scheme and helper scripts define what can safely live in source control.

## Top-Level Resource Groups

The current top-level groups are:

- `assets/adf/`
- `assets/roms/`
- `assets/libs/`
- `assets/docs/`
- `assets/system/`

Each group exists for a different reason and should not be treated as one undifferentiated "runtime image."

## Source-Control Contract Versus Local Payloads

The `.gitignore` rules intentionally ignore most of `assets/**` while keeping:

- directories,
- `*.placeholder` files,
- `assets/libs/download_classact33.sh`,
- `assets/docs/download_required_docs.sh`

in source control. In practice, that means the committed contract is:

- the expected filenames,
- the helper scripts,
- and the placeholder markers for non-redistributable material.

Actual ADFs, ROMs, extracted toolkit payloads, and downloaded raw docs may exist in a local working tree, but they are not the part of the repository that other users should assume is present by default.

## Relationship To Runtime Strategy

The asset tree is primarily a reference and staging area, not a direct `vamos` runtime tree. `Vamos` maps host directories as Amiga volumes and can work without Kickstart ROMs or full Workbench disks when Python-side library implementations are sufficient [S7 L100-L169] [S8 L9-L15]. That means:

- ADFs and ROMs are mainly reference or comparison media at this stage.
- Toolkit archives and extracted trees support dependency analysis.
- Raw docs support project-authored summaries.
- Prepared runtime trees, when needed, should be built deliberately rather than assumed to be identical to `assets/`.

## Section Guide

- [ADF Sets](./adf-sets.md) covers the AmigaOS disk-image families retained in the tree.
- [ROM Sets](./rom-sets.md) covers the Kickstart references and their limited current role.
- [Libraries And Toolkits](./libraries-and-toolkits.md) covers non-base toolkit dependencies, currently centered on ClassAct 3.3 [S16].
- [Documentation Sources](./documentation-sources.md) covers the fetched upstream reference material used to write the project docs.

## Working Rule

When adding new material under `assets/`, be explicit about which of these it is:

1. a committed script,
2. a committed placeholder,
3. an optional local payload,
4. an extracted local reference tree,
5. or a fetched raw documentation cache.
