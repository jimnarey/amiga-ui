---
title: "Agent Tool Contract"
status: draft
depends_on: []
citations_used: []
---

# Agent Tool Contract

Purpose: Define the tool-use and safety rules that apply to every autonomous coding harness working in this repository, so each harness's onboarding material only has to describe its own tool names and invocation mechanics instead of restating the rules themselves.

Needed for:
- Keeping OpenHands and Goose sessions behaviorally consistent without maintaining the same rules in multiple places.
- Giving a single place to fix a rule when a harness misbehaves, instead of patching one harness's copy and leaving the others stale.

## Tool Discipline

- Use only tools that the current harness actually exposes in this session. Do not invent tool names.
- Treat `find`, `rg`, `grep`, `git grep`, `sed`, `cat`, and `ls` as shell commands to run through whatever shell/command tool the harness provides, not as standalone tools.
- If a tool call fails because the tool does not exist or the arguments are invalid, do not repeat the same call. Choose a valid tool, or inspect files through shell commands instead.
- If a command-line program is missing from the container, install the small required package with passwordless `sudo` rather than inventing a tool or repeatedly working around the missing dependency.

## Protected Directories

Do not create, edit, overwrite, delete, chmod, or chown `.git/`, `.goose/`, `.openhands/`, `.codex/`, `.config/`, `.local/`, `.cache/`, or other tool, VCS, editor, credential, or agent configuration directories unless the user explicitly asks for that exact config change.

## Image Tool Contract

- Use image-reading tools only for paths ending in `.png`, `.jpg`, `.jpeg`, `.gif`, or `.webp`.
- Never use image tools for source code, Markdown, JSON, YAML, TOML, plain text, logs, directories, paths without an image extension, or unknown file types.
- Treat non-image paths as text by default, and inspect them with the harness's text/file-viewing tool, or with `sed`, `cat`, `rg`, `find`, or `git grep`.
- If an image tool reports `unsupported image format`, retry immediately with a text inspection method instead of repeating the image tool call.

## Narration And Stop Discipline

Some harnesses (OpenHands in particular) can treat a text-only response as the end of an autonomous run, even when the text is only narration such as "now I'll fix that next."

- Do not emit narration-only turns while more work remains.
- If you write "next I will do X", the tool call for `X` must be in the same response.
- Only end an autonomous run intentionally after creating the harness's stop marker: `./tools/openhands_allow_stop.sh` for OpenHands, `./tools/goose_allow_stop.sh` for Goose. Both take `complete`, `needs-user`, or `blocked`, plus an optional short note.
- Create the marker as the last action before an intentional final response — not earlier, and not as a promise to do it later.

## Where Harness Specifics Live

This file intentionally does not cover tool *names* or invocation mechanics, since those differ per harness:

- OpenHands: `.openhands/onboarding.md`
- Goose: `.goosehints` and `.goose/README.md`
