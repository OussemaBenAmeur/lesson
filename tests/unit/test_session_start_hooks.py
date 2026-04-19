"""Unit tests for session-start hook wrappers."""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest


CODEX_SESSION_START_PATH = (
    Path(__file__).resolve().parents[2] / "hooks" / "codex" / "session_start_codex.py"
)
COPILOT_SESSION_START_PATH = (
    Path(__file__).resolve().parents[2] / "hooks" / "copilot" / "session_start_copilot.py"
)
OPENCODE_BRIDGE_PATH = (
    Path(__file__).resolve().parents[2] / "hooks" / "opencode" / "opencode_bridge.py"
)


def _make_session(tmp_path: Path, slug: str = "session-start") -> Path:
    lessons_dir = tmp_path / ".claude" / "lessons"
    session_dir = lessons_dir / "sessions" / slug
    session_dir.mkdir(parents=True)
    (session_dir / "meta.json").write_text(json.dumps({"token_tracking": {}}), encoding="utf-8")
    (session_dir / "arc.jsonl").write_text("", encoding="utf-8")
    (session_dir / "counter").write_text("0", encoding="utf-8")
    (lessons_dir / "active-session").write_text(slug, encoding="utf-8")
    return session_dir


def _load_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def codex_session_start_module():
    return _load_module(CODEX_SESSION_START_PATH, "lesson_codex_session_start_hook")


@pytest.fixture
def copilot_session_start_module():
    return _load_module(COPILOT_SESSION_START_PATH, "lesson_copilot_session_start_hook")


@pytest.fixture
def opencode_bridge_module():
    return _load_module(OPENCODE_BRIDGE_PATH, "lesson_opencode_bridge_session_start")


def _run_module(module, monkeypatch, event: dict, argv: list[str] | None = None) -> int:
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(event)))
    if argv is not None:
        monkeypatch.setattr(sys, "argv", argv)
    return module.main()


def test_codex_session_start_updates_hook_state(codex_session_start_module, tmp_path, monkeypatch):
    session_dir = _make_session(tmp_path)

    rc = _run_module(
        codex_session_start_module,
        monkeypatch,
        {"cwd": str(tmp_path), "session_id": "codex-session-123"},
    )

    assert rc == 0
    meta = json.loads((session_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["hook_state"]["platform"] == "codex"
    assert meta["hook_state"]["session_id"] == "codex-session-123"


def test_copilot_session_start_updates_hook_state(
    copilot_session_start_module, tmp_path, monkeypatch
):
    session_dir = _make_session(tmp_path)

    rc = _run_module(
        copilot_session_start_module,
        monkeypatch,
        {"cwd": str(tmp_path), "sessionId": "copilot-session-123"},
    )

    assert rc == 0
    meta = json.loads((session_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["hook_state"]["platform"] == "copilot"
    assert meta["hook_state"]["session_id"] == "copilot-session-123"


def test_opencode_session_start_updates_hook_state(opencode_bridge_module, tmp_path, monkeypatch):
    session_dir = _make_session(tmp_path)

    rc = _run_module(
        opencode_bridge_module,
        monkeypatch,
        {"cwd": str(tmp_path), "session_id": "opencode-session-123"},
        argv=["bridge", "sessionStart"],
    )

    assert rc == 0
    meta = json.loads((session_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["hook_state"]["platform"] == "opencode"
    assert meta["hook_state"]["session_id"] == "opencode-session-123"
