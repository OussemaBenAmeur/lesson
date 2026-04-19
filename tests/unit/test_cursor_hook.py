"""Unit tests for Cursor hook wrappers."""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest


POST_HOOK_PATH = Path(__file__).resolve().parents[2] / "hooks" / "cursor" / "post_tool_use_cursor.py"
AFTER_EDIT_HOOK_PATH = (
    Path(__file__).resolve().parents[2] / "hooks" / "cursor" / "after_file_edit_cursor.py"
)
STOP_HOOK_PATH = Path(__file__).resolve().parents[2] / "hooks" / "cursor" / "stop_cursor.py"


def _make_session(tmp_path: Path, slug: str = "cursor-session") -> Path:
    lessons_dir = tmp_path / ".cursor" / "lessons"
    session_dir = lessons_dir / "sessions" / slug
    session_dir.mkdir(parents=True)
    (session_dir / "arc.jsonl").write_text("", encoding="utf-8")
    (session_dir / "counter").write_text("0", encoding="utf-8")
    (session_dir / "meta.json").write_text(json.dumps({"token_tracking": {}}), encoding="utf-8")
    (lessons_dir / "active-session").write_text(slug, encoding="utf-8")
    return session_dir


def _load_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def post_hook_module():
    return _load_module(POST_HOOK_PATH, "lesson_cursor_post_hook")


@pytest.fixture
def after_edit_hook_module():
    return _load_module(AFTER_EDIT_HOOK_PATH, "lesson_cursor_after_edit_hook")


@pytest.fixture
def stop_hook_module(monkeypatch):
    monkeypatch.setenv("LESSON_STOP_MIN_EVENTS", "3")
    return _load_module(STOP_HOOK_PATH, "lesson_cursor_stop_hook")


def _run_hook(module, monkeypatch, event: dict, capsys) -> str:
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(event)))
    rc = module.main()
    assert rc == 0
    return capsys.readouterr().out


def test_cursor_post_tool_use_allows_and_logs(post_hook_module, tmp_path, monkeypatch, capsys):
    session_dir = _make_session(tmp_path)
    event = {
        "cwd": str(tmp_path),
        "tool_name": "Edit",
        "tool_input": {"file_path": "main.ts"},
        "tool_response": {"content": "ok"},
    }

    out = _run_hook(post_hook_module, monkeypatch, event, capsys)

    assert json.loads(out) == {"permission": "allow"}
    assert len((session_dir / "arc.jsonl").read_text(encoding="utf-8").splitlines()) == 1


def test_cursor_after_file_edit_dedupes_by_tool_call_id(
    post_hook_module, after_edit_hook_module, tmp_path, monkeypatch, capsys
):
    session_dir = _make_session(tmp_path)
    event = {
        "cwd": str(tmp_path),
        "tool_name": "Edit",
        "tool_input": {"file_path": "main.ts"},
        "tool_response": {"content": "ok"},
        "tool_call_id": "cursor-dup-1",
    }

    _run_hook(post_hook_module, monkeypatch, event, capsys)
    out = _run_hook(after_edit_hook_module, monkeypatch, event, capsys)

    assert json.loads(out) == {"permission": "allow"}
    assert len((session_dir / "arc.jsonl").read_text(encoding="utf-8").splitlines()) == 1


def test_cursor_stop_allows_and_emits_stop_message(
    stop_hook_module, tmp_path, monkeypatch, capsys
):
    _make_session(tmp_path)
    session_dir = tmp_path / ".cursor" / "lessons" / "sessions" / "cursor-session"
    (session_dir / "arc.jsonl").write_text(
        "\n".join(json.dumps({"i": i}) for i in range(5)) + "\n",
        encoding="utf-8",
    )

    out = _run_hook(stop_hook_module, monkeypatch, {"cwd": str(tmp_path)}, capsys)

    data = json.loads(out)
    assert data["permission"] == "allow"
    assert data["hookSpecificOutput"]["hookEventName"] == "Stop"
    assert "run /lesson-done" in data["hookSpecificOutput"]["systemMessage"]
