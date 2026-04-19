"""Integration test for installed GitHub Copilot CLI hook assets."""

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


def _payload(name: str, cwd: Path) -> dict:
    data = json.loads((FIXTURES / "copilot" / name).read_text(encoding="utf-8"))
    data["cwd"] = str(cwd)
    return data


def test_installed_copilot_hook_logs_and_compresses(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    home = tmp_path / "home"
    monkeypatch.chdir(repo)

    module = _load_install_module()
    monkeypatch.setattr(module.Path, "home", staticmethod(lambda: home))
    module._install_copilot()

    sm = SessionManager(repo)
    slug = sm.create("copilot integration", platform="copilot")

    hook_script = repo / ".github" / "hooks" / "scripts" / "lesson" / "post_tool_use_copilot.py"
    prompt_hook_script = repo / ".github" / "hooks" / "scripts" / "lesson" / "user_prompt_copilot.py"
    payload = _payload("post_tool_use.shape.json", repo)
    prompt_payload = _payload("user_prompt_submitted.shape.json", repo)
    second_payload = {**payload, "toolName": "Edit", "toolInput": {"file_path": "main.py"}, "toolOutput": {"stdout": "saved"}}

    prompt_proc = subprocess.run(
        [sys.executable, str(prompt_hook_script)],
        cwd=str(repo),
        input=json.dumps(prompt_payload),
        text=True,
        capture_output=True,
        check=False,
    )
    assert prompt_proc.returncode == 0

    for event in [payload, second_payload]:
        proc = subprocess.run(
            [sys.executable, str(hook_script)],
            cwd=str(repo),
            input=json.dumps(event),
            text=True,
            capture_output=True,
            check=False,
        )
        assert proc.returncode == 0

    arc_lines = sm.arc_path(slug).read_text(encoding="utf-8").splitlines()
    assert len(arc_lines) == 2
    prompt_lines = sm.prompts_path(slug).read_text(encoding="utf-8").splitlines()
    assert len(prompt_lines) == 1

    compress = subprocess.run(
        [sys.executable, "-m", "lesson.cli", "compress", "--cwd", str(repo)],
        cwd=str(repo),
        text=True,
        capture_output=True,
        check=False,
    )
    assert compress.returncode == 0
    assert sm.graph_path(slug).exists()
    assert any(sm.session_dir(slug).glob("arc.jsonl.archive.*"))
