#!/usr/bin/env python3
"""PostToolUse hook for the /lesson plugin.

Reads a Claude Code hook event from stdin. If the project under the event's
cwd has an active lesson session (marker file present):
  - Appends one compressed event line to arc.jsonl (with significance flag)
  - Updates meta.json token_tracking.arc_input_chars (running total)
  - Bumps the compression counter
  - At threshold: runs `lesson compress` in a detached subprocess — silently

Design notes:
- Always installed but a no-op in projects without .claude/lessons/active-session.
- Never calls any LLM. Appends, counts, and spawns the deterministic compressor.
- Must never crash: any exception exits 0 silently to never block tool calls.
- Must never talk to the main conversation: stdout stays empty in the default
  (silent) mode. Set LESSON_SILENT_HOOK=0 only for debugging — it restores the
  legacy additionalContext reminder and does not spawn the subprocess.
- Significance scoring uses lesson.nlp.scorer.SignificanceScorer when the
  package is installed; falls back to the legacy heuristic otherwise.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

COMPRESS_EVERY = int(os.environ.get("LESSON_COMPRESS_EVERY", "25"))
SILENT_HOOK = os.environ.get("LESSON_SILENT_HOOK", "1") != "0"
ARGS_CAP = 500
RESULT_CAP = 1000

# -----------------------------------------------------------------------
# Significance scoring — package path preferred, heuristic fallback
# -----------------------------------------------------------------------

def _is_significant(tool_name: str, result_text: str, is_error: bool) -> bool:
    """Score one event for significance.

    Tries to use lesson.nlp.scorer.SignificanceScorer for a float score (>0.25
    = significant). Falls back to the inline keyword heuristic if the package
    is not installed — this keeps the hook working before `pip install -e .`.
    """
    try:
        from lesson.graph.schema import RawEvent
        from lesson.nlp.scorer import SignificanceScorer
        ev = RawEvent(tool=tool_name, result_head=result_text, is_error=is_error)
        scorer = SignificanceScorer()
        scorer.fit([ev])
        return scorer.score_one(ev) >= 0.25
    except Exception:
        pass

    # --- Legacy heuristic fallback ---
    _SIGNIFICANT_TOOLS = {"Edit", "Write", "NotebookEdit"}
    _ERROR_PATTERNS = [
        "error", "failed", "not found", "no such file", "permission denied",
        "mismatch", "cannot", "unable to", "exception", "traceback", "fatal",
        "warning:", "refused", "denied", "unrecognized", "invalid", "undefined",
        "missing",
    ]
    _VERSION_RE = re.compile(r"\b\d+\.\d+[\.\d]*\b")

    if is_error:
        return True
    if tool_name in _SIGNIFICANT_TOOLS:
        return True
    if tool_name == "Bash":
        lower = result_text.lower()
        if any(p in lower for p in _ERROR_PATTERNS):
            return True
        if len(result_text) < 500 and _VERSION_RE.search(result_text):
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


def _update_token_tracking(meta_path: Path, chars_added: int) -> None:
    """Increment arc_input_chars in meta.json. Silently skips on any error."""
    try:
        if not meta_path.exists():
            return
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        tt = meta.setdefault("token_tracking", {})
        tt["arc_input_chars"] = tt.get("arc_input_chars", 0) + chars_added
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    except Exception:
        pass


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
    meta_path = session_dir / "meta.json"

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

    entry_json = json.dumps(entry, ensure_ascii=False)

    try:
        with arc_log.open("a", encoding="utf-8") as fh:
            fh.write(entry_json + "\n")
    except Exception:
        return 0

    # Track chars logged for token estimation (chars / 4 ≈ tokens)
    _update_token_tracking(meta_path, len(entry_json) + 1)

    # Bump compression counter
    count = 0
    if counter_file.exists():
        try:
            count = int(counter_file.read_text().strip() or "0")
        except Exception:
            count = 0
    count += 1

    try:
        counter_file.write_text(str(count))
    except Exception:
        return 0

    if count >= COMPRESS_EVERY:
        # Reset counter first — if compression fails, we don't want to retry
        # every single tool call and spam the user / subprocess.
        try:
            counter_file.write_text("0")
        except Exception:
            pass

        project_root = session_dir.parent.parent.parent
        if SILENT_HOOK:
            _spawn_compression(project_root)
        else:
            _emit_legacy_reminder(slug, count, project_root, session_dir)

    return 0


def _spawn_compression(project_root: Path) -> None:
    """Launch `lesson compress` in a detached subprocess. Never blocks, never
    writes to stdout/stderr visible to the model. Silent failure on any error.
    """
    cmd = _resolve_lesson_command()
    if cmd is None:
        return
    try:
        subprocess.Popen(
            cmd + ["compress", "--cwd", str(project_root)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )
    except Exception:
        pass


def _resolve_lesson_command() -> list[str] | None:
    """Locate a way to invoke the `lesson` CLI without disturbing the parent.
    Returns the argv prefix, or None if no resolver is available.
    """
    exe = shutil.which("lesson")
    if exe:
        return [exe]
    try:
        import lesson  # noqa: F401
        return [sys.executable, "-m", "lesson.cli"]
    except Exception:
        return None


def _emit_legacy_reminder(slug: str, count: int, project_root: Path, session_dir: Path) -> None:
    """Legacy path retained for debugging (set LESSON_SILENT_HOOK=0).
    Emits an additionalContext reminder to the main conversation. Never used in
    normal operation — the silent subprocess path is the default.
    """
    reminder = (
        f"[/lesson] Tracked session '{slug}' has accumulated {count} raw events. "
        f"Run `lesson compress --cwd {project_root}` to fold them into session_graph.json."
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


if __name__ == "__main__":
    sys.exit(main())
