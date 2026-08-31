# pyright: reportMissingImports = none
# This module imports the optional "agent" dependency group (pydantic-ai,
# see pyproject.toml); the pragma keeps pyright green on the canonical
# `uv sync --group dev` bootstrap where that group is not installed. It is
# a no-op once the group is present.
"""LLM Agent definitions: classification and fix-proposal, plus local model
wiring.

Deliberately just two narrow structured calls. The driver in
agent/driver.py owns all control flow -- these agents never decide when to
stop, retry, or commit, which is the core design choice behind this whole
package (see docs/research/local-agent-performance.md's "Possible
Direction: A Bespoke, Narrow-Loop Driver").
"""

from __future__ import annotations

from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from .models import BlockerClassification, ClassifierDeps, ProposedFix

# $OLLAMA_URL is a sound, correctly-GPU-pointed environment convention now
# (fixed at the shell level) -- this no longer needs to second-guess it, so
# the default is just Ollama's own plain default.
DEFAULT_ENDPOINT = "localhost:11434"


def local_model(model_name: str, *, endpoint: str = DEFAULT_ENDPOINT) -> OpenAIChatModel:
    """An OpenAI-compatible local model at `host:port`.

    Point ``endpoint`` at whichever GPU/CPU-pinned server is serving a given
    role once splitting roles across multiple models -- nothing else in
    this module needs to change.
    """

    return OpenAIChatModel(
        model_name,
        provider=OpenAIProvider(base_url=f"http://{endpoint}/v1", api_key="local"),
    )


def _normalize_whitespace(text: str) -> str:
    """Collapses runs of whitespace so a quoted line still matches after
    minor re-wrapping/indentation differences, without being so loose it
    accepts a paraphrase."""

    return " ".join(text.split())


# Substrings that, if present in the classifier's own quoted evidence, prove
# the failure is a Python exception/traceback pointing at code this repo (or
# its amitools dependency) owns -- i.e. a fixable implementation bug, never
# a hardware/emulation-boundary issue. Directly motivated by two real
# observed misclassifications: a TypeError from a bad super().__init__() call
# in src/amiga_ui/vamos/intuition_library.py, and a VamosInternalError about
# memory bookkeeping in amitools' ExecLibrary.py, both called
# "out_of_scope_hardware_or_emulation" despite being ordinary code bugs.
_PYTHON_BUG_MARKERS = (
    "Traceback (most recent call last):",
    "src/amiga_ui/",
    "amitools/",
)


def build_classifier_agent(model: Model | str) -> Agent[ClassifierDeps, BlockerClassification]:
    agent: Agent[ClassifierDeps, BlockerClassification] = Agent(
        model,
        output_type=BlockerClassification,
        deps_type=ClassifierDeps,
        # pydantic-ai's default output-retry budget is 1: a local model that
        # misses the allowed-category restriction once has no room left to
        # self-correct, and the ModelRetry below turns into an uncaught
        # UnexpectedModelBehavior. Give it a few more tries -- the driver
        # (agent/driver.py) still treats an eventual failure as a graceful
        # needs-user escalation, not a crash, but there's no reason to give
        # up after a single miss.
        retries={"output": 3},
        system_prompt=(
            "You classify the first meaningful failure from an amiga-ui probe run. "
            "You will be given the actual log output -- quote real lines from it as "
            "evidence_lines, never paraphrase or invent a line that isn't there. "
            "You will be told exactly which categories are plausible for this "
            "failure -- pick one of those, never invent another.\n\n"
            "out_of_scope_hardware_or_emulation means ONLY: direct hardware register "
            "access, custom-chip/CIA timing, full desktop/session emulation, or "
            "audio/printer/serial/MIDI/joystick handling as the CENTRAL feature being "
            "exercised. A Python exception or traceback -- even one that looks "
            "low-level, mentions memory addresses, or comes from deep inside a "
            "library implementation -- is a bug in this repo's own code or its "
            "amitools dependency, not a hardware/emulation-boundary issue. Prefer "
            "missing_library_or_function or struct_or_message_translation for those, "
            "even when the error message sounds technical or unfamiliar."
        ),
    )

    @agent.output_validator
    def restrict_to_allowed_categories(
        ctx: RunContext[ClassifierDeps], output: BlockerClassification
    ) -> BlockerClassification:
        if output.category not in ctx.deps.allowed_categories:
            raise ModelRetry("category must be one of: " + ", ".join(ctx.deps.allowed_categories))
        return output

    @agent.output_validator
    def require_grounded_evidence(
        ctx: RunContext[ClassifierDeps], output: BlockerClassification
    ) -> BlockerClassification:
        # Directly motivated by a real observed failure: with nothing
        # concrete in the prompt to quote, the model confidently invented a
        # plausible-sounding but entirely fabricated "JSON validation error"
        # that didn't correspond to the actual failure at all. Now that the
        # driver always supplies real log text (agent/driver.py), enforce
        # that evidence_lines are actually drawn from it rather than trusting
        # the model's word for it -- the same "verify, don't self-report"
        # principle this whole package is built on, applied to evidence too.
        if not ctx.deps.source_text:
            return output
        if not output.evidence_lines:
            raise ModelRetry("Quote at least one real line from the provided log output as evidence_lines.")
        normalized_source = _normalize_whitespace(ctx.deps.source_text)
        unfound = [line for line in output.evidence_lines if _normalize_whitespace(line) not in normalized_source]
        if unfound:
            raise ModelRetry(
                "These evidence_lines do not appear in the log output you were given -- quote real "
                f"lines verbatim, don't paraphrase or invent text: {unfound}"
            )
        return output

    @agent.output_validator
    def reject_out_of_scope_for_python_bugs(
        ctx: RunContext[ClassifierDeps], output: BlockerClassification
    ) -> BlockerClassification:
        # A structural backstop on top of the system-prompt guidance above:
        # if the model's own (now-grounded) evidence contains a Python
        # traceback or a path into this repo's/amitools' source, it cannot
        # simultaneously be "out of scope hardware/emulation" -- that's a
        # direct contradiction, not a judgment call. See _PYTHON_BUG_MARKERS.
        if output.category != "out_of_scope_hardware_or_emulation":
            return output
        combined = " ".join(output.evidence_lines)
        hits = [marker for marker in _PYTHON_BUG_MARKERS if marker in combined]
        if hits:
            raise ModelRetry(
                "Your evidence_lines contain "
                f"{hits} -- that's a Python exception/traceback in this repo's own code or its "
                "amitools dependency, which is a fixable implementation bug, not "
                "out_of_scope_hardware_or_emulation. Reclassify using missing_library_or_function or "
                "struct_or_message_translation instead."
            )
        return output

    return agent


def build_fixer_agent(model: Model | str) -> Agent[None, ProposedFix]:
    return Agent(
        model,
        output_type=ProposedFix,
        system_prompt=(
            "You propose the smallest possible fix for one classified blocker, "
            "as a unified diff suitable for `git apply`. Do not bundle unrelated "
            "changes. State what you predict the *next* probe run will show if "
            "this fix works."
        ),
    )
