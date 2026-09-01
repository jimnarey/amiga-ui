# Goose Bootstrap

Goose-specific files for running autonomous work in this repository with
[Goose](https://block.github.io/goose/). For the project itself, its rules,
and its development loop, see `AGENTS.md` and `docs/` — this directory only
covers Goose's own invocation mechanics, which live nowhere else in the repo.

- `.goosehints` (repo root) — loaded automatically into every Goose session
  and points at the real documentation.
- `recipes/autonomous-dev.yaml` — the recipe for unattended `goose run`
  invocations.

## Prerequisites

```bash
uv sync --group dev
./check_dependencies.sh   # Xvfb and 7z on the host
git checkout development  # or a feature branch created from it
```

## Running the recipe

Unattended execution needs `GOOSE_MODE=auto` — without it, Goose pauses for
interactive tool-call approval and a headless run just hangs:

```bash
GOOSE_MODE=auto goose run \
  --recipe .goose/recipes/autonomous-dev.yaml \
  --max-turns 500
```

Both recipe parameters are optional and default to the `iTidy` target:

```bash
GOOSE_MODE=auto goose run \
  --recipe .goose/recipes/autonomous-dev.yaml \
  --params target_binary=amiga_apps/itidy1classic/binary/extracted/iTidy \
  --params focus="the requester layout blocker noted in the latest run-log entry" \
  --max-turns 500
```

`--max-turns` bounds a single attempt (default 1000 if omitted); raise it for
a longer unattended run. Avoid setting a low `--max-tool-repetitions` for normal
autonomous work: it is a circuit breaker, so Goose stops when the limit is hit
instead of making the model choose another approach. Use it only as an emergency
runaway-loop guard, and keep the value high enough that ordinary repeated shell
inspection is not interrupted. Validate the recipe after editing it:

```bash
goose recipe validate .goose/recipes/autonomous-dev.yaml
```

## How the completion gate works

Goose has no pre/post-tool-call hook system, so this repo can't enforce
things the way its OpenHands bootstrap does (`.openhands/hooks/`). Instead
the recipe uses Goose's `retry` field as the closest equivalent:

1. The agent must call `./tools/goose_allow_stop.sh {complete|blocked|needs-user} "<note>"`
   as its last action before ending a turn — see the recipe's `instructions`
   for the full contract.
2. Before `goose run` is allowed to finish, `tools/goose_quality_gate.sh`
   runs as the recipe's `retry.checks` command. It requires a fresh, valid
   marker on the current branch:
   - `complete` additionally runs `pre-commit`, the unit tests, and the GUI
     smoke test, and checks branch hygiene (no direct work left uncommitted
     on `main`/`development`).
   - `blocked` / `needs-user` are accepted without the quality gate.
   - No marker at all (e.g. the agent stopped with narration instead of
     acting, or ran out of turns mid-task) fails the check.
3. On failure, Goose resets the agent's message history and restarts the
   recipe from `prompt` — the git working tree is untouched, so the next
   attempt resumes from the same repo state. The rejection reason is written
   to `.goose/state/last-rejection.md`, along with recent failed tool calls
   when Goose's session database is available; the recipe instructs the agent
   to read that file first on the next attempt.
4. `retry.max_retries` (10) bounds how many restarts this buys before
   `goose run` gives up and returns control with a failure — treat that as
   the point needing human attention.

`.goose/state/` holds only this transient marker/rejection state; it is
gitignored.

## Recurring or resumable runs

Because progress is anchored in git branches and `docs/apps/*/run-log.md`,
not in Goose session state, re-running the same command later naturally
resumes where the last run left off. For scheduled/recurring execution
instead of a single long-lived run, use:

```bash
goose schedule add \
  --id amiga-ui-autonomous-dev \
  --cron "0 * * * *" \
  --recipe-source .goose/recipes/autonomous-dev.yaml
```
