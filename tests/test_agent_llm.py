"""Tests for agent/llm.py's model-endpoint resolution.

Guards against a real, directly-observed misconfiguration: in this
environment $OLLAMA_URL points at a CPU-only Ollama instance on a
different port than the GPU-backed one (docker-compose.yml's `ollama-cpu`
service sets CUDA_VISIBLE_DEVICES=-1 and maps a separate port) -- likely
intentional for other tools that shouldn't compete for VRAM, but silently
made every model call in this package 2-3x+ slower than necessary. The fix
reuses $OLLAMA_URL's host but always targets the GPU service's port.
"""

from __future__ import annotations

import unittest
from unittest import mock

from agent.llm import _GPU_PORT, resolve_base_url


class BaseUrlResolutionTests(unittest.TestCase):
    def test_defaults_to_localhost_when_ollama_url_is_unset(self) -> None:
        with mock.patch.dict("os.environ", {}, clear=False):
            import os

            os.environ.pop("OLLAMA_URL", None)
            self.assertEqual(resolve_base_url(), f"http://localhost:{_GPU_PORT}")

    def test_reuses_ollama_urls_host_but_forces_the_gpu_port(self) -> None:
        with mock.patch.dict("os.environ", {"OLLAMA_URL": "http://192.168.50.136:11435"}):
            self.assertEqual(resolve_base_url(), f"http://192.168.50.136:{_GPU_PORT}")

    def test_explicit_host_and_port_override_ollama_url_entirely(self) -> None:
        with mock.patch.dict("os.environ", {"OLLAMA_URL": "http://192.168.50.136:11435"}):
            self.assertEqual(
                resolve_base_url(host="10.0.0.5", port=9999),
                "http://10.0.0.5:9999",
            )

    def test_explicit_host_only_still_uses_the_gpu_port_default(self) -> None:
        with mock.patch.dict("os.environ", {"OLLAMA_URL": "http://192.168.50.136:11435"}):
            self.assertEqual(resolve_base_url(host="10.0.0.5"), f"http://10.0.0.5:{_GPU_PORT}")


if __name__ == "__main__":
    unittest.main()
