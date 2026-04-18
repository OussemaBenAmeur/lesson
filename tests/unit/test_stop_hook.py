"""Unit tests for hooks/stop.py non-blocking behavior.

The v0.3.0 contract: the Stop hook must NEVER emit `decision: "block"`. It
should instead surface a one-line `systemMessage` only when an active session
has accumulated enough events.
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest


HOOK_PATH = Path(__file__).resolve().parents[2] / "hooks" / "stop.py"


@pytest.fixture
def hook_module(monkeypatch):
    monkeypatch.setenv("LESSON_STOP_MIN_EVENTS", "3")
    spec = importlib.util.spec_from_file_location("lesson_stop_hook", HOOK_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _make_session(tmp_path: Path, slug: str, events: int) -> Path:
    lessons_dir = tmp_path / ".claude" / "lessons"
    session_dir = lessons_dir / "sessions" / slug
    session_dir.mkdir(parents=True)
    arc = session_dir / "arc.jsonl"
    arc.write_text("\n".join(json.dumps({"i": i}) for i in range(events)) + ("\n" if events else ""))
    (lessons_dir / "active-session").write_text(slug)
    return session_dir


def _run_hook(hook_module, monkeypatch, event: dict, capsys) -> str:
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(event)))
    rc = hook_module.main()
    assert rc == 0
    return capsys.readouterr().out


class TestNonBlocking:
    def test_never_emits_decision_block(self, hook_module, tmp_path, monkeypatch, capsys):
        _make_session(tmp_path, "20260418-big", events=50)
        out = _run_hook(hook_module, monkeypatch, {"cwd": str(tmp_path)}, capsys)
        assert out.strip(), "hook should emit something when session has enough events"
        data = json.loads(out)
        assert "decision" not in data, (
            f"Stop hook must never set `decision` — got {data!r}"
        )
        # Must use the passive systemMessage channel instead.
        hso = data.get("hookSpecificOutput", {})
        assert hso.get("hookEventName") == "Stop"
        assert "systemMessage" in hso
        assert "20260418-big" in hso["systemMessage"]

    def test_silent_when_below_min_events(self, hook_module, tmp_path, monkeypatch, capsys):
        # MIN_EVENTS=3 via fixture; 2 events → silent.
        _make_session(tmp_path, "20260418-thin", events=2)
        out = _run_hook(hook_module, monkeypatch, {"cwd": str(tmp_path)}, capsys)
        assert out == ""

    def test_silent_without_active_marker(self, hook_module, tmp_path, monkeypatch, capsys):
        out = _run_hook(hook_module, monkeypatch, {"cwd": str(tmp_path)}, capsys)
        assert out == ""

    def test_respects_stop_hook_active_flag(self, hook_module, tmp_path, monkeypatch, capsys):
        _make_session(tmp_path, "20260418-loop", events=50)
        event = {"cwd": str(tmp_path), "stop_hook_active": True}
        out = _run_hook(hook_module, monkeypatch, event, capsys)
        assert out == "", "hook must not re-nudge once /lesson-done is already running"
