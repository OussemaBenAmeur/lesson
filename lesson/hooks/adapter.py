"""Shared hook adapter logic for platform-specific wrappers."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

ARGS_CAP = 500
RESULT_CAP = 1000
DEDUPE_WINDOW = 200
DEFAULT_DATA_ROOT = ".claude/lessons"
DATA_ROOTS = {
    "cursor": ".cursor/lessons",
}


@dataclass(slots=True)
class NormalizedEvent:
    tool_name: str
    tool_input: Any
    result_text: str
    is_error: bool
    cwd: Path
    session_id: str | None = None
    event_id: str | None = None


def _compress_every() -> int:
    return int(os.environ.get("LESSON_COMPRESS_EVERY", "25"))


def _silent_hook() -> bool:
    return os.environ.get("LESSON_SILENT_HOOK", "1") != "0"


def _data_root(platform: str) -> Path:
    return Path(DATA_ROOTS.get(platform, DEFAULT_DATA_ROOT))


def _lessons_dir(cwd: Path, platform: str) -> Path:
    return cwd / _data_root(platform)


def _is_significant(tool_name: str, result_text: str, is_error: bool) -> bool:
    """Return whether an event should be treated as significant."""
    try:
        from lesson.graph.schema import RawEvent
        from lesson.nlp.scorer import SignificanceScorer

        ev = RawEvent(tool=tool_name, result_head=result_text, is_error=is_error)
        scorer = SignificanceScorer()
        scorer.fit([ev])
        return scorer.score_one(ev) >= 0.25
    except Exception:
        pass

    significant_tools = {"Edit", "Write", "NotebookEdit"}
    error_patterns = [
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
    version_re = re.compile(r"\b\d+\.\d+[\.\d]*\b")

    if is_error:
        return True
    if tool_name in significant_tools:
        return True
    if tool_name == "Bash":
        lower = result_text.lower()
        if any(pattern in lower for pattern in error_patterns):
            return True
        if len(result_text) < 500 and version_re.search(result_text):
            return True
    return False


def _safe_str(value: Any) -> str:
    try:
        if isinstance(value, (dict, list)):
            return json.dumps(value, default=str, ensure_ascii=False)
        return str(value)
    except Exception:
        return "<unserializable>"


def extract_result(tool_response: Any) -> tuple[str, bool]:
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
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    parts.append(item.get("text") or _safe_str(item))
                else:
                    parts.append(_safe_str(item))
            content = "\n".join(parts)
        return _safe_str(content), is_error
    return _safe_str(tool_response), False


def _update_token_tracking(meta_path: Path, chars_added: int) -> None:
    try:
        if not meta_path.exists():
            return
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        token_tracking = meta.setdefault("token_tracking", {})
        token_tracking["arc_input_chars"] = token_tracking.get("arc_input_chars", 0) + chars_added
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _event_ids_path(session_dir: Path) -> Path:
    return session_dir / ".hook_event_ids.json"


def _should_skip_duplicate(session_dir: Path, event_id: str | None) -> bool:
    if not event_id:
        return False

    path = _event_ids_path(session_dir)
    seen: list[str] = []
    try:
        if path.exists():
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                seen = [item for item in loaded if isinstance(item, str)]
    except Exception:
        seen = []

    if event_id in seen:
        return True

    seen.append(event_id)
    seen = seen[-DEDUPE_WINDOW:]
    try:
        path.write_text(json.dumps(seen, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return False


def _spawn_compression(project_root: Path) -> None:
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
    exe = shutil.which("lesson")
    if exe:
        return [exe]
    try:
        import lesson  # noqa: F401

        return [sys.executable, "-m", "lesson.cli"]
    except Exception:
        return None


def _emit_legacy_reminder(slug: str, count: int, project_root: Path) -> None:
    reminder = (
        f"[/lesson] Tracked session '{slug}' has accumulated {count} raw events. "
        f"Run `lesson compress --cwd {project_root}` to fold them into session_graph.json."
    )
    try:
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PostToolUse",
                        "additionalContext": reminder,
                    }
                }
            )
        )
    except Exception:
        pass


def handle_post_tool_use(
    raw_event: dict[str, Any],
    platform: str,
    extractor: Callable[[dict[str, Any]], NormalizedEvent],
) -> None:
    try:
        normalized = extractor(raw_event)
        lessons_dir = _lessons_dir(normalized.cwd, platform)
        marker = lessons_dir / "active-session"
        if not marker.exists():
            return

        slug = marker.read_text(encoding="utf-8").strip()
        if not slug:
            return

        session_dir = lessons_dir / "sessions" / slug
        if not session_dir.exists():
            return

        if _should_skip_duplicate(session_dir, normalized.event_id):
            return

        arc_log = session_dir / "arc.jsonl"
        counter_file = session_dir / "counter"
        meta_path = session_dir / "meta.json"

        args_summary = _safe_str(normalized.tool_input)[:ARGS_CAP]
        result_head = normalized.result_text[:RESULT_CAP]
        significant = _is_significant(normalized.tool_name, result_head, normalized.is_error)

        entry = {
            "ts": time.time(),
            "tool": normalized.tool_name,
            "args": args_summary,
            "result_head": result_head,
            "is_error": normalized.is_error,
            "significant": significant,
        }
        # JSONL requires one physical line per event. Use ASCII escapes so
        # line-separator code points like U+0085 cannot split the record.
        entry_json = json.dumps(entry, ensure_ascii=True)
        with arc_log.open("a", encoding="utf-8") as fh:
            fh.write(entry_json + "\n")

        _update_token_tracking(meta_path, len(entry_json) + 1)

        count = 0
        if counter_file.exists():
            try:
                count = int(counter_file.read_text(encoding="utf-8").strip() or "0")
            except Exception:
                count = 0
        count += 1
        counter_file.write_text(str(count), encoding="utf-8")

        if count >= _compress_every():
            try:
                counter_file.write_text("0", encoding="utf-8")
            except Exception:
                pass

            project_root = session_dir.parent.parent.parent
            if _silent_hook():
                _spawn_compression(project_root)
            else:
                _emit_legacy_reminder(slug, count, project_root)
    except Exception:
        return
