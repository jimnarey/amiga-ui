# pyright: reportMissingImports = none
# This module imports the optional "agent" dependency group (pydantic-ai,
# see pyproject.toml); the pragma keeps pyright green on the canonical
# `uv sync --group dev` bootstrap where that group is not installed. It is
# a no-op once the group is present.
"""The deterministic control loop.

LLM agents are called as functions for exactly two narrow judgment calls --
classification and fix-proposal -- and never decide when to stop, retry, or
commit. That decision is made here, by plain Python, using three separate
checks that are deliberately kept separate rather than collapsed into one
model opinion:

1. Did the fix help at all? ``ProbeResult.signature`` before and after must
   differ -- the same coarse standard docs/apps/itidy/run-log.md entries
   already use by hand ("advances startup to graphics.library"), just made
   mechanical. No LLM involvement.
2. Is it good enough to commit? ``gate.quality_gate_passes()`` -- the exact
   pre-commit/unittest/smoke-test/branch-hygiene gate from
   ``tools/lib/quality_checks.sh``, reused rather than reimplemented.
3. Should the run stop, and how should a human read that state afterward?
   ``gate.write_stop_marker(...)`` -- the same complete/blocked/needs-user
   vocabulary, written in this driver's own namespace.

See docs/research/local-agent-performance.md's "Possible Direction: A
Bespoke, Narrow-Loop Driver" for the design rationale.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic_ai import Agent
from pydantic_ai.exceptions import AgentRunError

from . import gate, git_ops, patch, probe, run_log
from .blockers import ambiguous_categories
from .models import BlockerClassification, ClassifierDeps, ProposedFix

MAX_ATTEMPTS_PER_BLOCKER = 2

Outcome = Literal["advanced", "no_blocker", "blocked", "needs_user"]


def _progress(message: str) -> None:
    """Prints a driver-level progress line, flushed immediately.

    Local reasoning models can take a minute or more per call (qwen3.5-128k
    has been observed taking 20-90+ seconds even for a trivial prompt) --
    without this, the driver goes completely silent for that whole window
    and a running process is indistinguishable from a hung one. flush=True
    matters here specifically because output is often redirected to a file
    or pipe rather than a tty, where Python's default buffering would
    otherwise hold lines back until the buffer fills or the process exits.
    """

    print(f"[agent] {message}", flush=True)


@dataclass
class BlockerAgents:
    classifier: Agent[ClassifierDeps, BlockerClassification]
    fixer: Agent[None, ProposedFix]


def run_one_blocker(target_binary: str, agents: BlockerAgents, *, app: str = "itidy") -> Outcome:
    _progress(f"probing {target_binary} ...")
    before = probe.run_probe(target_binary)
    _progress(f"probe status: {before.status}")

    if before.status == "completed":
        _progress("no blocker -- probe completed cleanly")
        return "no_blocker"

    try:
        return _handle_blocker(target_binary, before, agents, app)
    except AgentRunError as exc:
        # A model call itself failed outright -- a connection error, or the
        # model exhausting its output-retry budget without ever producing a
        # valid classification/fix (see agent/llm.py's output_validator).
        # That's meaningfully different from "the fix didn't help": there's
        # nothing to revert and nothing more to learn by retrying here, so
        # escalate to a human rather than crash the whole run.
        gate.write_stop_marker("needs-user", f"LLM call failed: {exc}")
        return "needs_user"


def _handle_blocker(target_binary: str, before: probe.ProbeResult, agents: BlockerAgents, app: str) -> Outcome:
    classification = _classify(before, agents.classifier)
    _progress(f"classified as {classification.category}: {classification.blocker_summary}")

    if classification.category == "out_of_scope_hardware_or_emulation":
        gate.write_stop_marker("blocked", classification.blocker_summary)
        _progress("out of scope -- stopping with a 'blocked' marker")
        return "blocked"

    for attempt in range(1, MAX_ATTEMPTS_PER_BLOCKER + 1):
        _progress(f"attempt {attempt}/{MAX_ATTEMPTS_PER_BLOCKER}: asking the fixer model for a diff ...")
        fix = agents.fixer.run_sync(_fix_prompt(classification, before)).output
        _progress(f"fixer proposed changes to {fix.target_files}; applying ...")

        if not patch.apply_diff(fix.diff):
            _progress("diff did not apply -- trying again")
            continue
        if not patch.syntax_ok(fix.target_files):
            _progress("syntax check failed -- reverting and trying again")
            patch.revert_diff(fix.diff)
            continue

        _progress("diff applied and syntax-checked; re-probing to see if it actually helped ...")
        after = probe.run_probe(target_binary)

        if after.signature == before.signature:
            _progress(f"no progress ({after.signature} unchanged) -- reverting and trying again")
            patch.revert_diff(fix.diff)
            continue

        _progress(f"progress: {before.signature} -> {after.signature}; recording and running the quality gate ...")
        run_log_path = run_log.append_run_log_entry(
            app,
            title=classification.blocker_summary,
            observed=f"{before.signature} -> {after.signature}",
            change=fix.rationale,
            next_step=f"predicted: {fix.predicted_next_signal}",
        )

        if not gate.quality_gate_passes():
            gate.write_stop_marker("needs-user", "fix advanced the probe but failed the quality gate")
            _progress("quality gate failed -- stopping with a 'needs-user' marker")
            return "needs_user"

        git_ops.commit(
            f"Advance past {before.signature}",
            paths=[*fix.target_files, str(run_log_path.relative_to(probe.PROJECT_ROOT))],
        )
        gate.write_stop_marker("complete", f"advanced past {before.signature}")
        _progress("committed and marked complete")
        return "advanced"

    gate.write_stop_marker("needs-user", f"{MAX_ATTEMPTS_PER_BLOCKER} fix attempts failed on: {before.signature}")
    _progress(f"all {MAX_ATTEMPTS_PER_BLOCKER} attempts failed -- stopping with a 'needs-user' marker")
    return "needs_user"


def _classify(
    result: probe.ProbeResult, classifier: Agent[ClassifierDeps, BlockerClassification]
) -> BlockerClassification:
    category = result.category
    if category is not None:
        # The launcher already told us for certain -- no model call, no risk
        # of an invented category, see agent/blockers.py.
        _progress(f"status {result.status!r} already implies {category} -- skipping the classifier model")
        return BlockerClassification(
            category=category,
            blocker_summary=result.details.get("diagnostic_summary", result.status),
            evidence_lines=[],
        )

    allowed = ambiguous_categories(result.status)
    _progress(f"status {result.status!r} is ambiguous -- asking the classifier model (allowed: {allowed}) ...")
    log_excerpt = result.read_log_excerpt()
    return classifier.run_sync(
        _classification_prompt(result, log_excerpt),
        deps=ClassifierDeps(allowed_categories=allowed, source_text=log_excerpt),
    ).output


def _log_section(log_excerpt: str) -> str:
    return log_excerpt if log_excerpt else "(no log output was captured for this run)"


def _classification_prompt(result: probe.ProbeResult, log_excerpt: str) -> str:
    return (
        f"Probe status: {result.status}\n"
        f"Details: {result.details}\n"
        f"\n{_log_section(log_excerpt)}\n\n"
        "Classify the blocker using only what's actually shown above."
    )


def _fix_prompt(classification: BlockerClassification, result: probe.ProbeResult) -> str:
    return (
        f"Category: {classification.category}\n"
        f"Summary: {classification.blocker_summary}\n"
        f"Evidence: {classification.evidence_lines}\n"
        f"Probe details: {result.details}\n"
        f"\n{_log_section(result.read_log_excerpt())}\n\n"
        "Propose the smallest fix."
    )
