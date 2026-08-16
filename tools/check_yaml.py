#!/usr/bin/env python3

"""Validate that each given file is parseable YAML."""

from __future__ import annotations

import sys

import yaml


def main(argv: list[str]) -> int:
    exit_code = 0
    for path in argv:
        try:
            with open(path, encoding="utf-8") as handle:
                list(yaml.safe_load_all(handle))
        except yaml.YAMLError as exc:
            print(f"{path}: invalid YAML: {exc}", file=sys.stderr)
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
