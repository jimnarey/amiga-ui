"""Tests for agent/llm.py's local model endpoint wiring.

Kept intentionally minimal -- $OLLAMA_URL is now sound at the shell level,
so this module no longer has any environment-sniffing logic to guard
against, just a plain default and a single combined host:port endpoint.
"""

from __future__ import annotations

import unittest

from agent.llm import DEFAULT_ENDPOINT, local_model


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
