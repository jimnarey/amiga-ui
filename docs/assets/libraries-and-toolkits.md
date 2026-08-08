---
title: "Libraries And Toolkits"
status: draft
depends_on:
  - "index.md"
citations_used:
  - "S16"
  - "S17"
---

# Libraries And Toolkits

Purpose: Document add-on libraries and GUI toolkits fetched outside the base OS sets.

Needed for:
- Understanding external GUI dependencies in target apps.

Depends on:
- `index.md`

Status: Draft.

Notes:
- Start with ClassAct 3.3 and expand only when new app dependencies require it.

## Summary

This directory is for non-base dependencies that are neither part of the default AmigaOS disk families nor part of the project's own Python environment. At the moment the key entry is ClassAct 3.3, retained because add-on GUI toolkit dependencies are conditionally in scope when a real target app needs them [S16].

## Current Toolkit: ClassAct 3.3

The project currently includes support material for the `classact33` Aminet package [S16] [S17]. The local layout distinguishes three things:

- `assets/libs/download_classact33.sh`
  The committed helper script that fetches and extracts the archive.
- `assets/libs/classact33.lha.placeholder`
  The committed expected-name marker for the archive.
- `assets/libs/classact33/`
  The extracted local reference tree when the archive has been downloaded and unpacked.

## Why ClassAct Is Kept

ClassAct is not part of the project's minimum Workbench GUI contract. It is kept because:

- some real Amiga GUI applications may depend on it,
- its presence lets the project inspect file layout and toolkit payloads early,
- and it gives a documented path for later widening scope without first scrambling for the package.

That makes it preparatory infrastructure rather than an unconditional promise of broad toolkit support from day one.

## Local Tree Shape

When extracted, the ClassAct tree includes:

- `Classes/`
- `Prefs/`
- various gadget and image classes
- associated `.info` metadata and preference tools

This should be treated as a reference/install tree for dependency analysis, not as evidence that the project has already implemented ClassAct compatibility.

## Source-Control Rule

The helper script and placeholder file are the stable committed interface. The archive and extracted payload may exist locally, but users should not assume they are present in source control by default.

## Expansion Rule

Do not add more third-party toolkit material here speculatively. Expand this directory only when:

1. a real target application needs the dependency,
2. the package source can be documented cleanly,
3. the placeholder or helper-script story remains clear.
