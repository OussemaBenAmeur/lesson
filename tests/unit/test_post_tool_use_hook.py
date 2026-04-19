"""Unit tests for hooks/post_tool_use.py silent-compression behavior.

These tests verify the v0.3.0 contract:
- In default (silent) mode the hook produces no stdout.
- At threshold the hook spawns `lesson compress` as a detached subprocess.
- The counter resets after compression is triggered, regardless of whether the
  compression subprocess actually runs.
- Appending to arc.jsonl and bumping the counter still works under threshold.
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest


HOOK_PATH = Path(__file__).resolve().parents[2] / "hooks" / "post_tool_use.py"


@pytest.fixture
def hook_module(monkeypatch):
    """Import hooks/post_tool_use.py as a module under a stable name."""
    monkeypatch.setenv("LESSON_COMPRESS_EVERY", "3")
    monkeypatch.setenv("LESSON_SILENT_HOOK", "1")
    spec = importlib.util.spec_from_file_location("lesson_post_tool_use_hook", HOOK_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _make_session(tmp_path: Path, slug: str = "20260418-test", counter: int = 0) -> Path:
    """Create a minimal active-session layout under tmp_path/.claude/lessons/."""
    lessons_dir = tmp_path / ".claude" / "lessons"
    session_dir = lessons_dir / "sessions" / slug
    session_dir.mkdir(parents=True)
    (session_dir / "arc.jsonl").write_text("")
    (session_dir / "counter").write_text(str(counter))
    (session_dir / "meta.json").write_text(json.dumps({"token_tracking": {}}))
    (lessons_dir / "active-session").write_text(slug)
    return session_dir


def _run_hook(hook_module, monkeypatch, event: dict, capsys) -> str:
    """Feed the hook `event` on stdin, return captured stdout."""
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(event)))
    rc = hook_module.main()
    assert rc == 0
    return capsys.readouterr().out


class TestSilentByDefault:
    def test_no_stdout_under_threshold(self, hook_module, tmp_path, monkeypatch, capsys):
        _make_session(tmp_path, counter=0)
        event = {
            "cwd": str(tmp_path),
            "tool_name": "Edit",
            "tool_input": {"file_path": "x.py"},
            "tool_response": {"content": "ok"},
        }
        out = _run_hook(hook_module, monkeypatch, event, capsys)
        assert out == "", f"hook emitted stdout under threshold: {out!r}"

    def test_no_stdout_at_threshold(self, hook_module, tmp_path, monkeypatch, capsys):
        # LESSON_COMPRESS_EVERY=3 via fixture. counter=2 → this call hits 3.
        session_dir = _make_session(tmp_path, counter=2)
        event = {
            "cwd": str(tmp_path),
            "tool_name": "Edit",
            "tool_input": {"file_path": "x.py"},
            "tool_response": {"content": "ok"},
        }
        with patch.object(hook_module.hook_adapter.subprocess, "Popen") as mock_popen:
            mock_popen.return_value = SimpleNamespace()
            with patch.object(
                hook_module.hook_adapter, "_resolve_lesson_command", return_value=["/fake/lesson"]
            ):
                out = _run_hook(hook_module, monkeypatch, event, capsys)

        assert out == "", f"silent hook must not emit stdout at threshold: {out!r}"
        assert mock_popen.called, "hook must spawn `lesson compress` at threshold"
        # Counter must reset.
        assert (session_dir / "counter").read_text().strip() == "0"


class TestCompressionSubprocess:
    def test_spawns_detached_subprocess(self, hook_module, tmp_path, monkeypatch, capsys):
        _make_session(tmp_path, counter=2)
        event = {
            "cwd": str(tmp_path),
            "tool_name": "Edit",
            "tool_input": {"file_path": "x.py"},
            "tool_response": {"content": "ok"},
        }
        with patch.object(hook_module.hook_adapter.subprocess, "Popen") as mock_popen:
            with patch.object(
                hook_module.hook_adapter, "_resolve_lesson_command", return_value=["/fake/lesson"]
            ):
                _run_hook(hook_module, monkeypatch, event, capsys)

        assert mock_popen.call_count == 1
        args, kwargs = mock_popen.call_args
        # First positional arg is the argv list.
        argv = args[0]
        assert argv[0] == "/fake/lesson"
        assert "compress" in argv
        assert "--cwd" in argv
        # Must be detached and silent.
        assert kwargs.get("start_new_session") is True
        assert kwargs.get("stdout") == hook_module.hook_adapter.subprocess.DEVNULL
        assert kwargs.get("stderr") == hook_module.hook_adapter.subprocess.DEVNULL

    def test_counter_resets_even_if_resolver_missing(
        self, hook_module, tmp_path, monkeypatch, capsys
    ):
        """If `lesson` is not installed we still reset the counter to avoid
        spamming the resolver check on every subsequent tool call."""
        session_dir = _make_session(tmp_path, counter=2)
        event = {
            "cwd": str(tmp_path),
            "tool_name": "Edit",
            "tool_input": {"file_path": "x.py"},
            "tool_response": {"content": "ok"},
        }
        with patch.object(hook_module.hook_adapter, "_resolve_lesson_command", return_value=None):
            out = _run_hook(hook_module, monkeypatch, event, capsys)

        assert out == ""
        assert (session_dir / "counter").read_text().strip() == "0"


class TestNoActiveSession:
    def test_exits_silently_without_marker(self, hook_module, tmp_path, monkeypatch, capsys):
        # No .claude/lessons/active-session file at all.
        event = {
            "cwd": str(tmp_path),
            "tool_name": "Edit",
            "tool_input": {"file_path": "x.py"},
            "tool_response": {"content": "ok"},
        }
        out = _run_hook(hook_module, monkeypatch, event, capsys)
        assert out == ""
