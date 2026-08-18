"""Blocker-category taxonomy, anchored to what src/amiga_ui/cli.py actually
restricts probe results to.

Design note (verified 2026-08-18): the docs' six-category blocker taxonomy
(docs/workflows/error-driven-porting.md) is a human/agent triage vocabulary,
not something the launcher computes. The launcher's own restricted output is
narrower: ``ProbeClassification.status`` in
``src/amiga_ui/cli.py::_classify_probe_outcome`` is exactly one of
"completed", "missing_asset", "timeout", "missing_library",
"path_setup_failed", "vamos_error", or "app_failed" -- a fixed detector
chain with "app_failed" as the only catch-all default.

Three of the six docs categories map 1:1 onto a status the code already
resolves for certain: host_dependency_or_setup <- missing_asset,
path_or_runtime_tree <- path_setup_failed, missing_library_or_function <-
missing_library (the OpenLibrary-failure case). Struct/message translation,
GUI/requester/layout, and out-of-scope-hardware issues have *no* code-level
detector at all -- and neither does a missing *function* inside an
already-open library, since the missing_library detector's regex only
matches OpenLibrary failures -- so all of these collapse into the same
"app_failed"/"vamos_error"/"timeout" catch-all statuses. For those, an LLM
classification call is genuinely needed, because the code cannot tell the
difference; anywhere else, asking a model to guess would be pure risk with
no upside, so this module skips the model call entirely and uses the
deterministic mapping instead.

If ``_classify_probe_outcome`` gains a new status value, the functions below
raise on it rather than silently misrouting. tests/test_agent_blockers.py
pins the known status set against the real detector chain in cli.py and
should be updated in the same change as any change there.
"""

from __future__ import annotations

from typing import Final, Literal

# The full closed set the LLM classifier's Pydantic output_type is
# restricted to. This alone is already stronger than the launcher's own text
# status, since pydantic-ai retries (via output_validator/ModelRetry, see
# agent/llm.py) rather than accepting a value outside this Literal -- but see
# below for the further, per-status restriction this module adds on top.
BlockerCategory = Literal[
    "host_dependency_or_setup",
    "path_or_runtime_tree",
    "missing_library_or_function",
    "struct_or_message_translation",
    "gui_requester_or_layout",
    "out_of_scope_hardware_or_emulation",
]

BLOCKER_CATEGORIES: Final[tuple[BlockerCategory, ...]] = (
    "host_dependency_or_setup",
    "path_or_runtime_tree",
    "missing_library_or_function",
    "struct_or_message_translation",
    "gui_requester_or_layout",
    "out_of_scope_hardware_or_emulation",
)

# The exact status values _classify_probe_outcome can produce. Kept in sync
# with src/amiga_ui/cli.py by hand -- there is no shared import, because
# cli.py's ProbeClassification.status is a plain str, not an enum, and this
# module intentionally does not reach into cli.py's private functions at
# runtime (tests do, to guard against drift).
KNOWN_PROBE_STATUSES: Final[frozenset[str]] = frozenset(
    {
        "completed",
        "missing_asset",
        "timeout",
        "missing_library",
        "path_setup_failed",
        "vamos_error",
        "app_failed",
    }
)

_DETERMINISTIC_STATUS_MAP: Final[dict[str, BlockerCategory]] = {
    "missing_asset": "host_dependency_or_setup",
    "path_setup_failed": "path_or_runtime_tree",
    "missing_library": "missing_library_or_function",
}

# Statuses where the launcher genuinely cannot tell what kind of blocker this
# is -- only these ever reach the LLM classifier, and only with this
# restricted subset as its allowed output (see agent/llm.py's
# output_validator, which enforces this at the model-call boundary).
_AMBIGUOUS_STATUS_CATEGORIES: Final[dict[str, tuple[BlockerCategory, ...]]] = {
    "app_failed": (
        "missing_library_or_function",
        "struct_or_message_translation",
        "gui_requester_or_layout",
        "out_of_scope_hardware_or_emulation",
    ),
    "vamos_error": (
        "missing_library_or_function",
        "struct_or_message_translation",
        "gui_requester_or_layout",
        "out_of_scope_hardware_or_emulation",
    ),
    # A timeout with no other detected cause is most plausibly a hang inside
    # GUI/requester interaction, struct/message mishandling, or genuinely
    # out-of-scope emulation -- host-dependency, path, and open-library
    # failures in this launcher all fail fast rather than hang.
    "timeout": (
        "struct_or_message_translation",
        "gui_requester_or_layout",
        "out_of_scope_hardware_or_emulation",
    ),
}


class UnknownProbeStatusError(ValueError):
    """A probe result reported a status this module doesn't know about.

    Deliberately not caught anywhere: silently defaulting to some category
    would defeat the point of anchoring classification to the launcher's
    real, restricted output. Treat this as "agent/blockers.py needs updating
    to match src/amiga_ui/cli.py", not something to paper over.
    """


def require_known_status(status: str) -> None:
    if status not in KNOWN_PROBE_STATUSES:
        raise UnknownProbeStatusError(
            f"probe status {status!r} is not one _classify_probe_outcome is known to "
            "produce; update agent/blockers.py (and KNOWN_PROBE_STATUSES) to match "
            "src/amiga_ui/cli.py before relying on it"
        )


def deterministic_category(status: str) -> BlockerCategory | None:
    """The category the launcher's own status already tells us for certain, if any."""

    require_known_status(status)
    return _DETERMINISTIC_STATUS_MAP.get(status)


def ambiguous_categories(status: str) -> tuple[BlockerCategory, ...]:
    """The restricted subset an LLM classifier may choose from for this status.

    Only meaningful when ``deterministic_category(status)`` is None and
    status isn't "completed" (not a blocker at all) -- callers must handle
    both of those cases before reaching here.
    """

    require_known_status(status)
    categories = _AMBIGUOUS_STATUS_CATEGORIES.get(status)
    if categories is None:
        raise UnknownProbeStatusError(
            f"probe status {status!r} is known but has neither a deterministic "
            "category nor a registered ambiguous set -- is it 'completed'? "
            "callers must handle that case before reaching here"
        )
    return categories
