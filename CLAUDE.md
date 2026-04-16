# lesson — AI Context

This is the `lesson` plugin: it turns AI coding sessions into textbook-quality lessons.

## What It Does

- User runs `/lesson [notes]` → session tracking starts
- During the session, tool events are logged to `arc.jsonl`
- Every 25 events, a compression subagent folds `arc.jsonl` into `session_graph.json`
- User runs `/lesson-done` → lesson is generated from the graph and written as markdown+PDF

## Key Files

| File | What it does |
|---|---|
| `hooks/post_tool_use.py` | Reads hook event from stdin, appends to `arc.jsonl`, triggers compression reminder at threshold |
| `agents/lesson-compress.md` | Subagent: reads `arc.jsonl`, extends `session_graph.json`, archives events |
| `commands/lesson.md` | `/lesson`: initialize session state, write `active-session` |
| `commands/lesson-done.md` | `/lesson-done`: generate lesson from graph, update profile, write output |
| `commands/regenerate.md` | `/regenerate [notes]`: re-generate last lesson with new direction |
| `commands/lesson-resume.md` | `/lesson resume`: restore last session to active state |
| `commands/lesson-profile.md` | `/lesson-profile`: show learner history and token usage |
| `commands/lesson-index.md` | `/lesson-index`: build HTML index from output lessons |
| `commands/lesson-map.md` | `/lesson-map [--last N --since DATE --tag X]`: concept map |
| `templates/lesson.md.tmpl` | Lesson markdown template with `{{PLACEHOLDER}}` fields |
| `scripts/render_pdf.py` | Convert `<slug>.md` → `<slug>.pdf` (mermaid → SVG → PDF). Always exits 0. |
| `scripts/install.py` | Multi-platform install dispatcher (`--list` to see all platforms) |
| `skills/skill-<platform>.md` | Per-platform skill file (Codex, Cursor, Gemini, Copilot, OpenCode, OpenClaw, Droid, Trae, Antigravity) |
| `docs/architecture.md` | Full architecture reference |

## Session Data Format

Sessions live in `.claude/lessons/sessions/<slug>/` inside the **target project** (not this repo).

- `meta.json` — slug, goal, notes, started_at, cwd, platform, token_tracking
- `arc.jsonl` — raw event log (one JSON line per significant tool use)
- `session_graph.json` — compressed knowledge graph (nodes + edges)
- `counter` — event counter since last compression

Learner profile: `~/.claude/lessons/profile.json` (global, shared across all projects)

## Session Graph Schema

```
Nodes: goal | observation | hypothesis | attempt | concept | resolution
Flags: pivotal (observation) | misconception (hypothesis) | root_cause (concept)
Edges: motivated | produced | revealed | contradicted | seemed_to_confirm |
       assumed_about | involves | enabled | achieves
Node IDs: type-initial + int (g1, o1, h1, a1, c1, r1) — NEVER renumber existing IDs
```

## Critical Rules

- `hooks/post_tool_use.py` must **never crash** — it exits 0 on any exception
- `scripts/render_pdf.py` must **never block lesson generation** — exits 0 on failure
- Node IDs in `session_graph.json` are **stable forever** — only append new ones
- The main conversation **never reads raw `arc.jsonl` directly** — only the compression subagent does
- Hook code must be **LLM-free** — no API calls, no subprocess to AI tools

## Multi-Platform Adaptation

Platforms without hooks (all except Claude Code and Gemini): the AI logs events to `arc.jsonl`
manually after each significant tool call and builds the graph inline at `/lesson-done` time.

Codex uses `$lesson` command prefix instead of `/lesson`.
Cursor uses `.mdc` format with `alwaysApply: true` frontmatter.
Session data root: `.claude/lessons/` (Claude Code, Gemini, all others) or `.cursor/lessons/` (Cursor).

## Environment Variables

| Variable | Default | Meaning |
|---|---|---|
| `LESSON_COMPRESS_EVERY` | 25 | Events between compression runs |
| `LESSON_STOP_MIN_EVENTS` | 5 | Min events before Stop hook nudges |
| `LESSON_MIN_EVENTS` | 8 | Min events before `/lesson-done` warns |
| `CLAUDE_PLUGIN_ROOT` | (auto-detected) | Absolute path to this plugin directory |

## Output

`/lesson-done` writes:
- `.claude/lessons/output/<slug>.md` — canonical lesson with YAML frontmatter
- `.claude/lessons/output/<slug>.pdf` — optional, rendered by `render_pdf.py`
- Updates `~/.claude/lessons/profile.json`
- Writes `.claude/lessons/last-session`
- Deletes `.claude/lessons/active-session`
