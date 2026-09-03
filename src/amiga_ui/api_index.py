"""Generate a local Amiga API index from FD tables and fetched AutoDocs."""

from __future__ import annotations

import argparse
import inspect
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from amitools.fd import read_lib_fd
from amitools.vamos.libcore.impl import LibImplScanner

from .assets import project_relative
from .config import ASSETS_ROOT

DEFAULT_DOCS_ROOT = ASSETS_ROOT / "docs"
DEFAULT_OUTPUT_JSON = ASSETS_ROOT / "generated" / "api-index.json"
DEFAULT_OUTPUT_MARKDOWN = ASSETS_ROOT / "generated" / "api-index.md"
TARGET_OS_FAMILY = "classic-m68k-workbench"
TARGET_VERSION_FLOOR = 39
TARGET_VERSION_BASELINE = 40
VERSION_MARKER_RE = re.compile(r"functions in V(?P<version>\d+) or higher", re.IGNORECASE)
FD_FUNCTION_RE = re.compile(r"^(?P<name>[A-Za-z_][A-Za-z0-9_]*)\(")


@dataclass(frozen=True)
class ApiTarget:
    """One library or device to include in the generated API index."""

    name: str
    role: str
    why: str


@dataclass(frozen=True)
class ApiFunction:
    """One function entry from a library/device FD table."""

    name: str
    index: int
    bias: int
    args: list[dict[str, str]]
    private: bool
    standard_trap: bool
    introduced_version: int | None
    target_status: str
    implemented: bool
    implementation_status: str
    ui_obligation: str
    implementation_file: str | None
    autodoc_path: str | None
    autodoc_url: str


@dataclass(frozen=True)
class ApiLibrary:
    """API index entry for one library or device."""

    name: str
    role: str
    why: str
    fd_source: str | None
    function_count: int
    implemented_count: int
    functions: list[ApiFunction]
    warnings: list[str]


DEFAULT_TARGETS: tuple[ApiTarget, ...] = (
    ApiTarget("exec.library", "core-runtime", "tasks, signals, memory, libraries, messages"),
    ApiTarget("dos.library", "filesystem-process", "paths, locks, file handles, process-facing IO"),
    ApiTarget("intuition.library", "host-ui-required", "screens, windows, menus, gadgets, requesters"),
    ApiTarget("graphics.library", "host-ui-required", "rastports, drawing, text, fonts, colors"),
    ApiTarget("layers.library", "host-ui-required", "window/layer clipping and refresh semantics"),
    ApiTarget("gadtools.library", "host-ui-required", "standard gadgets, menus, visual info, refresh"),
    ApiTarget("asl.library", "host-ui-required", "file/font/screen requesters"),
    ApiTarget("icon.library", "workbench-data-ui", "DiskObject metadata and icon image data"),
    ApiTarget("workbench.library", "workbench-integration", "Workbench startup, AppMessages, drawers, tool state"),
    ApiTarget("utility.library", "tag-support", "TagItem parsing and helper routines"),
    ApiTarget("iffparse.library", "structured-data", "IFF prefs and chunk parsing"),
    ApiTarget("diskfont.library", "host-ui-required", "font discovery and text rendering inputs"),
    ApiTarget("locale.library", "support", "catalogs, locale formatting, localized strings"),
    ApiTarget("datatypes.library", "workbench-data-ui", "Workbench-style typed content loading"),
    ApiTarget("commodities.library", "workbench-integration", "commodity broker and hotkey integration"),
    ApiTarget("keymap.library", "input", "keyboard mapping and text input semantics"),
    ApiTarget("rexxsyslib.library", "automation", "ARexx integration used by some Workbench software"),
    ApiTarget("bullet.library", "host-ui-required", "outline fonts and text rendering support"),
    ApiTarget("timer.device", "device-time", "system time and timer requests"),
    ApiTarget("input.device", "input", "keyboard and pointer event stream"),
    ApiTarget("console.device", "io", "console windows and text IO"),
    ApiTarget("clipboard.device", "workbench-integration", "clipboard interoperability"),
)

HOST_UI_REQUIRED_LIBRARIES = {
    "intuition.library",
    "graphics.library",
    "layers.library",
    "gadtools.library",
    "asl.library",
    "diskfont.library",
    "bullet.library",
}

WORKBENCH_UI_LIBRARIES = {"icon.library", "workbench.library", "datatypes.library", "commodities.library"}

HOST_UI_KEYWORDS = (
    "window",
    "screen",
    "gadget",
    "menu",
    "request",
    "requester",
    "visualinfo",
    "visual",
    "refresh",
    "display",
    "border",
    "image",
    "rastport",
    "draw",
    "rect",
    "text",
    "font",
    "pen",
    "color",
    "palette",
    "layer",
)

STATEFUL_RUNTIME_KEYWORDS = (
    "lock",
    "currentdir",
    "open",
    "read",
    "write",
    "seek",
    "match",
    "file",
    "loadseg",
    "tag",
    "chunk",
    "iff",
    "time",
    "signal",
    "msg",
    "port",
)


def build_api_index(
    target_names: list[str] | None = None,
    *,
    docs_root: Path = DEFAULT_DOCS_ROOT,
) -> dict[str, Any]:
    """Build the complete serializable API index payload."""

    selected_targets = _select_targets(target_names)
    fd_dirs = _discover_fd_dirs(docs_root)
    libraries = [build_library_entry(target, docs_root=docs_root, fd_dirs=fd_dirs) for target in selected_targets]
    return {
        "generated_by": "amiga_ui.api_index",
        "docs_root": project_relative(docs_root),
        "target": {
            "os_family": TARGET_OS_FAMILY,
            "version_floor": TARGET_VERSION_FLOOR,
            "version_baseline": TARGET_VERSION_BASELINE,
            "policy": (
                "Prefer documented classic m68k Workbench/AmigaOS 3.0-3.1 API behavior. "
                "Treat later classic APIs as explicit compatibility cases, not default assumptions."
            ),
        },
        "libraries": [asdict(library) for library in libraries],
    }


def build_library_entry(target: ApiTarget, *, docs_root: Path, fd_dirs: list[Path]) -> ApiLibrary:
    """Build one API library entry."""

    fd, fd_source = _read_function_table(target.name, fd_dirs)
    warnings: list[str] = []
    functions: list[ApiFunction] = []
    implementation_statuses, implementation_file = _implementation_statuses(target.name, fd)
    introduced_versions = _fd_introduced_versions(fd_source) if fd_source else {}

    if fd is None:
        warnings.append("No FD table found in fetched NDK material or amitools bundled data")
    else:
        for func in sorted(fd.get_funcs(), key=lambda item: item.get_bias()):
            name = str(func.get_name())
            status = implementation_statuses.get(name, "missing")
            implemented = status == "valid"
            introduced_version = introduced_versions.get(name)
            functions.append(
                ApiFunction(
                    name=name,
                    index=int(func.get_index()),
                    bias=int(func.get_bias()),
                    args=[{"name": str(arg), "register": str(reg)} for arg, reg in (func.get_args() or [])],
                    private=bool(func.is_private()),
                    standard_trap=bool(func.is_std()),
                    introduced_version=introduced_version,
                    target_status=classify_target_status(introduced_version),
                    implemented=implemented,
                    implementation_status=status,
                    ui_obligation=classify_ui_obligation(target.name, name),
                    implementation_file=project_relative(implementation_file)
                    if status in {"valid", "error", "invalid"} and implementation_file
                    else None,
                    autodoc_path=_autodoc_path(docs_root, target.name, name),
                    autodoc_url=_autodoc_url(target.name, name),
                )
            )

    return ApiLibrary(
        name=target.name,
        role=target.role,
        why=target.why,
        fd_source=project_relative(fd_source) if fd_source else None,
        function_count=len(functions),
        implemented_count=sum(1 for func in functions if func.implemented),
        functions=functions,
        warnings=warnings,
    )


def classify_ui_obligation(library_name: str, function_name: str) -> str:
    """Classify whether an API entry is likely to require visible host behavior."""

    if function_name.startswith("_"):
        return "standard-trap"

    lowered = function_name.lower()
    if library_name in HOST_UI_REQUIRED_LIBRARIES and any(keyword in lowered for keyword in HOST_UI_KEYWORDS):
        return "host-ui-required"
    if library_name in WORKBENCH_UI_LIBRARIES and any(keyword in lowered for keyword in HOST_UI_KEYWORDS):
        return "workbench-visible-state"
    if any(keyword in lowered for keyword in STATEFUL_RUNTIME_KEYWORDS):
        return "stateful-runtime-required"
    if library_name in HOST_UI_REQUIRED_LIBRARIES:
        return "likely-ui-support"
    if library_name in WORKBENCH_UI_LIBRARIES:
        return "workbench-support"
    return "support"


def classify_target_status(introduced_version: int | None) -> str:
    """Classify an API against the repository's classic Workbench 3.0/3.1 target."""

    if introduced_version is None:
        return "baseline-or-unknown"
    if introduced_version <= TARGET_VERSION_BASELINE:
        return "classic-baseline"
    if introduced_version <= 45:
        return "later-classic-optional"
    if introduced_version <= 47:
        return "later-classic-reference"
    return "out-of-target"


def write_api_index(payload: dict[str, Any], json_path: Path, markdown_path: Path) -> None:
    """Write JSON and Markdown renderings of the API index."""

    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(payload), encoding="utf-8")


def render_markdown(payload: dict[str, Any]) -> str:
    """Render a compact Markdown API index for humans and agents."""

    lines = [
        "# Generated Amiga API Index",
        "",
        "This file is generated by `uv run python tools/generate_api_index.py`.",
        "It is local reference output and should be regenerated when FD tables, AutoDocs, or repo library implementations change.",
        "",
    ]
    for library in payload["libraries"]:
        lines.extend(
            [
                f"## {library['name']}",
                "",
                f"- Role: `{library['role']}`",
                f"- Why: {library['why']}",
                f"- FD source: `{library['fd_source'] or 'missing'}`",
                f"- Implemented: {library['implemented_count']} / {library['function_count']}",
                "",
            ]
        )
        if library["warnings"]:
            for warning in library["warnings"]:
                lines.append(f"- Warning: {warning}")
            lines.append("")
            continue
        lines.append(
            "| Index | Bias | Function | Args | Min version | Target | Obligation | Impl status | Impl file | AutoDoc |"
        )
        lines.append("| --- | ---: | --- | --- | ---: | --- | --- | --- | --- | --- |")
        for func in library["functions"]:
            args = ", ".join(f"{arg['name']}[{arg['register']}]" for arg in func["args"])
            impl_file = func["implementation_file"] or ""
            impl_status = func.get("implementation_status", "unknown")
            autodoc = func["autodoc_path"] or func["autodoc_url"]
            min_version = func.get("introduced_version")
            min_version_text = "" if min_version is None else str(min_version)
            lines.append(
                f"| {func['index']} | {func['bias']} | `{func['name']}` | {args} | "
                f"{min_version_text} | `{func.get('target_status', 'baseline-or-unknown')}` | "
                f"`{func['ui_obligation']}` | `{impl_status}` | {impl_file} | {autodoc} |"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def load_api_index(path: Path = DEFAULT_OUTPUT_JSON) -> dict[str, Any] | None:
    """Load a generated API index if present."""

    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def api_lookup(payload: dict[str, Any] | None) -> dict[tuple[str, int], dict[str, Any]]:
    """Return lookup by (library/device name, bias)."""

    lookup: dict[tuple[str, int], dict[str, Any]] = {}
    if not payload:
        return lookup
    for library in payload.get("libraries", []):
        lib_name = library.get("name")
        if not isinstance(lib_name, str):
            continue
        for func in library.get("functions", []):
            bias = func.get("bias")
            if isinstance(bias, int):
                lookup[(lib_name, bias)] = func
    return lookup


def _select_targets(target_names: list[str] | None) -> list[ApiTarget]:
    if not target_names:
        return list(DEFAULT_TARGETS)
    wanted = {_normalize_target_name(name) for name in target_names}
    targets = [target for target in DEFAULT_TARGETS if target.name in wanted]
    missing = sorted(wanted - {target.name for target in targets})
    targets.extend(ApiTarget(name, "custom", "requested explicitly") for name in missing)
    return targets


def _normalize_target_name(name: str) -> str:
    lowered = name.strip().lower()
    if lowered.endswith(".library") or lowered.endswith(".device"):
        return lowered
    if lowered in {"timer", "input", "console", "clipboard"}:
        return f"{lowered}.device"
    return f"{lowered}.library"


def _read_function_table(library_name: str, fd_dirs: list[Path]) -> tuple[Any | None, Path | None]:
    fd_name = _fd_filename(library_name)
    for fd_dir in fd_dirs:
        fd_path = fd_dir / fd_name
        if not fd_path.is_file():
            continue
        fd = read_lib_fd(library_name, fd_dir=str(fd_dir))
        if fd is not None:
            return fd, fd_path

    fd = read_lib_fd(library_name)
    if fd is None:
        return None, None
    try:
        import amitools

        source = Path(amitools.__file__).resolve().parent / "data" / "fd" / fd_name
    except Exception:  # pragma: no cover - import path diagnostic only
        source = None
    return fd, source


def _fd_filename(library_name: str) -> str:
    if library_name.endswith(".library"):
        return library_name.removesuffix(".library") + "_lib.fd"
    if library_name.endswith(".device"):
        return library_name.removesuffix(".device") + "_lib.fd"
    return library_name + "_lib.fd"


def _discover_fd_dirs(docs_root: Path) -> list[Path]:
    candidates: list[Path] = []
    ndk_root = docs_root / "ndk"
    if ndk_root.is_dir():
        for path in sorted(ndk_root.rglob("*")):
            if (
                path.is_dir()
                and path.name.lower() == "fd"
                and any(child.is_file() and child.suffix.lower() == ".fd" for child in path.iterdir())
            ):
                candidates.append(path)
    return candidates


def _fd_introduced_versions(fd_path: Path) -> dict[str, int]:
    """Return per-function introduction versions parsed from FD comment blocks."""

    versions: dict[str, int] = {}
    current_version: int | None = None
    for raw_line in fd_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        marker = VERSION_MARKER_RE.search(line)
        if marker:
            current_version = int(marker.group("version"))
            continue
        if not line or line.startswith("*") or line.startswith("##"):
            continue
        func = FD_FUNCTION_RE.match(line)
        if func and current_version is not None:
            versions[func.group("name")] = current_version
    return versions


def _implementation_statuses(library_name: str, fd: Any | None) -> tuple[dict[str, str], Path | None]:
    if fd is None:
        return {}, None
    try:
        from .vamos.extensions import get_library_impl_overrides
    except Exception:  # pragma: no cover - diagnostic fallback only
        return {}, None

    impl_class = get_library_impl_overrides().get(library_name)
    if impl_class is None:
        return {}, None

    impl_file = Path(inspect.getfile(impl_class)).resolve()
    scan = LibImplScanner().scan(library_name, impl_class(), fd, True)
    statuses: dict[str, str] = {}
    statuses.update({name: "valid" for name in scan.get_valid_func_names()})
    statuses.update({name: "error" for name in scan.get_error_func_names()})
    statuses.update({name: "invalid" for name in scan.get_invalid_func_names()})
    statuses.update({name: "missing" for name in scan.get_missing_func_names()})
    return statuses, impl_file


def _autodoc_path(docs_root: Path, library_name: str, function_name: str) -> str | None:
    for candidate in (
        docs_root / "amigaos3-developer" / "autodocs" / library_name / f"{function_name}.html",
        docs_root / "amigaos3-developer" / f"{function_name}.html",
    ):
        if candidate.is_file():
            return project_relative(candidate)
    return None


def _autodoc_url(library_name: str, function_name: str) -> str:
    return f"https://developer.amigaos3.net/autodocs/{library_name}/{function_name}.html"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docs-root", type=Path, default=DEFAULT_DOCS_ROOT)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_OUTPUT_MARKDOWN)
    parser.add_argument("--target", action="append", default=[], help="library/device to index; may be repeated")
    parser.add_argument("--print-json", action="store_true", help="print the index instead of writing files")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    payload = build_api_index(args.target or None, docs_root=args.docs_root)
    if args.print_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        write_api_index(payload, args.json_output, args.markdown_output)
        print(f"Wrote {project_relative(args.json_output)}")
        print(f"Wrote {project_relative(args.markdown_output)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
