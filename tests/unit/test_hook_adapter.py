"""Unit tests for the shared hook adapter."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from lesson.hooks.adapter import handle_post_tool_use
from lesson.hooks.claude_code import extract_post_tool_use_event as extract_claude_event
from lesson.hooks.codex import extract_post_tool_use_event as extract_codex_event
from lesson.hooks.cursor import extract_post_tool_use_event as extract_cursor_event


def _make_session(tmp_path: Path, root: str = ".claude/lessons", slug: str = "session") -> Path:
    lessons_dir = tmp_path / root
    session_dir = lessons_dir / "sessions" / slug
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "arc.jsonl").write_text("", encoding="utf-8")
    (session_dir / "counter").write_text("0", encoding="utf-8")
    (session_dir / "meta.json").write_text(json.dumps({"token_tracking": {}}), encoding="utf-8")
    (lessons_dir / "active-session").write_text(slug, encoding="utf-8")
    return session_dir


def test_appends_claude_event_and_updates_tracking(tmp_path, monkeypatch):
    monkeypatch.setenv("LESSON_COMPRESS_EVERY", "10")
    session_dir = _make_session(tmp_path)
    event = {
        "cwd": str(tmp_path),
        "tool_name": "Edit",
        "tool_input": {"file_path": "app.py"},
        "tool_response": {"content": "ok"},
    }

    handle_post_tool_use(event, platform="claude-code", extractor=extract_claude_event)

    lines = (session_dir / "arc.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["tool"] == "Edit"
    assert record["args"] == '{"file_path": "app.py"}'
    assert json.loads((session_dir / "meta.json").read_text(encoding="utf-8"))["token_tracking"][
        "arc_input_chars"
    ] > 0


def test_uses_cursor_data_root(tmp_path, monkeypatch):
    monkeypatch.setenv("LESSON_COMPRESS_EVERY", "10")
    session_dir = _make_session(tmp_path, root=".cursor/lessons")
    event = {
        "cwd": str(tmp_path),
        "tool_name": "Edit",
        "tool_input": {"file_path": "ui.tsx"},
        "tool_response": {"content": "done"},
    }

    handle_post_tool_use(event, platform="cursor", extractor=extract_claude_event)

    lines = (session_dir / "arc.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["tool"] == "Edit"


def test_codex_marks_nonzero_exit_code_as_error(tmp_path, monkeypatch):
    monkeypatch.setenv("LESSON_COMPRESS_EVERY", "10")
    session_dir = _make_session(tmp_path)
    event = {
        "cwd": str(tmp_path),
        "tool_name": "Bash",
        "tool_input": {"command": "pytest"},
        "tool_response": {"stdout": "failed", "exit_code": 1},
    }

    handle_post_tool_use(event, platform="codex", extractor=extract_codex_event)

    record = json.loads((session_dir / "arc.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert record["is_error"] is True


def test_same_event_has_same_significance_across_platforms(tmp_path, monkeypatch):
    monkeypatch.setenv("LESSON_COMPRESS_EVERY", "10")
    claude_dir = _make_session(tmp_path / "claude")
    codex_dir = _make_session(tmp_path / "codex")
    event = {
        "tool_name": "Bash",
        "tool_input": {"command": "pip install numpy"},
        "tool_response": {"stdout": "Successfully installed numpy-1.26.4"},
    }

    handle_post_tool_use(
        {**event, "cwd": str(tmp_path / "claude")},
        platform="claude-code",
        extractor=extract_claude_event,
    )
    handle_post_tool_use(
        {**event, "cwd": str(tmp_path / "codex")},
        platform="codex",
        extractor=extract_codex_event,
    )

    claude_record = json.loads((claude_dir / "arc.jsonl").read_text(encoding="utf-8").splitlines()[0])
    codex_record = json.loads((codex_dir / "arc.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert claude_record["significant"] == codex_record["significant"]


def test_threshold_spawns_compression_once(tmp_path, monkeypatch):
    monkeypatch.setenv("LESSON_COMPRESS_EVERY", "1")
    session_dir = _make_session(tmp_path)
    event = {
        "cwd": str(tmp_path),
        "tool_name": "Edit",
        "tool_input": {"file_path": "x.py"},
        "tool_response": {"content": "ok"},
    }

    with patch("lesson.hooks.adapter._resolve_lesson_command", return_value=["/fake/lesson"]):
        with patch("lesson.hooks.adapter.subprocess.Popen") as mock_popen:
            handle_post_tool_use(event, platform="claude-code", extractor=extract_claude_event)

    assert mock_popen.call_count == 1
    assert (session_dir / "counter").read_text(encoding="utf-8").strip() == "0"


def test_cursor_duplicate_event_id_is_deduped(tmp_path, monkeypatch):
    monkeypatch.setenv("LESSON_COMPRESS_EVERY", "10")
    session_dir = _make_session(tmp_path, root=".cursor/lessons")
    event = {
        "cwd": str(tmp_path),
        "tool_name": "Edit",
        "tool_input": {"file_path": "ui.tsx"},
        "tool_response": {"content": "done"},
        "tool_call_id": "cursor-edit-1",
    }

    handle_post_tool_use(event, platform="cursor", extractor=extract_cursor_event)
    handle_post_tool_use(event, platform="cursor", extractor=extract_cursor_event)

    lines = (session_dir / "arc.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    tool_name=st.sampled_from(["Bash", "Edit", "Write", "Read"]),
    tool_input=st.dictionaries(
        keys=st.text(min_size=1, max_size=8),
        values=st.one_of(st.text(max_size=20), st.integers(min_value=0, max_value=10)),
        max_size=4,
    ),
    result_text=st.text(max_size=50),
    is_error=st.booleans(),
)
def test_adapter_appends_one_line_for_shape_based_events(
    tmp_path, monkeypatch, tool_name, tool_input, result_text, is_error
):
    monkeypatch.setenv("LESSON_COMPRESS_EVERY", "100")
    session_dir = _make_session(tmp_path)
    event = {
        "cwd": str(tmp_path),
        "tool_name": tool_name,
        "tool_input": tool_input,
        "tool_response": {"stdout": result_text, "is_error": is_error},
    }

    handle_post_tool_use(event, platform="claude-code", extractor=extract_claude_event)

    lines = (session_dir / "arc.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
