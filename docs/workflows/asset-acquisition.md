---
title: "Asset Acquisition"
status: draft
depends_on:
  - "../assets/index.md"
  - "../assets/adf-sets.md"
  - "../assets/rom-sets.md"
  - "../assets/libraries-and-toolkits.md"
citations_used:
  - "S1"
  - "S2"
  - "S3"
  - "S4"
  - "S5"
  - "S6"
  - "S13"
  - "S15"
  - "S16"
  - "S17"
---

# Asset Acquisition

Purpose: Explain how users obtain and place non-redistributable project assets.

Needed for:
- Filling placeholders without guesswork.

Depends on:
- `../assets/index.md`
- `../assets/adf-sets.md`
- `../assets/rom-sets.md`
- `../assets/libraries-and-toolkits.md`

Status: Draft.

Notes:
- Link each asset class to its location, helper script, and legal handling notes.

## Summary

The asset-acquisition workflow has one governing principle: commit the instructions and the filename contract, but do not commit local binary payloads that the project has decided not to redistribute. In practice, that means:

- tracked helper scripts for fetchable material,
- tracked underscore-prefixed `.placeholder` files for expected non-redistributable assets,
- git-ignored real binaries placed alongside those placeholders by the operator.

## Two Acquisition Paths

### 1. Fetchable Or Redistributable Material

If an upstream resource can be fetched from a stable public source and the project has chosen to keep it locally for analysis, the repo should prefer a tracked download script over undocumented manual steps.

That rule already covers:

- the documentation cache under `assets/docs/`, which is built from the AmigaOS 3.2 NDK plus selected official AmigaOS wiki and developer pages [S1] [S2] [S3] [S4] [S5] [S6]
- the ClassAct 3.3 archive and extracted tree under `assets/libs/`, which come from the Aminet package and archive referenced in the source registry [S16] [S17]

### 2. Operator-Supplied Local Binaries

If a resource is needed locally but is not meant to live in source control under the project's current policy, the repo expresses that need with a placeholder file. The real asset is then supplied manually by the operator in the same directory, using the same normalized filename minus the leading underscore and minus the `.placeholder` suffix.

Examples:

- `assets/adf/_amigaos_3.1_workbench.adf.placeholder` implies a local file named `assets/adf/amigaos_3.1_workbench.adf`
- `assets/roms/_kickstart_3.1_a1200.rom.placeholder` implies a local file named `assets/roms/kickstart_3.1_a1200.rom`

## Asset Classes

### ADF And ROM Sets

ADF disk images and Kickstart ROMs are kept under `assets/adf/` and `assets/roms/` respectively. Their placeholders are the primary inventory. The repo does not try to encode acquisition channels for those files. The working assumption is simply that the operator supplies them from legitimate media or downloads available to them, using the normalized filenames documented by the placeholders.

### Project Documentation Cache

Raw documentation for research and validation is acquired by running the docs download helper. Those source materials are inputs to the authored docs, not replacements for them [S1] [S2] [S3] [S4] [S5] [S6].

### Toolkits And Libraries

Optional third-party Amiga-side toolkit material, currently centered on ClassAct 3.3, is acquired with the tracked helper in `assets/libs/`. The archive is intentionally kept after download and the extracted tree is left unpacked so it can be inspected directly [S16] [S17].

### Test Applications

The current first target, `iTidy`, is already staged in the repository under `amiga_apps/itidy1classic/` as committed source plus committed release payload. Its provenance is still tracked through the upstream source archive and Aminet release archive in the source registry [S13] [S15].

### System Fragments

Some placeholders represent narrower runtime fragments rather than full OS media, for example files under `assets/system/`. These should be treated as evidence of a known possible dependency, not as proof that every run already needs them.

## Recommended Acquisition Order

For a fresh machine, the least confusing order is:

1. run the fetch scripts for docs and toolkit material;
2. place local ADFs, ROMs, and any required system fragments into the matching placeholder locations;
3. verify that every supplied file follows the placeholder naming contract exactly;
4. only then start constructing a prepared `sys:` runtime tree for actual `vamos` runs.

This keeps source analysis, copyrighted local payloads, and prepared runtime trees as three separate concerns.

## Working Rule

Do not invent filenames ad hoc when adding local assets. If a placeholder exists, match it. If no placeholder exists but the project truly needs a new non-redistributable asset, add the placeholder first so the inventory remains explicit.
