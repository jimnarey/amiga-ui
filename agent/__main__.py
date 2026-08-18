"""CLI entrypoint: `uv run python -m agent <target-binary>`.

Runs exactly one unit of work (one blocker), then exits -- consistent with
the "solve one blocker, commit, exit" shape this package exists to enable.
Call it again to pick up the next blocker.
"""

from __future__ import annotations

import argparse
import sys

from .driver import BlockerAgents, run_one_blocker
from .llm import build_classifier_agent, build_fixer_agent, local_model, resolve_base_url


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m agent")
    parser.add_argument("target_binary", help="e.g. amiga_apps/itidy1classic/binary/extracted/iTidy")
    parser.add_argument("--app", default="itidy", help="docs/apps/<app>/run-log.md to append to")
    parser.add_argument("--classifier-model", default="qwen3.5-128k")
    parser.add_argument("--classifier-host", default=None, help="defaults to $OLLAMA_URL's host if set, else localhost")
    parser.add_argument("--classifier-port", type=int, default=None, help="defaults to the GPU instance's port")
    parser.add_argument("--fixer-model", default="qwen3.5-128k")
    parser.add_argument("--fixer-host", default=None, help="defaults to $OLLAMA_URL's host if set, else localhost")
    parser.add_argument("--fixer-port", type=int, default=None, help="defaults to the GPU instance's port")
    args = parser.parse_args(argv)

    classifier_url = resolve_base_url(host=args.classifier_host, port=args.classifier_port)
    fixer_url = resolve_base_url(host=args.fixer_host, port=args.fixer_port)
    print(f"[agent] classifier: {args.classifier_model} @ {classifier_url}", flush=True)
    print(f"[agent] fixer: {args.fixer_model} @ {fixer_url}", flush=True)
    print(
        "[agent] each model call below can take a while on a local reasoning model; progress prints as it happens",
        flush=True,
    )

    agents = BlockerAgents(
        classifier=build_classifier_agent(
            local_model(args.classifier_model, host=args.classifier_host, port=args.classifier_port)
        ),
        fixer=build_fixer_agent(local_model(args.fixer_model, host=args.fixer_host, port=args.fixer_port)),
    )

    outcome = run_one_blocker(args.target_binary, agents, app=args.app)
    print(f"outcome: {outcome}")
    return 0 if outcome in ("advanced", "no_blocker") else 1


if __name__ == "__main__":
    sys.exit(main())
