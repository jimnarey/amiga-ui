---
title: "ROM Sets"
status: draft
depends_on:
  - "index.md"
citations_used:
  - "S7"
  - "S8"
---

# ROM Sets

Purpose: Document the Kickstart ROM files present in the tree and why they matter.

Needed for:
- Reference comparisons and later emulator-based validation.

## Summary

The `assets/roms/` directory names a small set of Kickstart ROM references by operating-system version and machine family. Their current role is limited: they are useful for comparison and later fuller-emulation checks, but they are not the main prerequisite for the present `vamos`-based workflow. `Vamos` is an API-level emulator and can run binaries without needing a real Kickstart ROM when the needed library behavior is supplied through its runtime model [S8 L9-L15]. It is also explicitly not a full-system emulator [S7 L16-L17].

## Naming Convention

The normalized naming scheme is:

- `kickstart_<version>_<machine>.rom` for local payloads
- `_kickstart_<version>_<machine>.rom.placeholder` for the committed expected-name marker

This mirrors the ADF placeholder system and keeps the repo's expectations stable even when the copyrighted ROM payload is absent.

## ROM Families Present

The current named ROM references are:

- `kickstart_2.0_a500plus.rom`
- `kickstart_2.0_a600.rom`
- `kickstart_3.0_a1200.rom`
- `kickstart_3.1_a600.rom`
- `kickstart_3.1_a1200.rom`
- `kickstart_3.1.4_a1200.rom`

## Why They Are Kept

These ROM references are mainly useful for:

1. model-specific comparison when a behavior looks tied to system generation,
2. later validation in a fuller emulator environment,
3. documenting which ROM families the operator has decided to stage early rather than chasing them piecemeal later.

## What They Are Not Used For

At the current stage, the ROM set should not be mistaken for:

- a direct input to the standard `vamos` run path,
- a guarantee that the project is booting full Amiga desktop sessions,
- or a reason to widen scope toward full-system emulation.

The default workflow remains API-level execution under `vamos`, with ROMs reserved for comparison and later validation.
