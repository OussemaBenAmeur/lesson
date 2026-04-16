#!/usr/bin/env python3
"""
/lesson install script — multi-platform skill installer.

Usage:
    python3 scripts/install.py --platform <name>
    python3 scripts/install.py --list

Supported platforms:
    claude-code    Native (hooks + commands). Registers PostToolUse + Stop hooks in ~/.claude/hooks.json.
    codex          Appends skill to ~/.codex/CODEX.md (creates if missing).
    cursor         Writes .cursor/rules/lesson.mdc in the current project directory.
    gemini         Appends skill to ~/.gemini/GEMINI.md and optionally registers BeforeTool hook.
    copilot        Appends skill to ~/.github/copilot-instructions.md.
    opencode       Appends skill to ~/.opencode/OPENCODE.md.
    openclaw       Appends skill to ~/.claw/CLAW.md.
    droid          Appends skill to ~/.droid/DROID.md.
    trae           Appends skill to ~/.trae/TRAE.md.
    antigravity    Writes .agent/lesson.md in the current project directory.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = PLUGIN_ROOT / "skills"
HOOKS_DIR = PLUGIN_ROOT / "hooks"

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

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_skill(name: str) -> str:
    """Read a skill file and replace <plugin_root> with the actual path."""
    path = SKILLS_DIR / f"skill-{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Skill file not found: {path}")
    text = path.read_text(encoding="utf-8")
    return text.replace("<plugin_root>", str(PLUGIN_ROOT))


def _append_to_file(dest: Path, content: str, marker: str = "# /lesson") -> None:
    """Append content to dest, creating the file if needed. Skip if marker already present."""
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


def _write_file(dest: Path, content: str) -> None:
    """Write (overwrite) a file, creating parent dirs as needed."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")
    print(f"  ↳ Written to {dest}")


# ---------------------------------------------------------------------------
# Platform installers
# ---------------------------------------------------------------------------

def _install_claude_code() -> None:
    """Register PostToolUse + Stop hooks in ~/.claude/hooks.json."""
    hooks_json = Path.home() / ".claude" / "hooks.json"
    hooks_json.parent.mkdir(parents=True, exist_ok=True)

    hook_data: dict = {}
    if hooks_json.exists():
        try:
            hook_data = json.loads(hooks_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"  WARNING: {hooks_json} is malformed. Will merge carefully.")

    post_tool_cmd = f"python3 {HOOKS_DIR / 'post_tool_use.py'}"
    stop_cmd = f"python3 {HOOKS_DIR / 'stop.py'}"

    changed = False

    # PostToolUse
    post_hooks = hook_data.setdefault("PostToolUse", [])
    if not any(post_tool_cmd in str(h) for h in post_hooks):
        post_hooks.append({"command": post_tool_cmd})
        changed = True

    # Stop
    stop_hooks = hook_data.setdefault("Stop", [])
    if not any(stop_cmd in str(h) for h in stop_hooks):
        stop_hooks.append({"command": stop_cmd})
        changed = True

    if changed:
        hooks_json.write_text(json.dumps(hook_data, indent=2), encoding="utf-8")
        print(f"  ↳ Registered hooks in {hooks_json}")
    else:
        print(f"  ↳ Hooks already registered in {hooks_json}. No changes.")

    # Ensure commands are symlinked / noted (they live in PLUGIN_ROOT/commands/)
    print(f"  ↳ Commands: {PLUGIN_ROOT / 'commands'}/ (already part of the plugin)")


def _install_codex() -> None:
    dest = Path.home() / ".codex" / "CODEX.md"
    content = _read_skill("codex")
    # Codex uses $command prefix — the skill file already documents this
    _append_to_file(dest, content)


def _install_cursor() -> None:
    """Write a .mdc rule file into the current project's .cursor/rules/ directory."""
    cwd = Path.cwd()
    dest = cwd / ".cursor" / "rules" / "lesson.mdc"
    content = _read_skill("cursor")
    # Cursor .mdc files need specific frontmatter — skill-cursor.md already has it
    _write_file(dest, content)
    print(f"  ↳ Rule active for project at {cwd}")


def _install_gemini() -> None:
    dest = Path.home() / ".gemini" / "GEMINI.md"
    content = _read_skill("gemini")
    _append_to_file(dest, content)

    # Optionally register BeforeTool hook in ~/.gemini/settings.json
    settings_path = Path.home() / ".gemini" / "settings.json"
    settings: dict = {}
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass

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
    dest = Path.home() / ".github" / "copilot-instructions.md"
    content = _read_skill("copilot")
    _append_to_file(dest, content)


def _install_opencode() -> None:
    dest = Path.home() / ".opencode" / "OPENCODE.md"
    content = _read_skill("opencode")
    _append_to_file(dest, content)


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
    """Write a skill file into the current project's .agent/ directory."""
    cwd = Path.cwd()
    dest = cwd / ".agent" / "lesson.md"
    content = _read_skill("antigravity")
    _write_file(dest, content)
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

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install the /lesson skill for a specific AI coding platform.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--platform", "-p",
        choices=PLATFORMS,
        metavar="PLATFORM",
        help="Target platform. One of: " + ", ".join(PLATFORMS),
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List supported platforms and exit.",
    )
    args = parser.parse_args()

    if args.list:
        print("Supported platforms:")
        install_locations = {
            "claude-code":  "~/.claude/hooks.json  (PostToolUse + Stop hooks)",
            "codex":        "~/.codex/CODEX.md",
            "cursor":       "<project>/.cursor/rules/lesson.mdc",
            "gemini":       "~/.gemini/GEMINI.md + ~/.gemini/settings.json (BeforeTool hook)",
            "copilot":      "~/.github/copilot-instructions.md",
            "opencode":     "~/.opencode/OPENCODE.md",
            "openclaw":     "~/.claw/CLAW.md",
            "droid":        "~/.droid/DROID.md",
            "trae":         "~/.trae/TRAE.md",
            "antigravity":  "<project>/.agent/lesson.md",
        }
        for p in PLATFORMS:
            print(f"  {p:<16}  →  {install_locations[p]}")
        return 0

    if not args.platform:
        parser.print_help()
        return 1

    platform = args.platform
    print(f"Installing /lesson skill for: {platform}")

    try:
        _INSTALLERS[platform]()
    except Exception as exc:
        print(f"  ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"\n✓ /lesson installed for {platform}.")

    # Print platform-specific next steps
    next_steps = {
        "claude-code":  "Restart Claude Code or reload hooks. Then use /lesson in any project.",
        "codex":        "Restart Codex. Use $lesson to start a session.",
        "cursor":       "Reload Cursor. Use /lesson in chat.",
        "gemini":       "Restart Gemini CLI. Use /lesson in any project.",
        "copilot":      "Restart GitHub Copilot. Use /lesson in chat.",
        "opencode":     "Restart OpenCode. Use /lesson in chat.",
        "openclaw":     "Restart OpenClaw. Use /lesson in chat.",
        "droid":        "Restart Factory Droid. Use /lesson in chat.",
        "trae":         "Restart Trae. Use /lesson in chat.",
        "antigravity":  "The .agent/lesson.md file is now active for this project.",
    }
    print(f"  Next: {next_steps[platform]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
