---
name: committing
description: >
  Prepare safe commits and clear commit messages for this repository. Use when
  the user asks for a commit or when evaluating whether the current changes are
  ready to commit.
---

# Committing

## Use This Skill When
- The user asks you to create a commit.
- You need to decide whether the working tree is ready to commit.
- You need to write a commit message for the current changes.

## Goal
Create commits at the right time which adhere to the standards required in this project.

## Commit Rules
- Commit each time a distinct problem has been solved, for example implementation of a single missing Amiga OS function.
- Inspect `git status` before committing.
- Review the diff for the files you plan to include.
- Do not include unrelated user changes unless the user clearly wants them included.
- Do not revert or discard user changes to make committing easier.
- Do not amend an existing commit unless the user explicitly asks for it.
- Prefer non-interactive git commands.

## Commit Selection Workflow
1. Check the working tree.
2. Identify which files belong to the requested change.
3. Exclude unrelated modifications.
4. If the change boundary is ambiguous, stop and ask rather than guessing.
5. Commit only the intended files.

## Commit Message Style
- Use a short imperative subject line.
- Keep the subject specific to the actual change.
- Add a body other than if the commit is truly trivial
- Commit bodies should summarise the changes, unless simple and obvious from the code
- Any decisions on implementation approach should be explained, other than in cases where there was only one plausible option
- Implications for future design decisions and other work should be noted
- Possible, future improvements to the implementation should be noted where relevant

## Good Subject Examples
- `Add in-process vamos launcher integration tests`
- `Move Xvfb management into Python`
- `Refactor probe result handling in cli`

## Avoid
- Vague subjects like `updates` or `fix stuff`
- Bundling unrelated changes into one commit
- Claiming broader verification than was actually performed
