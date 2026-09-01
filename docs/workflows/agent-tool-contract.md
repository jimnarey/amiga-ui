---
title: "Agent Tool Contract"
status: draft
depends_on: []
citations_used: []
---

# Agent Tool Contract

Purpose: Define the tool-use and safety rules that apply to every autonomous coding harness working in this repository, so each harness's onboarding material only has to describe its own tool names and invocation mechanics instead of restating the rules themselves.

Needed for:
- Keeping autonomous sessions behaviorally consistent without maintaining the same rules in multiple places.
- Giving a single place to fix a rule when a harness misbehaves, instead of patching one harness's copy and leaving the others stale.

## Tool Discipline

- Use only tools that the current harness actually exposes in this session. Do not invent tool names.
- Treat `find`, `rg`, `grep`, `git grep`, `sed`, `cat`, and `ls` as shell commands to run through whatever shell/command tool the harness provides, not as standalone tools.
- If a tool call fails because the tool does not exist or the arguments are invalid, do not repeat the same call. Choose a valid tool, or inspect files through shell commands instead.
- If a command-line program is missing from the container, install the small required package with passwordless `sudo` rather than inventing a tool or repeatedly working around the missing dependency.
- If a shell command fails, inspect the full stdout, stderr, exit code, and any available command/job output before retrying. Do not rerun the same failing command with cosmetic changes unless the inspected error explains why that should work.

## Protected Directories

Do not create, edit, overwrite, delete, chmod, or chown `.git/`, `.deprecated/`, `.codex/`, `.config/`, `.local/`, `.cache/`, or other tool, VCS, editor, credential, or agent configuration directories unless the user explicitly asks for that exact config change.

`.deprecated/` contains preserved legacy OpenHands, Goose, and bespoke local-agent material. It is not active repository guidance, and agents should ignore it unless the user explicitly asks about legacy harness behavior.

## Image Tool Contract

- Use image-reading tools only for paths ending in `.png`, `.jpg`, `.jpeg`, `.gif`, or `.webp`.
- Never use image tools for source code, Markdown, JSON, YAML, TOML, plain text, logs, directories, paths without an image extension, or unknown file types.
- Treat non-image paths as text by default, and inspect them with the harness's text/file-viewing tool, or with `sed`, `cat`, `rg`, `find`, or `git grep`.
- If an image tool reports `unsupported image format`, retry immediately with a text inspection method instead of repeating the image tool call.

## Narration And Stop Discipline

Some harnesses can treat a text-only response as the end of an autonomous run, even when the text is only narration such as "now I'll fix that next."

- Do not emit narration-only turns while more work remains.
- If you write "next I will do X", the tool call for `X` must be in the same response.
- Only end an autonomous run intentionally after the requested work is complete, blocked by a real external dependency, or needs a user decision.
- DSH does not currently use a repo-local stop-marker helper in this repository. Legacy OpenHands, Goose, and bespoke-agent stop-marker helpers are preserved under `.deprecated/` for reference only.

## Where Harness Specifics Live

This file intentionally does not cover tool names or invocation mechanics, since those differ per harness:

- DSH: [dsh.md](dsh.md)
- Legacy OpenHands: `.deprecated/openhands/`
- Legacy Goose: `.deprecated/goose/`
