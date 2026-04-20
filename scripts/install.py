#!/usr/bin/env python3
"""
/lesson install script — multi-platform skill installer.

Usage:
    python3 scripts/install.py --platform <name>
    python3 scripts/install.py --list

Supported platforms:
    claude-code    Native (hooks + commands). Registers PostToolUse + Stop hooks in ~/.claude/hooks.json.
    codex          Registers Codex hooks in ~/.codex/hooks.json and appends the fallback skill to ~/.codex/CODEX.md.
    cursor         Writes .cursor/rules/lesson.mdc in the current project directory.
    gemini         Appends skill to ~/.gemini/GEMINI.md and optionally registers BeforeTool hook.
    copilot        Appends skill to ~/.github/copilot-instructions.md.
    opencode       Appends skill to ~/.opencode/OPENCODE.md and installs the OpenCode plugin bridge.
    openclaw       Appends skill to ~/.claw/CLAW.md.
    droid          Appends skill to ~/.droid/DROID.md.
    trae           Appends skill to ~/.trae/TRAE.md.
    antigravity    Writes .agent/lesson.md in the current project directory.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = PLUGIN_ROOT / "skills"
HOOKS_DIR = PLUGIN_ROOT / "hooks"
LESSON_DIR = PLUGIN_ROOT / "lesson"
SHARED_SKILL = SKILLS_DIR / "_shared.md"

_HEADER_RE = re.compile(r"<!--\s*(.*?)\s*-->", re.DOTALL)
_DEFAULT_VARS = {
    "platform": "unknown",
    "data_root": ".claude/lessons",
    "cmd_prefix": "/",
}

PLATFORMS = [
    "claude-code",
    "codex",
    "cursor",
    "gemini",
    "copilot",
    "opencode",
    "openclaw",
    "droid",
    "trae",
    "antigravity",
]


def _parse_header(text: str) -> dict[str, str]:
    vars_ = dict(_DEFAULT_VARS)
    match = _HEADER_RE.search(text)
    if not match:
        return vars_
    for line in match.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            vars_[key.strip()] = value.strip()
    return vars_


def _render_shared(vars_: dict[str, str]) -> str:
    if not SHARED_SKILL.exists():
        return ""
    body = SHARED_SKILL.read_text(encoding="utf-8")
    body = _HEADER_RE.sub("", body, count=1).lstrip()
    replacements = {
        "{{DATA_ROOT}}": vars_["data_root"],
        "{{PLATFORM}}": vars_["platform"],
        "{{CMD_PREFIX}}": vars_["cmd_prefix"],
    }
    for src, dst in replacements.items():
        body = body.replace(src, dst)
    return body


def _read_skill(name: str) -> str:
    path = SKILLS_DIR / f"skill-{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Skill file not found: {path}")
    header_text = path.read_text(encoding="utf-8")
    vars_ = _parse_header(header_text)
    shared = _render_shared(vars_)
    combined = header_text if not shared else f"{header_text.rstrip()}\n\n{shared}"
    return combined.replace("<plugin_root>", str(PLUGIN_ROOT))


def _append_to_file(dest: Path, content: str, marker: str = "# /lesson") -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        existing = dest.read_text(encoding="utf-8")
        if marker in existing:
            print(f"  ↳ Already installed in {dest} (found marker '{marker}'). Skipping.")
            return
        dest.write_text(existing.rstrip() + "\n\n---\n\n" + content + "\n", encoding="utf-8")
    else:
        dest.write_text(content + "\n", encoding="utf-8")
    print(f"  ↳ Written to {dest}")


def _remove_from_file(dest: Path, marker: str = "# /lesson") -> None:
    if not dest.exists():
        return
    existing = dest.read_text(encoding="utf-8")
    idx = existing.find(marker)
    if idx == -1:
        return
    separator = "\n\n---\n\n"
    start = existing.rfind(separator, 0, idx)
    start = start if start != -1 else idx
    end = existing.find(separator, idx)
    if end == -1:
        updated = existing[:start].rstrip()
    else:
        updated = (existing[:start] + existing[end + len(separator):]).strip()
    if updated:
        dest.write_text(updated.rstrip() + "\n", encoding="utf-8")
    else:
        dest.unlink()
    print(f"  ↳ Removed lesson block from {dest}")


def _write_file(dest: Path, content: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")
    print(f"  ↳ Written to {dest}")


def _copy_file(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    print(f"  ↳ Installed {dest}")


def _remove_file(path: Path) -> None:
    if path.exists():
        path.unlink()
        print(f"  ↳ Removed {path}")


def _remove_empty_parents(path: Path, stop: Path) -> None:
    current = path
    while current != stop and current.exists():
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent


def _deep_merge(base: Any, patch: Any) -> Any:
    if isinstance(base, dict) and isinstance(patch, dict):
        merged = {key: deepcopy(value) for key, value in base.items()}
        for key, value in patch.items():
            if key in merged:
                merged[key] = _deep_merge(merged[key], value)
            else:
                merged[key] = deepcopy(value)
        return merged
    if isinstance(base, list) and isinstance(patch, list):
        merged = list(base)
        for item in patch:
            if item not in merged:
                merged.append(deepcopy(item))
        return merged
    return deepcopy(patch)


def _merge_json(path: Path, patch: dict[str, Any]) -> dict[str, Any]:
    current: dict[str, Any] = {}
    if path.exists():
        current = json.loads(path.read_text(encoding="utf-8"))
    merged = _deep_merge(current, patch)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    print(f"  ↳ Updated {path}")
    return merged


def _deep_remove(base: Any, patch: Any) -> Any:
    if isinstance(base, dict) and isinstance(patch, dict):
        updated = {key: deepcopy(value) for key, value in base.items()}
        for key, value in patch.items():
            if key not in updated:
                continue
            new_value = _deep_remove(updated[key], value)
            if new_value in ({}, [], None):
                updated.pop(key, None)
            else:
                updated[key] = new_value
        return updated
    if isinstance(base, list) and isinstance(patch, list):
        remaining = list(base)
        for item in patch:
            remaining = [candidate for candidate in remaining if candidate != item]
        return remaining
    if base == patch:
        return None
    return base


def _remove_json_patch(path: Path, patch: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return {}
    current = json.loads(path.read_text(encoding="utf-8"))
    updated = _deep_remove(current, patch)
    if updated in ({}, [], None):
        path.unlink()
        print(f"  ↳ Removed {path}")
        return {}
    path.write_text(json.dumps(updated, indent=2) + "\n", encoding="utf-8")
    print(f"  ↳ Updated {path}")
    return updated


def _toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    raise TypeError(f"Unsupported TOML value: {value!r}")


def _render_toml(data: dict[str, Any], prefix: tuple[str, ...] = ()) -> list[str]:
    lines: list[str] = []
    if prefix:
        lines.append(f"[{'.'.join(prefix)}]")
    scalars = [(key, value) for key, value in data.items() if not isinstance(value, dict)]
    tables = [(key, value) for key, value in data.items() if isinstance(value, dict)]
    for key, value in scalars:
        lines.append(f"{key} = {_toml_value(value)}")
    for index, (key, value) in enumerate(tables):
        if lines:
            lines.append("")
        lines.extend(_render_toml(value, prefix + (key,)))
        if index != len(tables) - 1:
            lines.append("")
    return lines


def _merge_toml(path: Path, patch: dict[str, Any]) -> dict[str, Any]:
    current: dict[str, Any] = {}
    if path.exists():
        if tomllib is None:
            raise RuntimeError("tomllib is required to merge TOML configs")
        current = tomllib.loads(path.read_text(encoding="utf-8"))
    merged = _deep_merge(current, patch)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(_render_toml(merged)).strip()
    path.write_text(content + "\n", encoding="utf-8")
    print(f"  ↳ Updated {path}")
    return merged


def _remove_toml_patch(path: Path, patch: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return {}
    if tomllib is None:
        raise RuntimeError("tomllib is required to edit TOML configs")
    current = tomllib.loads(path.read_text(encoding="utf-8"))
    updated = _deep_remove(current, patch)
    if updated in ({}, [], None):
        path.unlink()
        print(f"  ↳ Removed {path}")
        return {}
    content = "\n".join(_render_toml(updated)).strip()
    path.write_text(content + "\n", encoding="utf-8")
    print(f"  ↳ Updated {path}")
    return updated


def _install_python_adapters(dest: Path, sources: list[Path]) -> None:
    for src in sources:
        _copy_file(src, dest / src.name)


def _install_hook_support(dest: Path, module_names: list[str]) -> None:
    support_root = dest / "_support" / "lesson"
    hooks_dest = support_root / "hooks"
    _copy_file(LESSON_DIR / "__init__.py", support_root / "__init__.py")
    _copy_file(LESSON_DIR / "hooks" / "__init__.py", hooks_dest / "__init__.py")
    for name in module_names:
        _copy_file(LESSON_DIR / "hooks" / name, hooks_dest / name)


def _detect_version(cmd: list[str], minimum: tuple[int, int, int]) -> tuple[bool, str | None]:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return False, None

    text = " ".join(part for part in [result.stdout, result.stderr] if part).strip()
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", text)
    if not match:
        return False, text or None
    version = tuple(int(group) for group in match.groups())
    return version >= minimum, ".".join(match.groups())


def _install_claude_code() -> None:
    hooks_json = Path.home() / ".claude" / "hooks.json"
    hooks_json.parent.mkdir(parents=True, exist_ok=True)

    hook_data: dict[str, Any] = {}
    if hooks_json.exists():
        try:
            hook_data = json.loads(hooks_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"  WARNING: {hooks_json} is malformed. Will merge carefully.")

    post_tool_cmd = f"python3 {HOOKS_DIR / 'post_tool_use.py'}"
    stop_cmd = f"python3 {HOOKS_DIR / 'stop.py'}"

    changed = False
    post_hooks = hook_data.setdefault("PostToolUse", [])
    if not any(post_tool_cmd in str(hook) for hook in post_hooks):
        post_hooks.append({"command": post_tool_cmd})
        changed = True

    stop_hooks = hook_data.setdefault("Stop", [])
    if not any(stop_cmd in str(hook) for hook in stop_hooks):
        stop_hooks.append({"command": stop_cmd})
        changed = True

    if changed:
        hooks_json.write_text(json.dumps(hook_data, indent=2), encoding="utf-8")
        print(f"  ↳ Registered hooks in {hooks_json}")
    else:
        print(f"  ↳ Hooks already registered in {hooks_json}. No changes.")

    commands_src = PLUGIN_ROOT / "commands"
    commands_dst = Path.home() / ".claude" / "commands"
    commands_dst.mkdir(parents=True, exist_ok=True)

    for src in sorted(commands_src.glob("*.md")):
        dst = commands_dst / src.name
        if dst.is_symlink():
            dst.unlink()
        elif dst.exists():
            print(f"  WARNING: {dst} already exists and is not a symlink — skipping.")
            continue
        dst.symlink_to(src)
        print(f"  ↳ /{src.stem}  →  {dst}")


def _install_codex() -> None:
    codex_dir = Path.home() / ".codex"
    hooks_dir = codex_dir / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)

    content = _read_skill("codex")
    _append_to_file(codex_dir / "CODEX.md", content)

    _install_python_adapters(
        hooks_dir,
        [
            HOOKS_DIR / "codex" / "post_tool_use_codex.py",
            HOOKS_DIR / "codex" / "stop_codex.py",
            HOOKS_DIR / "codex" / "session_start_codex.py",
        ],
    )
    _install_hook_support(
        hooks_dir,
        [
            "__init__.py",
            "adapter.py",
            "claude_code.py",
            "codex.py",
            "session_start.py",
            "stop.py",
        ],
    )

    template = json.loads((HOOKS_DIR / "codex" / "hooks.json").read_text(encoding="utf-8"))
    _merge_json(codex_dir / "hooks.json", template)
    _merge_toml(codex_dir / "config.toml", {"features": {"codex_hooks": True}})

    supported, detected = _detect_version(["codex", "--version"], (0, 114, 0))
    if detected is None:
        print("  WARNING: `codex --version` was not available. Hooks were installed anyway.")
    elif not supported:
        print(
            f"  WARNING: Detected Codex {detected}. Hook support is documented for >= 0.114.0."
        )
    print("  ↳ Note: current Codex hook payloads only expose Bash tool events.")


def _install_cursor() -> None:
    cwd = Path.cwd()
    content = _read_skill("cursor")
    dest = cwd / ".cursor" / "rules" / "lesson.mdc"
    _write_file(dest, content)

    cursor_home = Path.home() / ".cursor"
    global_hooks_dir = cursor_home / "hooks"
    project_hooks_dir = cwd / ".cursor" / "hooks"

    sources = [
        HOOKS_DIR / "cursor" / "post_tool_use_cursor.py",
        HOOKS_DIR / "cursor" / "after_file_edit_cursor.py",
        HOOKS_DIR / "cursor" / "stop_cursor.py",
    ]
    _install_python_adapters(global_hooks_dir, sources)
    _install_hook_support(
        global_hooks_dir,
        [
            "__init__.py",
            "adapter.py",
            "cursor.py",
        ],
    )

    _install_python_adapters(project_hooks_dir, sources)
    _install_hook_support(
        project_hooks_dir,
        [
            "__init__.py",
            "adapter.py",
            "cursor.py",
        ],
    )

    template = json.loads((HOOKS_DIR / "cursor" / "hooks.json").read_text(encoding="utf-8"))
    _merge_json(cursor_home / "hooks.json", template)
    _merge_json(cwd / ".cursor" / "hooks.json", template)
    print(f"  ↳ Rule active for project at {cwd}")


def _install_gemini() -> None:
    dest = Path.home() / ".gemini" / "GEMINI.md"
    content = _read_skill("gemini")
    _append_to_file(dest, content)

    settings_path = Path.home() / ".gemini" / "settings.json"
    settings: dict[str, Any] = {}
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            settings = {}

    hook_cmd = f"python3 {HOOKS_DIR / 'post_tool_use.py'}"
    hooks = settings.setdefault("hooks", {})
    if "beforeTool" not in hooks:
        hooks["beforeTool"] = hook_cmd
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
        print(f"  ↳ Registered BeforeTool hook in {settings_path}")
    else:
        print(f"  ↳ BeforeTool hook already set in {settings_path}. Skipping.")


def _install_copilot() -> None:
    cwd = Path.cwd()
    if not (cwd / ".git").exists():
        raise RuntimeError("Copilot hook install must run inside a git repository")

    dest = Path.home() / ".github" / "copilot-instructions.md"
    content = _read_skill("copilot")
    _append_to_file(dest, content)

    hooks_root = cwd / ".github" / "hooks"
    config_path = hooks_root / "lesson.json"
    scripts_root = hooks_root / "scripts" / "lesson"

    _copy_file(HOOKS_DIR / "copilot" / "lesson.json", config_path)
    for name in [
        "post_tool_use_copilot.py",
        "session_end_copilot.py",
        "session_start_copilot.py",
        "user_prompt_copilot.py",
        "post_tool_use_copilot.sh",
        "session_end_copilot.sh",
        "session_start_copilot.sh",
        "user_prompt_copilot.sh",
    ]:
        _copy_file(HOOKS_DIR / "copilot" / name, scripts_root / name)
    _install_hook_support(
        scripts_root,
        [
            "__init__.py",
            "adapter.py",
            "copilot.py",
            "prompt_capture.py",
            "session_start.py",
            "stop.py",
        ],
    )


def _install_opencode() -> None:
    home = Path.home()
    dest = home / ".opencode" / "OPENCODE.md"
    content = _read_skill("opencode")
    _append_to_file(dest, content)

    supported, detected = _detect_version(["node", "--version"], (18, 0, 0))
    if detected is None:
        print("  WARNING: `node --version` was not available. Installed the prebuilt plugin anyway.")
    elif not supported:
        print(f"  WARNING: Detected Node {detected}. OpenCode plugin support is documented for >= 18.0.0.")

    plugin_dir = home / ".config" / "opencode" / "plugins" / "lesson"
    bridge_dir = home / ".local" / "share" / "lesson"

    _copy_file(HOOKS_DIR / "opencode" / "index.mjs", plugin_dir / "index.mjs")
    _copy_file(HOOKS_DIR / "opencode" / "opencode_bridge.py", bridge_dir / "opencode_bridge.py")
    _install_hook_support(
        bridge_dir,
        [
            "__init__.py",
            "adapter.py",
            "opencode.py",
            "session_start.py",
            "stop.py",
        ],
    )

    # OpenCode reads `~/.config/opencode/opencode.json` by default (XDG);
    # older installs read `~/.opencode/opencode.json`. Merge into both so the
    # plugin is picked up regardless of which path the user's runtime uses.
    plugin_patch = {"plugin": [str(plugin_dir / "index.mjs")]}
    for config_path in (
        home / ".config" / "opencode" / "opencode.json",
        home / ".opencode" / "opencode.json",
    ):
        _merge_json(config_path, plugin_patch)


def _uninstall_claude_code() -> None:
    _remove_json_patch(
        Path.home() / ".claude" / "hooks.json",
        {
            "PostToolUse": [{"command": f"python3 {HOOKS_DIR / 'post_tool_use.py'}"}],
            "Stop": [{"command": f"python3 {HOOKS_DIR / 'stop.py'}"}],
        },
    )
    commands_dst = Path.home() / ".claude" / "commands"
    for src in sorted((PLUGIN_ROOT / "commands").glob("*.md")):
        _remove_file(commands_dst / src.name)


def _uninstall_codex() -> None:
    codex_dir = Path.home() / ".codex"
    _remove_from_file(codex_dir / "CODEX.md")
    _remove_json_patch(codex_dir / "hooks.json", json.loads((HOOKS_DIR / "codex" / "hooks.json").read_text(encoding="utf-8")))
    _remove_toml_patch(codex_dir / "config.toml", {"features": {"codex_hooks": True}})
    hooks_dir = codex_dir / "hooks"
    for name in ["post_tool_use_codex.py", "stop_codex.py", "session_start_codex.py"]:
        _remove_file(hooks_dir / name)
    # `stop.py` is a generic filename; only delete it if it's the one we shipped.
    generic_stop = hooks_dir / "stop.py"
    shipped_stop = HOOKS_DIR / "stop.py"
    try:
        if (
            generic_stop.exists()
            and shipped_stop.exists()
            and generic_stop.read_bytes() == shipped_stop.read_bytes()
        ):
            _remove_file(generic_stop)
    except Exception:
        pass
    shutil.rmtree(hooks_dir / "_support", ignore_errors=True)


def _uninstall_cursor() -> None:
    cwd = Path.cwd()
    _remove_file(cwd / ".cursor" / "rules" / "lesson.mdc")
    template = json.loads((HOOKS_DIR / "cursor" / "hooks.json").read_text(encoding="utf-8"))
    _remove_json_patch(Path.home() / ".cursor" / "hooks.json", template)
    _remove_json_patch(cwd / ".cursor" / "hooks.json", template)
    for base in [Path.home() / ".cursor" / "hooks", cwd / ".cursor" / "hooks"]:
        for name in ["post_tool_use_cursor.py", "after_file_edit_cursor.py", "stop_cursor.py"]:
            _remove_file(base / name)
        shutil.rmtree(base / "_support", ignore_errors=True)


def _uninstall_gemini() -> None:
    _remove_from_file(Path.home() / ".gemini" / "GEMINI.md")
    _remove_json_patch(
        Path.home() / ".gemini" / "settings.json",
        {"hooks": {"beforeTool": f"python3 {HOOKS_DIR / 'post_tool_use.py'}"}},
    )


def _uninstall_copilot() -> None:
    cwd = Path.cwd()
    _remove_from_file(Path.home() / ".github" / "copilot-instructions.md")
    _remove_file(cwd / ".github" / "hooks" / "lesson.json")
    scripts_root = cwd / ".github" / "hooks" / "scripts" / "lesson"
    for name in [
        "post_tool_use_copilot.py",
        "session_end_copilot.py",
        "session_start_copilot.py",
        "user_prompt_copilot.py",
        "post_tool_use_copilot.sh",
        "session_end_copilot.sh",
        "session_start_copilot.sh",
        "user_prompt_copilot.sh",
    ]:
        _remove_file(scripts_root / name)
    shutil.rmtree(scripts_root / "_support", ignore_errors=True)


def _uninstall_opencode() -> None:
    home = Path.home()
    _remove_from_file(home / ".opencode" / "OPENCODE.md")
    plugin_path = home / ".config" / "opencode" / "plugins" / "lesson" / "index.mjs"
    plugin_patch = {"plugin": [str(plugin_path)]}
    for config_path in (
        home / ".config" / "opencode" / "opencode.json",
        home / ".opencode" / "opencode.json",
    ):
        _remove_json_patch(config_path, plugin_patch)
    _remove_file(plugin_path)
    bridge_dir = home / ".local" / "share" / "lesson"
    _remove_file(bridge_dir / "opencode_bridge.py")
    shutil.rmtree(bridge_dir / "_support", ignore_errors=True)


def _uninstall_openclaw() -> None:
    _remove_from_file(Path.home() / ".claw" / "CLAW.md")


def _uninstall_droid() -> None:
    _remove_from_file(Path.home() / ".droid" / "DROID.md")


def _uninstall_trae() -> None:
    _remove_from_file(Path.home() / ".trae" / "TRAE.md")


def _uninstall_antigravity() -> None:
    cwd = Path.cwd()
    home = Path.home()
    _remove_file(cwd / ".agent" / "lesson.md")
    _remove_file(cwd / ".agent" / "rules" / "lesson.md")
    _remove_file(cwd / ".agent" / "workflows" / "lesson.md")
    bridge_dir = home / ".local" / "share" / "lesson"
    _remove_file(bridge_dir / "antigravity_mcp.py")
    shutil.rmtree(bridge_dir / "_support", ignore_errors=True)
    _remove_json_patch(
        home / ".gemini" / "settings.json",
        {
            "mcpServers": {
                "lesson": {
                    "command": "python3",
                    "args": [str(bridge_dir / "antigravity_mcp.py")],
                    "trust": True,
                }
            }
        },
    )


def _install_openclaw() -> None:
    dest = Path.home() / ".claw" / "CLAW.md"
    content = _read_skill("openclaw")
    _append_to_file(dest, content)


def _install_droid() -> None:
    dest = Path.home() / ".droid" / "DROID.md"
    content = _read_skill("droid")
    _append_to_file(dest, content)


def _install_trae() -> None:
    dest = Path.home() / ".trae" / "TRAE.md"
    content = _read_skill("trae")
    _append_to_file(dest, content)


def _install_antigravity() -> None:
    cwd = Path.cwd()
    home = Path.home()
    dest = cwd / ".agent" / "lesson.md"
    content = _read_skill("antigravity")
    _write_file(dest, content)
    _copy_file(HOOKS_DIR / "antigravity" / "rules" / "lesson.md", cwd / ".agent" / "rules" / "lesson.md")
    _copy_file(
        HOOKS_DIR / "antigravity" / "workflows" / "lesson.md",
        cwd / ".agent" / "workflows" / "lesson.md",
    )

    bridge_dir = home / ".local" / "share" / "lesson"
    _copy_file(LESSON_DIR / "hooks" / "antigravity_mcp.py", bridge_dir / "antigravity_mcp.py")
    _install_hook_support(
        bridge_dir,
        [
            "__init__.py",
            "adapter.py",
            "antigravity.py",
            "stop.py",
        ],
    )

    _merge_json(
        home / ".gemini" / "settings.json",
        {
            "mcpServers": {
                "lesson": {
                    "command": "python3",
                    "args": [str(bridge_dir / "antigravity_mcp.py")],
                    "trust": True,
                }
            }
        },
    )
    print(f"  ↳ Agent file active for project at {cwd}")


_INSTALLERS = {
    "claude-code": _install_claude_code,
    "codex": _install_codex,
    "cursor": _install_cursor,
    "gemini": _install_gemini,
    "copilot": _install_copilot,
    "opencode": _install_opencode,
    "openclaw": _install_openclaw,
    "droid": _install_droid,
    "trae": _install_trae,
    "antigravity": _install_antigravity,
}

_UNINSTALLERS = {
    "claude-code": _uninstall_claude_code,
    "codex": _uninstall_codex,
    "cursor": _uninstall_cursor,
    "gemini": _uninstall_gemini,
    "copilot": _uninstall_copilot,
    "opencode": _uninstall_opencode,
    "openclaw": _uninstall_openclaw,
    "droid": _uninstall_droid,
    "trae": _uninstall_trae,
    "antigravity": _uninstall_antigravity,
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install the /lesson skill for a specific AI coding platform.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--platform",
        "-p",
        choices=PLATFORMS,
        metavar="PLATFORM",
        help="Target platform. One of: " + ", ".join(PLATFORMS),
    )
    parser.add_argument(
        "--list",
        "-l",
        action="store_true",
        help="List supported platforms and exit.",
    )
    parser.add_argument(
        "--uninstall",
        action="store_true",
        help="Remove the installed lesson integration for the selected platform.",
    )
    args = parser.parse_args()

    if args.list:
        print("Supported platforms:")
        install_locations = {
            "claude-code": "~/.claude/hooks.json  (PostToolUse + Stop hooks)",
            "codex": "~/.codex/hooks.json + ~/.codex/config.toml + ~/.codex/CODEX.md",
            "cursor": "~/.cursor/hooks.json + <project>/.cursor/hooks.json + <project>/.cursor/rules/lesson.mdc",
            "gemini": "~/.gemini/GEMINI.md + ~/.gemini/settings.json (BeforeTool hook)",
            "copilot": "~/.github/copilot-instructions.md + <repo>/.github/hooks/lesson.json",
            "opencode": "~/.opencode/OPENCODE.md + ~/.opencode/opencode.json + ~/.config/opencode/plugins/lesson/index.mjs",
            "openclaw": "~/.claw/CLAW.md",
            "droid": "~/.droid/DROID.md",
            "trae": "~/.trae/TRAE.md",
            "antigravity": "<project>/.agent/lesson.md + .agent/rules + .agent/workflows + ~/.gemini/settings.json",
        }
        for platform in PLATFORMS:
            print(f"  {platform:<16}  →  {install_locations[platform]}")
        return 0

    if not args.platform:
        parser.print_help()
        return 1

    platform = args.platform
    action = "Uninstalling" if args.uninstall else "Installing"
    print(f"{action} /lesson skill for: {platform}")

    try:
        if args.uninstall:
            _UNINSTALLERS[platform]()
        else:
            _INSTALLERS[platform]()
    except Exception as exc:
        print(f"  ERROR: {exc}", file=sys.stderr)
        return 1

    if args.uninstall:
        print(f"\n✓ /lesson uninstalled for {platform}.")
        return 0

    print(f"\n✓ /lesson installed for {platform}.")

    next_steps = {
        "claude-code": "Restart Claude Code or reload hooks. Then use /lesson in any project.",
        "codex": "Restart Codex. Hooks are now configured; use $lesson to start a session.",
        "cursor": "Reload Cursor. Use /lesson in chat.",
        "gemini": "Restart Gemini CLI. Use /lesson in any project.",
        "copilot": "Restart GitHub Copilot. Use /lesson in chat.",
        "opencode": "Restart OpenCode. Use /lesson in chat.",
        "openclaw": "Restart OpenClaw. Use /lesson in chat.",
        "droid": "Restart Factory Droid. Use /lesson in chat.",
        "trae": "Restart Trae. Use /lesson in chat.",
        "antigravity": "The .agent/lesson.md file is now active for this project.",
    }
    print(f"  Next: {next_steps[platform]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
