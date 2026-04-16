#!/usr/bin/env python3
"""PostToolUse hook for the /lesson plugin.

Reads a Claude Code hook event from stdin. If the project under the event's
cwd has an active lesson session (marker file present), append one compressed
event line to arc.jsonl, bump the counter, and — at threshold — emit an
additionalContext reminder telling Claude to spawn the lesson-compress subagent.

Design notes:
- This hook is always installed (via the plugin manifest) but is a cheap
  no-op in any project that does not have .claude/lessons/active-session.
- The hook does NOT summarize. Summarization is a Claude job done via the
  compression subagent. The hook just appends truncated raw events.
- The hook must never crash: any exception should exit 0 silently so it
  cannot block the user's real tool calls.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

COMPRESS_EVERY = int(os.environ.get("LESSON_COMPRESS_EVERY", "25"))
ARGS_CAP = 500
RESULT_CAP = 1000


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

    entry = {
        "ts": time.time(),
        "tool": tool_name,
        "args": args_summary,
        "result_head": result_head,
        "is_error": is_error,
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
            f"    Compress the /lesson arc log at {session_dir}. Merge arc.jsonl "
            f"into summary.md, archive the consumed raw events to arc.jsonl.archive.N, "
            f"then write a fresh empty arc.jsonl. Follow the lesson-compress skill "
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
