# pyright: reportPossiblyUnboundVariable = none
# agent/llm.py requires the optional "agent" dependency group (pydantic-ai,
# see pyproject.toml); the pragma keeps pyright green on the canonical
# `uv sync --group dev` bootstrap, where that group is not installed. It is
# a no-op once the group is present. The runtime guard below skips the
# suite instead of failing to import.
"""Tests for agent/llm.py's local model endpoint wiring.

Kept intentionally minimal -- $OLLAMA_URL is now sound at the shell level,
so this module no longer has any environment-sniffing logic to guard
against, just a plain default and a single combined host:port endpoint.
"""

from __future__ import annotations

import unittest

try:
    from agent.llm import DEFAULT_ENDPOINT, local_model

    _AGENT_GROUP_AVAILABLE = True
except ImportError:
    _AGENT_GROUP_AVAILABLE = False

_AGENT_GROUP_SKIP_REASON = "agent dependency group is not installed; run: uv sync --group agent --group dev"


@unittest.skipUnless(_AGENT_GROUP_AVAILABLE, _AGENT_GROUP_SKIP_REASON)
class LocalModelEndpointTests(unittest.TestCase):
    def test_default_endpoint_is_localhost_11434(self) -> None:
        self.assertEqual(DEFAULT_ENDPOINT, "localhost:11434")

    def test_default_model_targets_the_default_endpoint(self) -> None:
        model = local_model("qwen3.5-128k")
        self.assertEqual(str(model.client.base_url), "http://localhost:11434/v1/")

    def test_explicit_endpoint_is_used_verbatim(self) -> None:
        model = local_model("qwen3.5-128k", endpoint="192.168.50.136:11434")
        self.assertEqual(str(model.client.base_url), "http://192.168.50.136:11434/v1/")


if __name__ == "__main__":
    unittest.main()
