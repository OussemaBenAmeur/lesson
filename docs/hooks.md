# Hook And MCP Support

This document summarizes the non-LLM event capture paths shipped with `lesson`.

## Claude Code

- Hooks: `PostToolUse`, `Stop`
- Install surface: `~/.claude/hooks.json`
- Install: `python3 scripts/install.py --platform claude-code`
- Notes: native baseline behavior; wrapper scripts route into `lesson/hooks/adapter.py` and `lesson/hooks/stop.py`

## Codex

- Hooks: `PostToolUse`, `Stop`, `SessionStart`
- Install surface: `~/.codex/hooks.json`, `~/.codex/config.toml`, `~/.codex/hooks/`
- Install: `python3 scripts/install.py --platform codex`
- Payload sample: `tests/fixtures/hooks/codex/post_tool_use.shape.json`
- Notes: current Codex hook payloads only expose Bash tool events, so file edits are not captured natively yet

## Cursor

- Hooks: `postToolUse`, `afterFileEdit`, `stop`
- Install surface: `~/.cursor/hooks.json`, `<project>/.cursor/hooks.json`, `<project>/.cursor/rules/lesson.mdc`
- Install: `python3 scripts/install.py --platform cursor`
- Payload sample: `tests/fixtures/hooks/cursor/post_tool_use.shape.json`
- Notes: edit hooks can arrive twice; `lesson` dedupes by `tool_call_id` within the active session

## GitHub Copilot CLI

- Hooks: `postToolUse`, `sessionEnd`, `sessionStart`, `userPromptSubmitted`
- Install surface: `~/.github/copilot-instructions.md`, `<repo>/.github/hooks/lesson.json`, `<repo>/.github/hooks/scripts/lesson/`
- Install: `python3 scripts/install.py --platform copilot`
- Payload sample: `tests/fixtures/hooks/copilot/post_tool_use.shape.json`
- Notes: Copilot hooks are repo-scoped, not global; the installer must run inside a git repository
- Notes: `userPromptSubmitted` is captured into `prompts.jsonl` as a sidecar stream and is intentionally ignored by compression

## OpenCode

- Bridge: plugin `tool.after`, `session.start`, `session.idle`
- Install surface: `~/.opencode/OPENCODE.md`, `~/.opencode/opencode.json`, `~/.config/opencode/plugins/lesson/index.mjs`, `~/.local/share/lesson/opencode_bridge.py`
- Install: `python3 scripts/install.py --platform opencode`
- Payload sample: `tests/fixtures/hooks/opencode/post_tool_use.shape.json`
- Notes: the shipped `.mjs` plugin forwards events to a Python bridge over stdio, so no Node build step is required

## Google Antigravity

- MCP tools: `lesson.record_event`, `lesson.finalize_session`
- Install surface: `<project>/.agent/lesson.md`, `<project>/.agent/rules/lesson.md`, `<project>/.agent/workflows/lesson.md`, `~/.gemini/settings.json`
- Install: `python3 scripts/install.py --platform antigravity`
- Payload sample: `tests/fixtures/hooks/antigravity/record_event.shape.json`
- Notes: this is Tier 2 MCP-mediated rather than a native hook API; the agent must still call the provided MCP tools
