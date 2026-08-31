# pyright: reportMissingImports = none
# pyright: reportPossiblyUnboundVariable = none
# The imports below require the optional "agent" dependency group
# (pydantic-ai, see pyproject.toml). These pragmas keep pyright green on
# the canonical `uv sync --group dev` bootstrap, where that group is not
# installed; they are no-ops once the group is present. The runtime guard
# below skips the suite instead of failing to import.
"""Tests for agent/driver.py's control flow -- in particular, how it decides
whether a unit of work succeeded. Uses pydantic-ai's TestModel so no live
local model server is required; all repo side effects (probe runs, git,
the quality gate, the run log) are mocked so this suite never touches the
real working tree.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

try:
    from pydantic_ai.models.test import TestModel

    from agent import driver
    from agent import gate as gate_module
    from agent import git_ops as git_ops_module
    from agent import patch as patch_module
    from agent import probe as probe_module
    from agent import run_log as run_log_module
    from agent.driver import BlockerAgents, run_one_blocker
    from agent.llm import build_classifier_agent, build_fixer_agent
    from agent.models import ClassifierDeps
    from agent.probe import ProbeResult

    _AGENT_GROUP_AVAILABLE = True
except ImportError:
    _AGENT_GROUP_AVAILABLE = False

_AGENT_GROUP_SKIP_REASON = "agent dependency group is not installed; run: uv sync --group agent --group dev"


def _result(status: str, **details: object) -> ProbeResult:
    return ProbeResult(status=status, ok=status == "completed", artifact_root=Path("."), details=details)


def _classifier_test_model(category: str, evidence_lines: list[str] | None = None) -> TestModel:
    return TestModel(
        custom_output_args={
            "category": category,
            "blocker_summary": "stub blocker",
            "evidence_lines": evidence_lines or [],
        }
    )


def _fixer_test_model(diff: str = "diff --git a/x b/x\n") -> TestModel:
    return TestModel(
        custom_output_args={
            "target_files": ["src/amiga_ui/vamos/stub.py"],
            "diff": diff,
            "rationale": "stub rationale",
            "predicted_next_signal": "stub prediction",
        }
    )


@unittest.skipUnless(_AGENT_GROUP_AVAILABLE, _AGENT_GROUP_SKIP_REASON)
class ClassifierRestrictionTests(unittest.TestCase):
    """The output_validator restriction is the second, structural layer on
    top of agent/blockers.py's routing -- confirm it actually holds even
    when the model insists on an out-of-set category."""

    def test_model_cannot_escape_the_allowed_category_subset(self) -> None:
        from pydantic_ai.exceptions import UnexpectedModelBehavior

        agent = build_classifier_agent(_classifier_test_model("gui_requester_or_layout"))
        with self.assertRaises(UnexpectedModelBehavior):
            agent.run_sync(
                "classify",
                deps=ClassifierDeps(allowed_categories=("host_dependency_or_setup",)),
            )

    def test_model_output_accepted_when_within_the_allowed_subset(self) -> None:
        agent = build_classifier_agent(_classifier_test_model("gui_requester_or_layout"))
        result = agent.run_sync(
            "classify",
            deps=ClassifierDeps(allowed_categories=("gui_requester_or_layout", "struct_or_message_translation")),
        )
        self.assertEqual(result.output.category, "gui_requester_or_layout")


@unittest.skipUnless(_AGENT_GROUP_AVAILABLE, _AGENT_GROUP_SKIP_REASON)
class EvidenceGroundingTests(unittest.TestCase):
    """Reproduces, and guards against, a real observed failure: with no real
    log text in the prompt, the classifier confidently invented a plausible-
    sounding but entirely fabricated justification. Now that the driver
    always supplies real log text (agent/driver.py's _classification_prompt),
    evidence_lines must actually be drawn from it."""

    SOURCE_TEXT = "--- vamos.log (last 4000 chars) ---\nTypeError: object.__init__() takes exactly one argument"

    def test_fabricated_evidence_is_rejected(self) -> None:
        from pydantic_ai.exceptions import UnexpectedModelBehavior

        agent = build_classifier_agent(
            _classifier_test_model("struct_or_message_translation", evidence_lines=["this line was never in the log"])
        )
        with self.assertRaises(UnexpectedModelBehavior):
            agent.run_sync(
                "classify",
                deps=ClassifierDeps(
                    allowed_categories=("struct_or_message_translation",), source_text=self.SOURCE_TEXT
                ),
            )

    def test_missing_evidence_is_rejected_when_source_text_is_available(self) -> None:
        from pydantic_ai.exceptions import UnexpectedModelBehavior

        agent = build_classifier_agent(_classifier_test_model("struct_or_message_translation", evidence_lines=[]))
        with self.assertRaises(UnexpectedModelBehavior):
            agent.run_sync(
                "classify",
                deps=ClassifierDeps(
                    allowed_categories=("struct_or_message_translation",), source_text=self.SOURCE_TEXT
                ),
            )

    def test_evidence_actually_present_in_source_text_is_accepted(self) -> None:
        agent = build_classifier_agent(
            _classifier_test_model(
                "struct_or_message_translation",
                evidence_lines=["TypeError: object.__init__() takes exactly one argument"],
            )
        )
        result = agent.run_sync(
            "classify",
            deps=ClassifierDeps(allowed_categories=("struct_or_message_translation",), source_text=self.SOURCE_TEXT),
        )
        self.assertEqual(result.output.category, "struct_or_message_translation")

    def test_empty_source_text_disables_grounding_entirely(self) -> None:
        # ClassifierDeps.source_text defaults to "" -- existing callers
        # (and ClassifierRestrictionTests above) that don't care about
        # grounding shouldn't be forced to supply it.
        agent = build_classifier_agent(
            _classifier_test_model("struct_or_message_translation", evidence_lines=["anything at all"])
        )
        result = agent.run_sync(
            "classify",
            deps=ClassifierDeps(allowed_categories=("struct_or_message_translation",)),
        )
        self.assertEqual(result.output.category, "struct_or_message_translation")


@unittest.skipUnless(_AGENT_GROUP_AVAILABLE, _AGENT_GROUP_SKIP_REASON)
class OutOfScopeForPythonBugsTests(unittest.TestCase):
    """Guards against the second real observed misclassification: a Python
    traceback pointing at this repo's own code (or amitools) called
    "out_of_scope_hardware_or_emulation" twice in real runs -- a TypeError
    in src/amiga_ui/vamos/intuition_library.py, and a VamosInternalError in
    amitools' ExecLibrary.py. Neither is remotely a hardware/emulation
    boundary issue per docs/architecture/compatibility-scope.md."""

    SOURCE_TEXT = (
        "--- vamos.log (last 4000 chars) ---\n"
        'File "/mnt/work/projects/amiga-ui/src/amiga_ui/vamos/intuition_library.py", line 9\n'
        "TypeError: object.__init__() takes exactly one argument"
    )

    def test_out_of_scope_is_rejected_when_evidence_shows_a_repo_traceback(self) -> None:
        from pydantic_ai.exceptions import UnexpectedModelBehavior

        agent = build_classifier_agent(
            _classifier_test_model(
                "out_of_scope_hardware_or_emulation",
                evidence_lines=["src/amiga_ui/vamos/intuition_library.py"],
            )
        )
        with self.assertRaises(UnexpectedModelBehavior):
            agent.run_sync(
                "classify",
                deps=ClassifierDeps(
                    allowed_categories=("out_of_scope_hardware_or_emulation", "missing_library_or_function"),
                    source_text=self.SOURCE_TEXT,
                ),
            )

    def test_missing_library_or_function_with_the_same_evidence_is_accepted(self) -> None:
        # Same repo-traceback evidence, but a category that isn't a direct
        # contradiction -- the guardrail is specific to out_of_scope, not a
        # blanket ban on quoting tracebacks.
        agent = build_classifier_agent(
            _classifier_test_model(
                "missing_library_or_function",
                evidence_lines=["src/amiga_ui/vamos/intuition_library.py"],
            )
        )
        result = agent.run_sync(
            "classify",
            deps=ClassifierDeps(
                allowed_categories=("out_of_scope_hardware_or_emulation", "missing_library_or_function"),
                source_text=self.SOURCE_TEXT,
            ),
        )
        self.assertEqual(result.output.category, "missing_library_or_function")

    def test_out_of_scope_without_any_repo_traceback_evidence_is_still_allowed(self) -> None:
        # A genuinely out-of-scope call (e.g. evidence naming a hardware
        # device/CIA register, not a repo file path) must not be blocked by
        # this guardrail -- only a direct traceback/repo-path contradiction is.
        agent = build_classifier_agent(
            _classifier_test_model(
                "out_of_scope_hardware_or_emulation",
                evidence_lines=["CIA timer A register access requested"],
            )
        )
        result = agent.run_sync(
            "classify",
            deps=ClassifierDeps(
                allowed_categories=("out_of_scope_hardware_or_emulation",),
                source_text="--- vamos.log ---\nCIA timer A register access requested",
            ),
        )
        self.assertEqual(result.output.category, "out_of_scope_hardware_or_emulation")


@unittest.skipUnless(_AGENT_GROUP_AVAILABLE, _AGENT_GROUP_SKIP_REASON)
class DriverOutcomeTests(unittest.TestCase):
    def _agents(self, *, classifier_category: str = "struct_or_message_translation") -> BlockerAgents:
        return BlockerAgents(
            classifier=build_classifier_agent(_classifier_test_model(classifier_category)),
            fixer=build_fixer_agent(_fixer_test_model()),
        )

    def test_no_blocker_short_circuits_without_any_model_call(self) -> None:
        with mock.patch.object(probe_module, "run_probe", return_value=_result("completed")):
            outcome = run_one_blocker("dummy", self._agents())
        self.assertEqual(outcome, "no_blocker")

    def test_deterministic_status_skips_the_classifier_entirely(self) -> None:
        # missing_library has a code-known category -- if the classifier were
        # actually called, this TestModel would return an out-of-scope
        # category and the run would incorrectly stop as "blocked".
        agents = BlockerAgents(
            classifier=build_classifier_agent(_classifier_test_model("out_of_scope_hardware_or_emulation")),
            fixer=build_fixer_agent(_fixer_test_model()),
        )
        before = _result("missing_library", missing_library="icon.library")
        after = _result("missing_library", missing_library="graphics.library")
        with (
            mock.patch.object(probe_module, "run_probe", side_effect=[before, after]),
            mock.patch.object(patch_module, "apply_diff", return_value=True),
            mock.patch.object(patch_module, "syntax_ok", return_value=True),
            mock.patch.object(gate_module, "quality_gate_passes", return_value=True),
            mock.patch.object(git_ops_module, "commit"),
            mock.patch.object(gate_module, "write_stop_marker"),
            mock.patch.object(
                run_log_module,
                "append_run_log_entry",
                return_value=probe_module.PROJECT_ROOT / "docs" / "apps" / "itidy" / "run-log.md",
            ),
        ):
            outcome = run_one_blocker("dummy", agents)
        self.assertEqual(outcome, "advanced")

    def test_classifier_exhausting_its_retry_budget_escalates_instead_of_crashing(self) -> None:
        # Reproduces the real failure this test guards against: a local
        # model that keeps missing the allowed-category restriction exhausts
        # pydantic-ai's output-retry budget and raises UnexpectedModelBehavior
        # (a subclass of AgentRunError). Before the fix, this propagated out
        # of run_one_blocker as an uncaught exception and crashed `python -m
        # agent` entirely instead of leaving a legible needs-user marker.
        agents = BlockerAgents(
            classifier=build_classifier_agent(_classifier_test_model("host_dependency_or_setup")),
            fixer=build_fixer_agent(_fixer_test_model()),
        )
        with (
            mock.patch.object(probe_module, "run_probe", return_value=_result("app_failed")),
            mock.patch.object(gate_module, "write_stop_marker") as write_marker,
        ):
            outcome = run_one_blocker("dummy", agents)
        self.assertEqual(outcome, "needs_user")
        write_marker.assert_called_once()
        self.assertEqual(write_marker.call_args.args[0], "needs-user")
        self.assertIn("LLM call failed", write_marker.call_args.args[1])

    def test_out_of_scope_classification_never_reaches_the_fixer(self) -> None:
        agents = BlockerAgents(
            classifier=build_classifier_agent(_classifier_test_model("out_of_scope_hardware_or_emulation")),
            fixer=build_fixer_agent(_fixer_test_model()),
        )
        with (
            mock.patch.object(probe_module, "run_probe", return_value=_result("app_failed")),
            mock.patch.object(gate_module, "write_stop_marker") as write_marker,
            mock.patch.object(patch_module, "apply_diff") as apply_diff,
        ):
            outcome = run_one_blocker("dummy", agents)
        self.assertEqual(outcome, "blocked")
        apply_diff.assert_not_called()
        write_marker.assert_called_once_with("blocked", "stub blocker")

    def test_fix_that_does_not_change_the_signature_is_reverted_and_retried_then_escalated(self) -> None:
        unchanged = _result("missing_library", missing_library="icon.library")
        with (
            mock.patch.object(probe_module, "run_probe", return_value=unchanged),
            mock.patch.object(patch_module, "apply_diff", return_value=True),
            mock.patch.object(patch_module, "syntax_ok", return_value=True),
            mock.patch.object(patch_module, "revert_diff") as revert_diff,
            mock.patch.object(gate_module, "write_stop_marker") as write_marker,
            mock.patch.object(gate_module, "quality_gate_passes") as quality_gate,
        ):
            outcome = run_one_blocker("dummy", self._agents())
        self.assertEqual(outcome, "needs_user")
        self.assertEqual(revert_diff.call_count, driver.MAX_ATTEMPTS_PER_BLOCKER)
        quality_gate.assert_not_called()
        write_marker.assert_called_once()
        self.assertEqual(write_marker.call_args.args[0], "needs-user")

    def test_diff_that_fails_to_apply_is_retried_without_reverting(self) -> None:
        before = _result("missing_library", missing_library="icon.library")
        with (
            mock.patch.object(probe_module, "run_probe", return_value=before),
            mock.patch.object(patch_module, "apply_diff", return_value=False) as apply_diff,
            mock.patch.object(patch_module, "revert_diff") as revert_diff,
            mock.patch.object(gate_module, "write_stop_marker"),
        ):
            outcome = run_one_blocker("dummy", self._agents())
        self.assertEqual(outcome, "needs_user")
        self.assertEqual(apply_diff.call_count, driver.MAX_ATTEMPTS_PER_BLOCKER)
        revert_diff.assert_not_called()  # nothing applied, nothing to revert

    def test_fix_that_advances_and_passes_the_gate_commits_and_completes(self) -> None:
        before = _result("missing_library", missing_library="icon.library")
        after = _result("missing_library", missing_library="graphics.library")
        with (
            mock.patch.object(probe_module, "run_probe", side_effect=[before, after]),
            mock.patch.object(patch_module, "apply_diff", return_value=True),
            mock.patch.object(patch_module, "syntax_ok", return_value=True),
            mock.patch.object(gate_module, "quality_gate_passes", return_value=True),
            mock.patch.object(git_ops_module, "commit") as commit,
            mock.patch.object(gate_module, "write_stop_marker") as write_marker,
            mock.patch.object(
                run_log_module,
                "append_run_log_entry",
                return_value=probe_module.PROJECT_ROOT / "docs" / "apps" / "itidy" / "run-log.md",
            ) as append_entry,
        ):
            outcome = run_one_blocker("dummy", self._agents())
        self.assertEqual(outcome, "advanced")
        commit.assert_called_once()
        append_entry.assert_called_once()
        write_marker.assert_called_once_with("complete", "advanced past missing_library:icon.library")

    def test_fix_that_advances_but_fails_the_quality_gate_escalates_instead_of_committing(self) -> None:
        before = _result("missing_library", missing_library="icon.library")
        after = _result("missing_library", missing_library="graphics.library")
        with (
            mock.patch.object(probe_module, "run_probe", side_effect=[before, after]),
            mock.patch.object(patch_module, "apply_diff", return_value=True),
            mock.patch.object(patch_module, "syntax_ok", return_value=True),
            mock.patch.object(gate_module, "quality_gate_passes", return_value=False),
            mock.patch.object(git_ops_module, "commit") as commit,
            mock.patch.object(gate_module, "write_stop_marker") as write_marker,
            mock.patch.object(
                run_log_module,
                "append_run_log_entry",
                return_value=probe_module.PROJECT_ROOT / "docs" / "apps" / "itidy" / "run-log.md",
            ),
        ):
            outcome = run_one_blocker("dummy", self._agents())
        self.assertEqual(outcome, "needs_user")
        commit.assert_not_called()
        write_marker.assert_called_once_with("needs-user", "fix advanced the probe but failed the quality gate")


if __name__ == "__main__":
    unittest.main()
