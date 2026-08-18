"""Pydantic models exchanged with the LLM agents.

Kept deliberately small. ``ProposedFix`` carries a unified diff as plain
text rather than a tool call -- see docs/research/local-agent-performance.md's
"External Research" section: plain-text edit formats have proven more
reliable than native function-calling for local/weaker models, which is
exactly the model tier this project targets.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field

from .blockers import BlockerCategory


class BlockerClassification(BaseModel):
    category: BlockerCategory
    blocker_summary: str = Field(description="One sentence: what actually failed and where")
    evidence_lines: list[str] = Field(
        default_factory=list,
        description="Exact lines quoted from the probe's vamos.log/stderr that support this",
    )


class ProposedFix(BaseModel):
    target_files: list[str] = Field(description="Repo-relative paths this diff touches")
    diff: str = Field(description="A unified diff (git-apply compatible), not a tool call")
    rationale: str
    predicted_next_signal: str = Field(
        description="What the *next* probe's status/detail should look like if this fix works"
    )


@dataclass(frozen=True)
class ClassifierDeps:
    """Restricts BlockerClassification.category to what's plausible for the
    current probe status, and grounds evidence_lines against real log text.
    Both are enforced by classifier_agent's output_validators (agent/llm.py)
    -- not just prompted, structurally rejected on mismatch.

    ``source_text`` defaults to "" so tests that only care about the
    category restriction don't need to supply it; production code (see
    agent/driver.py) always passes the real log excerpt, and an empty
    source_text disables the grounding check entirely (nothing to check
    against) rather than rejecting everything.
    """

    allowed_categories: tuple[BlockerCategory, ...]
    source_text: str = ""
