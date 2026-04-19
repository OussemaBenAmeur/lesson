"""Unit tests for the GitHub Copilot prompt hook wrapper."""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest


PROMPT_HOOK_PATH = (
    Path(__file__).resolve().parents[2] / "hooks" / "copilot" / "user_prompt_copilot.py"
)


def _make_session(tmp_path: Path, slug: str = "copilot-session") -> Path:
    lessons_dir = tmp_path / ".claude" / "lessons"
    session_dir = lessons_dir / "sessions" / slug
    session_dir.mkdir(parents=True)
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
def prompt_hook_module():
    return _load_module(PROMPT_HOOK_PATH, "lesson_copilot_prompt_hook")


def test_copilot_user_prompt_writes_sidecar(prompt_hook_module, tmp_path, monkeypatch, capsys):
    session_dir = _make_session(tmp_path)
    event = {
        "cwd": str(tmp_path),
        "sessionId": "copilot-session-123",
        "prompt": "Why is this failing after I edited main.py?",
    }

    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(event)))
    rc = prompt_hook_module.main()

    assert rc == 0
    assert capsys.readouterr().out == ""
    prompts_path = session_dir / "prompts.jsonl"
    lines = prompts_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
