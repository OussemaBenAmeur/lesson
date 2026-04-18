# How `lesson` Works — A Complete Guide

This document explains every part of the `lesson` plugin from the ground up. It assumes you know how to write code but nothing about how Claude Code plugins or "hooks" work. Read it top to bottom the first time; use it as a reference after that.

---

## Table of Contents

1. [The Big Idea](#1-the-big-idea)
2. [What Is a Claude Code Plugin?](#2-what-is-a-claude-code-plugin)
3. [What Are Hooks?](#3-what-are-hooks)
4. [The Two Sides of This Project](#4-the-two-sides-of-this-project)
5. [A Session, Step by Step](#5-a-session-step-by-step)
6. [The PostToolUse Hook — `hooks/post_tool_use.py`](#6-the-posttooluse-hook)
7. [The Stop Hook — `hooks/stop.py`](#7-the-stop-hook)
8. [The Session Knowledge Graph](#8-the-session-knowledge-graph)
9. [Compression — The Algorithmic Pipeline](#9-compression--the-algorithmic-pipeline)
10. [Generating the Lesson — `commands/lesson-done.md`](#10-generating-the-lesson)
11. [The Learner Profile](#11-the-learner-profile)
12. [PDF Rendering — `scripts/render_pdf.py`](#12-pdf-rendering)
13. [Multi-Platform Support — `skills/` and `scripts/install.py`](#13-multi-platform-support)
14. [The Lesson Template — `templates/lesson.md.tmpl`](#14-the-lesson-template)
15. [All the Files and What They Do](#15-all-the-files-and-what-they-do)
16. [Data Flow Diagram](#16-data-flow-diagram)
17. [Frequently Asked Questions](#17-frequently-asked-questions)

---

## 1. The Big Idea

When you're debugging something with an AI assistant, a lot of teaching signal is flying by: the errors you hit, the wrong assumptions you made, the exact moment you understood what was actually going on. All of that disappears when the session ends.

`lesson` captures that signal and turns it into a structured lesson — one that explains the fundamental concept you were missing, starting from absolute first principles, using your actual errors and commands as examples.

The difference from a generic tutorial is that the lesson knows *why* you got stuck, not just what the answer is.

---

## 2. What Is a Claude Code Plugin?

Claude Code is Anthropic's command-line AI assistant. A **plugin** is a directory of files that extends what Claude Code can do. When installed, a plugin can add:

- **Slash commands** — custom instructions that Claude follows when you type `/lesson`, `/lesson-done`, etc.
- **Hooks** — Python scripts that Claude Code runs automatically at specific moments (e.g. after every tool call)

This plugin lives at `~/.claude/plugins/lesson/`. Claude Code reads its `hooks.json` to know which scripts to run and when. The commands in `commands/` become available as `/lesson`, `/lesson-done`, etc. in any Claude Code session.

**Nothing runs on a server.** Everything is local files, local Python scripts, and calls to Claude's API via your normal Claude Code session.

---

## 3. What Are Hooks?

A **hook** is a Python script that Claude Code calls automatically at a specific event. Think of hooks as event listeners — they fire in response to things Claude does, not things you type.

Claude Code has several hook events. This plugin uses two:

### PostToolUse

Fires **after every single tool call** Claude makes. A "tool call" is any time Claude uses one of its built-in tools: reading a file, running a bash command, editing a file, searching for code, etc.

When this hook fires, Claude Code passes a JSON object to the script via **stdin** (standard input — the same way you'd pipe data between programs on the command line). That JSON contains:
- `tool_name` — which tool was used (e.g. `"Bash"`, `"Edit"`, `"Read"`)
- `tool_input` — what arguments were passed to the tool
- `tool_response` — what the tool returned (the output)
- `cwd` — the current working directory of the project

The hook script reads this JSON, decides what to do with it, and exits. It can optionally print JSON to stdout to give Claude additional context for its next response.

### Stop

Fires when Claude Code is **about to end the session** — when you close the chat or Claude finishes responding and becomes idle. This hook can either let Claude stop, or **block** the stop and give Claude a reason to keep going.

---

## 4. The Two Sides of This Project

`lesson` has two distinct sides that work together:

**Side 1 — The AI side (slash commands + hooks)**
These are markdown files containing instructions that Claude reads and follows. When you type `/lesson`, Claude reads `commands/lesson.md` and executes those instructions. The hooks (`post_tool_use.py`, `stop.py`) are Python scripts that run in the background automatically.

**Side 2 — The Python package (`lesson/`)**
This is a standard Python package you can install with `pip install -e .`. It provides a command-line tool (`lesson compress`, `lesson stats`, etc.) and a reusable library for graph compression that works independently of any AI assistant.

The two sides share the same file format for session data (`arc.jsonl`, `session_graph.json`) so they interoperate seamlessly.

---

## 5. A Session, Step by Step

Here is the complete lifecycle of a single learning session:

```
You type:    /lesson fix the asyncio blocking issue — I don't know what an event loop is

Claude runs: commands/lesson.md
  → creates .claude/lessons/sessions/20260418-143000-asyncio/
  → writes meta.json, arc.jsonl (empty), counter (0)
  → writes .claude/lessons/active-session  ← "tracking is now ON"

You work normally (Claude reads files, runs bash, edits code)
  → after EVERY tool call, Claude Code runs post_tool_use.py
  → the script appends a compact event record to arc.jsonl
  → when arc.jsonl reaches 25 events, the script tells Claude to compress

Compression runs silently (every 25 events)
  → post_tool_use.py spawns `lesson compress` as a detached subprocess
  → arc.jsonl is processed into session_graph.json (~50ms, zero LLM tokens)
  → arc.jsonl is archived and reset to empty
  → the user sees nothing — their main conversation is never interrupted

You type:    /lesson-done

Claude runs: commands/lesson-done.md
  → reads session_graph.json (the structured record of what happened)
  → reads ~/.claude/lessons/profile.json (your learning history)
  → decides if web research is needed
  → fills templates/lesson.md.tmpl with real content
  → writes .claude/lessons/output/20260418-143000-asyncio.md
  → runs scripts/render_pdf.py to create the PDF
  → updates your learner profile
  → deletes active-session marker (tracking is now OFF)
```

---

## 6. The PostToolUse Hook

**File:** `hooks/post_tool_use.py`

This is the most important piece of infrastructure in the plugin. It runs silently after every tool call during a session and is the reason the lesson knows what actually happened.

### What it receives

Claude Code calls the script like this under the hood:
```
echo '<json event>' | python3 hooks/post_tool_use.py
```

The JSON looks like:
```json
{
  "tool_name": "Bash",
  "tool_input": {"command": "pip install numpy"},
  "tool_response": {"output": "Successfully installed numpy-1.26.0"},
  "cwd": "/home/user/myproject"
}
```

### What it does

**Step 1 — Check if tracking is active.**
The script looks for `.claude/lessons/active-session` in the current project. If the file doesn't exist, it exits immediately (returns 0 — success) without doing anything. This means the hook is completely silent on every project that isn't running a lesson session.

**Step 2 — Read the session slug.**
If tracking is active, it reads the slug from `active-session` (e.g. `20260418-143000-asyncio`) and finds the session directory.

**Step 3 — Decide if the event is significant.**
Not every tool call is worth recording. Reading a random file for context is noise. An error is signal. The script uses cheap heuristics (no AI, no network) to decide:

```python
# Always significant:
- is_error is True                     # something failed
- tool is Edit / Write / NotebookEdit  # Claude changed something

# Significant if Bash and:
- result contains "error", "failed", "not found", "traceback", etc.
- result is short AND contains a version string like "3.10.12"

# Otherwise: not significant
```

**Step 4 — Append to arc.jsonl.**
It writes one JSON line to the session's `arc.jsonl` file:
```json
{"ts": 1713449823.4, "tool": "Bash", "args": "pip install numpy", "result_head": "Successfully installed numpy-1.26.0", "is_error": false, "significant": false}
```

`result_head` is capped at 1000 characters. `args` is capped at 500. This keeps the log compact.

**Step 5 — Track token usage.**
It increments `arc_input_chars` in `meta.json` — a running count of how many characters have been logged. Later this is used to estimate how many tokens the session consumed.

**Step 6 — Trigger compression when needed.**
It increments a counter in a file called `counter`. When that counter reaches 25 (configurable via `LESSON_COMPRESS_EVERY`), it resets the counter to 0 and spawns `lesson compress` as a detached background subprocess:

```python
subprocess.Popen(
    [lesson_cmd, "compress", "--cwd", project_root],
    stdout=DEVNULL,
    stderr=DEVNULL,
    start_new_session=True,
    close_fds=True,
)
```

The subprocess runs independently — the hook returns in under 10 ms without waiting. Nothing is written to stdout; no message is injected into the model's context. The user's main conversation is never interrupted.

Setting `LESSON_SILENT_HOOK=0` restores the legacy behavior (a single-line `additionalContext` reminder instead of a subprocess), which is useful only for debugging.

**Critical rule:** This script must never crash. If anything goes wrong, it exits with code 0 (success) silently. A hook that crashes would interfere with Claude's normal operation.

---

## 7. The Stop Hook

**File:** `hooks/stop.py`

This hook fires when Claude Code is about to end the session. Its job is to leave a one-line reminder that a tracked session is still active, without forcing any action.

It checks:
1. Is there an `active-session` marker? If not, do nothing.
2. How many events have been logged across `arc.jsonl` and all archives?
3. If fewer than 5 events (configurable via `LESSON_STOP_MIN_EVENTS`), do nothing — too thin to be useful.

If there are enough events, it emits a single passive `systemMessage`:

```json
{
  "hookSpecificOutput": {
    "hookEventName": "Stop",
    "systemMessage": "[/lesson] Session 'slug' still active — run /lesson-done when ready."
  }
}
```

The hook **does not block**. Earlier versions of the plugin returned `{"decision": "block", "reason": ...}`, which stopped the session mid-flight and forced Claude to run `/lesson-done` — a disruptive interruption. The current design surfaces a quiet reminder and lets you decide when (or if) to generate the lesson.

There's a `stop_hook_active` flag in the event that prevents repeating the reminder every turn — once `/lesson-done` has been triggered, the hook sees that flag and stays silent.

---

## 8. The Session Knowledge Graph

**File:** `session_graph.json` inside each session directory

The raw event log (`arc.jsonl`) captures everything, but it's verbose and unstructured. The **session knowledge graph** is a compressed, structured representation of the same information. It encodes *causality*, not just sequence.

### Why a graph?

A raw log might have 200 entries like "ran this command, got this output, edited this file, got this error." A graph would extract 10-15 meaningful nodes from those 200 entries and connect them with typed edges that explain *why* things happened in that order.

When `/lesson-done` runs, it reads the graph rather than the raw log. This means:
- Less token consumption — a graph with 15 nodes is much smaller than 200 log entries
- Better analysis — the root cause concept is already identified, the misconception is already flagged

### Node types

Every node has an `id`, a `type`, a `label` (a short description), and a `flags` dictionary.

| Type | What it represents | Example label |
|---|---|---|
| `goal` | What you were trying to accomplish | `"fix asyncio task never awaited warning"` |
| `observation` | Something you discovered — an error, a command output, a file state | `"RuntimeWarning: Enable tracemalloc to get the object allocation traceback"` |
| `hypothesis` | An assumption you were operating under (often wrong) | `"the task is being awaited somewhere downstream"` |
| `attempt` | A deliberate action — an edit, a command, a fix tried | `"Edit main.py: added await keyword"` |
| `concept` | A technical concept that turned out to be central | `"asyncio event loop — coroutine scheduling"` |
| `resolution` | The approach that worked | `"resolved via explicitly awaiting the coroutine at call site"` |

Flags are used to mark special nodes:
- `{"pivotal": true}` — an observation that changed the direction of debugging
- `{"misconception": true}` — a hypothesis that was proven wrong
- `{"root_cause": true}` — the concept node at the heart of the problem

### Edge types

Edges connect nodes and describe *why* they're connected:

| Type | Meaning | Example |
|---|---|---|
| `motivated` | hypothesis → attempt: a belief drove an action | `"thought task was awaited" → "added await keyword"` |
| `produced` | attempt → observation: an action revealed something | `"ran the script" → "RuntimeWarning appeared"` |
| `contradicted` | observation → hypothesis: evidence proved a belief wrong | `"still seeing error" → "task was awaited somewhere"` |
| `revealed` | observation → concept: a finding exposed a concept | `"coroutine object printed" → "asyncio event loop"` |
| `enabled` | concept → resolution: understanding made the fix possible | `"asyncio scheduling" → "awaited at call site"` |
| `achieves` | resolution → goal: the fix accomplished the goal | `"awaited at call site" → "fix asyncio warning"` |

### Schema version

The graph uses schema version `"2"`. In v2, flags are stored as a dictionary (`{"root_cause": true}`) rather than as individual boolean fields on the node. The Pydantic models in `lesson/graph/schema.py` are the authoritative definition.

### Node ID stability

Node IDs are permanently stable. Once a node gets the ID `c1`, it keeps that ID forever — across compression cycles, across tool calls, across restarts. New nodes continue the sequence (`c2`, `c3`, ...) but existing IDs are never changed. This is essential because edges reference node IDs by value.

---

## 9. Compression — The Algorithmic Pipeline

**Compression** is the process of reading raw events from `arc.jsonl` and converting them into nodes and edges in `session_graph.json`. The PostToolUse hook runs it automatically every 25 events by spawning `lesson compress` as a detached subprocess; you can also run it manually from any terminal.

| Property | Value |
|---|---|
| **Speed** | ~50ms per run (pure Python) |
| **Token cost** | Zero — no LLM calls |
| **Determinism** | Same input always produces the same graph |
| **Availability** | Any terminal, any platform — the Python package is the single source of truth |

Earlier versions of the plugin shipped an LLM subagent (`agents/lesson-compress.md`) that did this work by prompting Claude. It has been removed: the algorithmic pipeline is faster, cheaper, deterministic, and — critically — runs without interrupting the user's main conversation.

**Package:** `lesson/` (install with `pip install -e .`)

The main class is `EventGraphBuilder` in `lesson/graph/builder.py`. It runs a five-stage pipeline:

### Stage 1 — Significance Scoring (`lesson/nlp/scorer.py`)

Every event gets a float score between 0.0 and 1.0. This is a weighted composite of four signals:

```
score = 0.40 × TF-IDF_novelty
      + 0.35 × error_signal
      + 0.15 × edit_signal
      + 0.10 × version_signal
```

**TF-IDF novelty** — TF-IDF is a classic information-retrieval technique. It measures how unusual the words in an event are compared to the rest of the batch. An event that says "ModuleNotFoundError" scores higher than one that says "Reading file" because that error word is rarer and more informative within the batch. This captures events that introduced new information.

**Error signal** — 1.0 if `is_error` is true, 0.6 if the result text contains error keywords. This directly captures failures.

**Edit signal** — 1.0 if the tool was `Edit`, `Write`, or `NotebookEdit`. Edits represent deliberate decisions.

**Version signal** — 0.5 if a version string (like `3.10.2`) appears; 0.3 if a file path appears. These often indicate version comparisons or file discoveries that are relevant.

Events are sorted by score descending. The top candidates (score ≥ 0.25, max 12 per batch) move on to the next stage.

### Stage 2 — Entity Extraction (`lesson/nlp/extractor.py`)

For each candidate event, the extractor finds structured entities in the text using regular expressions:

- **File paths** — anything matching `./src/main.py` or `/etc/config`
- **Version strings** — `3.10.2`, `v2.1.0-beta`
- **Error names** — `ModuleNotFoundError`, `AttributeError`, `ENOENT`, `404`
- **Package names** — extracted from `pip install X`, `npm install X`
- **Bash command** — the first token of a bash command string

These entities become node labels. Using verbatim error names and paths makes the graph readable and recognizable — you see your own session in it.

### Stage 3 — Node Promotion

Each candidate event gets classified into a node type:

```
is_error → observation
tool is Edit/Write/NotebookEdit → attempt
tool is Bash + error keywords in output → observation
tool is Bash + no errors → attempt
tool is Read/Glob/Grep → observation
```

A node is created with the entity as its label. If the event is an error that follows a prior attempt, the observation node gets `{"pivotal": true}` in its flags.

### Stage 4 — Semantic Deduplication (`lesson/nlp/embedder.py`)

Before adding a new node, the embedder checks if a similar node already exists. It uses `sentence-transformers/all-MiniLM-L6-v2` — a small 22MB model that runs fast on CPU — to embed the new node's label and compare it to existing nodes of the same type.

If the cosine similarity exceeds 0.85, the new "node" is considered a duplicate and the existing node is reused instead. This prevents the graph from accumulating 10 slightly different ways to say "ModuleNotFoundError".

This step is **optional** — if `sentence-transformers` is not installed, the embedder falls back to exact string matching.

### Stage 5 — Edge Inference and Root Cause Detection

Edges are inferred from the types of consecutive nodes:

```
attempt → observation      =  "produced"     (action revealed something)
observation → hypothesis   =  "contradicted" if is_error, else "seemed_to_confirm"
observation → concept      =  "revealed"
concept → resolution       =  "enabled"
resolution → goal          =  "achieves"
```

Finally, `find_root_cause()` in `lesson/graph/algorithms.py` uses **betweenness centrality** (a NetworkX algorithm) on the concept nodes. Betweenness centrality measures how many shortest paths between other nodes pass through a given node. The concept node that sits between the most other nodes is the one the entire debugging arc depended on — that's the root cause.

### The CLI

Once installed, you use the package via the `lesson` command:

```bash
lesson start "fix asyncio issue"   # create session, write meta.json + arc.jsonl
lesson compress                     # run the pipeline above on arc.jsonl
lesson stats                        # print graph metrics in a table
lesson graph                        # open interactive Plotly graph in browser
lesson graph --mermaid              # print Mermaid flowchart syntax
lesson resume                       # reactivate the last session
lesson done                         # final compression + instructions for /lesson-done
```

---

## 10. Generating the Lesson

**File:** `commands/lesson-done.md`

When you type `/lesson-done`, Claude reads this command file and executes the generation pipeline. Here is every step:

### Step 1 — Load session data

Claude reads:
- `active-session` to get the slug
- `session_graph.json` — the primary data source
- The tail of `arc.jsonl` — any events since the last compression
- `meta.json` — goal, notes, token tracking

### Step 2 — Quality guard

Claude checks if the session has enough data. If there are fewer than 8 total events (configurable via `LESSON_MIN_EVENTS`), it warns you and asks for confirmation before continuing. If there are fewer than 5 events AND the graph has no concept or observation nodes, it stops entirely: "Session has too little data for a useful lesson."

### Step 3 — Read the learner profile

Claude reads `~/.claude/lessons/profile.json` (your global learner profile) to check if the current misconception has appeared before. If it has, the lesson will include a callout: "You've encountered this pattern before — session 20260310."

### Step 4 — Decide on web research

Claude asks: can this concept be explained accurately from general knowledge, or does it need external grounding?

Web research happens when:
- The concept involves specific version numbers, compatibility matrices, or release timing
- The concept is distribution-specific, tool-specific, or involves third-party library internals
- The session graph contains specific error messages that likely have community documentation

Web research is skipped when:
- The concept is a fundamental CS/OS/language concept (e.g. how a Python event loop works)
- General knowledge is sufficient

If research is done: `WebSearch` finds 3–5 authoritative sources, `WebFetch` retrieves them, and short quotes are used as inline citations in the lesson.

### Step 5 — Fill the lesson template

Claude loads `templates/lesson.md.tmpl` and fills every `{{PLACEHOLDER}}` with real content derived from the session graph. See [section 14](#14-the-lesson-template) for what each placeholder means.

### Step 6 — Compute token estimates

Before writing, Claude calculates how many tokens this session consumed:

```
hook_logged       = arc_input_chars / 4
compression_input = (arc_input_chars + graph_chars × cycles) / 4
compression_output = graph_chars / 4
lesson_done_input  = (graph_chars + web_fetch_chars + template_chars) / 4
lesson_done_output = lesson_chars / 4
total              = sum of all above
```

(Characters ÷ 4 ≈ tokens — a standard approximation used across the industry.)

These estimates are written to `meta.json` under `token_tracking`.

### Step 7 — Write output, render PDF, update profile

1. Writes `.claude/lessons/output/<slug>.md`
2. Runs `scripts/render_pdf.py` to produce the PDF (see section 14)
3. Updates `~/.claude/lessons/profile.json` — appends the misconception, the learned concept, increments session count and token totals
4. Writes `last-session` with the current slug
5. Deletes `active-session` — tracking is now off

---

## 11. The Learner Profile

**File:** `~/.claude/lessons/profile.json` (global — not per project)

The learner profile accumulates knowledge about you across all sessions and all projects. It lives in your home directory so it's shared regardless of which project you're working on.

```json
{
  "schema_version": "1",
  "total_sessions": 4,
  "misconceptions": [
    {
      "concept": "asyncio event loop — coroutine scheduling",
      "count": 2,
      "last_seen": "2026-04-18",
      "slug": "20260418-143000-asyncio",
      "project": "/home/user/myproject"
    }
  ],
  "learned_concepts": [
    {
      "concept": "asyncio event loop",
      "date": "2026-04-18",
      "slug": "20260418-143000-asyncio"
    }
  ],
  "aggregate_tokens": {
    "total_estimated": 187000,
    "sessions": 4
  }
}
```

**`misconceptions`** tracks concepts where you had a wrong mental model. If the same misconception appears in two different sessions, `count` increments to 2 and the next lesson you generate on that topic will include: *"You've encountered this pattern before (last seen: 2026-04-10, session X). This lesson explains why it keeps appearing."*

**`learned_concepts`** is a record of every root cause concept you've generated a lesson on.

**`aggregate_tokens`** is a running total of estimated token usage across all sessions.

Run `/lesson-profile` to display this in a readable format.

---

## 12. PDF Rendering

**File:** `scripts/render_pdf.py`

The Markdown lesson is the canonical output — it's what goes into git, what AI tools can read, and what renders in GitHub, Obsidian, and VS Code. The PDF is a bonus: a visually complete version where Mermaid diagrams are rendered as actual images.

The script uses zero LLM calls and always exits with code 0 (even on failure) — PDF generation must never block lesson creation.

### Pipeline

```
1. Extract mermaid blocks
   Find every ```mermaid ... ``` section in the markdown.

2. Render each block to SVG (optional)
   Run: npx @mermaid-js/mermaid-cli mmdc -i diagram.mmd -o diagram.svg
   If npx or mmdc is unavailable: skip, use code block as-is.

3. Replace mermaid fences with SVG images
   Substitute each ```mermaid...``` with ![](path/to/diagram.svg)
   in a temporary copy of the markdown.

4. Convert markdown → PDF
   Try in order:
   a. pandoc --pdf-engine=weasyprint
   b. pandoc --pdf-engine=wkhtmltopdf
   c. pandoc --pdf-engine=xelatex
   d. chromium --headless --print-to-pdf

5. If no tool is available
   Print: "PDF skipped — install pandoc or chromium"
   Exit 0. The .md file is still valid.
```

---

## 13. Multi-Platform Support

**Files:** `skills/skill-<platform>.md`, `scripts/install.py`

The plugin uses a "Single Core, Platform Wrapper" pattern. The core lesson format — session graph schema, template, learner profile — is identical across all platforms. What changes per platform is: how events are logged, where configuration lives, and what the command prefix is.

### How platforms differ

**Platforms with hooks (Claude Code, Gemini CLI):** The AI runtime automatically calls Python scripts after tool use. Event logging is invisible to the user.

**Platforms without hooks (everyone else):** There is no automatic mechanism to run Python after a tool call. Instead, the skill file instructs the AI to log events to `arc.jsonl` manually after each significant tool call. The AI follows these instructions as part of its response.

**Codex:** Commands use `$lesson` prefix instead of `/lesson`. This is just a naming convention Codex uses.

**Cursor:** Configuration is stored in `.cursor/rules/lesson.mdc` inside the project directory. The `.mdc` format is Cursor's version of a system prompt with `alwaysApply: true` frontmatter, meaning the rule is always active.

**Antigravity:** Configuration lives in `<project>/.agent/lesson.md`.

### The install script

`scripts/install.py` is a command-line dispatcher. You tell it which platform you want and it installs the right skill file in the right location:

```bash
python3 scripts/install.py --list                   # show all 10 platforms + their config paths
python3 scripts/install.py --platform claude-code   # registers hooks in ~/.claude/hooks.json
python3 scripts/install.py --platform cursor        # writes .cursor/rules/lesson.mdc in current dir
python3 scripts/install.py --platform gemini        # appends to ~/.gemini/GEMINI.md
                                                    # + registers BeforeTool hook in settings.json
```

For append-based installs (Codex, Copilot, OpenCode, etc.), the script checks for a marker string before appending so it's safe to run twice.

---

## 14. The Lesson Template

**File:** `templates/lesson.md.tmpl`

The template is a Markdown file with `{{PLACEHOLDER}}` tokens that Claude fills in during `/lesson-done`. Here is what each placeholder becomes:

| Placeholder | Content |
|---|---|
| `{{SLUG}}` | Session ID, e.g. `20260418-143000-asyncio` |
| `{{CONCEPT_TITLE}}` | Short name for the root cause concept |
| `{{DATE}}` | YYYY-MM-DD |
| `{{GOAL}}` | The goal from `meta.json` |
| `{{ROOT_CAUSE_LABEL}}` | The root cause concept node's label, lowercased |
| `{{TAGS}}` | 3–7 keywords derived from the concept nodes |
| `{{RECURRING_NOTE}}` | Callout if this misconception appeared before (empty string otherwise) |
| `{{NARRATIVE_GOAL}}` | 1–3 sentences: what you were trying to do |
| `{{NARRATIVE_BREAKDOWN}}` | Where it broke, in plain language |
| `{{REAL_SNIPPET_OR_ERROR}}` | The actual error message, verbatim from the graph |
| `{{FOUNDATIONS}}` | Bottom-up explanation of every prerequisite concept, from first principles |
| `{{CONCEPT_EXPLANATION}}` | The core concept explained in 3–6 paragraphs |
| `{{CONCEPT_DIAGRAM}}` | Raw Mermaid syntax for a concept diagram |
| `{{MISCONCEPTION_CONNECTION}}` | Connects your wrong assumption to the concept |
| `{{DEBUG_PATH_DIAGRAM}}` | Raw Mermaid flowchart of your actual debugging path |
| `{{FIX_EXPLANATION}}` | Why the fix works, in terms of the concept |
| `{{FIX_SNIPPET}}` | The actual fix — commands, code, or config — verbatim |
| `{{QUIZ}}` | 3–5 Q&A pairs with immediately visible answers |
| `{{RESOURCES_SECTION}}` | Links to sources if web research was done (empty otherwise) |

The `{{FOUNDATIONS}}` section is what makes the lesson different from a typical answer. It builds up every prerequisite concept from scratch using `###` subheadings — one per prerequisite. The depth is calibrated to the notes you provided in `/lesson [notes]`.

---

## 15. All the Files and What They Do

```
lesson/
│
├── hooks/
│   ├── hooks.json             Tells Claude Code which scripts to run for PostToolUse and Stop
│   ├── post_tool_use.py       Runs after every tool call: logs events, silently triggers `lesson compress`
│   └── stop.py                Runs when session ends: emits a one-line reminder (non-blocking)
│
├── commands/
│   ├── lesson.md              /lesson: create session, write active-session marker
│   ├── lesson-done.md         /lesson-done: generate lesson from graph
│   ├── regenerate.md          /regenerate [notes]: rewrite last lesson with new direction
│   ├── lesson-resume.md       /lesson resume: restore last session to active state
│   ├── lesson-profile.md      /lesson-profile: display learner profile and token usage
│   ├── lesson-index.md        /lesson-index: scan output/*.md, write index.html
│   └── lesson-map.md          /lesson-map [flags]: concept map across lessons
│
├── lesson/                    Python package (pip install -e .)
│   ├── cli.py                 `lesson` CLI: start/compress/stats/graph/resume/done
│   ├── session.py             SessionManager class: lifecycle, path helpers
│   ├── graph/
│   │   ├── schema.py          Pydantic models: SessionGraph, Node, Edge, RawEvent
│   │   ├── builder.py         EventGraphBuilder: deterministic compression pipeline
│   │   ├── algorithms.py      NetworkX algorithms: root cause, causal chain, communities
│   │   └── visualize.py       to_mermaid(), to_dot(), to_plotly_html()
│   ├── nlp/
│   │   ├── scorer.py          SignificanceScorer: TF-IDF + error + edit composite
│   │   ├── extractor.py       NLPExtractor: file paths, versions, error names
│   │   └── embedder.py        NodeEmbedder: semantic dedup via sentence-transformers
│   └── render/
│       ├── markdown.py        Markdown rendering helpers
│       └── pdf.py             PDF rendering helpers
│
├── eval/
│   ├── metrics.py             GraphQualityReport: F1, edge accuracy, quality score
│   └── benchmark.py           Compare algorithmic vs LLM compression
│
├── tests/
│   ├── unit/                  Unit tests for each module
│   ├── integration/           End-to-end pipeline tests
│   └── fixtures/              Sample arc.jsonl files for testing
│
├── templates/
│   ├── lesson.md.tmpl         Lesson markdown template with {{PLACEHOLDER}} tokens
│   └── lesson.html.tmpl       HTML template for index/map pages
│
├── scripts/
│   ├── render_pdf.py          Mermaid → SVG → PDF pipeline (always exits 0)
│   └── install.py             Multi-platform install dispatcher
│
├── skills/
│   ├── skill-claude-code.md   Reference (natively supported)
│   ├── skill-codex.md         Codex workflow ($lesson prefix, manual logging)
│   ├── skill-cursor.md        Cursor .mdc format, .cursor/lessons/ data root
│   ├── skill-gemini.md        Gemini CLI, optional BeforeTool hook
│   ├── skill-copilot.md       GitHub Copilot CLI
│   ├── skill-opencode.md      OpenCode
│   ├── skill-openclaw.md      OpenClaw
│   ├── skill-droid.md         Factory Droid
│   ├── skill-trae.md          Trae
│   └── skill-antigravity.md   Google Antigravity (.agent/ directory)
│
├── docs/
│   ├── how-it-works.md        This file — educational deep dive
│   └── architecture.md        Technical reference for contributors
│
├── .claude-plugin/
│   └── plugin.json            Plugin manifest: name, version, platforms, install command
│
├── CLAUDE.md                  AI context file (auto-loaded by Claude Code and most platforms)
├── README.md                  User-facing documentation
└── pyproject.toml             Python package config, dependencies, entry point
```

---

## 16. Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER ACTION                               │
│                    types: /lesson goal                           │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
                   commands/lesson.md
                   ┌─────────────────┐
                   │ create slug     │
                   │ write meta.json │
                   │ write arc.jsonl │  (empty)
                   │ write counter   │  (0)
                   │ write           │
                   │ active-session  │  ← tracking ON
                   └─────────────────┘

━━━━━━━━━━━━━━━━━  SESSION ACTIVE  ━━━━━━━━━━━━━━━━━

Every tool call Claude makes:
┌─────────────────────────────────────────────────────┐
│  Claude Code → stdin  →  post_tool_use.py           │
│                                                     │
│  1. active-session exists?  →  no: exit (no-op)     │
│  2. is_significant()?                               │
│  3. append JSON line to arc.jsonl                   │
│  4. increment arc_input_chars in meta.json          │
│  5. increment counter                               │
│  6. counter >= 25?  →  spawn `lesson compress`      │
│                       (detached subprocess, silent) │
└─────────────────────────────────────────────────────┘

Every 25 events — COMPRESSION runs in background:

  ┌────────────────────────────────────────┐
  │  lesson compress (detached subprocess) │
  │                                        │
  │  SignificanceScorer                    │
  │  → float score per event               │
  │                                        │
  │  NLPExtractor                          │
  │  → entity labels                       │
  │                                        │
  │  NodeEmbedder                          │
  │  → dedup check                         │
  │                                        │
  │  find_root_cause()                     │
  │  → betweenness centrality              │
  │                                        │
  │  archives arc.jsonl                    │
  └────────────────────────────────────────┘
                     │
                     ▼
            session_graph.json
        (nodes + edges + root_cause_id)

━━━━━━━━━━━━━━━  USER TYPES /lesson-done  ━━━━━━━━━━━━━

                   commands/lesson-done.md
  ┌──────────────────────────────────────────────────┐
  │  1. load session_graph.json + arc tail           │
  │  2. quality guard (< 8 events → warn)            │
  │  3. read ~/.claude/lessons/profile.json          │
  │  4. web research? (if version-specific concept)  │
  │  5. fill templates/lesson.md.tmpl                │
  │  6. compute token estimates → meta.json          │
  │  7. write output/<slug>.md                       │
  │  8. run scripts/render_pdf.py → output/<slug>.pdf│
  │  9. update profile.json                         │
  │ 10. write last-session                          │
  │ 11. delete active-session    ← tracking OFF      │
  └──────────────────────────────────────────────────┘

When Claude is about to stop (Stop hook):
  ┌──────────────────────────────────────────────────┐
  │  stop.py                                         │
  │  active session + >= 5 events?                   │
  │  → emit one-line systemMessage (non-blocking)    │
  │  → stop proceeds normally; user decides when to  │
  │    run /lesson-done                              │
  └──────────────────────────────────────────────────┘
```

---

## 17. Frequently Asked Questions

**Q: Does the hook run on every project I open, even ones without a lesson session?**
Yes, the hook is registered globally. But it exits immediately (in under 1ms) if `.claude/lessons/active-session` doesn't exist in the current project. The overhead is negligible.

**Q: What if the hook crashes?**
All exception-catching code in both hook scripts ends with `return 0` (or `sys.exit(0)`). Exit code 0 means "success" — Claude Code ignores the hook output and continues normally. A crash in a hook never affects Claude's behavior.

**Q: Can I use the Python package without Claude Code?**
Yes. `pip install -e .`, then `lesson start "my goal"` to create a session, work on your project, periodically run `lesson compress`, and finally `lesson done` to prepare the graph for lesson generation. You'd then pass the `session_graph.json` to any LLM to generate the actual lesson text.

**Q: What's the difference between `arc.jsonl` and `session_graph.json`?**
`arc.jsonl` is the raw event log — one JSON line per tool call, up to the last 25 events. It's like a rolling buffer. `session_graph.json` is the compressed, structured representation — nodes and edges extracted from all events so far. The graph accumulates across the whole session; `arc.jsonl` is periodically archived and reset.

**Q: Why does `/lesson-done` sometimes do web research and sometimes not?**
Claude decides based on the root cause concept. If the concept is a fundamental CS principle (how a Python event loop schedules coroutines), Claude can explain it accurately from training data. If the concept involves specific version numbers, a third-party library's internal behavior, or a Linux distribution quirk, Claude fetches authoritative sources to avoid hallucinating specifics.

**Q: How does the recurring misconception detection work?**
After every `/lesson-done`, the misconception node label from the graph is appended to `profile.json`. On the next session, `/lesson-done` reads the profile and checks if the current misconception's label fuzzy-matches any past entry. If it does and `count >= 1`, the lesson includes the callout. The profile lives at `~/.claude/lessons/profile.json` so it persists across all projects.

**Q: What does `flags: dict` mean in the graph schema?**
In schema v1, nodes had individual boolean fields like `"root_cause": true`, `"misconception": true`. In schema v2 (current), these are stored inside a single `flags` dictionary: `"flags": {"root_cause": true}`. The Pydantic model in `lesson/graph/schema.py` is the authoritative definition — if you're reading or writing the graph in code, use that model rather than hand-parsing JSON.

**Q: What if the PDF tools aren't installed?**
`scripts/render_pdf.py` prints a message like "PDF skipped — install pandoc or chromium" and exits 0. The Markdown lesson is always written regardless. The PDF is a bonus, never a blocker.
