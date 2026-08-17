# Changelog

All notable changes to `lesson` are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0] — unreleased

Full rewrite. Nothing from 0.3 survives except the plugin manifest. The old tree
is preserved at tag `v0.3-graph-era`.

**Why:** 0.3 built a knowledge graph of each *session* from tool-call logs. It
could not work. `_classify()` only ever produced `observation` or `attempt`
nodes — nothing in 4,529 lines ever created a `concept` or `hypothesis` — so
root-cause and misconception detection returned nothing every single time, and
the shipping behaviour was an LLM reading a truncated tool log. 151 tests passed
throughout, because they checked that the machinery ran, never that the output
was worth reading.

### Changed

- Models **the learner**, not the session. One knowledge graph of what a person
  understands, global and permanent, at `~/.claude/lesson/graph.json`.
- Reads the transcripts Claude Code already writes instead of keeping its own
  `arc.jsonl`, which was a strictly lossy subset of them.
- Analysis runs out of band in a detached `claude --bare -p`, so the main
  conversation is never touched. `--bare` skips hooks and is what stops it
  recursing into itself.
- Lessons are self-contained HTML in the style of the `make-lesson` skill, not
  markdown plus a mermaid-to-PDF chain.
- Ends a session with an **offer**, never a quiz. One unread lesson at a time.

### Added

- `observed` / `guessed` tags plus session provenance on every claim, so nothing
  is asserted about a person that can't be traced and challenged.
- `viewer/graph.html` — self-contained, click-through graph of what you know.
- Explicit prohibition on copying code, secrets, or file contents into the graph.

### Removed

- The Python package, both hooks, the event graph, TF-IDF significance scoring,
  spaCy extraction, embeddings, PDF rendering, the eval harness, the test suite,
  and eight non-Claude-Code platform adapters.
- The fixed concept list. Concepts are infinite; the graph grows from real usage
  via a match-first rule instead.

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
