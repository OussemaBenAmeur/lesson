"""Unit tests for installer merge helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path


INSTALL_PATH = Path(__file__).resolve().parents[2] / "scripts" / "install.py"


def _load_install_module():
    spec = importlib.util.spec_from_file_location("lesson_install_script", INSTALL_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_merge_json_is_idempotent(tmp_path):
    module = _load_install_module()
    path = tmp_path / "hooks.json"
    path.write_text('{"hooks":{"Stop":[{"command":"existing"}]}}', encoding="utf-8")

    patch = {"hooks": {"Stop": [{"command": "existing"}], "PostToolUse": [{"command": "new"}]}}
    module._merge_json(path, patch)
    first = path.read_text(encoding="utf-8")
    module._merge_json(path, patch)
    second = path.read_text(encoding="utf-8")

    assert first == second
    assert '"PostToolUse"' in second


def test_merge_toml_preserves_existing_keys(tmp_path):
    module = _load_install_module()
    path = tmp_path / "config.toml"
    path.write_text('[features]\nexisting = true\n\n[profile]\nname = "dev"\n', encoding="utf-8")

    module._merge_toml(path, {"features": {"codex_hooks": True}})
    content = path.read_text(encoding="utf-8")

    assert "existing = true" in content
    assert "codex_hooks = true" in content
    assert '[profile]' in content


def test_remove_json_patch_prunes_matching_values(tmp_path):
    module = _load_install_module()
    path = tmp_path / "hooks.json"
    path.write_text('{"hooks":{"Stop":[{"command":"keep"},{"command":"drop"}]}}', encoding="utf-8")

    module._remove_json_patch(path, {"hooks": {"Stop": [{"command": "drop"}]}})

    content = path.read_text(encoding="utf-8")
    assert '"keep"' in content
    assert '"drop"' not in content


def test_remove_toml_patch_prunes_matching_values(tmp_path):
    module = _load_install_module()
    path = tmp_path / "config.toml"
    path.write_text('[features]\nexisting = true\ncodex_hooks = true\n', encoding="utf-8")

    module._remove_toml_patch(path, {"features": {"codex_hooks": True}})

    content = path.read_text(encoding="utf-8")
    assert "existing = true" in content
    assert "codex_hooks = true" not in content


def test_install_copilot_writes_repo_hook_files(tmp_path, monkeypatch):
    module = _load_install_module()
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    monkeypatch.chdir(repo)
    monkeypatch.setattr(module.Path, "home", staticmethod(lambda: tmp_path / "home"))

    module._install_copilot()

    assert (repo / ".github" / "hooks" / "lesson.json").exists()
    assert (repo / ".github" / "hooks" / "scripts" / "lesson" / "post_tool_use_copilot.py").exists()
    assert (repo / ".github" / "hooks" / "scripts" / "lesson" / "user_prompt_copilot.py").exists()
    assert (repo / ".github" / "hooks" / "scripts" / "lesson" / "_support" / "lesson" / "hooks" / "copilot.py").exists()
    assert (repo / ".github" / "hooks" / "scripts" / "lesson" / "_support" / "lesson" / "hooks" / "prompt_capture.py").exists()


def test_install_opencode_writes_plugin_and_bridge(tmp_path, monkeypatch):
    module = _load_install_module()
    home = tmp_path / "home"
    monkeypatch.setattr(module.Path, "home", staticmethod(lambda: home))

    module._install_opencode()

    assert (home / ".config" / "opencode" / "plugins" / "lesson" / "index.mjs").exists()
    assert (home / ".local" / "share" / "lesson" / "opencode_bridge.py").exists()
    assert (home / ".local" / "share" / "lesson" / "_support" / "lesson" / "hooks" / "opencode.py").exists()
    config = (home / ".opencode" / "opencode.json").read_text(encoding="utf-8")
    assert "index.mjs" in config


def test_install_antigravity_writes_rules_and_mcp_config(tmp_path, monkeypatch):
    module = _load_install_module()
    repo = tmp_path / "repo"
    repo.mkdir()
    home = tmp_path / "home"
    monkeypatch.chdir(repo)
    monkeypatch.setattr(module.Path, "home", staticmethod(lambda: home))

    module._install_antigravity()

    assert (repo / ".agent" / "lesson.md").exists()
    assert (repo / ".agent" / "rules" / "lesson.md").exists()
    assert (repo / ".agent" / "workflows" / "lesson.md").exists()
    assert (home / ".local" / "share" / "lesson" / "antigravity_mcp.py").exists()
    settings = (home / ".gemini" / "settings.json").read_text(encoding="utf-8")
    assert "antigravity_mcp.py" in settings


def test_uninstall_opencode_removes_plugin_and_bridge(tmp_path, monkeypatch):
    module = _load_install_module()
    home = tmp_path / "home"
    monkeypatch.setattr(module.Path, "home", staticmethod(lambda: home))

    module._install_opencode()
    module._uninstall_opencode()

    assert not (home / ".config" / "opencode" / "plugins" / "lesson" / "index.mjs").exists()
    assert not (home / ".local" / "share" / "lesson" / "opencode_bridge.py").exists()
