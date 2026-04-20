"""Unit tests for hooks/stop.py non-blocking behavior.

The v0.3.0 contract: the Stop hook must NEVER emit `decision: "block"`. It
should instead surface a one-line `systemMessage` only when an active session
has accumulated enough events.
"""

from __future__ import annotations

import importlib.util
import io
import json
import subprocess
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


class TestStopCodexScriptForm:
    """Regression: stop_codex.py must work when run as a plain script.

    Before the fix, stop_codex.py used runpy to dispatch to hooks/stop.py
    (the Claude wrapper), which added only its own parent to sys.path and
    could not find lesson.hooks.stop in the installed _support bundle.
    The hook would silently return 0 and the reminder would never appear.
    """

    def test_emits_reminder_when_session_active(self, tmp_path, monkeypatch):
        _make_session(tmp_path, "codex-sess", events=10)
        monkeypatch.setenv("LESSON_STOP_MIN_EVENTS", "3")
        script = Path(__file__).resolve().parents[2] / "hooks" / "codex" / "stop_codex.py"
        event = json.dumps({"cwd": str(tmp_path)})
        result = subprocess.run(
            [sys.executable, str(script)],
            input=event,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert result.stdout.strip(), "stop_codex.py must emit reminder JSON when session is active"
        data = json.loads(result.stdout.strip())
        hso = data.get("hookSpecificOutput", {})
        assert hso.get("hookEventName") == "Stop"
        assert "codex-sess" in hso.get("systemMessage", "")

    def test_silent_without_active_session(self, tmp_path):
        script = Path(__file__).resolve().parents[2] / "hooks" / "codex" / "stop_codex.py"
        result = subprocess.run(
            [sys.executable, str(script)],
            input=json.dumps({"cwd": str(tmp_path)}),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert result.stdout.strip() == ""
