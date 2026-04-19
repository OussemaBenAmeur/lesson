"""Integration test for the Antigravity MCP server."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from lesson.session import SessionManager

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "hooks"


def _rpc(proc: subprocess.Popen[str], payload: dict) -> dict:
    assert proc.stdin is not None
    assert proc.stdout is not None
    proc.stdin.write(json.dumps(payload) + "\n")
    proc.stdin.flush()
    return json.loads(proc.stdout.readline())


def test_antigravity_mcp_records_and_compresses(tmp_path):
    sm = SessionManager(tmp_path)
    slug = sm.create("antigravity integration", platform="antigravity")
    record_payload = json.loads(
        (FIXTURES / "antigravity" / "record_event.shape.json").read_text(encoding="utf-8")
    )
    record_payload["cwd"] = str(tmp_path)

    proc = subprocess.Popen(
        [sys.executable, "-m", "lesson.hooks.antigravity_mcp"],
        cwd=str(tmp_path),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        _rpc(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        for idx, tool_name in enumerate(["Bash", "Edit"], start=2):
            payload = {
                **record_payload,
                "tool_name": tool_name,
                "event_id": f"antigravity-{idx}",
                "tool_input": {"value": idx},
            }
            result = _rpc(
                proc,
                {
                    "jsonrpc": "2.0",
                    "id": idx,
                    "method": "tools/call",
                    "params": {"name": "lesson.record_event", "arguments": payload},
                },
            )
            assert result["result"]["content"][0]["text"] == "recorded"
    finally:
        proc.kill()
        proc.wait()

    assert len(sm.arc_path(slug).read_text(encoding="utf-8").splitlines()) == 2
    compress = subprocess.run(
        [sys.executable, "-m", "lesson.cli", "compress", "--cwd", str(tmp_path)],
        cwd=str(tmp_path),
        text=True,
        capture_output=True,
        check=False,
    )
    assert compress.returncode == 0
    assert sm.graph_path(slug).exists()
