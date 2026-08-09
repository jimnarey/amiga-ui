"""Project command-line interface."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .assets import asset_inventory, project_relative, required_asset_checks
from .config import DEFAULT_PROBE_TIMEOUT_SECONDS, PROJECT_ROOT
from .host.gui_smoke import run_smoke_gui
from .host.xvfb import run_with_xvfb
from .run_artifacts import create_run_artifacts, write_json
from .targets import ProbeTarget, get_probe_target


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
    checks: list[dict[str, Any]] = []

    def add_check(label: str, ok: bool, detail: str) -> None:
        checks.append({"label": label, "ok": ok, "detail": detail})

    python_ok = sys.version_info >= (3, 12)
    add_check(
        "Python 3.12 or newer",
        python_ok,
        f"running {sys.version.split()[0]}",
    )

    for module_name in ("PySide6", "amitools"):
        try:
            __import__(module_name)
        except Exception as exc:  # pragma: no cover - exercised by manual preflight
            add_check(f"Python import: {module_name}", False, str(exc))
        else:
            add_check(f"Python import: {module_name}", True, "import succeeded")

    for label, command in (
        ("7z command available", ["7z", "-h"]),
        ("Xvfb command available", ["Xvfb", "-help"]),
    ):
        try:
            completed = subprocess.run(
                command,
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            ok = completed.returncode == 0
            detail = f"exit code {completed.returncode}"
        except FileNotFoundError:
            ok = False
            detail = "command not found"
        add_check(label, ok, detail)

    for asset in required_asset_checks():
        status_label = f"Asset: {asset.label}"
        detail = project_relative(asset.path)
        if not asset.exists and asset.required:
            add_check(status_label, False, f"missing required file at {detail}")
        elif not asset.exists:
            add_check(status_label, True, f"optional file not present at {detail}")
        else:
            add_check(status_label, True, f"found at {detail}")

    inventories = asset_inventory()
    payload = {
        "ok": all(item["ok"] for item in checks),
        "checks": checks,
        "inventory": [asdict(entry) | {"directory": project_relative(entry.directory)} for entry in inventories],
    }

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print("Checking project environment...")
        for item in checks:
            prefix = "[ok]" if item["ok"] else "[missing]"
            print(f"{prefix} {item['label']}: {item['detail']}")
        print()
        print("Asset inventory:")
        for entry in inventories:
            print(
                f"- {entry.label}: {entry.present_count} present, "
                f"{entry.placeholder_count} placeholders in {project_relative(entry.directory)}"
            )
        if not payload["ok"]:
            print()
            print("Missing dependencies or required assets:")
            for item in checks:
                if not item["ok"]:
                    print(f"- {item['label']}: {item['detail']}")

    return 0 if payload["ok"] else 1


def _run_smoke_gui(args: argparse.Namespace) -> int:
    if args.direct:
        return run_smoke_gui(duration_ms=args.duration_ms)

    command = [
        sys.executable,
        "-m",
        "amiga_ui",
        "smoke-gui",
        "--direct",
        "--duration-ms",
        str(args.duration_ms),
    ]
    completed = run_with_xvfb(command, capture_output=False, text=True)
    return completed.returncode


def _run_probe(args: argparse.Namespace) -> int:
    target = get_probe_target(args.target)
    artifacts = create_run_artifacts("probe", target.name)

    invocation_base = {
        "command": "probe",
        "target": target.name,
        "direct": bool(args.direct),
        "timeout_seconds": args.timeout,
        "artifact_root": project_relative(artifacts.root),
    }

    preflight_errors = _probe_preflight_errors(target)
    if preflight_errors:
        result = {
            "status": "missing_asset",
            "ok": False,
            "target": target.name,
            "errors": preflight_errors,
            "artifact_root": project_relative(artifacts.root),
        }
        write_json(artifacts.invocation_path, invocation_base)
        write_json(artifacts.result_path, result)
        artifacts.stdout_path.write_text("", encoding="utf-8")
        artifacts.stderr_path.write_text("", encoding="utf-8")
        print(f"Probe aborted before launch. Artifacts: {project_relative(artifacts.root)}")
        for error in preflight_errors:
            print(f"- {error}")
        return 1

    runtime_paths = _prepare_probe_runtime(artifacts.runtime_root)
    command = _build_probe_command(target, runtime_paths, artifacts.vamos_log_path)
    write_json(
        artifacts.invocation_path,
        invocation_base
        | {
            "vamos_command": command,
            "runtime": {key: project_relative(value) for key, value in runtime_paths.items()},
        },
    )

    try:
        completed = _execute_probe(command, args.timeout, direct=args.direct)
        artifacts.stdout_path.write_text(completed.stdout, encoding="utf-8")
        artifacts.stderr_path.write_text(completed.stderr, encoding="utf-8")
        classification = _classify_probe_outcome(
            completed.returncode,
            artifacts.vamos_log_path,
            artifacts.stderr_path,
        )
        result = {
            "status": classification["status"],
            "ok": classification["ok"],
            "target": target.name,
            "returncode": completed.returncode,
            "artifact_root": project_relative(artifacts.root),
            "stdout_path": project_relative(artifacts.stdout_path),
            "stderr_path": project_relative(artifacts.stderr_path),
            "vamos_log_path": project_relative(artifacts.vamos_log_path),
        }
        result.update(classification["details"])
        write_json(artifacts.result_path, result)
        print(f"Probe finished with status {result['status']}.")
        if "diagnostic_summary" in result:
            print(result["diagnostic_summary"])
        print(f"Artifacts: {project_relative(artifacts.root)}")
        return 0 if result["ok"] else 1
    except subprocess.TimeoutExpired:
        artifacts.stdout_path.write_text("", encoding="utf-8")
        artifacts.stderr_path.write_text("", encoding="utf-8")
        result = {
            "status": "timeout",
            "ok": False,
            "target": target.name,
            "timeout_seconds": args.timeout,
            "artifact_root": project_relative(artifacts.root),
            "stdout_path": project_relative(artifacts.stdout_path),
            "stderr_path": project_relative(artifacts.stderr_path),
            "vamos_log_path": project_relative(artifacts.vamos_log_path),
        }
        write_json(artifacts.result_path, result)
        print(f"Probe timed out after {args.timeout}s. Artifacts: {project_relative(artifacts.root)}")
        return 1


def _probe_preflight_errors(target: ProbeTarget) -> list[str]:
    errors: list[str] = []
    if not target.host_binary_path.is_file():
        errors.append(f"missing target binary: {project_relative(target.host_binary_path)}")
    if _find_vamos_binary() is None:
        errors.append("unable to locate the vamos executable in the current Python environment")
    return errors


def _prepare_probe_runtime(runtime_root: Path) -> dict[str, Path]:
    sys_root = runtime_root / "sys"
    work_root = runtime_root / "work"
    volumes_root = runtime_root / "volumes"
    for path in (sys_root, work_root, volumes_root):
        path.mkdir(parents=True, exist_ok=True)
    for relative_dir in ("C", "S", "Libs", "Devs", "L", "T"):
        (sys_root / relative_dir).mkdir(exist_ok=True)
    (sys_root / "S" / "startup-sequence").write_text(
        "; amiga-ui probe runtime\n",
        encoding="utf-8",
    )
    return {
        "sys_root": sys_root,
        "work_root": work_root,
        "volumes_root": volumes_root,
    }


def _build_probe_command(
    target: ProbeTarget,
    runtime_paths: dict[str, Path],
    vamos_log_path: Path,
) -> list[str]:
    vamos_binary = _find_vamos_binary()
    if vamos_binary is None:
        raise RuntimeError("vamos executable not found")

    sys_root = runtime_paths["sys_root"]
    work_root = runtime_paths["work_root"]
    volumes_root = runtime_paths["volumes_root"]
    return [
        str(vamos_binary),
        "-S",
        "--vols-base-dir",
        str(volumes_root),
        "--auto-volumes",
        "off",
        "--auto-assigns",
        "off",
        "-V",
        "root:/",
        "-V",
        f"app:{target.app_volume_root}",
        "-V",
        f"sys:{sys_root}",
        "-V",
        f"work:{work_root}",
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


def _execute_probe(command: list[str], timeout: int, *, direct: bool) -> subprocess.CompletedProcess[str]:
    if direct:
        return subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    return run_with_xvfb(
        command,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _classify_probe_outcome(
    returncode: int,
    vamos_log_path: Path,
    stderr_path: Path,
) -> dict[str, Any]:
    if returncode == 0:
        return {"status": "completed", "ok": True, "details": {}}

    log_text = ""
    stderr_text = ""
    if vamos_log_path.is_file():
        log_text = vamos_log_path.read_text(encoding="utf-8")
    if stderr_path.is_file():
        stderr_text = stderr_path.read_text(encoding="utf-8")

    missing_library = _find_missing_library(log_text)
    if missing_library is not None:
        return {
            "status": "missing_library",
            "ok": False,
            "details": {
                "missing_library": missing_library,
                "diagnostic_summary": f"First missing library: {missing_library}",
            },
        }

    if "path setup failed!" in log_text:
        return {
            "status": "path_setup_failed",
            "ok": False,
            "details": {"diagnostic_summary": "Vamos failed during path setup."},
        }

    if "Traceback" in stderr_text:
        return {
            "status": "vamos_error",
            "ok": False,
            "details": {"diagnostic_summary": "Vamos raised a Python traceback during launch."},
        }

    return {"status": "app_failed", "ok": False, "details": {}}


def _find_missing_library(log_text: str) -> str | None:
    match = re.search(r"OpenLibrary: '([^']+)' V\d+ -> 000000", log_text)
    if match is None:
        return None
    return match.group(1)


def _find_vamos_binary() -> Path | None:
    candidate = Path(sys.executable).with_name("vamos")
    if candidate.is_file():
        return candidate
    virtual_env = sys.prefix
    virtual_env_candidate = Path(virtual_env) / "bin" / "vamos"
    if virtual_env_candidate.is_file():
        return virtual_env_candidate
    which_result = shutil.which("vamos")
    if which_result is None:
        return None
    return Path(which_result)


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
