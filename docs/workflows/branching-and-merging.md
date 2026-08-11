---
title: "Branching And Merging"
status: draft
depends_on:
  - "bootstrap-environment.md"
  - "regression-checks.md"
citations_used: []
---

# Branching And Merging

Purpose: Define the repository branch strategy and the conditions for committing and merging work.

Needed for:
- Safe autonomous development.
- Predictable review and rollback points.

Depends on:
- `bootstrap-environment.md`
- `regression-checks.md`

Status: Draft.

Notes:
- This document records a local project policy, not an externally sourced fact.

## Branch Roles

The repository has two long-lived branches:

- `main`
- `development`

`main` is the protected history branch. OpenHands should not develop directly on it and should not merge work into it as part of routine iteration.

`development` is the integration branch for accepted incremental work. OpenHands should start from `development`, but should still do feature work on a separate short-lived branch.

## Feature Branch Rule

Each distinct task should use its own branch created from `development`. Typical names are:

- `feature/<short-topic>`
- `fix/<short-topic>`
- `docs/<short-topic>`

Do not commit implementation work directly to `main`. Do not commit implementation work directly to `development` either, except for rare repository-maintenance operations that are explicitly intended to update the integration branch itself.

## Commit Conditions

It is acceptable to commit a branch when all of the following are true:

1. The branch addresses one coherent problem or decision.
2. The working tree changes are limited to that problem.
3. The relevant tests and checks for the change exist.
4. The relevant tests and checks have been run and have passed.
5. Any required documentation updates have been made.

For this repository, the normal minimum quality bar is:

- `pre-commit` passes
- the relevant unit tests pass
- any affected smoke or probe checks have been run when they are the highest-value verification for the change

## Merge Conditions

A feature branch may be merged into `development` only when all of the following are true:

1. The branch has a clear purpose and history.
2. `pre-commit run --all-files` passes.
3. The relevant tests pass.
4. New or changed behavior is covered by tests where sensible.
5. Any required docs updates are already on the branch.
6. The resulting state is still within project scope.

Routine OpenHands work should merge into `development`, not into `main`.

## Branch Retention

Do not delete branches after merge. The project wants to retain feature branches as an audit trail of how individual compatibility features or fixes were developed.

## Practical OpenHands Rule

At the start of a fresh OpenHands session:

1. ensure the repo is on `development`;
2. create or switch to a feature branch before making code changes;
3. run the normal quality checks before attempting to finish the task;
4. merge only into `development` when the branch meets the merge conditions above.
