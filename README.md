# lesson

**An AI coding plugin that turns real working sessions into grounded, reusable lessons.**

`lesson` watches tool activity inside a live AI session, keeps a compact record of the important turns, and turns the final arc into a lesson built from your actual files, commands, errors, and wrong assumptions.

Instead of generating a generic tutorial from scratch, it produces a lesson about what really happened:

- what you were trying to do
- where it broke
- which concept was actually missing
- why the misconception was believable
- what fixed it
- how to test whether you now understand it

```text
/lesson react useEffect infinite loop when depending on an object
# work normally
/lesson-done
```

```text
.claude/lessons/
├── sessions/<slug>/
│   ├── meta.json
│   ├── arc.jsonl
│   ├── session_graph.json      # created after the first compression cycle
│   └── arc.jsonl.archive.N
└── output/
    ├── <slug>.md
    ├── <slug>.pdf              # optional
    ├── index.html
    └── map.html
```

---

## Why This Exists

Most learning tools start with a topic and invent an explanation.

`lesson` starts with a real failure path.

That difference matters. A working session contains high-quality teaching signal: the commands you ran, the outputs you misread, the hypotheses you formed, the file edits you tried, and the observation that finally changed your mind. That is the raw material a serious lesson should be built from.

| Generic tutorial | `lesson` |
| --- | --- |
| Starts from an abstract topic | Starts from your actual session |
| Uses canned examples | Uses your files, errors, and commands |
| Explains the concept in general | Explains why *you* got stuck |
| Often guesses at relevance | Has a concrete arc to teach from |

---

## Platform Support

Works across 10 AI coding platforms. One install script, one core format.

| Platform | Hook support | Config location | Command prefix |
| --- | --- | --- | --- |
| **Claude Code** | PostToolUse + Stop (automatic) | `~/.claude/hooks.json` | `/lesson` |
| **Codex** | None (manual logging) | `~/.codex/CODEX.md` | `$lesson` |
| **Cursor** | None (manual logging) | `<project>/.cursor/rules/lesson.mdc` | `/lesson` |
| **Gemini CLI** | BeforeTool (optional) | `~/.gemini/GEMINI.md` | `/lesson` |
| **GitHub Copilot CLI** | None (manual logging) | `~/.github/copilot-instructions.md` | `/lesson` |
| **OpenCode** | None (manual logging) | `~/.opencode/OPENCODE.md` | `/lesson` |
| **OpenClaw** | None (manual logging) | `~/.claw/CLAW.md` | `/lesson` |
| **Factory Droid** | None (manual logging) | `~/.droid/DROID.md` | `/lesson` |
| **Trae** | None (manual logging) | `~/.trae/TRAE.md` | `/lesson` |
| **Google Antigravity** | None (manual logging) | `<project>/.agent/lesson.md` | `/lesson` |

On platforms with hooks (Claude Code, Gemini), event logging is automatic. On all others, the AI logs significant events manually to `arc.jsonl` during the session.

---

## What Ships Today

- **Silent-by-default tracking.** Once `/lesson` starts, the plugin never speaks to the main conversation until you call it back. No reminders, no exit blocks, no model nags.
- Session tracking via hooks (Claude Code, Gemini) or manual LLM logging (all other platforms)
- **Deterministic compression** — `lesson compress` CLI runs `EventGraphBuilder` in ~50 ms with zero LLM tokens. The PostToolUse hook spawns it in a detached subprocess at the 25-event threshold.
- Session knowledge graph (`session_graph.json`) — structured causal record of the session
- Cross-session learner profile at `~/.claude/lessons/profile.json` — tracks recurring misconceptions and concepts across all projects and platforms
- "You've hit this before" callout when the same misconception recurs
- Per-session token tracking with cost estimates
- Canonical markdown lesson output with YAML frontmatter
- Best-effort PDF rendering with Mermaid diagrams rendered as SVG
- `/regenerate [notes]` to rewrite the latest lesson with new guidance
- `/lesson resume` to continue a paused session
- `/lesson-profile` to display your learning history and token usage
- `/lesson-index` to build a browsable lesson list
- `/lesson-map` to build a concept map across generated lessons
- **`lesson` CLI** — use the compression and graph tooling standalone, outside of any AI assistant
- **Eval framework** — measure compression quality (node F1, edge accuracy, graph quality score)

---

## Install

### Requirements

- Python 3.10+
- An AI coding platform listed above
- Optional for PDF export:
  - `npx` with `@mermaid-js/mermaid-cli`
  - `pandoc` plus `weasyprint`, `wkhtmltopdf`, `xelatex`, or `pdflatex`
  - or a Chromium-based browser for the fallback renderer

### Python Package

```bash
git clone https://github.com/OussemaBenAmeur/lesson.git
cd lesson

pip install -e .              # core (networkx, pydantic, typer, rich, plotly)
pip install -e ".[nlp]"       # + semantic deduplication (spacy, sentence-transformers)
pip install -e ".[dev]"       # + pytest, hypothesis
```

### Claude Code — From GitHub Marketplace

Inside Claude Code:

```text
/plugin marketplace add OussemaBenAmeur/lesson
/plugin install lesson
```

### All Platforms — Install Script

```bash
# List supported platforms
python3 scripts/install.py --list

# Install for your platform
python3 scripts/install.py --platform claude-code
python3 scripts/install.py --platform cursor       # run inside a project directory
python3 scripts/install.py --platform gemini
python3 scripts/install.py --platform codex
# ... etc
```

Restart your AI assistant after install. On Claude Code, hooks are registered at session start.

---

## Quick Start

### 1. Start tracking

```text
/lesson python asyncio task never awaited explain from scratch
```

The argument is optional but guides how the final lesson is written.

```text
/lesson linux driver mismatch explain from first principles
/lesson react stale closure I know hooks basics, focus on the bug pattern
/lesson
```

### 2. Work normally

Read files. Edit code. Run commands. Fail. Recover. Try again.

On Claude Code and Gemini, the hook logs tool events into `arc.jsonl` automatically and — at the 25-event threshold — silently runs `lesson compress` as a detached subprocess. On other platforms, the AI logs events itself and calls `lesson compress` inline. Either way, the main conversation stays silent until you invoke a command.

### 3. Generate the lesson

```text
/lesson-done
```

Writes the final markdown lesson to `.claude/lessons/output/<slug>.md` and (if PDF tooling is available) `.claude/lessons/output/<slug>.pdf`.

### 4. Refine or explore

```text
/regenerate make the foundations deeper and the quiz harder
/lesson-profile
/lesson-index
/lesson-map --last 10
```

---

## Command Reference

| Command | Purpose |
| --- | --- |
| `/lesson [notes]` | Start a tracked learning session |
| `/lesson-done` | Generate the lesson from the active session |
| `/regenerate [notes]` | Rebuild the most recent lesson with new instructions |
| `/lesson resume` | Resume tracking on the most recent session |
| `/lesson-profile` | Display learning history and token usage |
| `/lesson-index` | Build `output/index.html` listing generated lessons |
| `/lesson-map [flags]` | Build `output/map.html` connecting lessons by concepts |

Supported `/lesson-map` filters: `--last N`, `--since YYYY-MM-DD`, `--slugs slug1,slug2,...`, `--tag keyword`

---

## CLI (`lesson` command)

The Python package ships a standalone CLI that works outside of any AI assistant. Useful for triggering compression from CI, inspecting graphs, or integrating with other tools.

```bash
lesson start "fix asyncio blocking issue"   # create a new session
lesson compress                              # fold arc.jsonl into session_graph.json (~50ms, zero tokens)
lesson stats                                 # print graph metrics
lesson graph                                 # open interactive Plotly graph in browser
lesson graph --mermaid                       # print Mermaid syntax
lesson graph --dot                           # print DOT syntax
lesson resume                                # re-activate the last session
lesson done                                  # final compression + instructions for /lesson-done
```

The `lesson compress` command runs `EventGraphBuilder` — a deterministic pipeline:

```
arc.jsonl events
  → SignificanceScorer  (TF-IDF novelty × error signal × edit signal × version signal → float)
  → top candidates (score ≥ 0.25, max 12 per batch)
  → _classify() → NodeType
  → NodeEmbedder deduplication (optional, requires lesson[nlp])
  → edge inference from (prev.type, curr.type, is_error)
  → betweenness centrality → root_cause_id
```

This is the sole compression path across all platforms — no LLM subagent is involved.

---

## What The Plugin Writes

All runtime state lives in the target project's `.claude/lessons/` directory (or `.cursor/lessons/` on Cursor). The learner profile is global at `~/.claude/lessons/profile.json`.

```text
.claude/lessons/
├── active-session
├── last-session
├── sessions/<slug>/
│   ├── meta.json               # goal, notes, timestamps, cwd, platform, token_tracking
│   ├── arc.jsonl               # raw event log since last compression
│   ├── session_graph.json      # structured causal graph (created after first compression)
│   ├── counter
│   └── arc.jsonl.archive.<N>
└── output/
    ├── <slug>.md
    ├── <slug>.pdf              # optional
    ├── index.html
    └── map.html

~/.claude/lessons/
└── profile.json               # cross-session learner memory (global, shared across platforms)
```

Recommended `.gitignore` entries:

```gitignore
.claude/lessons/active-session
.claude/lessons/sessions/
```

Version `output/` if you want lessons to live with the repo.

---

## What A Lesson Contains

The markdown template in [templates/lesson.md.tmpl](templates/lesson.md.tmpl) produces:

- YAML frontmatter: slug, concept, date, goal, root_cause, tags
- Recurring misconception callout if this pattern was seen before (`profile.json`)
- Session narrative grounded in the real failure
- Foundations section built from lower-level prerequisites, explained from scratch
- Concept explanation with citations when research was needed
- Mermaid concept diagram
- Mermaid debug-path flowchart derived from the session graph
- Fix explanation and verbatim fix snippet
- Quiz with immediately visible answers (no hidden spoilers)
- Optional resources section

---

## Learner Profile

After each `/lesson-done`, the plugin updates `~/.claude/lessons/profile.json`:

```json
{
  "schema_version": "1",
  "total_sessions": 4,
  "misconceptions": [
    {
      "concept": "kernel module / userspace version coupling",
      "count": 2,
      "last_seen": "2026-04-16",
      "slug": "20260416-010610",
      "project": "/home/user/myproject"
    }
  ],
  "learned_concepts": [
    { "concept": "DKMS", "date": "2026-04-16", "slug": "20260416-010610" }
  ],
  "aggregate_tokens": {
    "total_estimated": 187000,
    "sessions": 4
  }
}
```

When the same misconception appears in a new session, the lesson adds a callout:

> **Pattern detected:** You've encountered this misconception before (last seen: 2026-04-10, session `20260310-153200`). This lesson explains why it keeps appearing.

Run `/lesson-profile` to see your full history.

---

## Token Tracking

Every session records token usage estimates in `meta.json` under `token_tracking`:

```json
{
  "arc_input_chars": 84000,
  "compression_cycles": 3,
  "graph_output_chars": 4200,
  "estimated_tokens": {
    "hook_logged": 21000,
    "compression_input": 7500,
    "lesson_done_input": 12400,
    "lesson_done_output": 2450,
    "total": 52150
  }
}
```

`/lesson-profile` shows per-session and aggregate token estimates with cost at Sonnet pricing.

---

## How It Works

Four rules govern the architecture:

1. **Silent by default.** The plugin only speaks when explicitly invoked (`/lesson*`, `/lesson-done`). No hook-driven model reminders, no blocking exit.
2. **Hooks stay dumb.** No LLM calls, no blocking, no side effects beyond writing `arc.jsonl` and spawning a detached compression subprocess.
3. **The main AI conversation stays lean.** The deterministic compressor folds raw events into the graph so the main context only ever sees structured nodes and edges.
4. **The lesson must be grounded or it must not be written.** Generation stops rather than inventing content when session data is insufficient.

### Flow (Claude Code)

```text
/lesson
  -> commands/lesson.md
  -> writes session files + active-session marker

normal work
  -> hooks/post_tool_use.py logs compact events to arc.jsonl
  -> every N events: spawns `lesson compress` in a detached subprocess
     (zero tokens, no output to the main conversation)

compression cycle
  -> EventGraphBuilder reads arc.jsonl
  -> extends session_graph.json with nodes and edges
  -> archives consumed events to arc.jsonl.archive.N

/lesson-done
  -> commands/lesson-done.md reads graph + tail events
  -> quality guard: refuses to generate from thin sessions
  -> reads ~/.claude/lessons/profile.json for recurring patterns
  -> decides whether web grounding is needed
  -> fills templates/lesson.md.tmpl
  -> writes output/<slug>.md
  -> scripts/render_pdf.py tries to create output/<slug>.pdf
  -> updates profile.json + token_tracking
```

### Flow (platforms without hooks)

Same flow, but the AI logs events to `arc.jsonl` manually after each significant tool call and calls `lesson compress` (or builds the graph inline) at the 25-event threshold and at `/lesson-done` time. No LLM subagent is involved on any platform.

### Repo Components

| File | Purpose |
| --- | --- |
| `hooks/post_tool_use.py` | Append-only event logger; spawns the silent compression subprocess at threshold |
| `hooks/stop.py` | Passive session-end nudge (never blocks exit) |
| `commands/lesson.md` | Session initialization |
| `commands/lesson-done.md` | Final lesson generation |
| `commands/regenerate.md` | Regeneration flow |
| `commands/lesson-resume.md` | Session resume |
| `commands/lesson-profile.md` | Learner profile display |
| `commands/lesson-index.md` | Lesson listing page |
| `commands/lesson-map.md` | Cross-lesson concept map |
| `templates/lesson.md.tmpl` | Lesson markdown template |
| `scripts/render_pdf.py` | Mermaid-to-PDF pipeline |
| `scripts/install.py` | Multi-platform install dispatcher |
| `skills/skill-<platform>.md` | Per-platform skill file |
| `lesson/` | Python package — algorithmic compression, CLI, graph algorithms |
| `eval/` | Compression quality metrics and benchmark |
| `tests/` | Unit + integration tests (pytest) |
| `docs/architecture.md` | Design notes and system rationale |

---

## Configuration

All settings are optional environment variables.

| Variable | Default | Effect |
| --- | --- | --- |
| `LESSON_COMPRESS_EVERY` | `25` | Events between compression runs |
| `LESSON_SILENT_HOOK` | `1` | When `1` (default) the PostToolUse hook spawns `lesson compress` silently. Set to `0` for debugging to restore the legacy `additionalContext` reminder. |
| `LESSON_STOP_MIN_EVENTS` | `5` | Min events before the Stop hook emits its passive nudge |
| `LESSON_MIN_EVENTS` | `8` | Min events before `/lesson-done` warns of thin session |
| `CLAUDE_PLUGIN_ROOT` | (auto) | Path to plugin root, used in PDF generation |

The `lesson compress` CLI also accepts `--threshold` (default `0.25`) and `--no-embed` flags.

---

## PDF Export

Markdown is the canonical output. PDF generation is optional and never blocks lesson creation.

`scripts/render_pdf.py` pipeline:
1. Extract Mermaid blocks from the lesson markdown
2. Render each diagram to SVG via `npx @mermaid-js/mermaid-cli`
3. Convert processed markdown to PDF via `pandoc`, or fall back to Chromium headless

If required tools are missing, the plugin succeeds with the markdown lesson only.

---

## Privacy and Trust

- Hooks only read stdin and write under `.claude/lessons/` — no network calls
- Tracking is a no-op unless `.claude/lessons/active-session` exists
- `/lesson-done` may use WebSearch/WebFetch when the concept needs external grounding
- The learner profile (`profile.json`) lives only on your local filesystem
- All prompts, templates, hook code, and the renderer are plain text and easy to audit

---

## Troubleshooting

**`/lesson` is not available after install**
Restart your AI assistant. Hooks and commands are registered at session start.

**`/lesson-done` says there is no active session**
`.claude/lessons/active-session` is missing. Run `/lesson` to start a new session, or `/lesson resume` to bring back the last one.

**The Stop hook keeps nudging me**
The nudge is a single non-blocking line. If you want silence even at Stop, delete `.claude/lessons/active-session` to abandon the session, or raise `LESSON_STOP_MIN_EVENTS` so the nudge only fires on substantial sessions.

**PDF export does not appear**
The markdown lesson is still valid. Install optional Mermaid and PDF tooling to get PDFs.

**Running on a platform without hooks — events not being logged**
The AI should be logging events manually. If it isn't, mention it in your prompt or add a note to your platform's skill file.

---

## Contributing

Issues and PRs are welcome.

Design constraints worth preserving:

- hooks must stay fast and LLM-free
- the main AI conversation should not read raw session logs directly
- graph compression should stay explicit and inspectable
- lessons should stay grounded in real session data
- graceful degradation is better than hidden failure
- platform skill files should share the same core lesson format

For a deeper technical overview, read [docs/architecture.md](docs/architecture.md).

## Further Reading

- [docs/architecture.md](docs/architecture.md) — design notes, data flow, schema reference, rationale
- [docs/how-it-works.md](docs/how-it-works.md) — pedagogical deep dive from hook to lesson
- [docs/blog-article.md](docs/blog-article.md) — short manifesto on why grounded lessons beat generic tutorials
- [CHANGELOG.md](CHANGELOG.md) — release history

## License

[MIT](LICENSE)
