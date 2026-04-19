"""Integration test for installed Codex hook assets."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

from lesson.session import SessionManager

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "hooks"
INSTALL_PATH = Path(__file__).resolve().parents[2] / "scripts" / "install.py"


def _load_install_module():
    spec = importlib.util.spec_from_file_location("lesson_install_script", INSTALL_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_installed_codex_hooks_track_session_start_and_post_tool_use(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    home = tmp_path / "home"
    monkeypatch.chdir(repo)

    module = _load_install_module()
    monkeypatch.setattr(module.Path, "home", staticmethod(lambda: home))
    monkeypatch.setattr(module, "_detect_version", lambda cmd, minimum: (True, "0.114.0"))
    module._install_codex()

    sm = SessionManager(repo)
    slug = sm.create("codex integration", platform="codex")

    hooks_dir = home / ".codex" / "hooks"
    session_start_script = hooks_dir / "session_start_codex.py"
    post_tool_use_script = hooks_dir / "post_tool_use_codex.py"

    session_start_payload = {"cwd": str(repo), "session_id": "codex-session-123"}
    start_proc = subprocess.run(
        [sys.executable, str(session_start_script)],
        cwd=str(repo),
        input=json.dumps(session_start_payload),
        text=True,
        capture_output=True,
        check=False,
    )
    assert start_proc.returncode == 0

    meta = sm.meta(slug)
    assert meta["hook_state"]["platform"] == "codex"
    assert meta["hook_state"]["session_id"] == "codex-session-123"

    post_payload = json.loads(
        (FIXTURES / "codex" / "post_tool_use.shape.json").read_text(encoding="utf-8")
    )
    post_payload["cwd"] = str(repo)
    post_proc = subprocess.run(
        [sys.executable, str(post_tool_use_script)],
        cwd=str(repo),
        input=json.dumps(post_payload),
        text=True,
        capture_output=True,
        check=False,
    )
    assert post_proc.returncode == 0

    arc_lines = sm.arc_path(slug).read_text(encoding="utf-8").splitlines()
    assert len(arc_lines) == 1
