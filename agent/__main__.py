"""CLI entrypoint: `uv run python -m agent <target-binary>`.

Runs exactly one unit of work (one blocker), then exits -- consistent with
the "solve one blocker, commit, exit" shape this package exists to enable.
Call it again to pick up the next blocker.
"""

from __future__ import annotations

import argparse
import sys

from .driver import BlockerAgents, run_one_blocker
from .llm import DEFAULT_ENDPOINT, build_classifier_agent, build_fixer_agent, local_model


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m agent")
    parser.add_argument("target_binary", help="e.g. amiga_apps/itidy1classic/binary/extracted/iTidy")
    parser.add_argument("--app", default="itidy", help="docs/apps/<app>/run-log.md to append to")
    parser.add_argument("--classifier-model", default="qwen3.5-128k")
    parser.add_argument("--classifier-endpoint", default=DEFAULT_ENDPOINT, help="host:port")
    parser.add_argument("--fixer-model", default="qwen3.5-128k")
    parser.add_argument("--fixer-endpoint", default=DEFAULT_ENDPOINT, help="host:port")
    args = parser.parse_args(argv)

    print(f"[agent] classifier: {args.classifier_model} @ {args.classifier_endpoint}", flush=True)
    print(f"[agent] fixer: {args.fixer_model} @ {args.fixer_endpoint}", flush=True)
    print(
        "[agent] each model call below can take a while on a local reasoning model; progress prints as it happens",
        flush=True,
    )

    agents = BlockerAgents(
        classifier=build_classifier_agent(local_model(args.classifier_model, endpoint=args.classifier_endpoint)),
        fixer=build_fixer_agent(local_model(args.fixer_model, endpoint=args.fixer_endpoint)),
    )

    outcome = run_one_blocker(args.target_binary, agents, app=args.app)
    print(f"outcome: {outcome}")
    return 0 if outcome in ("advanced", "no_blocker") else 1


if __name__ == "__main__":
    sys.exit(main())
