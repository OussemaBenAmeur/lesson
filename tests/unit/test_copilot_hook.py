"""Unit tests for GitHub Copilot CLI hook wrappers."""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest


POST_HOOK_PATH = Path(__file__).resolve().parents[2] / "hooks" / "copilot" / "post_tool_use_copilot.py"
SESSION_END_HOOK_PATH = (
    Path(__file__).resolve().parents[2] / "hooks" / "copilot" / "session_end_copilot.py"
)


def _make_session(tmp_path: Path, slug: str = "copilot-session", events: int = 0) -> Path:
    lessons_dir = tmp_path / ".claude" / "lessons"
    session_dir = lessons_dir / "sessions" / slug
    session_dir.mkdir(parents=True)
    arc_lines = "\n".join(json.dumps({"i": i}) for i in range(events))
    (session_dir / "arc.jsonl").write_text(arc_lines + ("\n" if events else ""), encoding="utf-8")
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
    return _load_module(POST_HOOK_PATH, "lesson_copilot_post_hook")


@pytest.fixture
def session_end_hook_module(monkeypatch):
    monkeypatch.setenv("LESSON_STOP_MIN_EVENTS", "3")
    return _load_module(SESSION_END_HOOK_PATH, "lesson_copilot_session_end_hook")


def _run_hook(module, monkeypatch, event: dict, capsys) -> str:
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(event)))
    rc = module.main()
    assert rc == 0
    return capsys.readouterr().out


def test_copilot_post_tool_use_logs_event(post_hook_module, tmp_path, monkeypatch, capsys):
    session_dir = _make_session(tmp_path)
    event = {
        "cwd": str(tmp_path),
        "toolName": "Bash",
        "toolInput": {"command": "pytest"},
        "toolOutput": {"stdout": "ok"},
        "exitCode": 0,
    }

    out = _run_hook(post_hook_module, monkeypatch, event, capsys)

    assert out == ""
    assert len((session_dir / "arc.jsonl").read_text(encoding="utf-8").splitlines()) == 1


def test_copilot_session_end_emits_stop_message(
    session_end_hook_module, tmp_path, monkeypatch, capsys
):
    _make_session(tmp_path, events=5)

    out = _run_hook(session_end_hook_module, monkeypatch, {"cwd": str(tmp_path)}, capsys)

    data = json.loads(out)
    assert data["hookSpecificOutput"]["hookEventName"] == "Stop"
    assert "run /lesson-done" in data["hookSpecificOutput"]["systemMessage"]
