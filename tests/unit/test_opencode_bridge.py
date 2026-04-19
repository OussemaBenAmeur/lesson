"""Unit tests for the OpenCode bridge."""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest


BRIDGE_PATH = Path(__file__).resolve().parents[2] / "hooks" / "opencode" / "opencode_bridge.py"


def _make_session(tmp_path: Path, slug: str = "opencode-session") -> Path:
    lessons_dir = tmp_path / ".claude" / "lessons"
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
def bridge_module(monkeypatch):
    monkeypatch.setenv("LESSON_STOP_MIN_EVENTS", "3")
    return _load_module(BRIDGE_PATH, "lesson_opencode_bridge")


def _run_bridge(module, monkeypatch, argv: list[str], event: dict, capsys) -> str:
    monkeypatch.setattr(sys, "argv", argv)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(event)))
    rc = module.main()
    assert rc == 0
    return capsys.readouterr().out


def test_opencode_bridge_logs_post_tool_use(bridge_module, tmp_path, monkeypatch, capsys):
    session_dir = _make_session(tmp_path)
    event = {
        "cwd": str(tmp_path),
        "tool_name": "Edit",
        "tool_input": {"file_path": "main.py"},
        "tool_response": {"content": "ok"},
    }

    out = _run_bridge(bridge_module, monkeypatch, ["bridge", "postToolUse"], event, capsys)

    assert out == ""
    assert len((session_dir / "arc.jsonl").read_text(encoding="utf-8").splitlines()) == 1


def test_opencode_bridge_stop_is_silent(bridge_module, tmp_path, monkeypatch, capsys):
    _make_session(tmp_path)

    out = _run_bridge(bridge_module, monkeypatch, ["bridge", "stop"], {"cwd": str(tmp_path)}, capsys)

    assert out == ""
