#!/usr/bin/env python3
"""PostToolUse hook for the /lesson plugin.

Reads a Claude Code hook event from stdin. If the project under the event's
cwd has an active lesson session (marker file present), append one compressed
event line to arc.jsonl, bump the counter, and — at threshold — emit an
additionalContext reminder telling Claude to spawn the lesson-compress subagent.

Each event is tagged with `significant: true/false` using cheap Python heuristics
so the compression subagent can prioritise which events to promote to graph nodes
without re-reading everything.

Design notes:
- This hook is always installed (via the plugin manifest) but is a cheap
  no-op in any project that does not have .claude/lessons/active-session.
- The hook does NOT summarize or call any LLM. It only appends, counts, and signals.
- The hook must never crash: any exception should exit 0 silently so it
  cannot block the user's real tool calls.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

COMPRESS_EVERY = int(os.environ.get("LESSON_COMPRESS_EVERY", "25"))
ARGS_CAP = 500
RESULT_CAP = 1000

# Tools whose invocation is always worth noting in the graph (user changed something).
_SIGNIFICANT_TOOLS = {"Edit", "Write", "NotebookEdit"}

# Substrings that, when present in a Bash result, indicate an error or important discovery.
_SIGNIFICANT_BASH_PATTERNS = [
    "error",
    "failed",
    "not found",
    "no such file",
    "permission denied",
    "mismatch",
    "cannot",
    "unable to",
    "exception",
    "traceback",
    "fatal",
    "warning:",
    "refused",
    "denied",
    "unrecognized",
    "invalid",
    "undefined",
    "missing",
]

_VERSION_RE = re.compile(r"\b\d+\.\d+[\.\d]*\b")


def _has_version_string(text: str) -> bool:
    return bool(_VERSION_RE.search(text))


def _is_significant(tool_name: str, result_text: str, is_error: bool) -> bool:
    """Return True if this event is likely worth promoting to a graph node.

    Heuristics only — no LLM. The compression subagent makes the final call;
    this flag is a prioritisation hint, not a hard filter.
    """
    if is_error:
        return True
    if tool_name in _SIGNIFICANT_TOOLS:
        return True
    if tool_name == "Bash":
        lower = result_text.lower()
        if any(p in lower for p in _SIGNIFICANT_BASH_PATTERNS):
            return True
        # Short output containing version strings suggests a version comparison
        # or state-check — common pivotal moments in debugging sessions.
        if len(result_text) < 500 and _has_version_string(result_text):
            return True
    return False


def _safe_str(value) -> str:
    try:
        if isinstance(value, (dict, list)):
            return json.dumps(value, default=str, ensure_ascii=False)
        return str(value)
    except Exception:
        return "<unserializable>"


def _extract_result(tool_response) -> tuple[str, bool]:
    if tool_response is None:
        return "", False
    if isinstance(tool_response, dict):
        is_error = bool(
            tool_response.get("is_error")
            or tool_response.get("isError")
            or tool_response.get("error")
        )
        content = (
            tool_response.get("content")
            or tool_response.get("output")
            or tool_response.get("stdout")
            or tool_response.get("result")
            or ""
        )
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict):
                    parts.append(item.get("text") or _safe_str(item))
                else:
                    parts.append(_safe_str(item))
            content = "\n".join(parts)
        return _safe_str(content), is_error
    return _safe_str(tool_response), False


def main() -> int:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return 0
        event = json.loads(raw)
    except Exception:
        return 0

    cwd = event.get("cwd") or os.getcwd()
    lessons_dir = Path(cwd) / ".claude" / "lessons"
    marker = lessons_dir / "active-session"
    if not marker.exists():
        return 0

    try:
        slug = marker.read_text().strip()
    except Exception:
        return 0
    if not slug:
        return 0

    session_dir = lessons_dir / "sessions" / slug
    if not session_dir.exists():
        return 0

    arc_log = session_dir / "arc.jsonl"
    counter_file = session_dir / "counter"

    tool_name = event.get("tool_name") or "unknown"
    tool_input = event.get("tool_input") or {}
    tool_response = event.get("tool_response")

    args_summary = _safe_str(tool_input)[:ARGS_CAP]
    result_head, is_error = _extract_result(tool_response)
    result_head = result_head[:RESULT_CAP]

    significant = _is_significant(tool_name, result_head, is_error)

    entry = {
        "ts": time.time(),
        "tool": tool_name,
        "args": args_summary,
        "result_head": result_head,
        "is_error": is_error,
        "significant": significant,
    }

    try:
        with arc_log.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        return 0

    count = 0
    if counter_file.exists():
        try:
            count = int((counter_file.read_text().strip() or "0"))
        except Exception:
            count = 0
    count += 1

    try:
        counter_file.write_text(str(count))
    except Exception:
        return 0

    if count >= COMPRESS_EVERY:
        try:
            counter_file.write_text("0")
        except Exception:
            pass
        reminder = (
            f"[/lesson] Tracked session '{slug}' has accumulated {count} raw events "
            f"since the last compression. Before doing anything else, spawn a Task "
            f"subagent of type 'lesson-compress' with this prompt:\n\n"
            f"    Compress the /lesson arc log at {session_dir}. Read arc.jsonl and "
            f"extend session_graph.json with new nodes and edges derived from the events. "
            f"Prioritise events where significant=true. Archive arc.jsonl to "
            f"arc.jsonl.archive.N and reset it. Follow the lesson-compress skill "
            f"instructions exactly. Report one line when done.\n\n"
            f"This keeps the main context lean. Do not read arc.jsonl yourself."
        )
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": reminder,
            }
        }
        try:
            print(json.dumps(output))
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
