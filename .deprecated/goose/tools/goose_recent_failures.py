#!/usr/bin/env python3
"""Summarize recent Goose tool failures for retry guidance."""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
from pathlib import Path
from typing import Any

DEFAULT_DB = Path("/home/runuser/.local/share/goose/sessions/sessions.db")
MAX_TEXT = 900


def compact(value: Any, limit: int = 500) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        text = value
    else:
        try:
            text = json.dumps(value, ensure_ascii=True, sort_keys=True)
        except TypeError:
            text = str(value)
    text = re.sub(r"\s+", " ", text).strip()
    return text[: limit - 3] + "..." if len(text) > limit else text


def load_json(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return []


def candidate_sessions(con: sqlite3.Connection, cwd: Path) -> list[str]:
    env_session = os.environ.get("GOOSE_SESSION_ID") or os.environ.get("GOOSE_SESSION")
    if env_session:
        row = con.execute(
            "select id from sessions where id = ?",
            (env_session,),
        ).fetchone()
        if row:
            return [str(row[0])]

    cwd_text = str(cwd)
    rows = con.execute(
        """
        select id, working_dir
        from sessions
        order by updated_at desc, created_at desc
        limit 50
        """
    ).fetchall()
    exact = [str(session_id) for session_id, workdir in rows if workdir == cwd_text]
    fuzzy = [
        str(session_id)
        for session_id, workdir in rows
        if str(session_id) not in exact and (cwd_text.endswith(str(workdir)) or str(workdir).endswith(cwd.name))
    ]
    fallback = [str(session_id) for session_id, _workdir in rows]
    seen: set[str] = set()
    candidates: list[str] = []
    for session_id in [*exact, *fuzzy, *fallback]:
        if session_id not in seen:
            candidates.append(session_id)
            seen.add(session_id)
    return candidates


def content_text(value: Any) -> str:
    if isinstance(value, dict):
        parts: list[str] = []
        for item in value.get("content", []) or []:
            if isinstance(item, dict):
                text = item.get("text") or item.get("thinking")
                if text:
                    parts.append(str(text))
        if parts:
            return "\n".join(parts)
        if "error" in value:
            return str(value["error"])
    return compact(value, MAX_TEXT)


def is_failed_response(tool_result: dict[str, Any]) -> bool:
    if tool_result.get("status") == "error":
        return True
    value = tool_result.get("value")
    if not isinstance(value, dict):
        return False
    if value.get("isError") is True:
        return True
    structured = value.get("structuredContent")
    if isinstance(structured, dict):
        exit_code = structured.get("exit_code")
        return isinstance(exit_code, int) and exit_code != 0
    return False


def response_error_text(tool_result: dict[str, Any]) -> str:
    if tool_result.get("status") == "error":
        return str(tool_result.get("error", "unknown tool error"))
    value = tool_result.get("value")
    if isinstance(value, dict):
        structured = value.get("structuredContent")
        chunks: list[str] = []
        if isinstance(structured, dict):
            for key in ("stderr", "stdout"):
                text = structured.get(key)
                if text:
                    chunks.append(str(text))
        text = content_text(value)
        if text:
            chunks.append(text)
        return "\n".join(dict.fromkeys(chunks))
    return compact(tool_result, MAX_TEXT)


def recovery_hint(tool_name: str, error_text: str) -> str | None:
    lower = error_text.lower()
    if "tool '" in lower and "not found" in lower:
        available = ""
        match = re.search(r"Available tools: \[([^\]]+)\]", error_text)
        if match:
            available = f" Available tools reported by Goose: `{match.group(1)}`."
        return (
            "Use one of Goose's actual tools instead of inventing a tool name. "
            "For command-line work, use the `shell` tool with the command as "
            "its argument." + available
        )
    if tool_name == "read_image" or "unsupported image format" in lower:
        return (
            "This was not an image file. Inspect source, Markdown, JSON, YAML, "
            "logs, and other text with `shell` commands such as `sed -n`, "
            "`cat`, `grep`, `git grep`, or `find`."
        )
    if "rg: command not found" in lower:
        return (
            "`rg` is unavailable in this container. Install it with "
            "`sudo apt-get update && sudo apt-get install -y ripgrep`, or use "
            "`git grep`, `grep -R`, or `find` through `shell` until installed."
        )
    if "python: command not found" in lower:
        return (
            "Use `python3` or the repo-standard `uv run python`, not bare `python`. "
            "If a small missing command-line dependency blocks progress, install "
            "the required package with passwordless `sudo`."
        )
    if "no such file or directory" in lower:
        return "Verify the path with `pwd`, `ls`, `find`, or `git ls-files` before retrying the command."
    if "no match found for the specified text" in lower:
        return "Refresh the target file contents first, then make a smaller edit against exact current text."
    if "command exited with code" in lower:
        return (
            "Read the command output, inspect the affected files or artifacts, "
            "then change the next command instead of repeating it."
        )
    return None


def collect_failures(
    con: sqlite3.Connection,
    session_id: str,
    limit: int,
) -> list[dict[str, str]]:
    rows = con.execute(
        """
        select role, content_json, created_timestamp
        from messages
        where session_id = ?
        order by created_timestamp asc, id asc
        """,
        (session_id,),
    ).fetchall()

    requests: dict[str, dict[str, Any]] = {}
    failures: list[dict[str, str]] = []

    for _role, content_json, _created in rows:
        content = load_json(content_json)
        if not isinstance(content, list):
            continue
        for item in content:
            if not isinstance(item, dict):
                continue
            item_id = str(item.get("id") or "")
            if item.get("type") == "toolRequest" and item_id:
                value = (item.get("toolCall") or {}).get("value") or {}
                requests[item_id] = value
            elif item.get("type") == "toolResponse" and item_id:
                tool_result = item.get("toolResult") or {}
                if not isinstance(tool_result, dict):
                    continue
                if not is_failed_response(tool_result):
                    continue
                request = requests.get(item_id, {})
                tool_name = str(request.get("name") or "unknown")
                error = response_error_text(tool_result)
                failures.append(
                    {
                        "tool": tool_name,
                        "arguments": compact(request.get("arguments"), 650),
                        "error": compact(error, MAX_TEXT),
                        "hint": recovery_hint(tool_name, error)
                        or "Choose a different inspection or edit strategy before retrying.",
                    }
                )
    return failures[-limit:]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--limit", type=int, default=6)
    parser.add_argument("--cwd", default=os.getcwd())
    parser.add_argument(
        "--session-id",
        help="Inspect one specific Goose session instead of choosing candidates.",
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print("No Goose session database was found; no failures could be inspected.")
        return 0

    try:
        con = sqlite3.connect(str(db_path))
    except sqlite3.Error as exc:
        print(f"Could not open Goose session database: {exc}")
        return 0

    session_ids = (
        [args.session_id]
        if args.session_id
        else candidate_sessions(
            con,
            Path(args.cwd),
        )
    )
    if not session_ids:
        print("No Goose session rows were found; no failures could be inspected.")
        return 0

    inspected: list[str] = []
    failures: list[dict[str, str]] = []
    for session_id in session_ids[:12]:
        inspected.append(session_id)
        failures = collect_failures(con, session_id, args.limit)
        if failures:
            break

    print("## Recent Goose Tool Failures\n")
    print(f"Sessions inspected: `{', '.join(inspected)}`\n")
    if not failures:
        print(
            "No failed tool responses were found in the inspected sessions. "
            "This usually means the run ended before making tool calls, or Goose "
            "reset the active message history before the helper inspected it."
        )
        return 0

    for index, failure in enumerate(failures, 1):
        print(f"{index}. Tool: `{failure['tool']}`")
        if failure["arguments"]:
            print(f"   Arguments: `{failure['arguments']}`")
        print(f"   Error: {failure['error']}")
        print(f"   Recovery: {failure['hint']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
