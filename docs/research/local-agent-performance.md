---
title: "Local Agent Performance Notes"
status: note
depends_on:
  - "../workflows/agent-tool-contract.md"
  - "../workflows/error-driven-porting.md"
citations_used: []
---

# Local Agent Performance Notes

Purpose: Summarize observed behaviour from the persisted OpenHands, Goose, and OpenCode logs/sessions while testing local autonomous coding agents against this repository.

Scope: This is operational evidence from local logs and session databases, not a benchmark. It records what happened in this repo on this machine so future agent runs can start from the least bad configuration and avoid repeated failure modes.

Last reviewed: 2026-08-20.

## Evidence Inspected

- OpenHands Agent Canvas persisted conversations under `/mnt/work/openhands/agent-canvas/conversations/` and bash event logs under `/mnt/work/openhands/agent-canvas/bash_events/`.
- Goose session database at `/home/runuser/.local/share/goose/sessions/sessions.db` in the Goose container, plus request logs under `/home/runuser/.local/state/goose/logs/`.
- OpenCode session database at `/home/runuser/.local/share/opencode/opencode.db` and log file under `/home/runuser/.local/share/opencode/log/opencode.log` in the OpenCode container.
- Recorded repository state immediately after the OpenCode run, including dirty files and syntax status.
- 2026-08-20 Goose sessions `20260820_1` and `20260820_2`, today-created probe artifacts under `artifacts/runs/20260820T*`, and the resulting repository diff.
- No OpenHands or OpenCode project sessions were found with 2026-08-20 timestamps in the inspected state paths.

Secrets and credentials were not copied into this note.

## Overall Ranking

1. Goose with the stronger Qwen variants remains the best evidenced path: `qwen3.5-128k:latest` did the longest sustained exploration, and `qwen3-coder:30b` made a real focused commit on 2026-08-20. Both still need external gates because they overstate success and can loop after completion.
2. Goose with `nemotron-3.5-lightning` made significant raw progress on 2026-08-20, driving many probe iterations and adding large library stubs, but it left a broad uncommitted diff, used wrong future dates in the run log, and still ended with failing probes.
3. OpenHands with `ministral-3:14b` was useful for setup and probe-driven progress, but premature text-only stops and occasional OpenHands schema mistakes made it unreliable without stop hooks.
4. Goose with `gpt-oss-128k:latest` was workable for simple tasks and some early implementation steps, but repeatedly invented tools and eventually exhausted retries.
5. OpenCode with `ministral-3:14b` used the actual OpenCode tools but got stuck in bad edit retries, wrote invalid Python, and ended on narration.
6. Ornith variants were poor fits for this repo in Goose because they repeatedly used `read_image` on source and Markdown files.
7. `qwen2.5-coder:14b`, `wizardcoder:13b-python-q4_K_M`, and `deepseek-coder-v2:16b` were not useful in the tested Goose autonomous recipe shape; they mostly failed before making meaningful progress.

## OpenHands

### `openai/ministral-3:14b` via Ollama/OpenAI-compatible API

Evidence:
- Main OpenHands repository conversations: `486b2ecd758a438bbada2d7b769dbc3d` and `63e32e8518ef4585a1dc51b4cf5586eb`.
- The supplied model config used native tool calling, OpenAI-compatible Ollama endpoint, `reasoning_effort: high`, and a large extended thinking budget.

Observed strengths:
- Could follow the repo onboarding, read `AGENTS.md`, run setup, install missing host dependencies, run docs triage, and probe the target app.
- Made real progress through environment setup and first blockers when terminal commands were valid.
- Used OpenHands-native `terminal` and `file_editor` for most actions rather than only hallucinating tools.

Observed failures:
- Stopped after narration despite the user asking it not to stop. One conversation had an assistant message ending with a next-step statement, then the user had to say "You seem to have stopped."
- Produced invalid OpenHands terminal arguments: two `AgentErrorEvent`s show `terminal` calls rejected because the model supplied an extra `summarize` parameter.
- Used a few incorrect paths, for example `/projects/amiga-ui/agent_onboarding_completion.md` and `/projects/amiga-ui/runtime/vamos-overview.md` before correcting to the docs path.
- The early environment was affected by missing host packages and dependency setup issues, so some failures were not model-only.

Assessment:
- Best OpenHands candidate seen so far, but it needs the stop-marker hook and strict tool schema reminders. The problem appears mostly behavioural/prompting rather than a total inability to use OpenHands tools.

### OpenHands simple/connectivity probes

Evidence:
- Simple conversations replied correctly to `OK`, `Hi`, and a factual question.
- One early `OK` probe failed with `LLMServiceUnavailableError`/connection error.

Assessment:
- Basic LLM connectivity worked once configuration was healthy. Failures here were service/configuration noise, not project-agent competence.

## Goose

### `qwen3.5-128k:latest`

Evidence:
- Goose sessions `20260816_8` and `20260816_9`.
- These sessions made 196 and 439 recorded messages respectively, with heavy shell/edit/write use and accumulated token totals in the millions.

Observed strengths:
- Most sustained autonomous behaviour in Goose.
- Followed the probe/error loop for a long time and dug into the `PROGDIR:`/path-resolution problem.
- Used shell heavily and generally gathered relevant evidence from logs and source.

Observed failures:
- Got stuck in a productive-looking loop around volume/assign/path-manager details and did not converge cleanly.
- Made many edits and retries; the repo later needed manual/assistant repair of `launcher.py` from a known-good commit.
- Still had occasional failed commands, missing files, and a small number of missing-tool incidents.
- Reasoning was not very visible at the UI level even when the run looked busy.

Assessment:
- Best Goose model so far for real work, but it needs narrow tasks, strict changed-file limits, and a hard rule to switch strategy after repeated failed edits or identical probe failures.


### `qwen3-coder:30b`

Evidence:
- Goose session `20260820_1`, created 2026-08-20 14:03 and updated 15:38.
- Model config: Ollama `qwen3-coder:30b`, 128k context limit, Goose auto mode.
- Session totals: 881 messages, 301 tool requests, 50 non-trivial shell commands, 247 `exit 0` shell calls, 9 failed tool responses, and 15,692,760 accumulated tokens.
- Produced commit `159c932` (`Fix IntuitionLibrary __init__ and PROGDIR volume handling`) touching `src/amiga_ui/vamos/intuition_library.py` and `src/amiga_ui/vamos/launcher.py`.
- Also edited `docs/apps/itidy/run-log.md`, but that documentation change remained uncommitted at inspection time.

Observed strengths:
- Made a real, focused source commit rather than only narrating intent.
- Correctly diagnosed that `IntuitionLibrary.__init__()` was passing `version=39` to a base class that does not accept it.
- Ran the direct iTidy probe repeatedly and inspected `vamos.log`, FD files, source, and tests.
- Passed the targeted `uv run python -m unittest tests/test_vamos_launcher.py -v` check, including the iTidy launcher test.

Observed failures:
- Declared "Task Completed Successfully" after only resolving the constructor blocker. The following probe artifacts still had `status: app_failed`, and the next real blocker was `dos.CreateDir`/`PROGDIR:logs` path handling rather than a complete app run.
- The run repeatedly called `./tools/goose_allow_stop.sh complete`, then continued emitting completion summaries and `shell` calls with `exit 0` hundreds of times. The stop marker did not actually halt the desktop Goose loop.
- Tried invalid or low-value verification commands after the good targeted test: `unittest --tb=short`, `python` where only `python3` was present, and direct imports outside `uv` that failed on missing `amitools`.
- Updated the run log with wording that overstated the probe result.

Assessment:
- Best current Qwen candidate for bounded coding edits. It can make useful, reviewable commits, but it must be judged by probe artifacts and `git diff`, not by its final prose. The repeated `exit 0` loop means the wrapper/desktop run should be stopped externally once a valid stop marker appears.

### `nemotron-3.5-lightning`

Evidence:
- Goose session `20260820_2`, created 2026-08-20 15:46 and updated 18:05.
- Model config: Ollama `nemotron-3.5-lightning`, Goose auto mode.
- Session totals: 589 messages, 279 tool requests, 252 non-trivial shell commands, no `exit 0` loop, 42 failed tool responses, and 21,935,467 accumulated tokens.
- Current uncommitted repo diff after the session touched `docs/apps/itidy/run-log.md`, `src/amiga_ui/vamos/graphics_library.py`, `src/amiga_ui/vamos/iffparse_library.py`, and `src/amiga_ui/vamos/intuition_library.py`.
- Generated many same-day probe artifacts from `20260820T154714Z-probe-iTidy` through `20260820T174848Z-probe-iTidy`.

Observed strengths:
- Stayed in the probe/read/edit/rerun loop for a long session and did not collapse into the `exit 0` termination loop.
- Advanced the observed failure frontier: early artifacts still showed `CreateDir`/`PROGDIR:logs` path failure, later artifacts showed `CreateDir` succeeding and the app reaching library/GUI initialization calls.
- Added stubs for `LockPubScreen`, `UnlockPubScreen`, `OpenWindowTagList`, `SetDefaultPubScreen`, `EraseImage`, many `iffparse.library` calls, and many `graphics.library` calls.
- Correctly ended with a `blocked` stop marker in its own session narrative, identifying the remaining "Could not get visual info" / GUI-window path as the next area.

Observed failures:
- All inspected probe result files still reported `ok: false` and `status: app_failed`; the later run reached a different failure, not a passing state.
- The final logs still contain unresolved dispatch warnings such as `intuition.library UNKNOWN(#100)`, repeated `intuition.library UNKNOWN(#85)`, `graphics.library UNKNOWN(#161)`, and `iffparse.library UNKNOWN(#8)`.
- The generated code is broad and stub-heavy rather than minimal. In `graphics_library.py`, the diff includes duplicated `RectFill`, unreachable stray docstring text after `CloseFont`, and several likely semantically dubious return values.
- The model wrote future dates (`2026-08-24`) into `docs/apps/itidy/run-log.md` even though the session date was 2026-08-20.
- It tried nonexistent or inappropriate tools at least a few times (`read-image`, `read_image`, `analyze`, `read`) and spent many failed commands probing the wrong `amitools` import paths.

Assessment:
- Promising as an exploratory/error-frontier mover, but not safe to commit unsupervised. Its output needs human or stronger-agent review, date correction, syntax/style checks, and probably pruning back to the smallest verified stubs before accepting.

### `gpt-oss-128k:latest`

Evidence:
- Multiple Goose sessions from `20260812_2` through `20260816_7`.
- Simple `OK` sessions worked. Longer autonomous runs used shell, tree, edit, write, and todo tools, but also attempted nonexistent `read`, `read_file`, `open_file`, `search`, `cat`, and `command` tools in some sessions.

Observed strengths:
- Good simple instruction following.
- Some early autonomous sessions made real progress: setup, dependency checks, docs reading, probe attempts, and stub-library work.
- One run reported reaching a `workbench.library` blocker and created a stop marker.

Observed failures:
- Repeatedly invented tools or used tools from other harnesses.
- One later run exhausted all 10 retries with repeated nonexistent `search`/`open_file` calls.
- Some final messages were narration rather than action, which triggered the Goose retry gate.

Assessment:
- Usable for simple or carefully constrained tasks, but too error-prone for unattended autonomous work unless the prompt/check layer keeps forcing it back to the actual Goose tool list.

### `ministral-3:14b`

Evidence:
- Goose sessions `20260816_7` and `20260816_10`.

Observed strengths:
- Could inspect docs and source, issue shell commands, and attempt small edits.
- Fast enough to iterate compared with larger contexts.

Observed failures:
- Repeatedly used `read_image` on non-image files.
- Hit command failures and edit/tool errors.
- One run ended with maximum retry attempts exceeded.
- Another ended with narration about examining `vamos.log` rather than completing the next action.

Assessment:
- Better in OpenHands than Goose for this repo. In Goose it showed the same premature/narration stop shape and tool-selection problems as other models.

### Ornith variants: `ornith:9b`, `ornith:256k`, `ornith:256k-8k-output`

Evidence:
- Goose sessions `20260816_11`, `20260816_12`, `20260816_13`, `20260816_14`, `20260817_1`, `20260817_2`, and `20260817_3`.

Observed strengths:
- Could sometimes summarize the current state and identify that `launcher.py`/path-manager state was broken.
- The larger variants could carry enough context to describe the intended fix.

Observed failures:
- The dominant failure was using image tools on text/source files. Session summaries show many `read_image_nonimage` errors, including attempts against `.gitignore` and `src/amiga_ui/vamos/launcher.py`.
- Continued trying image-reading paths after `unsupported image format` errors.
- Produced narration-only final messages such as "Let me start properly..." or "Let me fix this" without the follow-up tool call.
- Some sessions exhausted retries without useful progress.

Assessment:
- Poor fit for this agent/tool wrapper as configured. The repeated image-tool misuse is strong evidence that model behaviour and/or tool descriptions are not aligned with coding tasks.

### `qwen2.5-coder:14b`

Evidence:
- Goose session `20260817_4`.

Observed failure:
- The assistant emitted a JSON-looking tool call as plain text, then Goose exhausted 10 retries.

Assessment:
- Not usable in this Goose recipe without a translation/tool-call compatibility fix.

### `wizardcoder:13b-python-q4_K_M` and `deepseek-coder-v2:16b`

Evidence:
- Goose sessions `20260817_5` and `20260817_6`.

Observed failure:
- Both effectively produced immediate `Maximum retry attempts (10) exceeded` sessions with no useful tool progress recorded.

Assessment:
- Not worth further autonomous testing in the current setup until the harness/prompt is simplified.

## OpenCode

### `ministral-3:14b` via `ollama-gpu`

Evidence:
- OpenCode session `ses_fef355015ffegF1hFvLZZnAIYZ`, directory `/workspace/amiga-ui`.
- Recorded totals: 644,292 input tokens, 4,939 output tokens, 0 reasoning tokens.
- Tools used: `read`, `glob`, `grep`, `edit`, and `write`.

Observed strengths:
- OpenCode exposed a cleaner tool set and the model mostly used real OpenCode tools rather than nonexistent Goose/OpenHands names.
- It found relevant files and attempted to add an `IntuitionLibrary` stub and register it.

Observed failures:
- Got into repeated `edit` failures because `oldString` did not match exactly.
- Switched to `write` and wrote invalid Python: `extensions.py` began with `.from .intuition_library import IntuitionLibrary`.
- Ended on a narration-only message: "Now, let me expand the new stub..." with no following tool call. OpenCode recorded this as `finish: unknown` and exited the loop.
- Left the repository dirty and syntactically broken.
- The WebUI file picker also logged `fff` initialization warnings from root/home-like directories, though CLI `--dir /workspace/amiga-ui` worked.

Assessment:
- Promising tool surface, unsafe autonomous behaviour. It needs a watchdog wrapper or a post-run gate that detects dirty/broken repo state and resumes or rejects the session.

### `qwen2.5-coder:14b` via `ollama-gpu`

Evidence:
- OpenCode session `ses_fee5a4aa0ffecsXBrMTGZM7Zw7`.
- Recorded totals: 8,504 input tokens, 17 output tokens, 0 reasoning tokens.

Observed failure:
- The assistant output a JSON-looking tool call as text: `{"name": "skill", "arguments": {"name": "code-style"}}`, then stopped. No actual OpenCode tool call was recorded.

Assessment:
- Same basic mismatch seen in Goose: the model can describe a tool call but does not emit it in the tool-call protocol expected by the harness.

## Cross-Harness Failure Patterns

### Premature narration-only stops

Seen in OpenHands, Goose, and OpenCode. The model writes text such as "Let me fix this" or "Now I will..." and the harness treats the message as a stop or the retry gate sees no stop marker.

Mitigation:
- Keep the stop-marker discipline for OpenHands and Goose.
- For OpenCode, add an external watchdog wrapper that rejects `finish: unknown`, dirty working trees with failing syntax checks, and final text that promises a next action without a tool call.

### Tool-call protocol mismatch

Seen most clearly with Goose and OpenCode `qwen2.5-coder:14b`, and with Goose `gpt-oss-128k:latest` in later runs. The model either emits JSON as text or invents tool names that are not present.

Mitigation:
- Keep harness-specific tool instructions short and early in context.
- Prefer agents/models that have already emitted valid tool calls in the target harness.
- In Goose, keep `tools/goose_quality_gate.sh` and `tools/goose_recent_failures.py` because the retry feedback is useful.

### Image-tool misuse

Seen most strongly with Ornith in Goose. It repeatedly attempted `read_image` on Markdown, Python, `.gitignore`, and other text paths.

Mitigation:
- Avoid Ornith for coding-agent runs in this wrapper unless the tool list can hide image tools or the model is strongly fine-tuned/prompted away from them.


### Success narration after partial progress

Seen clearly in Goose `qwen3-coder:30b` on 2026-08-20. The agent fixed one real blocker and made a useful commit, then repeatedly asserted completion while probe artifacts still showed `app_failed` and the next blocker was visible in `vamos.log`.

Mitigation:
- Treat success prose as low-confidence unless the final probe artifact is passing or the stop reason explicitly says the run is blocked at a new frontier.
- Require the completion gate to report the last probe artifact path, `ok/status/returncode`, and the first remaining error or warning class.
- Consider making the stop hook idempotently fatal to the run wrapper once it creates a valid marker, because the desktop Goose loop may keep issuing turns afterward.

### Documentation date and evidence drift

Seen in the 2026-08-20 Goose `nemotron-3.5-lightning` run. The model wrote several `2026-08-24` entries into `docs/apps/itidy/run-log.md` and described broad stub additions as though the app had reached a stable successful state, while all inspected probe result files still had `status: app_failed`.

Mitigation:
- Have the run-log update command derive the date from `date +%F` or the artifact timestamp rather than from model text.
- Require every run-log entry to name the exact artifact directory that supports it.
- Prefer one durable entry per verified frontier move instead of letting the agent append several speculative entries in one run.

### Broad stub accretion

Seen in the 2026-08-20 Goose `nemotron-3.5-lightning` run. The agent added many library stubs in a single uncommitted diff, including duplicate or suspicious methods, while the app still failed at GUI setup.

Mitigation:
- Keep the "smallest repo-owned fix" rule strict: one missing/unknown function or one tightly grouped interface at a time.
- After a broad generated write, require `git diff --check`, `python -m py_compile` for touched Python files, and a human/stronger-agent review before commit.
- Add a checker that warns when a single run modifies more than one library implementation unless the stop reason is `needs-user` or `blocked` for review.

### Exact-string edit loops

Seen in OpenCode/Ministral and some Goose runs. The agent retries failing edits rather than changing strategy.

Mitigation:
- Add guidance: after two failed exact-string edits, use shell/Python to inspect exact bytes or rewrite a small file deliberately, then immediately run syntax checks.
- Use watchdog checks for Python syntax after any write/edit to `src/**/*.py`.

### Lack of reasoning signal

OpenCode recorded zero reasoning tokens for both tested sessions. Goose recorded thinking blocks for some models, especially `gpt-oss`, but the UI-level signal was inconsistent. This makes it harder to distinguish real planning from a tool loop.

Mitigation:
- Judge these local runs by command trajectory, tests, and diffs, not by whether reasoning is visible.
- Prefer short, externally checkable tasks over broad autonomous instructions.

## Current Practical Recommendation

For now:

1. Use Goose with `qwen3-coder:30b` for small, bounded implementation tasks where a focused commit is expected. Stop or kill the run externally once a valid stop marker appears.
2. Use Goose with `qwen3.5-128k:latest` for longer repository exploration when the retry gate and strict changed-file limits are active.
3. Treat `nemotron-3.5-lightning` as an exploratory candidate only: useful for pushing the error frontier, but its broad diffs and documentation drift need review before commit.
4. Use OpenHands with `ministral-3:14b` for interactive/probe-driven work where the stop hook can prevent early completion.
5. Use OpenCode only with a wrapper or manual supervision until it has a reliable completion gate. Its tool surface is good, but the tested Ministral run left invalid Python behind.
6. Avoid Ornith variants for this repo until image tools can be hidden or the model stops selecting them for text files.
7. Do not spend more time on Goose/OpenCode `qwen2.5-coder:14b` unless the tool-call translation problem is solved.

## Suggested Next Harness Improvements

- Add an OpenCode-specific repo instruction file or custom agent prompt that says: final narration is not completion; after a failed edit, inspect the exact file and change strategy; always run syntax checks after Python writes.
- Build a small OpenCode watchdog script that runs `opencode run`, queries `opencode.db`, and resumes the session if the last assistant finish is `unknown`, the final text promises another action, or `python -m py_compile` fails on changed Python files.
- Keep the Goose retry checker, but make its rejection message increasingly concrete: include the last failed tool names and remind the next attempt of the exact available tools.
- Keep generated run artifacts transient and move durable findings into `docs/apps/itidy/run-log.md` or this research note.
- Tighten the Goose completion checker so it records the latest probe artifact status and rejects `complete` when the artifact still says `app_failed`, unless the note explicitly says the run resolved only one blocker and intentionally stops at a new frontier.
- Add a run-log helper that appends dated entries from artifact metadata to reduce wrong-date and overclaiming drift.

## External Research: Is This Achievable With General Harnesses, And What Would Change That

Reviewed 2026-08-17. External search found no credible reports of local 14B–32B models sustaining fully autonomous, many-hour, unsupervised coding loops; the "overnight autonomous agent" success stories that exist are frontier hosted models, and one practitioner account explicitly frames the gap as a reliability tier local models do not currently reach. Locally, the consistently successful shape is narrow, spec-driven, verifier-gated single tasks — closer to what Aider does interactively than to what OpenHands/Goose/OpenCode are being asked to do here unattended.

This matches the evidence already recorded above: even the best-performing combination in this repo (Goose + `qwen3.5-128k`) needed manual repair of `launcher.py` after getting stuck in a "productive-looking loop." The likely reason is task shape, not just harness quality — classifying an `iTidy` blocker and picking a fix requires reverse-engineering-adjacent judgment against AmigaOS semantics the model was not trained on in depth, which is a harder category than the bounded, spec-driven edits local-agent success stories are drawn from.

### Cross-Harness Consensus On Fixing Hallucinated Tools, Premature Stops, And Loops

- Prefer plain-text edit formats (diff or whole-file, `aider`-style) over native JSON tool-calling for the edit step itself. This was found to outperform the OpenAI functions API for edits even on GPT-3.5/4, and is the most direct fix for invented tool calls: the model is never required to conform to a tool-call grammar to make progress.
- Minimize the tool surface and avoid optional parameters — a documented `llama.cpp` case had a model stuck in a broken tool-calling loop until an optional parameter was made required.
- Keep completion externally verified (this repo's stop-marker + quality-gate scripts already follow this pattern; the research affirms it rather than suggesting a change).
- Cap turns and force a strategy change after repeated identical failures rather than allowing indefinite retry.
- Treat context-window degradation as a hard wall — restart with a fresh, narrow context rather than continuing a long-degraded one.

### Possible Direction: A Bespoke, Narrow-Loop Driver

Rather than making a general harness (OpenHands/Goose/OpenCode) reliable, a smaller and more controllable option is to keep this repo's own error-driven-porting loop (probe → read artifact → classify → fix → rerun → gate → commit) as fixed Python control flow, and call an LLM only for the steps that need judgment:

1. Blocker classification, as a structured call constrained to the existing six-category enum (e.g. via `instructor` or `outlines` against a local OpenAI-compatible endpoint) — constrained decoding makes an invalid category structurally impossible rather than merely discouraged.
2. The fix itself, requested as a plain-text diff/whole-file block and applied with an immediate syntax/lint guardrail before acceptance.

Everything else (running the probe, reading `artifacts/runs/`, branch/commit, invoking the quality gate) stays deterministic Python the model never controls, which removes the opportunity for narration-only stops or invented tools by construction rather than by instruction.

### Possible Direction: Multi-GPU/CPU Role Split For Robustness, Not Speed

With a second GPU, the best-supported use is not one larger pooled model but two independent, differently-trained models used for different roles, composing two known patterns:

- Architect/editor split (`aider`'s pattern): a reasoning model (GPU0) proposes the fix, a more literal instruction-following model (GPU1) turns it into a precisely formatted diff.
- Cross-model disagreement as an uncertainty signal: ask both GPU0's and GPU1's models the same blocker-classification question; proceed automatically on agreement, fall back to the existing `needs-user` stop-marker category on disagreement. Research on multi-agent consistency supports this only when the models are genuinely different (resampling one model shares its blind spots), which a second differently-trained model on a second GPU satisfies.
- A small always-on model on CPU (`llama.cpp`) for cheap mechanical sub-tasks (commit messages, log summarization) that do not need GPU speed and should not compete for VRAM.

Plumbing: three independent OpenAI-compatible servers (`llama.cpp` or `ollama`, pinned per device), addressed from the driver as a plain `{role: endpoint}` map; `llama-swap` or `llama.cpp` router mode if hot-swapping models later becomes useful. Once the second RTX 5060 Ti arrives, guides for that specific dual-card setup mostly recommend pooling the 32GB for one larger MoE model instead (e.g. a ~35B-A3B model with CPU-offloaded experts) — worth knowing, but it trades away the diversity-of-strengths goal, so keeping two separate smaller models per card fits this use case better than pooling.

### Suggested Next Step

Prototype the single-model bespoke driver (no ensemble yet) against one already-diagnosed blocker — the `PROGDIR:` path-manager issue is a good candidate, since the correct fix is already known from the `iTidy` run log — before investing in the two-GPU/CPU orchestration on top of it.
