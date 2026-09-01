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

Notes:
- This document records a local project policy, not an externally sourced fact.

## Branch Roles

The repository has two long-lived branches:

- `main`
- `development`

`main` is the protected history branch. Autonomous agents should not develop directly on it and should not merge work into it as part of routine iteration.

`development` is the integration branch for accepted incremental work. Autonomous agents should start from `development` when it exists and the user has not requested a different branch, but should still do feature work on a separate short-lived branch.

## Feature Branch Rule

Each distinct task should use its own branch created from `development`. Typical names are:

- `feature/<short-topic>`
- `fix/<short-topic>`
- `docs/<short-topic>`

Do not commit implementation work directly to `main`. Do not commit implementation work directly to `development` either, except for rare repository-maintenance operations that are explicitly intended to update the integration branch itself.

Treat one coherent blocker, fix, or decision as the normal maximum scope for one feature branch. If a blocker has been solved, verified, documented, and merged into `development`, the next blocker should start on a fresh branch created from the updated `development` branch rather than continuing on the old feature branch.

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

Routine autonomous work should merge into `development`, not into `main`.

Meeting the merge conditions is not merely permission to merge later. For routine autonomous work, merge into `development` is the normal completion step once those conditions are satisfied, unless:

- the user explicitly asked to leave the branch unmerged,
- a merge conflict or branch-state problem needs human input,
- or the work is intentionally being left in a draft or handoff state.

If none of those exceptions apply, do not stop at "the branch is ready." Merge it into `development`.

## Branch Retention

Do not delete branches after merge. The project wants to retain feature branches as an audit trail of how individual compatibility features or fixes were developed.

## Practical Agent Rule

At the start of a fresh autonomous session:

1. ensure the repo is on `development` when that branch exists and the user has not requested a different branch;
2. create or switch to a feature branch before making code changes;
3. keep one coherent blocker or decision per feature branch;
4. run the normal quality checks before attempting to finish the task;
5. commit the completed blocker-level change on the feature branch;
6. merge that feature branch into `development` when the branch meets the merge conditions above;
7. leave the feature branch in place after merge;
8. start the next blocker from a fresh branch created from the updated `development` branch.

Typical blocker-to-blocker sequence:

```bash
git checkout development
git checkout -b fix/<first-blocker>
# implement, verify, document, commit
git checkout development
git merge --no-ff fix/<first-blocker>
git checkout -b fix/<next-blocker>
```

For a concrete repository example of a blocker-sized change that was completed and integrated, inspect commit `c097fbb` in `main` history (`Add minimal icon.library override`).
