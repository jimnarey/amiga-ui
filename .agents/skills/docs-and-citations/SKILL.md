---
name: docs-and-citations
description: >
  Write and maintain project documentation using the repo's metadata and
  citation conventions. Use when editing docs, adding sources, or recording
  project decisions.
---

# Docs And Citations

## Use This Skill When
- Editing files under `docs/`.
- Adding or updating sources.
- Turning discussion outcomes into authoritative repo documentation.

## Goal
Keep documentation compact, layered, and verifiable by humans and LLMs.

## Default Rules
- The docs themselves are authoritative for settled project decisions.
- Use YAML front matter consistently.
- Keep one file focused on one concept or one tightly related cluster of concepts.
- Prefer concise, high-signal prose over broad narrative repetition.

## Required Front Matter Pattern
Each documentation file should maintain appropriate metadata such as:
- `title`
- `status`
- `depends_on`
- `citations_used`

## Citation Rules
- Use the project's numbered source IDs from `docs/sources.md`.
- Keep references granular enough to support later validation.
- Add a new source entry before relying on a new external source.
- Distinguish sourced facts from local design decisions.

## Guardrails
- Do not cite transient local bootstrap paths as authoritative sources.
- Do not duplicate large amounts of content across files.
- Do not leave unsourced factual claims in docs that are meant to be authoritative.
- If a point is unresolved, record it as an open question or deferred decision rather than pretending it is settled.

## Key Repo Files
- `docs/sources.md`
- `docs/research/open-questions.md`
- `docs/research/deferred-decisions.md`
