---
name: code-review
description: >
  Perform a structured, depth-controlled review of a diff, PR, or changeset.
  Use whenever asked to review, critique, or check code changes, including
  requests to "review this", "check this PR", or "look over this diff" —
  regardless of how the request is phrased.
---

# Code Review

## Use This Skill When
- Asked to review a diff, pull request, or set of changed files.
- Asked to check, critique, or sanity-check a change before it is committed or merged.
- Asked to compare an implementation against a spec, ticket, or stated intent.

## Goal
Produce a review whose depth is explicit and chosen on purpose, not one whose
depth depends on how the request happened to be phrased or on the model's own
judgment. Depth is a control the requester sets, not an adjective the model
infers.

## Step 0: State The Depth Level
Before writing any assessment, state which depth level this review uses. If
the requester named one, use it. If not, default to `standard`. Do not
silently pick a depth and never say so.

- `triage` — enumerate every changed file. For each file, either flag a real
  issue with evidence, or state "no issue found" in one line. Do not walk
  every hunk individually.
- `standard` — enumerate every changed file and every hunk within it. Each
  hunk gets one entry: a finding, or an explicit "no issue" note. No hunk is
  silently skipped.
- `exhaustive` — as `standard`, plus: read every touched function in full
  (not only the diff context lines), trace at least one real call path into
  and out of each changed function, and check the change against tests that
  exercise it (existing or missing).

State the chosen level and why, in one line, before the findings.

## Step 1: Enumerate Before Assessing
List every changed file and, at `standard`/`exhaustive`, every hunk, before
writing any finding. This list is the coverage contract for the rest of the
review — anything not on it was not reviewed, and that must be stated, not
implied.

## Step 2: Walk And Cite
For each item on the enumeration:
- State the finding, or state that none was found.
- Cite the exact file and line range for every claim. A finding without a
  citation is not a finding.
- Prefer a concrete failure scenario ("this crashes when X is empty") over a
  general concern ("this could be an issue").

## Priority Order
1. Correctness — will this do what it claims to do, on the inputs it will
   actually see?
2. Safety — injection, unchecked input, unsafe deserialization, secrets,
   resource leaks, concurrency hazards.
3. Test coverage — does a change in behavior have a change in tests? Flag
   untested behavior change explicitly; do not assume it's covered.
4. Consistency — does this match the patterns already in the surrounding
   code, or introduce a second way of doing the same thing without reason?
5. Style and naming, last, and only if nothing above needs the words.

Do not lead with style. A review that opens with formatting nitpicks and
buries a real correctness bug is a failed review regardless of what it
eventually mentions.

## Guardrails
- Do not summarize what a diff "generally does" as a substitute for walking
  it. A paragraph of prose about intent is not a review.
- Do not report "looks good" or "no issues" for a file or hunk without
  evidence it was actually read, not skimmed.
- Do not claim a wider scope was checked than actually was — if only the
  diff context was read, not the full file, say so.
- Do not invent an issue to appear thorough. An empty finding at
  `standard`/`exhaustive` ("no issue found") is a valid, complete answer.
- Do not silently expand scope: a review is not the place to redesign an
  approach the requester didn't ask about. Note a design concern once,
  clearly, and move on.
- If a file is generated, vendored, or a lockfile, say so and skip it rather
  than reviewing it line by line.
- If something needed to assess a hunk correctly is missing (the function it
  calls, the type it assumes, the test it should have), say what's missing
  rather than guessing and reviewing the guess.

## Output Format
1. Depth level used, one line.
2. Coverage list: every file (and hunk, if `standard`/`exhaustive`) considered.
3. Findings, most severe first: file:line, what's wrong, concrete failure
   scenario, suggested fix if obvious.
4. Explicit closing line: what was and was not covered, and any remaining risk.
