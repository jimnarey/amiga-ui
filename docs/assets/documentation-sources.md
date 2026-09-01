---
title: "Documentation Sources"
status: draft
depends_on:
  - "index.md"
citations_used:
  - "S1"
  - "S2"
  - "S3"
  - "S4"
  - "S5"
  - "S6"
  - "S24"
  - "S26"
  - "S27"
  - "S28"
  - "S36"
  - "S46"
  - "S47"
  - "S50"
  - "S52"
  - "S54"
---

# Documentation Sources

Purpose: Record which upstream documentation sets were fetched and how they should be used.

Needed for:
- Turning raw documents into project-owned markdown summaries.

## Summary

The `assets/docs/` area is the raw documentation cache used to support the project-authored docs in `docs/`. It is deliberately not the primary reading surface. The human- and model-facing documentation lives under `docs/`, while `assets/docs/` holds fetched upstream material that can be inspected when a project summary needs to be validated or expanded.

## Current Upstream Documentation Families

The download helper currently fetches four kinds of upstream material:

- the AmigaOS 3.2 NDK archive [S1]
- selected AmigaOS wiki pages for Workbench, Intuition, icons, IFF, tags, libraries, and app development [S2] [S3] [S4]
- selected AmigaOS 3 Developer pages, including AutoDoc indexes and function pages for the libraries/devices most likely to block Workbench GUI applications [S5] [S6]
- the helper scripts at `assets/docs/download_required_docs.sh` and `assets/docs/fetch_autodocs.py`

## Local Layout

The current local subdirectories are:

- `assets/docs/ndk/`
- `assets/docs/amigaos-wiki/`
- `assets/docs/amigaos3-developer/`
- `assets/docs/amigaos3-developer/autodocs/<library-or-device>/`

Their contents are fetched raw material, not project-owned polished summaries.

## Why These Sources Matter

Each family serves a different role:

- `ndk/`
  Canonical headers, examples, and low-level structure definitions.
- `amigaos-wiki/`
  Higher-level conceptual docs such as Workbench behavior and development overviews.
- `amigaos3-developer/`
  API reference and curated supporting reading. The `autodocs/` subdirectory is the local source used by `uv run python tools/generate_api_index.py` when function pages have been fetched.

This split is what makes the current docs strategy workable for small-context models: narrow project pages in `docs/`, deeper source material in `assets/docs/`.

## Source-Control Rule

The committed contract here is the download scripts and generation commands, not the fetched payload. The raw downloaded files, extracted NDK tree, fetched AutoDocs, and generated API index are local cache material that may be regenerated.

## Usage Rule

Use the materials under `assets/docs/` to:

1. verify specific API or structure claims,
2. inspect original headers and examples,
3. support new project-authored summaries,
4. generate `assets/generated/api-index.json` and `assets/generated/api-index.md` with `uv run python tools/generate_api_index.py`.

Do not treat the raw cache as the authoritative place to write project decisions. Those belong in `docs/`.
