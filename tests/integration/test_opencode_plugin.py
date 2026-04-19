"""Integration test for the OpenCode bridge path."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from lesson.session import SessionManager

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "hooks"
BRIDGE = Path(__file__).resolve().parents[2] / "hooks" / "opencode" / "opencode_bridge.py"


def test_opencode_bridge_logs_fixture_payload(tmp_path):
    sm = SessionManager(tmp_path)
    slug = sm.create("opencode integration", platform="opencode")
    payload = json.loads((FIXTURES / "opencode" / "post_tool_use.shape.json").read_text(encoding="utf-8"))
    payload["cwd"] = str(tmp_path)

    proc = subprocess.run(
        [sys.executable, str(BRIDGE), "postToolUse"],
        cwd=str(tmp_path),
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0
    assert len(sm.arc_path(slug).read_text(encoding="utf-8").splitlines()) == 1
