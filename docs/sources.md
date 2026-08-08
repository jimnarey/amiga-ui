# Sources

This file is the external source registry for the documentation in `docs/`.

Project-authored documentation is authoritative for project-specific decisions. External references are for factual validation, historical behavior, API details, and source provenance.

## Reference Notation

Use numbered inline references in the body text, not per-file source lists.

### Format

- Basic form: `[S<n>]`
- With a granular locator: `[S<n> <locator>]`

Examples:

- `Workbench launches pass a WBStartup message rather than CLI argc/argv [S2 §WBStartup Message ¶1-4].`
- `Vamos uses the -V switch to define volumes [S7 L103-L113].`
- `The 3.2 NDK archive was published as NDK3.2.lha [S1].`

### Locator Rules

Prefer the narrowest locator that a reviewer can verify directly from the cited source.

Use these locator styles:

- `Lx-Ly`
  Use for GitHub file pages and other sources where line numbers are stable and visible.
- `§Heading ¶n`
  Use for prose web pages when the claim lives under a named section.
- `§Heading ¶n-m`
  Use when several consecutive paragraphs under the same heading support the claim.
- `p.n`
  Use for PDFs, books, or scans with stable page numbers.
- `p.n-m`
  Use for a page range.
- `tbl.n`, `fig.n`, `item n`
  Use when the source is best verified through a table, figure, or enumerated item.

### Citation Placement

- Put the reference at the end of the sentence or paragraph it supports.
- If one sentence contains several distinct factual claims from different sources, split the sentence or cite each claim separately.
- If a whole paragraph is derived from one source span, a single citation at the end of the paragraph is acceptable.

### Stability Rules

- Do not renumber existing sources casually.
- Add new sources by appending the next number.
- If a source URL changes materially, add a new source number instead of silently reusing the old one.
- Prefer exact source pages and exact file pages over site home pages.

## Registered Sources

| No. | Title | URL | Typical locator style | Notes |
| --- | --- | --- | --- | --- |
| `S1` | AmigaOS 3.2 NDK archive | https://aminet.net/dev/misc/NDK3.2.lha | `p.n`, archive-internal path, or none | Direct archive fetched into the docs cache. |
| `S2` | Workbench Library | https://wiki.amigaos.net/wiki/Workbench_Library | `§Heading ¶n-m` | Workbench API behavior and startup conventions. |
| `S3` | AmigaOS Manual: Workbench | https://wiki.amigaos.net/wiki/AmigaOS_Manual%3A_Workbench | `§Heading ¶n-m` | General Workbench behavior and concepts. |
| `S4` | AmigaOS Apps Development | https://wiki.amigaos.net/wiki/AmigaOS_Apps_Development | `§Heading ¶n-m` | Development overview and tool links. |
| `S5` | `dos.library` autodocs | https://developer.amigaos3.net/autodocs/dos.library/ | `§Heading ¶n-m` | Detailed DOS API and data model reference. |
| `S6` | Recommended reading for the Amiga Developer | https://developer.amigaos3.net/article/13-recommended-reading-amiga-developer | `§Heading ¶n-m` | Reading-priority and background guidance. |
| `S7` | `vamos` user documentation | https://github.com/jimnarey/amitools/blob/3b57f2052ee76c28bbc5e4256227f62dca7b1c9f/docs/vamos.md | `Lx-Ly` | Commit-pinned GitHub file page for the bootstrap checkout. |
| `S8` | `vamos` library documentation | https://github.com/jimnarey/amitools/blob/3b57f2052ee76c28bbc5e4256227f62dca7b1c9f/docs/vamos-lib.md | `Lx-Ly` | Commit-pinned GitHub file page for library behavior. |
| `S9` | `vamos` helper runner | https://github.com/jimnarey/amitools/blob/3b57f2052ee76c28bbc5e4256227f62dca7b1c9f/test/helper/runner.py | `Lx-Ly` | Useful for tracing and runtime invocation patterns. |
| `S10` | `vamos` sample config | https://github.com/jimnarey/amitools/blob/3b57f2052ee76c28bbc5e4256227f62dca7b1c9f/test/test.vamosrc | `Lx-Ly` | Useful as a configuration reference. |
| `S11` | `iTidy` source README | https://github.com/Kwezza/iTidy/blob/v1/README.md | `Lx-Ly` | Upstream app overview. |
| `S12` | `iTidy` manual | https://github.com/Kwezza/iTidy/blob/v1/docs/manual/iTidy.md | `Lx-Ly` | App behavior and usage details. |
| `S13` | `iTidy` source archive | https://github.com/Kwezza/iTidy/archive/refs/heads/v1.zip | none | Exact source archive used during bootstrap. |
| `S14` | Aminet `iTidy` package page | https://aminet.net/package/util/wb/iTidy | `item n` or named subsection | Metadata for the released binary package. |
| `S15` | Aminet `iTidy` archive | https://aminet.net/util/wb/iTidy.lha | none | Direct binary archive. |
| `S16` | Aminet `classact33` package page | https://aminet.net/package/dev/gui/classact33 | `item n` or named subsection | Metadata and contents listing for ClassAct 3.3. |
| `S17` | Aminet `classact33` archive | https://aminet.net/dev/gui/classact33.lha | none | Direct archive fetched by the helper script. |
