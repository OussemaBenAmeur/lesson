# lesson

**A Claude Code plugin that turns real debugging sessions into grounded, reusable lessons.**

`lesson` watches the tool activity inside a live Claude Code session, keeps a compact record of the important turns, and turns the final arc into a lesson built from your actual files, commands, errors, and wrong assumptions.

Instead of generating a generic tutorial from scratch, it produces a lesson about what really happened:

- what you were trying to do
- where it broke
- which concept was actually missing
- why the misconception was believable
- what fixed it
- how to test whether you now understand it

```text
/lesson react useEffect infinite loop when depending on an object
# work normally in Claude Code
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

## Why This Exists

Most learning tools start with a topic and invent an explanation.

`lesson` starts with a real failure path.

That difference matters. A debugging session contains high-quality teaching signal: the commands you ran, the outputs you misread, the hypotheses you formed, the file edits you tried, and the observation that finally changed your mind. That is the raw material a serious lesson should be built from.

| Generic tutorial | `lesson` |
| --- | --- |
| Starts from an abstract topic | Starts from your actual session |
| Uses canned examples | Uses your files, errors, and commands |
| Explains the concept in general | Explains why *you* got stuck |
| Often guesses at relevance | Has a concrete debugging arc to teach from |

## What Ships Today

- Session tracking via Claude Code `PostToolUse` and `Stop` hooks
- Graph-based compression so long sessions stay manageable
- Canonical markdown lesson output
- Best-effort PDF rendering with Mermaid diagrams
- `/regenerate` to rewrite the latest lesson with new guidance
- `/lesson resume` to continue a paused session
- `/lesson-index` to build a browsable lesson list
- `/lesson-map` to build a concept map across generated lessons

## Install

### Requirements

- Claude Code
- Python 3.10+
- Optional for PDF export:
  - `npx` with `@mermaid-js/mermaid-cli`
  - `pandoc` plus `weasyprint`, `wkhtmltopdf`, `xelatex`, or `pdflatex`
  - or a Chromium-based browser for the fallback renderer

### From GitHub Marketplace

Inside Claude Code:

```text
/plugin marketplace add OussemaBenAmeur/lesson
/plugin install lesson
```

Restart Claude Code after install. The hooks and commands are registered when the session starts.

### Local Development Install

```bash
git clone https://github.com/OussemaBenAmeur/lesson.git
```

Then inside Claude Code:

```text
/plugin marketplace add /absolute/path/to/lesson
/plugin install lesson
```

## Quick Start

### 1. Start tracking

```text
/lesson python asyncio task never awaited explain from scratch
```

The argument is optional, but useful. It becomes part of the session metadata and guides how the final lesson is written.

Examples:

```text
/lesson linux driver mismatch explain from first principles
/lesson react stale closure I know hooks basics, focus on the bug pattern
/lesson
```

### 2. Work normally

Read files. Edit code. Run Bash commands. Fail. Recover. Try again.

The hook logs tool events into `.claude/lessons/sessions/<slug>/arc.jsonl`. Every `LESSON_COMPRESS_EVERY` events, the plugin asks Claude to run the compression subagent so the raw trace gets folded into a structured `session_graph.json`.

### 3. Generate the lesson

```text
/lesson-done
```

This writes the final markdown lesson to `.claude/lessons/output/<slug>.md` and records `<slug>` in `.claude/lessons/last-session`.

If optional PDF tooling is available, the repo also tries to render `.claude/lessons/output/<slug>.pdf`.

### 4. Refine or explore

```text
/regenerate make the foundations deeper and the quiz harder
/lesson-index
/lesson-map --last 10
```

## Command Reference

| Command | Purpose |
| --- | --- |
| `/lesson [notes]` | Start a tracked learning session in the current project |
| `/lesson-done` | Generate the lesson from the active session |
| `/regenerate [notes]` | Rebuild the most recent lesson with new instructions |
| `/lesson resume` | Resume tracking on the most recent session |
| `/lesson-index` | Build `output/index.html` listing generated lessons |
| `/lesson-map [flags]` | Build `output/map.html` connecting lessons by concepts |

Supported `/lesson-map` filters:

- `--last N`
- `--since YYYY-MM-DD`
- `--slugs slug1,slug2,...`
- `--tag keyword`

## What The Plugin Writes

All runtime state lives in the target project's `.claude/lessons/` directory, not in the plugin directory.

```text
.claude/lessons/
├── active-session
├── last-session
├── sessions/<slug>/
│   ├── meta.json
│   ├── arc.jsonl
│   ├── summary.md              # compatibility / fallback file
│   ├── session_graph.json      # created after compression
│   ├── counter
│   └── arc.jsonl.archive.<N>
└── output/
    ├── <slug>.md
    ├── <slug>.pdf              # optional
    ├── index.html
    └── map.html
```

Key files:

- `meta.json`: session goal, notes, timestamps, working directory
- `arc.jsonl`: compact raw event log since the last compression cycle
- `session_graph.json`: the structured view of the session used by generation
- `output/<slug>.md`: the canonical lesson artifact
- `output/<slug>.pdf`: optional rendered export, generated on a best-effort basis

Recommended `.gitignore` entries:

```gitignore
.claude/lessons/active-session
.claude/lessons/sessions/
```

Version `output/` if you want the lessons to live with the repo. Ignore it if they are personal notes.

## What A Lesson Contains

The markdown template in [templates/lesson.md.tmpl](templates/lesson.md.tmpl) produces:

- YAML frontmatter with slug, concept, date, goal, root cause, and tags
- a session narrative grounded in the real failure
- a foundations section that builds the missing concept from lower-level prerequisites
- a concept explanation with citations when research is needed
- a Mermaid concept diagram
- a Mermaid debug-path diagram based on the actual session arc
- a fix explanation and concrete fix snippet
- a quiz that checks understanding, not just recall
- an optional resources section

## How It Works

The architecture follows three rules:

1. Hooks stay dumb.
2. The main Claude conversation stays lean.
3. The lesson should be grounded or it should not be written.

### Flow

```text
/lesson
  -> commands/lesson.md
  -> writes session files + active-session marker

normal Claude Code work
  -> hooks/post_tool_use.py logs compact events to arc.jsonl
  -> every N events, Claude is nudged to run the compression subagent

compression cycle
  -> agents/lesson-compress.md reads arc.jsonl
  -> extends session_graph.json
  -> archives consumed events

/lesson-done
  -> commands/lesson-done.md reads graph + tail events
  -> decides whether web grounding is needed
  -> fills templates/lesson.md.tmpl
  -> writes output/<slug>.md
  -> scripts/render_pdf.py tries to create output/<slug>.pdf
```

### Repo Components

- [hooks/post_tool_use.py](hooks/post_tool_use.py): append-only event logger and compression trigger
- [hooks/stop.py](hooks/stop.py): session-end nudge so active tracked sessions are not silently abandoned
- [agents/lesson-compress.md](agents/lesson-compress.md): graph compression instructions
- [commands/lesson.md](commands/lesson.md): session initialization
- [commands/lesson-done.md](commands/lesson-done.md): final lesson generation
- [commands/regenerate.md](commands/regenerate.md): regeneration flow
- [commands/lesson-index.md](commands/lesson-index.md): lesson listing page generation
- [commands/lesson-map.md](commands/lesson-map.md): cross-lesson concept map generation
- [scripts/render_pdf.py](scripts/render_pdf.py): Mermaid-to-PDF pipeline
- [docs/architecture.md](docs/architecture.md): design notes and system rationale

## Configuration

All settings are optional environment variables.

| Variable | Default | Effect |
| --- | --- | --- |
| `LESSON_COMPRESS_EVERY` | `25` | Number of tracked events between compression runs |
| `LESSON_STOP_MIN_EVENTS` | `5` | Minimum tracked events before the Stop hook blocks exit and nudges `/lesson-done` |

Example `.claude/settings.json`:

```json
{
  "env": {
    "LESSON_COMPRESS_EVERY": "15",
    "LESSON_STOP_MIN_EVENTS": "8"
  }
}
```

## PDF Export

Markdown is the canonical output. PDF generation is optional and never blocks lesson creation.

The renderer in [scripts/render_pdf.py](scripts/render_pdf.py) does this:

1. Extract Mermaid blocks from the lesson markdown
2. Render diagrams to SVG through `npx @mermaid-js/mermaid-cli` when available
3. Convert processed markdown to PDF via `pandoc`, or fall back to Chromium headless

If the required tools are missing, the plugin still succeeds and keeps the markdown lesson.

## Privacy And Trust Model

Within this plugin, the tracking and archive flow are local-file operations.

- Hooks only read stdin, inspect the current project, and write under `.claude/lessons/`
- The tracking hook is a no-op unless `.claude/lessons/active-session` exists
- The generation flow may use `WebSearch` and `WebFetch` during `/lesson-done` when the concept needs authoritative grounding
- The lesson is supposed to stop rather than bluff when grounding is necessary but unavailable

This repository is optimized for transparency: the prompts, templates, hook code, and renderer are all plain text and easy to audit.

## Current Scope

`lesson` is already useful as a serious Claude Code learning plugin, but it is intentionally focused.

Today it is optimized for:

- debugging and problem-solving sessions in Claude Code
- one active tracked session per project
- markdown-first lesson artifacts
- technical concepts that benefit from tracing a real failure path

It is not yet a general-purpose LMS, cross-editor platform, or community lesson network. The README only documents behavior that exists in this repository today.

## Troubleshooting

**`/lesson` is not available after install**

Restart Claude Code. Plugin commands and hooks are registered at session start.

**`/lesson-done` says there is no active session**

You do not have `.claude/lessons/active-session` in the current project, or it was deleted. Start a new session with `/lesson`.

**The Stop hook keeps nudging me**

Delete `.claude/lessons/active-session` if you explicitly want to abandon the session without generating a lesson.

**PDF export does not appear**

The markdown lesson is still valid. Install the optional Mermaid and PDF tooling if you want rendered PDFs.

## Contributing

Issues and PRs are welcome.

Design constraints worth preserving:

- hooks must stay fast and LLM-free
- the main Claude conversation should not read raw session logs directly
- graph compression should stay explicit and inspectable
- lessons should stay grounded in real session data
- graceful degradation is better than hidden failure

For a deeper technical overview, start with [docs/architecture.md](docs/architecture.md).

## License

[MIT](LICENSE)
