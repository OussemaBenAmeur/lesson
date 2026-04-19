"""Unit tests for prompt sidecar capture."""

from __future__ import annotations

import json
from pathlib import Path

from lesson.hooks.prompt_capture import handle_user_prompt


def _make_session(tmp_path: Path, slug: str = "prompt-session") -> Path:
    lessons_dir = tmp_path / ".claude" / "lessons"
    session_dir = lessons_dir / "sessions" / slug
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "meta.json").write_text(json.dumps({"token_tracking": {}}), encoding="utf-8")
    (lessons_dir / "active-session").write_text(slug, encoding="utf-8")
    return session_dir


def test_handle_user_prompt_writes_sidecar_entry(tmp_path):
    session_dir = _make_session(tmp_path)

    handle_user_prompt(
        {
            "cwd": str(tmp_path),
            "sessionId": "copilot-session-1",
            "prompt": "Why is this failing after I edited main.py?",
        },
        platform="copilot",
    )

    prompts_path = session_dir / "prompts.jsonl"
    lines = prompts_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["session_id"] == "copilot-session-1"
    assert record["prompt_text_head"].startswith("Why is this failing")
    assert len(record["prompt_hash"]) == 64
