---
title: "External Helpers And Shell-Outs"
status: draft
depends_on:
  - "error-driven-porting.md"
  - "../apps/itidy/dependencies.md"
  - "../runtime/subsystem-stop-rules.md"
citations_used:
  - "S32"
---

# External Helpers And Shell-Outs

Purpose: Define how to triage missing external commands and helper programs.

Needed for:
- Handling feature dependencies such as `LhA` honestly.

Notes:
- This is about helper-command policy, not host package management in general.

## Summary

Some target-app features rely on external commands rather than only on libraries. The current `iTidy` target is the concrete example: backup features search for `LhA` in common locations and then invoke it through `Execute()` [S32 L93-L119] [S32 L162-L195]. That means the agent needs a rule for when to fail, when to defer, and when a host-side substitute is acceptable.

## Classification Rule

Classify a missing external helper as one of:

1. launch blocker
2. core workflow blocker
3. optional feature gate
4. out-of-scope subsystem pressure

Do not treat every missing helper as if it had the same priority.

## Default Policy

### Launch And Main-Window Stages

If the app can still reach launch and main-window milestones without the helper, do not let the helper dominate the current iteration. Record it and defer it.

### Core Workflow Features

If the helper is part of the app's main value, the project should eventually support it honestly rather than pretending the workflow succeeded.

### Optional Features

If the helper only gates an optional feature, the normal answer is:

- document the dependency,
- fail or disable the feature honestly,
- and continue working on earlier blockers.

### Out-Of-Scope Pressure

If supporting the helper would really require broad subsystem emulation or a new platform-integration story outside the project's target class, stop and document that rather than normalizing it as "just another missing command."

## Host-Side Replacement Rule

A host-side replacement for an Amiga-side helper is acceptable only when:

1. the replacement preserves the user-visible meaning of the feature,
2. it does not hide an unrelated missing compatibility layer underneath,
3. and the substitution is documented clearly.

Do not silently replace every unknown Amiga helper command with an unrelated host-side behavior just because it is easy.

## Current Example: `LhA`

For `iTidy`, `LhA` is a good example of an optional-but-real dependency. It matters to backup and restore features, but it is not the app's entire reason for existing [S32 L93-L119] [S32 L162-L195]. That makes it a normal later-phase feature dependency rather than the first thing to fake away or the first thing to block all progress on.
