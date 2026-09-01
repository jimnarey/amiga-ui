---
title: "ADF Sets"
status: draft
depends_on:
  - "index.md"
citations_used:
  - "S7"
---

# ADF Sets

Purpose: Document which AmigaOS disk sets are present and what each disk contributes.

Needed for:
- Choosing the smallest useful runtime/reference set for a task.

## Summary

The repository currently recognizes four AmigaOS ADF families under `assets/adf/`:

- 2.1
- 3.0
- 3.1
- 3.1.4

The project keeps these as named reference media, not as direct `vamos` runtime mounts. `Vamos` maps host directories as volumes rather than mounting ADF files directly [S7 L100-L117].

## Naming Convention

The naming scheme is normalized and lower-case:

- real disks use names such as `amigaos_3.1_workbench.adf`
- placeholder markers use the same base name with a leading underscore and `.placeholder`, for example `_amigaos_3.1_workbench.adf.placeholder`

This makes it easy to talk about the expected asset set without requiring the copyrighted payload itself to live in source control.

## Disk Families Present

### AmigaOS 2.1

The recognized 2.1 set is:

- `workbench`
- `install`
- `extras`
- `fonts`
- `locale`

This set mainly serves as a lower-baseline reference for pre-3.x behavior and file layout.

### AmigaOS 3.0

The recognized 3.0 set is:

- `workbench`
- `install`
- `extras`
- `fonts`
- `locale`
- `storage`

This is useful as the earliest default in-scope Workbench 3.x family.

### AmigaOS 3.1

The recognized 3.1 set is:

- `workbench`
- `install`
- `extras`
- `fonts`
- `locale`
- `storage`

This is the most important baseline family for the project's current scope because Workbench 3.0 and 3.1 are the default behavioral target in the architecture docs.

### AmigaOS 3.1.4

The recognized 3.1.4 family is larger:

- `workbench`
- `install`
- `extras`
- `fonts`
- `locale`
- `storage`
- `modules`
- `update` as `3.1.4.1`

This family is kept as a later 3.x comparison set rather than as the project's default contract.

## Intended Use

At the current stage, these ADFs support three main jobs:

1. reference comparison when a Workbench behavior differs across releases,
2. source material for building prepared runtime trees outside the raw `assets/adf/` directory,
3. later emulator-based validation when `vamos` behavior needs checking against a fuller environment.

## Minimal Practical Guidance

If a task needs the smallest likely-useful default reference set, prefer:

1. AmigaOS 3.1 first,
2. AmigaOS 3.0 when earlier 3.x comparison matters,
3. AmigaOS 3.1.4 when later-library or later-media differences matter,
4. AmigaOS 2.1 only when intentionally probing older pre-3.x behavior.

## Extraction

After the operator has supplied local `.adf` files beside the placeholders, extract them into ignored local reference trees with:

```bash
uv run python tools/extract_adfs.py --force
```

The extractor uses `amitools`/`xdftool` in read-only mode and writes per-image trees under `assets/extracted/adf/<adf-stem>/`. `xdftool unpack` preserves Amiga filesystem metadata in sidecar files such as `.xdfmeta`, `.blkdev`, and boot-code output where applicable. These extracted trees are for source comparison and runtime-tree construction; they are not source-controlled project assets and should not be treated as the canonical runtime layout.
