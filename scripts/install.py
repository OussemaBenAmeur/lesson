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
import re
import shutil
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = PLUGIN_ROOT / "skills"
HOOKS_DIR = PLUGIN_ROOT / "hooks"
SHARED_SKILL = SKILLS_DIR / "_shared.md"

# Per-platform skill files carry a leading HTML-comment header with:
#   platform: <name>
#   data_root: .claude/lessons | .cursor/lessons
#   cmd_prefix: / | $
# Those values are substituted into _shared.md and concatenated below the
# platform-specific intro. Keeping the workflow in one file prevents drift.
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

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_header(text: str) -> dict[str, str]:
    """Extract `key: value` pairs from the first HTML comment in the skill file."""
    vars_ = dict(_DEFAULT_VARS)
    m = _HEADER_RE.search(text)
    if not m:
        return vars_
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            vars_[k.strip()] = v.strip()
    return vars_


def _render_shared(vars_: dict[str, str]) -> str:
    """Load _shared.md and substitute {{DATA_ROOT}} / {{PLATFORM}} / {{CMD_PREFIX}}."""
    if not SHARED_SKILL.exists():
        return ""
    body = SHARED_SKILL.read_text(encoding="utf-8")
    # Drop the leading explanation comment block from _shared.md.
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
    """Return the final skill text for a given platform.

    Per-platform file provides the intro/header; _shared.md provides the
    workflow. `<plugin_root>` and `{{…}}` placeholders are substituted.
    """
    path = SKILLS_DIR / f"skill-{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Skill file not found: {path}")
    header_text = path.read_text(encoding="utf-8")
    vars_ = _parse_header(header_text)
    shared = _render_shared(vars_)
    combined = header_text if not shared else f"{header_text.rstrip()}\n\n{shared}"
    return combined.replace("<plugin_root>", str(PLUGIN_ROOT))


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
    """Register PostToolUse + Stop hooks and symlink commands into ~/.claude/commands/."""
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

    # Symlink commands into ~/.claude/commands/ so they appear as /lesson, /lesson-done, etc.
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
        cmd_name = src.stem
        print(f"  ↳ /{cmd_name}  →  {dst}")


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
