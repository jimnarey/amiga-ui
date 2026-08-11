---
title: "Fake And Deferred Implementations"
status: draft
depends_on:
  - "error-driven-porting.md"
  - "../runtime/subsystem-stop-rules.md"
  - "../host-gui/translation-obligations.md"
citations_used:
  - "S8"
---

# Fake And Deferred Implementations

Purpose: Define when temporary fakes are acceptable and when they are the wrong shape of progress.

Needed for:
- Avoiding misleading compatibility wins.
- Keeping temporary shortcuts disciplined.

Depends on:
- `error-driven-porting.md`
- `../runtime/subsystem-stop-rules.md`
- `../host-gui/translation-obligations.md`

Status: Draft.

Notes:
- This file covers project policy, not just `vamos` capability.

## Summary

`Vamos` library handling can mix Python `vamos` libraries, original Amiga libraries, and fake libraries [S8 L18-L32] [S8 L40-L55]. That flexibility is useful for diagnosis, but it can also tempt the project into claiming progress by faking away the very behavior that should be implemented honestly.

## The Main Rule

Do not fake success for a behavior that is currently a real correctness obligation.

In particular, do not use a fake implementation to bypass:

- Workbench launch semantics that the app actively depends on
- visible UI interactions that should be translated into host UI behavior
- data/results that should come from the user's real interaction
- subsystem boundaries that should instead trigger an honest stop

## Acceptable Temporary Fakes

A temporary fake is acceptable only when all of the following are true:

1. it is exposing the next real blocker rather than hiding it,
2. it is not pretending a required visible interaction already works,
3. it is narrow enough to explain in one sentence,
4. it is documented as temporary,
5. and it is not the new de facto long-term behavior.

## Unacceptable Fakes

Do not treat these as valid default progress:

- a fake requester result instead of a translated dialog
- a fake window-open success while no host window exists
- a fake helper-command success that skips a real workflow result
- a fake subsystem response when the honest outcome should be "out of scope"
- a fake library result that suppresses the actual next missing semantic behavior

## Defer Instead Of Faking

If a feature is real but not yet worth implementing, the better move is often to defer it explicitly. That means:

- classify it as later-phase,
- record the dependency,
- fail honestly when it is actually reached,
- and keep earlier milestones focused.

Deferral is healthier than a fake when the feature is:

- optional,
- not currently launch-blocking,
- or only relevant after the main workflow already works.

## Working Rule

Use a fake only as a narrow diagnostic tool. Use deferral as the normal answer for nonessential later features. Use real implementation for current correctness obligations.
