"""Analyze the latest target probe failure and point at API evidence."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .api_index import DEFAULT_OUTPUT_JSON, api_lookup, classify_ui_obligation, load_api_index
from .assets import project_relative
from .config import ARTIFACTS_ROOT

CALL_RE = re.compile(
    r"\? CALL: \((?P<library>[^)]+)\)\s+(?P<bias>\d+)\s+"
    r"(?P<function>UNKNOWN\(#(?P<unknown_index>\d+)\)|[A-Za-z_][A-Za-z0-9_]*)"
    r"(?P<args>\([^)]*\))?.*?from PC=(?P<pc>[0-9A-Fa-f]+).*?-> d0=(?P<d0>[^ ]+) \(default\)"
)
OPEN_LIBRARY_RE = re.compile(r"OpenLibrary: '([^']+)' V\d+ -> 000000")
MISSING_PATH_RE = re.compile(r"\b(?:Open|Lock): .*?'([^']+)'.* -> None")

STDOUT_SIGNAL_PATTERNS = (
    "Failed to open GUI window",
    "Could not get visual info",
    "Failed to load Workbench Icon Font",
    "Error getting current directory",
    "CRITICAL_FAILURE",
)


@dataclass(frozen=True)
class DefaultedCall:
    """One unique defaulted vamos library/device call."""

    library: str
    bias: int
    function: str
    count: int
    first_line: int
    pc: str
    d0: str
    resolved_function: str | None
    ui_obligation: str
    implemented: bool | None
    autodoc: str | None


@dataclass(frozen=True)
class TargetFailureAnalysis:
    """Serializable target failure analysis."""

    artifact_root: str
    status: str
    ok: bool
    returncode: int | None
    stdout_signals: list[str]
    missing_libraries: list[str]
    missing_paths: list[dict[str, Any]]
    defaulted_calls: list[DefaultedCall]
    priority: str
    recommended_next_steps: list[str]


def latest_probe_artifact(artifacts_root: Path = ARTIFACTS_ROOT) -> Path | None:
    """Return the newest probe artifact directory that has a result.json file."""

    if not artifacts_root.is_dir():
        return None
    candidates = [path for path in artifacts_root.iterdir() if path.is_dir() and (path / "result.json").is_file()]
    if not candidates:
        return None
    return sorted(candidates, key=lambda path: path.name)[-1]


def analyze_artifact(
    artifact_root: Path,
    *,
    api_index_path: Path = DEFAULT_OUTPUT_JSON,
) -> TargetFailureAnalysis:
    """Analyze one probe artifact directory."""

    artifact_root = artifact_root.resolve()
    result = _read_json(artifact_root / "result.json")
    stdout_text = _read_text(artifact_root / "stdout.txt")
    log_text = _read_text(artifact_root / "vamos.log")
    lookup = api_lookup(load_api_index(api_index_path))

    defaulted_calls = _defaulted_calls(log_text, lookup)
    stdout_signals = [pattern for pattern in STDOUT_SIGNAL_PATTERNS if pattern in stdout_text]
    missing_libraries = sorted(set(OPEN_LIBRARY_RE.findall(log_text)))
    missing_paths = _missing_paths(log_text)
    priority = _priority(stdout_signals, defaulted_calls)

    return TargetFailureAnalysis(
        artifact_root=project_relative(artifact_root),
        status=str(result.get("status", "unknown")),
        ok=bool(result.get("ok", False)),
        returncode=result.get("returncode") if isinstance(result.get("returncode"), int) else None,
        stdout_signals=stdout_signals,
        missing_libraries=missing_libraries,
        missing_paths=missing_paths,
        defaulted_calls=defaulted_calls,
        priority=priority,
        recommended_next_steps=_recommended_next_steps(priority, defaulted_calls, stdout_signals, missing_paths),
    )


def render_text(analysis: TargetFailureAnalysis) -> str:
    """Render an analysis report for terminal use."""

    lines = [
        f"Target failure analysis: {analysis.artifact_root}",
        f"Status: {analysis.status} ok={analysis.ok} returncode={analysis.returncode}",
        f"Priority: {analysis.priority}",
        "",
    ]
    if analysis.stdout_signals:
        lines.append("Stdout/app signals:")
        lines.extend(f"- {signal}" for signal in analysis.stdout_signals)
        lines.append("")
    if analysis.missing_libraries:
        lines.append("Missing libraries:")
        lines.extend(f"- {name}" for name in analysis.missing_libraries)
        lines.append("")
    if analysis.missing_paths:
        lines.append("Missing paths:")
        for item in analysis.missing_paths[:12]:
            lines.append(f"- {item['path']} ({item['count']}x)")
        lines.append("")
    if analysis.defaulted_calls:
        lines.append("Defaulted library/device calls:")
        for call in analysis.defaulted_calls[:20]:
            resolved = f" -> {call.resolved_function}" if call.resolved_function else ""
            implemented = "unknown" if call.implemented is None else str(call.implemented)
            lines.append(
                f"- {call.library} bias {call.bias} {call.function}{resolved} "
                f"({call.count}x, first line {call.first_line}, obligation={call.ui_obligation}, implemented={implemented})"
            )
        lines.append("")
    lines.append("Recommended next steps:")
    lines.extend(f"- {step}" for step in analysis.recommended_next_steps)
    return "\n".join(lines).rstrip() + "\n"


def _defaulted_calls(log_text: str, lookup: dict[tuple[str, int], dict[str, Any]]) -> list[DefaultedCall]:
    first: dict[tuple[str, int, str], dict[str, Any]] = {}
    counts: Counter[tuple[str, int, str]] = Counter()
    for line_number, line in enumerate(log_text.splitlines(), start=1):
        match = CALL_RE.search(line)
        if match is None:
            continue
        library = match.group("library")
        bias = int(match.group("bias"))
        function = match.group("function")
        key = (library, bias, function)
        counts[key] += 1
        first.setdefault(
            key,
            {
                "line": line_number,
                "pc": match.group("pc"),
                "d0": match.group("d0"),
            },
        )

    calls: list[DefaultedCall] = []
    for (library, bias, function), count in counts.items():
        api_entry = lookup.get((library, bias))
        resolved = api_entry.get("name") if api_entry else None
        obligation = (
            str(api_entry.get("ui_obligation"))
            if api_entry and api_entry.get("ui_obligation")
            else classify_ui_obligation(library, resolved or function)
        )
        implemented = api_entry.get("implemented") if api_entry else None
        autodoc = None
        if api_entry:
            autodoc = api_entry.get("autodoc_path") or api_entry.get("autodoc_url")
        seen = first[(library, bias, function)]
        calls.append(
            DefaultedCall(
                library=library,
                bias=bias,
                function=function,
                count=count,
                first_line=int(seen["line"]),
                pc=str(seen["pc"]),
                d0=str(seen["d0"]),
                resolved_function=str(resolved) if resolved and resolved != function else None,
                ui_obligation=obligation,
                implemented=implemented if isinstance(implemented, bool) else None,
                autodoc=str(autodoc) if autodoc else None,
            )
        )
    return sorted(calls, key=lambda call: (call.first_line, call.library, call.bias))


def _missing_paths(log_text: str) -> list[dict[str, Any]]:
    counts = Counter(MISSING_PATH_RE.findall(log_text))
    return [{"path": path, "count": count} for path, count in counts.most_common()]


def _priority(stdout_signals: list[str], defaulted_calls: list[DefaultedCall]) -> str:
    if "Failed to open GUI window" in stdout_signals or "Could not get visual info" in stdout_signals:
        return "visible-ui-blocker"
    if any(call.ui_obligation in {"host-ui-required", "workbench-visible-state"} for call in defaulted_calls):
        return "api-with-ui-obligation"
    if defaulted_calls:
        return "defaulted-api-call"
    return "inspect-artifacts"


def _recommended_next_steps(
    priority: str,
    defaulted_calls: list[DefaultedCall],
    stdout_signals: list[str],
    missing_paths: list[dict[str, Any]],
) -> list[str]:
    steps = ["Regenerate the API index with `uv run python tools/generate_api_index.py` if it is missing or stale."]
    if priority == "visible-ui-blocker":
        steps.append(
            "Treat the next fix as a real host-UI translation task: a fake handle is not success when the app is trying to create windows, gadgets, menus, requesters, fonts, or drawing state."
        )
    for call in defaulted_calls[:5]:
        name = call.resolved_function or call.function
        if call.autodoc:
            steps.append(f"Read API evidence for `{call.library}/{name}`: {call.autodoc}")
        else:
            steps.append(
                f"Find API evidence for `{call.library}` bias {call.bias} `{name}` in FD/proto/AutoDoc material."
            )
    if stdout_signals:
        steps.append(
            "Tie the code change to a host-visible milestone from stdout, not just to allowing the probe to run further."
        )
    if missing_paths:
        steps.append(
            "Decide whether missing `ENV:`/`ENVARC:`/`RAM:` paths need prepared runtime files, assigns, or better DOS path behavior before adding unrelated stubs."
        )
    return steps


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_text(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", nargs="?", type=Path, help="probe artifact directory; defaults to latest")
    parser.add_argument("--latest", action="store_true", help="analyze the latest probe artifact")
    parser.add_argument("--api-index", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument(
        "--fail-on-target-failure", action="store_true", help="return non-zero when the analyzed target run failed"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    artifact = latest_probe_artifact() if args.latest or args.artifact is None else args.artifact
    if artifact is None:
        print("No probe artifacts found", flush=True)
        return 1
    analysis = analyze_artifact(artifact, api_index_path=args.api_index)
    if args.json:
        print(json.dumps(asdict(analysis), indent=2, sort_keys=True))
    else:
        print(render_text(analysis), end="")
    return 1 if args.fail_on_target_failure and not analysis.ok else 0


if __name__ == "__main__":
    raise SystemExit(main())
