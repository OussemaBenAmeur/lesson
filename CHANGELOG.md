# Changelog

All notable changes to `lesson` are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Shared hook packages under `lesson/hooks/` for post-tool logging, stop handling, payload normalization, and platform-specific adapters.
- Hook or bridge support for Codex, Cursor, GitHub Copilot CLI, OpenCode, and Antigravity MCP.
- New unit coverage for the shared adapter, Cursor and Copilot wrappers, OpenCode bridge, Antigravity MCP server, and installer merge behavior.
- `docs/hooks.md` documenting install surfaces, hook events, and current platform limits.
- Copilot `userPromptSubmitted` capture now writes sidecar `prompts.jsonl` records that are excluded from compression.

### Changed

- `scripts/install.py` now merges JSON and TOML config instead of appending one-off files only, and it installs platform-specific hook/bridge assets where supported.
- `SessionManager` now auto-detects `.cursor/lessons/` and honors `LESSON_DATA_ROOT` so CLI commands can operate on Cursor-managed sessions.
- `lesson stats` now surfaces sidecar prompt counts separately from compressed tool events.

## [0.3.0] — 2026-04-18

Silent-by-default release and first OSS-ready cut.

### Changed

- **PostToolUse hook is now silent.** Instead of emitting an `additionalContext` reminder every `LESSON_COMPRESS_EVERY` events, `hooks/post_tool_use.py` spawns `lesson compress` as a detached background subprocess. The user's main conversation is never interrupted; compression runs in ~50 ms with zero LLM tokens.
- **Stop hook no longer blocks session exit.** The previous `{"decision": "block", ...}` response forced Claude to run `/lesson-done` mid-flow. The hook now emits a single-line non-blocking `systemMessage` and lets you choose when to generate the lesson.
- Skill files deduplicated: the ~80 % shared workflow lives in `skills/_shared.md` and `scripts/install.py` concatenates it with the per-platform header at install time. Skills directory shrinks from ~900 lines to ~350.
- `pyproject.toml` now carries full metadata: authors, MIT license, classifiers, keywords, project URLs (Homepage / Repository / Issues / Changelog).
- `docs/architecture.md`, `docs/how-it-works.md`, `docs/blog-article.md`, `README.md`, and `CLAUDE.md` rewritten to describe the single silent-compression path.

### Added

- `LESSON_SILENT_HOOK` environment variable (default `1`). Set to `0` to restore the legacy `additionalContext` reminder — useful only for debugging.
- `skills/_shared.md` — platform-agnostic workflow template with `{{DATA_ROOT}}`, `{{PLATFORM}}`, `{{CMD_PREFIX}}` placeholders.
- `CONTRIBUTING.md`, this `CHANGELOG.md`, and `.github/workflows/ci.yml` (matrix on Python 3.10 / 3.11 / 3.12).
- `docs/blog-article.md` and `docs/how-it-works.md` as top-level published narratives.

### Removed

- `agents/lesson-compress.md` — the LLM subagent compression path. The Python package (`pip install lesson`) is now the single source of truth for graph compression across all supported platforms.

### Fixed

- Version is now consistent across `pyproject.toml`, `lesson/__init__.py`, and `.claude-plugin/plugin.json` (all `0.3.0`). The previous `0.1.0` / `0.2.0` / `0.1.0` split is gone.
- `.gitignore` now covers `.coverage`, `.hypothesis/`, `.pytest_cache/`, `*.egg-info/`, `.idea/`, `.vscode/`, `docs/_build/`, `dist/`, `build/`. Previously-tracked build artifacts (`.coverage`, `.idea/`, `lesson.egg-info/`) are untracked.

## [0.2.0] — unreleased

Internal iteration — never tagged. Changes from this period are folded into 0.3.0.

## [0.1.0] — 2026-03

Initial prototype: PostToolUse/Stop hooks, LLM-subagent compression, single-platform (Claude Code) skill.

[0.3.0]: https://github.com/OussemaBenAmeur/lesson/releases/tag/v0.3.0
