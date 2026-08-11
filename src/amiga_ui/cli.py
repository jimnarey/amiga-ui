"""Project command-line interface."""

from __future__ import annotations

import argparse
import contextlib
import json
import re
import signal
import subprocess
import sys
import tempfile
import traceback
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .assets import AssetCheck, asset_inventory, project_relative, required_asset_checks
from .config import DEFAULT_PROBE_TIMEOUT_SECONDS, PROJECT_ROOT
from .host.gui_smoke import run_smoke_gui
from .host.xvfb import run_with_xvfb
from .run_artifacts import RunArtifacts, create_run_artifacts, write_json
from .targets import ProbeTarget, get_probe_target
from .vamos.launcher import run_vamos_in_process


@dataclass(frozen=True)
class CheckResult:
    """One host or asset preflight check."""

    label: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class ProbeRuntimePaths:
    """Prepared host directories mapped into the probe runtime."""

    sys_root: Path
    work_root: Path
    volumes_root: Path

    def as_display_dict(self) -> dict[str, str]:
        """Render runtime paths relative to the repo root when possible."""

        return {
            "sys_root": project_relative(self.sys_root),
            "work_root": project_relative(self.work_root),
            "volumes_root": project_relative(self.volumes_root),
        }


@dataclass(frozen=True)
class ProbeClassification:
    """Classification of one probe result."""

    status: str
    ok: bool
    details: dict[str, Any] = field(default_factory=dict)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="amiga-ui")
    subparsers = parser.add_subparsers(dest="command", required=True)

    check_parser = subparsers.add_parser(
        "check",
        help="verify the host environment and core project assets",
    )
    check_parser.add_argument(
        "--json",
        action="store_true",
        help="emit the final result as JSON",
    )
    check_parser.set_defaults(func=_run_check)

    smoke_parser = subparsers.add_parser(
        "smoke-gui",
        help="launch a minimal Qt Widgets window to verify GUI operation",
    )
    smoke_parser.add_argument(
        "--direct",
        action="store_true",
        help="run directly instead of via the Xvfb wrapper",
    )
    smoke_parser.add_argument(
        "--duration-ms",
        type=int,
        default=250,
        help="how long the test window should stay alive",
    )
    smoke_parser.set_defaults(func=_run_smoke_gui)

    probe_parser = subparsers.add_parser(
        "probe",
        help="run an Amiga application probe under vamos and capture artifacts",
    )
    probe_parser.add_argument(
        "target",
        choices=["itidy"],
        help="the named application target to probe",
    )
    probe_parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_PROBE_TIMEOUT_SECONDS,
        help="timeout for the probe in seconds",
    )
    probe_parser.add_argument(
        "--direct",
        action="store_true",
        help="run the probe directly instead of through the Xvfb wrapper",
    )
    probe_parser.set_defaults(func=_run_probe)
    return parser


def _run_check(args: argparse.Namespace) -> int:
    checks = _collect_check_results()
    inventories = asset_inventory()
    payload = _build_check_payload(checks, inventories)

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        _print_check_report(checks, inventories)

    return 0 if payload["ok"] else 1


def _collect_check_results() -> list[CheckResult]:
    checks = [_check_python_version()]
    checks.extend(_check_python_import(module_name) for module_name in ("PySide6", "amitools"))
    checks.extend(
        (
            _check_command_available("7z command available", ["7z", "-h"]),
            _check_command_available("Xvfb command available", ["Xvfb", "-help"]),
        )
    )
    checks.extend(_check_required_asset(asset) for asset in required_asset_checks())
    return checks


def _check_python_version() -> CheckResult:
    return CheckResult(
        label="Python 3.12 or newer",
        ok=sys.version_info >= (3, 12),
        detail=f"running {sys.version.split()[0]}",
    )


def _check_python_import(module_name: str) -> CheckResult:
    try:
        __import__(module_name)
    except Exception as exc:  # pragma: no cover - exercised by manual preflight
        return CheckResult(f"Python import: {module_name}", False, str(exc))
    return CheckResult(f"Python import: {module_name}", True, "import succeeded")


def _check_command_available(label: str, command: list[str]) -> CheckResult:
    try:
        completed = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return CheckResult(label, completed.returncode == 0, f"exit code {completed.returncode}")
    except FileNotFoundError:
        return CheckResult(label, False, "command not found")


def _check_required_asset(asset: AssetCheck) -> CheckResult:
    detail = project_relative(asset.path)
    if asset.exists:
        return CheckResult(f"Asset: {asset.label}", True, f"found at {detail}")
    if asset.required:
        return CheckResult(f"Asset: {asset.label}", False, f"missing required file at {detail}")
    return CheckResult(f"Asset: {asset.label}", True, f"optional file not present at {detail}")


def _build_check_payload(checks: list[CheckResult], inventories: list[Any]) -> dict[str, Any]:
    return {
        "ok": all(check.ok for check in checks),
        "checks": [asdict(check) for check in checks],
        "inventory": [asdict(entry) | {"directory": project_relative(entry.directory)} for entry in inventories],
    }


def _print_check_report(checks: list[CheckResult], inventories: list[Any]) -> None:
    print("Checking project environment...")
    for check in checks:
        prefix = "[ok]" if check.ok else "[missing]"
        print(f"{prefix} {check.label}: {check.detail}")

    print()
    print("Asset inventory:")
    for entry in inventories:
        print(
            f"- {entry.label}: {entry.present_count} present, "
            f"{entry.placeholder_count} placeholders in {project_relative(entry.directory)}"
        )

    missing = [check for check in checks if not check.ok]
    if missing:
        print()
        print("Missing dependencies or required assets:")
        for check in missing:
            print(f"- {check.label}: {check.detail}")


def _run_smoke_gui(args: argparse.Namespace) -> int:
    if args.direct:
        return run_smoke_gui(duration_ms=args.duration_ms)
    return _run_smoke_gui_with_xvfb(args.duration_ms)


def _run_smoke_gui_with_xvfb(duration_ms: int) -> int:
    command = [
        sys.executable,
        "-m",
        "amiga_ui",
        "smoke-gui",
        "--direct",
        "--duration-ms",
        str(duration_ms),
    ]
    completed = run_with_xvfb(command, capture_output=False, text=True)
    return completed.returncode


def _run_probe(args: argparse.Namespace) -> int:
    if not args.direct:
        return _run_probe_with_xvfb(args.target, args.timeout)
    return _run_probe_direct(args.target, args.timeout)


def _run_probe_with_xvfb(target_name: str, timeout: int) -> int:
    command = [
        sys.executable,
        "-m",
        "amiga_ui",
        "probe",
        target_name,
        "--direct",
        "--timeout",
        str(timeout),
    ]
    completed = run_with_xvfb(command, capture_output=False, text=True)
    return completed.returncode


def _run_probe_direct(target_name: str, timeout: int) -> int:
    target = get_probe_target(target_name)
    artifacts = create_run_artifacts("probe", target.name)
    invocation = _build_probe_invocation_base(target.name, timeout)
    preflight_errors = _probe_preflight_errors(target)

    if preflight_errors:
        return _finish_probe_preflight_failure(artifacts, invocation, target, preflight_errors)

    runtime_paths = _prepare_probe_runtime(artifacts.runtime_root)
    vamos_args = _build_probe_args(target, runtime_paths, artifacts.vamos_log_path)
    _write_probe_invocation(artifacts, invocation, runtime_paths, vamos_args)

    try:
        completed = _execute_probe(vamos_args, timeout)
    except ProbeTimeoutError:
        return _finish_probe_timeout(artifacts, target, timeout)

    _write_probe_streams(artifacts, completed.stdout, completed.stderr)
    classification = _classify_probe_outcome(
        completed.returncode,
        artifacts.vamos_log_path,
        artifacts.stderr_path,
    )
    return _finish_probe_completion(artifacts, target, completed.returncode, classification)


def _build_probe_invocation_base(target_name: str, timeout: int) -> dict[str, Any]:
    return {
        "command": "probe",
        "target": target_name,
        "direct": True,
        "timeout_seconds": timeout,
    }


def _write_probe_invocation(
    artifacts: RunArtifacts,
    invocation_base: dict[str, Any],
    runtime_paths: ProbeRuntimePaths,
    vamos_args: list[str],
) -> None:
    payload = invocation_base | {
        "artifact_root": project_relative(artifacts.root),
        "launch_mode": "in_process",
        "runtime": runtime_paths.as_display_dict(),
        "vamos_args": vamos_args,
    }
    write_json(artifacts.invocation_path, payload)


def _finish_probe_preflight_failure(
    artifacts: RunArtifacts,
    invocation_base: dict[str, Any],
    target: ProbeTarget,
    errors: list[str],
) -> int:
    write_json(
        artifacts.invocation_path,
        invocation_base | {"artifact_root": project_relative(artifacts.root)},
    )
    _write_probe_streams(artifacts, "", "")
    payload = {
        "status": "missing_asset",
        "ok": False,
        "target": target.name,
        "errors": errors,
        "artifact_root": project_relative(artifacts.root),
    }
    _write_probe_result(artifacts, payload)
    _print_probe_message("Probe aborted before launch.", project_relative(artifacts.root), errors)
    return 1


def _finish_probe_timeout(artifacts: RunArtifacts, target: ProbeTarget, timeout: int) -> int:
    _write_probe_streams(artifacts, "", "")
    payload = {
        "status": "timeout",
        "ok": False,
        "target": target.name,
        "timeout_seconds": timeout,
        "artifact_root": project_relative(artifacts.root),
        "stdout_path": project_relative(artifacts.stdout_path),
        "stderr_path": project_relative(artifacts.stderr_path),
        "vamos_log_path": project_relative(artifacts.vamos_log_path),
    }
    _write_probe_result(artifacts, payload)
    _print_probe_message(
        f"Probe timed out after {timeout}s.",
        project_relative(artifacts.root),
    )
    return 1


def _finish_probe_completion(
    artifacts: RunArtifacts,
    target: ProbeTarget,
    returncode: int,
    classification: ProbeClassification,
) -> int:
    payload = {
        "status": classification.status,
        "ok": classification.ok,
        "target": target.name,
        "returncode": returncode,
        "artifact_root": project_relative(artifacts.root),
        "stdout_path": project_relative(artifacts.stdout_path),
        "stderr_path": project_relative(artifacts.stderr_path),
        "vamos_log_path": project_relative(artifacts.vamos_log_path),
    }
    payload.update(classification.details)
    _write_probe_result(artifacts, payload)
    _print_probe_message(
        f"Probe finished with status {classification.status}.",
        project_relative(artifacts.root),
        _probe_detail_lines(classification),
    )
    return 0 if classification.ok else 1


def _write_probe_result(artifacts: RunArtifacts, payload: dict[str, Any]) -> None:
    write_json(artifacts.result_path, payload)


def _write_probe_streams(artifacts: RunArtifacts, stdout_text: str, stderr_text: str) -> None:
    artifacts.stdout_path.write_text(stdout_text, encoding="utf-8")
    artifacts.stderr_path.write_text(stderr_text, encoding="utf-8")


def _print_probe_message(summary: str, artifact_root: str, details: list[str] | None = None) -> None:
    print(summary)
    if details:
        for detail in details:
            print(detail)
    print(f"Artifacts: {artifact_root}")


def _probe_detail_lines(classification: ProbeClassification) -> list[str]:
    summary = classification.details.get("diagnostic_summary")
    if summary is None:
        return []
    return [summary]


def _probe_preflight_errors(target: ProbeTarget) -> list[str]:
    errors: list[str] = []
    if not target.host_binary_path.is_file():
        errors.append(f"missing target binary: {project_relative(target.host_binary_path)}")
    return errors


def _prepare_probe_runtime(runtime_root: Path) -> ProbeRuntimePaths:
    sys_root = runtime_root / "sys"
    work_root = runtime_root / "work"
    volumes_root = runtime_root / "volumes"

    _ensure_probe_runtime_root(sys_root, work_root, volumes_root)
    _ensure_probe_sys_layout(sys_root)
    _write_probe_startup_sequence(sys_root / "S" / "startup-sequence")

    return ProbeRuntimePaths(
        sys_root=sys_root,
        work_root=work_root,
        volumes_root=volumes_root,
    )


def _ensure_probe_runtime_root(*paths: Path) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


def _ensure_probe_sys_layout(sys_root: Path) -> None:
    for relative_dir in ("C", "S", "Libs", "Devs", "L", "T"):
        (sys_root / relative_dir).mkdir(exist_ok=True)


def _write_probe_startup_sequence(path: Path) -> None:
    path.write_text("; amiga-ui probe runtime\n", encoding="utf-8")


def _build_probe_args(
    target: ProbeTarget,
    runtime_paths: ProbeRuntimePaths,
    vamos_log_path: Path,
) -> list[str]:
    return [
        "-S",
        "--vols-base-dir",
        str(runtime_paths.volumes_root),
        "--auto-volumes",
        "off",
        "--auto-assigns",
        "off",
        "-V",
        "root:/",
        "-V",
        f"app:{target.app_volume_root}",
        "-V",
        f"sys:{runtime_paths.sys_root}",
        "-V",
        f"work:{runtime_paths.work_root}",
        "-a",
        "c:sys:C",
        "-a",
        "libs:sys:Libs",
        "-a",
        "s:sys:S",
        "-a",
        "l:sys:L",
        "-a",
        "devs:sys:Devs",
        "-a",
        "t:sys:T",
        "-p",
        "c:",
        "--cwd",
        "sys:T",
        "-C",
        "68000",
        "-m",
        "2048",
        "-H",
        "abort",
        "-P",
        "-l",
        "dos:info,exec:info",
        "-L",
        str(vamos_log_path),
        target.amiga_binary,
    ]


class ProbeTimeoutError(Exception):
    """Raised when an in-process probe exceeds its time limit."""


def _execute_probe(vamos_args: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    with (
        tempfile.NamedTemporaryFile("w+", encoding="utf-8") as stdout_file,
        tempfile.NamedTemporaryFile("w+", encoding="utf-8") as stderr_file,
    ):
        returncode = 1
        try:
            with (
                contextlib.redirect_stdout(stdout_file),
                contextlib.redirect_stderr(stderr_file),
                _probe_timeout(timeout),
            ):
                returncode = run_vamos_in_process(args=vamos_args)
        except ProbeTimeoutError:
            raise
        except Exception:
            traceback.print_exc(file=stderr_file)

        stdout_file.flush()
        stderr_file.flush()
        stdout_file.seek(0)
        stderr_file.seek(0)
        return subprocess.CompletedProcess(
            vamos_args,
            returncode,
            stdout_file.read(),
            stderr_file.read(),
        )


def _classify_probe_outcome(
    returncode: int,
    vamos_log_path: Path,
    stderr_path: Path,
) -> ProbeClassification:
    if returncode == 0:
        return ProbeClassification("completed", True)

    log_text = _read_probe_text(vamos_log_path)
    stderr_text = _read_probe_text(stderr_path)

    for detector in (
        lambda: _detect_missing_library(log_text),
        lambda: _detect_path_setup_failure(log_text),
        lambda: _detect_vamos_error(stderr_text),
    ):
        classification = detector()
        if classification is not None:
            return classification

    return ProbeClassification("app_failed", False)


def _read_probe_text(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def _detect_missing_library(log_text: str) -> ProbeClassification | None:
    match = re.search(r"OpenLibrary: '([^']+)' V\d+ -> 000000", log_text)
    if match is None:
        return None
    missing_library = match.group(1)
    return ProbeClassification(
        "missing_library",
        False,
        {
            "missing_library": missing_library,
            "diagnostic_summary": f"First missing library: {missing_library}",
        },
    )


def _detect_path_setup_failure(log_text: str) -> ProbeClassification | None:
    if "path setup failed!" not in log_text:
        return None
    return ProbeClassification(
        "path_setup_failed",
        False,
        {"diagnostic_summary": "Vamos failed during path setup."},
    )


def _detect_vamos_error(stderr_text: str) -> ProbeClassification | None:
    if "Traceback" not in stderr_text:
        return None
    return ProbeClassification(
        "vamos_error",
        False,
        {"diagnostic_summary": "Vamos raised a Python traceback during launch."},
    )


@contextlib.contextmanager
def _probe_timeout(timeout_seconds: int):
    if timeout_seconds <= 0:
        yield
        return

    def handle_timeout(signum, frame):  # pragma: no cover - signal callback
        raise ProbeTimeoutError()

    previous_handler = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, handle_timeout)
    signal.setitimer(signal.ITIMER_REAL, timeout_seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
