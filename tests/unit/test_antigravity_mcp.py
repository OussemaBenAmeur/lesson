"""Unit tests for the Antigravity MCP server."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _make_session(tmp_path: Path, slug: str = "antigravity-session") -> Path:
    lessons_dir = tmp_path / ".claude" / "lessons"
    session_dir = lessons_dir / "sessions" / slug
    session_dir.mkdir(parents=True)
    (session_dir / "arc.jsonl").write_text("", encoding="utf-8")
    (session_dir / "counter").write_text("0", encoding="utf-8")
    (session_dir / "meta.json").write_text(json.dumps({"token_tracking": {}}), encoding="utf-8")
    (lessons_dir / "active-session").write_text(slug, encoding="utf-8")
    return session_dir


def _rpc(proc: subprocess.Popen[str], payload: dict) -> dict:
    assert proc.stdin is not None
    assert proc.stdout is not None
    proc.stdin.write(json.dumps(payload) + "\n")
    proc.stdin.flush()
    return json.loads(proc.stdout.readline())


def test_antigravity_mcp_lists_tools_and_records_event(tmp_path):
    session_dir = _make_session(tmp_path)
    proc = subprocess.Popen(
        [sys.executable, "-m", "lesson.hooks.antigravity_mcp"],
        cwd=str(tmp_path),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        init = _rpc(
            proc,
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        )
        assert init["result"]["serverInfo"]["name"] == "lesson-antigravity"

        tools = _rpc(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        names = {tool["name"] for tool in tools["result"]["tools"]}
        assert "lesson.record_event" in names
        assert "lesson.finalize_session" in names

        result = _rpc(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "lesson.record_event",
                    "arguments": {
                        "tool_name": "Bash",
                        "tool_input": {"command": "pytest"},
                        "result_text": "ok",
                        "is_error": False,
                        "cwd": str(tmp_path),
                    },
                },
            },
        )
        assert result["result"]["content"][0]["text"] == "recorded"
        assert len((session_dir / "arc.jsonl").read_text(encoding="utf-8").splitlines()) == 1
    finally:
        proc.kill()
        proc.wait()


def test_antigravity_mcp_script_form_starts_without_import_error(tmp_path):
    """Regression: antigravity_mcp.py must be runnable as a plain script (no -m).

    The MCP server launcher invokes it as `python3 /path/to/antigravity_mcp.py`,
    which sets __package__ = None and makes relative imports fail.  The bootstrap
    block in the module must add the repo root (or _support) to sys.path first.
    """
    mcp_script = Path(__file__).resolve().parents[2] / "lesson" / "hooks" / "antigravity_mcp.py"
    session_dir = _make_session(tmp_path)
    proc = subprocess.Popen(
        [sys.executable, str(mcp_script)],
        cwd=str(tmp_path),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        # Send initialize handshake — if imports failed the process would have
        # already exited with a traceback before we get here.
        result = _rpc(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        assert result.get("result", {}).get("protocolVersion") == "2024-11-05"
        assert proc.poll() is None, "MCP server exited unexpectedly"
    finally:
        proc.kill()
        proc.wait()
