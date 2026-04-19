"""End-to-end acceptance test for the 25-event compression trigger.

Verifies plan §8 acceptance criterion #3: after `LESSON_COMPRESS_EVERY`
events flow through the shared adapter, `_spawn_compression` is invoked
exactly once and the counter is reset to zero.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from lesson.hooks.adapter import handle_post_tool_use
from lesson.hooks.claude_code import extract_post_tool_use_event as extract_claude_event
from lesson.hooks.cursor import extract_post_tool_use_event as extract_cursor_event


def _make_session(root: Path, data_root: str, slug: str = "sess-1") -> Path:
    lessons_dir = root / data_root
    session_dir = lessons_dir / "sessions" / slug
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "arc.jsonl").write_text("", encoding="utf-8")
    (session_dir / "counter").write_text("0", encoding="utf-8")
    (session_dir / "meta.json").write_text(
        json.dumps({"token_tracking": {"arc_input_chars": 0}}), encoding="utf-8"
    )
    (lessons_dir / "active-session").write_text(slug, encoding="utf-8")
    return session_dir


def _event(cwd: Path, idx: int, tool: str = "Bash") -> dict:
    return {
        "cwd": str(cwd),
        "tool_name": tool,
        "tool_input": {"command": f"step-{idx}"},
        "tool_response": {"stdout": f"ok {idx}", "exit_code": 0},
        "tool_call_id": f"call-{idx}",
    }


def test_claude_code_triggers_compression_at_threshold(tmp_path, monkeypatch):
    monkeypatch.setenv("LESSON_COMPRESS_EVERY", "25")
    monkeypatch.setenv("LESSON_SILENT_HOOK", "1")
    session_dir = _make_session(tmp_path, ".claude/lessons")

    with patch("lesson.hooks.adapter._resolve_lesson_command", return_value=["/fake/lesson"]):
        with patch("lesson.hooks.adapter.subprocess.Popen") as mock_popen:
            for i in range(25):
                handle_post_tool_use(
                    _event(tmp_path, i),
                    platform="claude-code",
                    extractor=extract_claude_event,
                )

    # Compression spawn exactly once on the 25th event.
    assert mock_popen.call_count == 1
    # Counter reset after spawn.
    assert (session_dir / "counter").read_text(encoding="utf-8").strip() == "0"
    # All 25 events landed in arc.jsonl.
    assert len((session_dir / "arc.jsonl").read_text(encoding="utf-8").splitlines()) == 25


def test_cursor_triggers_compression_and_survives_duplicates(tmp_path, monkeypatch):
    """Cursor fires duplicate events for edits (postToolUse + afterFileEdit).

    The dedup layer must ensure the counter reflects unique events, not
    duplicates — otherwise a single user action would trip the threshold
    early or twice.
    """
    monkeypatch.setenv("LESSON_COMPRESS_EVERY", "25")
    monkeypatch.setenv("LESSON_SILENT_HOOK", "1")
    session_dir = _make_session(tmp_path, ".cursor/lessons")

    with patch("lesson.hooks.adapter._resolve_lesson_command", return_value=["/fake/lesson"]):
        with patch("lesson.hooks.adapter.subprocess.Popen") as mock_popen:
            for i in range(25):
                # Simulate Cursor firing the same event twice.
                event = _event(tmp_path, i, tool="Edit")
                handle_post_tool_use(event, platform="cursor", extractor=extract_cursor_event)
                handle_post_tool_use(event, platform="cursor", extractor=extract_cursor_event)

    assert mock_popen.call_count == 1
    assert (session_dir / "counter").read_text(encoding="utf-8").strip() == "0"
    # Dedup keeps arc.jsonl to 25 unique lines despite 50 calls.
    assert len((session_dir / "arc.jsonl").read_text(encoding="utf-8").splitlines()) == 25
