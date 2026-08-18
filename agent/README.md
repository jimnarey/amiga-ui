# agent/

A bespoke, narrow-loop driver for this repo's error-driven-porting loop,
built on [PydanticAI](https://pydantic.dev/docs/ai/overview/). See
`docs/research/local-agent-performance.md` for why this exists: OpenHands,
Goose, and OpenCode sessions against this repo repeatedly hit hallucinated
tools, premature narration-only stops, and unproductive loops, and the
research behind this package points at giving the model less control, not
more.

## Design

The LLM is called for exactly two narrow, validated judgment calls:

1. **Classify** the current probe blocker into one of the categories from
   `docs/workflows/error-driven-porting.md`.
2. **Propose a fix**, as a plain unified diff rather than a tool call.

Everything else — running the probe, applying the diff, running the syntax
guardrail, running the quality gate, writing the run log, committing, and
deciding when to stop — is deterministic Python in this package. The model
is never in control of the loop, so it cannot narrate instead of acting or
invent a tool that doesn't exist: those failure modes require the model to
be driving, and here it isn't.

### The category restriction (important, and non-obvious)

`docs/workflows/error-driven-porting.md`'s six-category taxonomy is a
human/agent *triage vocabulary* — it is not something `src/amiga_ui/cli.py`
computes. The launcher's actual restricted output
(`ProbeClassification.status` in `_classify_probe_outcome`) is a different,
narrower set: `completed`, `missing_asset`, `timeout`, `missing_library`,
`path_setup_failed`, `vamos_error`, `app_failed`. Three of the six docs
categories map onto a status the launcher already resolves for certain;
three (struct/message translation, GUI/requester/layout, out-of-scope
hardware) have no code-level detector at all and collapse into the same
`app_failed`/`vamos_error`/`timeout` catch-all.

`agent/blockers.py` routes off the launcher's real status, not the docs
taxonomy directly:

- For a status the launcher already resolves (`missing_asset`,
  `path_setup_failed`, `missing_library`), the category is assigned
  deterministically — **no model call happens at all**.
- For an ambiguous status (`app_failed`, `vamos_error`, `timeout`), the
  classifier is called, but its `output_type` is a closed Pydantic
  `Literal`, and `agent/llm.py` additionally registers an `output_validator`
  that rejects (via `ModelRetry`) any category outside the subset that's
  actually plausible for that specific status — a structural restriction,
  not a prompted one. See `tests/test_agent_driver.py`'s
  `ClassifierRestrictionTests` for this being exercised directly, and
  `tests/test_agent_blockers.py`'s `LauncherStatusSetDriftGuardTests` for a
  guard against the launcher's status set drifting out from under this
  routing table unnoticed.

### Determining success

Three separate, independently-checked questions, deliberately not collapsed
into one model opinion:

1. **Did the fix help?** `ProbeResult.signature` (the status plus whatever
   distinguishing detail the launcher captured) before and after must
   differ. Plain Python, no LLM. This is the same coarse standard
   `docs/apps/itidy/run-log.md` entries already use by hand.
2. **Is it good enough to commit?** `agent/gate.py` shells out to
   `tools/lib/quality_checks.sh` — the exact pre-commit/unittest/GUI-smoke/
   branch-hygiene gate already shared with the OpenHands and Goose
   harnesses. Not reimplemented here.
3. **Should the run stop, and how should that be legible afterward?**
   `agent/gate.py` writes the same `complete`/`blocked`/`needs-user` marker
   vocabulary as `tools/openhands_allow_stop.sh` and
   `tools/goose_allow_stop.sh`, via the new `tools/bespoke_agent_allow_stop.sh`
   and this driver's own `.agent/state/` directory.

A failed fix attempt is retried once (`MAX_ATTEMPTS_PER_BLOCKER = 2` total),
then escalates to `needs-user` rather than looping indefinitely.

## Running it

```bash
uv sync --group agent --group dev
uv run python -m agent amiga_apps/itidy1classic/binary/extracted/iTidy
```

Both the classifier and fixer default to `qwen3.5-128k` on
`localhost:11434` (Ollama's default). Point them at a different
endpoint/model with `--classifier-endpoint host:port`/`--classifier-model`
and the `--fixer-*` equivalents — this is the seam where a second model on a
second GPU, or a CPU-hosted model, plugs in later without changing anything
else in this package.

It runs exactly one unit of work (one blocker) and exits, matching the
"solve one blocker, commit, exit" shape — call it again from an external
loop to continue.

## Testing

```bash
uv run python -m unittest tests.test_agent_blockers tests.test_agent_driver
```

Uses `pydantic_ai.models.test.TestModel` for the LLM calls and mocks every
repo side effect (probe runs, git, the quality gate, the run log), so the
suite never touches the real working tree or requires a live local model
server.

## Not yet implemented

- Cross-model agreement checking (ask a second, differently-trained model
  the same classification question; escalate on disagreement rather than
  proceeding on one model's say-so) — the design this package is meant to
  grow into once a second GPU is available, per
  `docs/research/local-agent-performance.md`.
- Branch creation. This package intentionally never creates, switches, or
  merges branches — `tools/lib/quality_checks.sh`'s branch-hygiene check
  already refuses to pass on `main` or a dirty `development`, so being on
  the right feature branch first is a precondition the caller satisfies.
