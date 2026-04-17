# /lesson Plugin — Architecture

## Overview

`/lesson` is a multi-platform AI coding skill that turns real working sessions into textbook-quality markdown lessons. It works across 10 platforms: Claude Code, Codex, Cursor, Gemini CLI, GitHub Copilot CLI, OpenCode, OpenClaw, Factory Droid, Trae, and Google Antigravity.

The core insight is that a working session contains more pedagogical signal than any generic tutorial — the specific errors you hit, the wrong assumptions you made, and the turning points where you figured it out are exactly what a good lesson needs.

The philosophy has three rules:

1. **Hooks are dumb.** The PostToolUse hook is a Python script that appends and counts. No LLM calls, never blocks.
2. **Main context stays lean.** Session data is compressed into a knowledge graph by a subagent. The main conversation only sees the graph, not hundreds of raw events.
3. **Grounded or nothing.** If the concept can't be researched or the session has too little data, the plugin says so rather than producing a weak lesson.

---

## File Layout

### Plugin (this repo)

```
lesson/
├── commands/
│   ├── lesson.md           — /lesson command (start tracking)
│   ├── lesson-done.md      — /lesson-done command (generate lesson)
│   ├── regenerate.md       — /regenerate command (re-generate with new notes)
│   ├── lesson-resume.md    — /lesson resume command (resume a paused session)
│   ├── lesson-profile.md   — /lesson-profile command (view learner profile)
│   ├── lesson-index.md     — /lesson-index command (index all lessons)
│   └── lesson-map.md       — /lesson-map command (concept map across lessons)
├── agents/
│   └── lesson-compress.md  — compression subagent definition
├── hooks/
│   ├── hooks.json          — PostToolUse + Stop hook registration (Claude Code)
│   ├── post_tool_use.py    — event logger + compression trigger + token tracking
│   └── stop.py             — session-end nudge
├── skills/
│   ├── skill-claude-code.md   — reference (natively supported via commands/)
│   ├── skill-codex.md         — full workflow for Codex ($lesson prefix, manual logging)
│   ├── skill-cursor.md        — .mdc format, alwaysApply: true, .cursor/lessons/ data root
│   ├── skill-gemini.md        — optional BeforeTool hook, ~/.gemini/GEMINI.md
│   ├── skill-copilot.md       — ~/.github/copilot-instructions.md
│   ├── skill-opencode.md      — ~/.opencode/OPENCODE.md
│   ├── skill-openclaw.md      — ~/.claw/CLAW.md
│   ├── skill-droid.md         — ~/.droid/DROID.md
│   ├── skill-trae.md          — ~/.trae/TRAE.md
│   └── skill-antigravity.md   — <project>/.agent/lesson.md
├── templates/
│   ├── lesson.md.tmpl      — markdown lesson template (canonical output)
│   └── lesson.html.tmpl    — HTML viewer template (for /lesson-index, /lesson-map)
├── scripts/
│   ├── render_pdf.py       — converts lesson .md to PDF with rendered mermaid SVG
│   └── install.py          — multi-platform install dispatcher (--list, --platform <name>)
├── CLAUDE.md               — AI context file (auto-loaded by Claude Code and most platforms)
└── docs/
    └── architecture.md     — this file
```

### Per-Project Runtime State

Created in the project's `.claude/lessons/` — never in the plugin directory.

```
.claude/lessons/
├── active-session                    — marker: contains slug of active session
├── last-session                      — pointer to most recently completed session
├── sessions/<slug>/
│   ├── meta.json                     — goal, notes, timestamps, token_tracking
│   ├── arc.jsonl                     — raw events since last compression
│   ├── session_graph.json            — structured knowledge graph (primary session data)
│   ├── counter                       — events since last compression trigger
│   └── arc.jsonl.archive.<N>         — consumed raw events (one file per compression cycle)
└── output/
    ├── <slug>.md                     — generated lesson (canonical, commit this)
    └── <slug>.pdf                    — generated lesson (visual, rendered diagrams)
```

### Global Learner Profile

```
~/.claude/lessons/
└── profile.json                      — cross-project misconception and concept history
```

---

## Data Flow

```
user types /lesson
  └─> commands/lesson.md
        creates session dir, writes active-session marker, initializes meta.json

user works (tool calls fire)
  └─> hooks/post_tool_use.py   (runs after EVERY tool call, ~0ms, zero LLM tokens)
        if no active-session → exit 0 (no-op)
        else:
          append event to arc.jsonl (with significant: true/false flag)
          update meta.json token_tracking.arc_input_chars
          bump counter
          if counter >= LESSON_COMPRESS_EVERY (default: 25):
            reset counter
            emit additionalContext reminder to Claude

Claude receives the reminder
  └─> spawns Task subagent of type lesson-compress
        reads arc.jsonl + session_graph.json + meta.json
        adds new nodes and edges to session_graph.json
        updates meta.json token_tracking (compression_cycles, graph_output_chars)
        archives arc.jsonl → arc.jsonl.archive.N
        resets arc.jsonl
        reports one line to parent

user types /lesson-done
  └─> commands/lesson-done.md
        1. load session_graph.json + arc.jsonl tail + meta.json
        2. read ~/.claude/lessons/profile.json (learner history)
        3. quality guard (too few events → warn)
        4. analyze graph: root cause, misconception, prerequisites
        5. decide: web research needed?
        6. load templates/lesson.md.tmpl
        7. fill template (foundations, concept, diagrams, quiz, recurring note)
        8. compute token_tracking estimates, write to meta.json
        9. write output/<slug>.md
       10. call scripts/render_pdf.py → output/<slug>.pdf
       11. update ~/.claude/lessons/profile.json
       12. write last-session, delete active-session
```

---

## The Session Knowledge Graph

Stored in `session_graph.json`. Built incrementally by the compression subagent. This is the primary input to `/lesson-done` — it avoids re-analyzing hundreds of raw events.

### Schema

```json
{
  "schema_version": "1",
  "slug": "20260416-010610",
  "goal": "get nvidia-smi working on kernel 6.17.8",
  "total_events_compressed": 47,
  "root_cause_id": "c1",
  "resolution_id": "r1",
  "nodes": [...],
  "edges": [...]
}
```

### Node types

| type | what it represents | key flags |
|---|---|---|
| `goal` | the session objective (1 per session) | — |
| `observation` | a factual finding: error, command output, file state | `pivotal` |
| `hypothesis` | a belief or assumption that drove action | `misconception` |
| `attempt` | a deliberate action: fix tried, file edited, command run | — |
| `concept` | a technical concept that became relevant | `root_cause` |
| `resolution` | an approach that worked | — |

Node IDs use type-initial + integer: `g1`, `o1`, `h1`, `a1`, `c1`, `r1`. IDs are stable — never renumbered across compression cycles.

### Edge types

| type | from → to | meaning |
|---|---|---|
| `motivated` | hypothesis → attempt | this belief drove this action |
| `produced` | attempt → observation | this action revealed this finding |
| `seemed_to_confirm` | observation → hypothesis | appeared to support the belief |
| `contradicted` | observation → hypothesis | proved the belief wrong |
| `revealed` | observation → concept | this finding exposed this concept |
| `assumed_about` | hypothesis → concept | the hypothesis was an assumption about this |
| `involves` | concept → concept | requires understanding another concept |
| `enabled` | concept → resolution | knowing this made the fix possible |
| `achieves` | resolution → goal | the fix accomplishes the goal |

---

## Token Tracking

The hook and compression subagent accumulate data in `meta.json` under `token_tracking`. `/lesson-done` computes final estimates before writing the lesson.

```json
"token_tracking": {
  "arc_input_chars": 84000,
  "compression_cycles": 3,
  "graph_output_chars": 4200,
  "web_fetch_chars": 31000,
  "lesson_output_chars": 9800,
  "estimated_tokens": {
    "hook_logged": 21000,
    "compression_input": 7500,
    "compression_output": 1050,
    "lesson_done_input": 12400,
    "lesson_done_output": 2450,
    "web_research": 7750,
    "total": 52150
  }
}
```

**Estimation formula:** characters ÷ 4 ≈ tokens (standard approximation, ±20%).

Token tracking is best-effort. If any step fails to write, the session continues normally.

---

## The Learner Profile

Stored globally at `~/.claude/lessons/profile.json`. Updated after every `/lesson-done`. Used to detect recurring misconceptions and reference past lessons.

```json
{
  "schema_version": "1",
  "total_sessions": 4,
  "misconceptions": [
    {
      "concept": "kernel module / userspace version coupling",
      "count": 1,
      "last_seen": "2026-04-16",
      "slug": "20260416-010610",
      "project": "/home/oussema/myproject"
    }
  ],
  "learned_concepts": [
    {
      "concept": "DKMS — Dynamic Kernel Module Support",
      "date": "2026-04-16",
      "slug": "20260416-010610"
    }
  ],
  "aggregate_tokens": {
    "total_estimated": 187000,
    "sessions": 4
  }
}
```

If a new session's misconception matches one already in the profile, `/lesson-done` adds a callout in the lesson: "You've encountered this pattern before."

---

## PDF Generation

`scripts/render_pdf.py` runs as a subprocess after `/lesson-done` writes the `.md`. Zero LLM calls.

**Pipeline:**
1. Extract all ` ```mermaid ` blocks from the `.md`
2. Render each to `.svg` via `npx @mermaid-js/mermaid-cli mmdc`
3. Replace mermaid fences in markdown with `![](path/to/diagram.svg)`
4. Convert modified markdown → PDF via pandoc (tries engines: weasyprint → wkhtmltopdf → xelatex)
5. Fallback: chromium headless `--print-to-pdf`

Graceful degradation: if no tools are available, prints a helpful message and exits 0. The `.md` is always written regardless.

---

## Significance Flagging

`post_tool_use.py` tags each arc.jsonl event with `"significant": true/false` using cheap Python heuristics:

- Any `is_error: true` → significant
- Tool is `Edit`, `Write`, or `NotebookEdit` → significant (user changed something)
- Tool is `Bash` and result contains error keywords → significant
- Tool is `Bash` with short output containing version strings → significant (likely a comparison/discovery)

This flag is a hint to the compression subagent — events with `significant: true` are prioritized for promotion to graph nodes. Non-significant events (background reads, navigation) are usually not promoted.

---

## Command Reference

| Command | What it does |
|---|---|
| `/lesson [notes]` | Start a tracked session. Notes guide generation depth/style. |
| `/lesson-done` | Generate lesson from current session. |
| `/regenerate [notes]` | Re-generate the most recent lesson with optional new direction. |
| `/lesson resume` | Re-activate tracking on the most recent paused session. |
| `/lesson-profile` | Display learner profile: misconceptions, concepts learned, token usage. |
| `/lesson-index` | Write `output/index.html` listing all lessons. |
| `/lesson-map [flags]` | Write `output/map.html` concept graph. Flags: `--last N`, `--since DATE`, `--slugs`, `--tag`. |

---

## Multi-Platform Support

The plugin uses a "Single Core, Platform Wrapper" pattern. The core lesson format, session graph schema, and learner profile are identical across all platforms. What varies per platform:

| Dimension | Claude Code | Gemini CLI | All others |
|---|---|---|---|
| Event logging | PostToolUse hook (automatic) | BeforeTool hook (optional) | LLM logs manually to `arc.jsonl` |
| Graph compression | Task subagent (automatic) | Inline or subagent | Inline at `/lesson-done` time |
| Session data root | `.claude/lessons/` | `.claude/lessons/` | `.claude/lessons/` (`.cursor/lessons/` on Cursor) |
| Command prefix | `/lesson` | `/lesson` | `/lesson` (Codex: `$lesson`) |
| Install target | `~/.claude/hooks.json` | `~/.gemini/GEMINI.md` | Platform-specific (see below) |

### Install Locations

```
Claude Code   — ~/.claude/hooks.json  (registers PostToolUse + Stop hooks)
Codex         — ~/.codex/CODEX.md
Cursor        — <project>/.cursor/rules/lesson.mdc
Gemini CLI    — ~/.gemini/GEMINI.md  +  ~/.gemini/settings.json (BeforeTool hook)
Copilot CLI   — ~/.github/copilot-instructions.md
OpenCode      — ~/.opencode/OPENCODE.md
OpenClaw      — ~/.claw/CLAW.md
Factory Droid — ~/.droid/DROID.md
Trae          — ~/.trae/TRAE.md
Antigravity   — <project>/.agent/lesson.md
```

### Data Flow (platforms without hooks)

On hook-less platforms, the AI performs the steps that the hook and compression subagent would normally handle automatically:

```
user types /lesson
  └─> skill file instructions → AI creates session dir, writes active-session

user works (tool calls fire)
  └─> AI appends event to arc.jsonl manually after each significant tool call

at 25 events (or at /lesson-done time)
  └─> AI builds/extends session_graph.json inline
      archives arc.jsonl → arc.jsonl.archive.N

user types /lesson-done
  └─> same generation flow as Claude Code (profile read, web research, template fill,
      render_pdf.py, profile update, last-session write)
```

### Installing

```bash
python3 scripts/install.py --list                   # show all platforms + config paths
python3 scripts/install.py --platform claude-code   # registers hooks
python3 scripts/install.py --platform cursor        # writes to current project
python3 scripts/install.py --platform gemini        # appends to GEMINI.md + settings.json
```

---

## Configuration

All settings are optional environment variables. Set in shell or under `env` in `.claude/settings.json`.

| Variable | Default | Effect |
|---|---|---|
| `LESSON_COMPRESS_EVERY` | `25` | Events between compression subagent runs |
| `LESSON_STOP_MIN_EVENTS` | `5` | Minimum events for the Stop hook to nudge `/lesson-done` |
| `LESSON_MIN_EVENTS` | `8` | Minimum events for `/lesson-done` to proceed without warning |

---

## Design Decisions

**Why markdown as canonical output, not HTML?**
Markdown is git-diffable, AI-readable (future Claude sessions can parse it cleanly), and renders mermaid natively in GitHub, Obsidian, and VS Code. The `.pdf` file handles visual rendering of diagrams — there is no need for an intermediate HTML layer in the output chain.

**Why a knowledge graph instead of prose summaries?**
The previous design wrote narrative `summary.md` files (500–1500 words per compression cycle). The graph encodes causality explicitly — edges say `contradicted` and `revealed`, not "and then." `/lesson-done` reads `root_cause_id` directly instead of re-deriving it from prose. The graph is also ~3× smaller than equivalent prose, reducing token cost for longer sessions.

**Why are hooks LLM-free?**
Hooks run after every tool call. Any latency or failure in a hook directly impacts the user's experience. A Python script that appends JSON and reads a file exits in milliseconds and can never produce an LLM error. Summarization, which requires judgment, belongs in Claude — hence the compression subagent.

**Why a global learner profile?**
Misconceptions are personal and project-agnostic. The same async misconception can appear in a Python project and a Node.js project. A per-project profile would miss the pattern. The global profile at `~/.claude/lessons/profile.json` accumulates knowledge across all projects.

**Why estimate tokens rather than count them exactly?**
Claude Code does not expose API token counts to hooks or command prompts. Character ÷ 4 is a standard, widely-accepted approximation (±20%) that requires no external calls. The tracking is useful for order-of-magnitude awareness, not billing precision.

**Why one skill file per platform rather than a single universal file?**
Platform constraints differ enough that a single file would be riddled with conditionals. Each platform gets a clean, self-contained file that describes exactly how `/lesson` works on that platform — no irrelevant sections, no branching prose. The core lesson format (session graph schema, template, learner profile) stays identical across all skill files.
