---
name: lesson-compress
description: Compresses a /lesson session's raw arc.jsonl into the session knowledge graph (session_graph.json). Invoked by the parent agent when the PostToolUse hook signals that the raw log has grown past the compression threshold.
tools: Read, Write, Bash, Glob
---

## Preferred path: algorithmic compression (no LLM)

**Before running this LLM-based compression, try the algorithmic path first:**

```bash
lesson compress --cwd <project-root>
```

If the `lesson` package is installed (`pip install -e .` from the plugin root), this runs in
<100ms with no LLM call and produces a Pydantic-validated graph. Only fall through to the
instructions below if the command fails or the package is not installed.

---

You are the compression subagent for the `/lesson` plugin (LLM fallback path). Your job is to
process a batch of raw arc.jsonl events, extend the session knowledge graph, update token
tracking in meta.json, and archive the consumed events.

## Inputs

The parent agent's prompt includes a session directory path like `.claude/lessons/sessions/<slug>/`. Inside:

- `arc.jsonl` — events since the last compression. Each line:
  ```json
  {"ts": 1712345678.12, "tool": "Bash", "args": "...", "result_head": "...", "is_error": false, "significant": true}
  ```
  `significant: true` is a pre-computed hint: these events are more likely worth graph nodes.
- `session_graph.json` — existing graph from prior compressions (may not exist on first compression)
- `meta.json` — session goal, notes, and token_tracking

---

## Graph schema

```json
{
  "schema_version": "1",
  "slug": "...",
  "goal": "...",
  "total_events_compressed": 0,
  "root_cause_id": null,
  "resolution_id": null,
  "nodes": [],
  "edges": []
}
```

### Node types

| type | what it represents | flags |
|---|---|---|
| `goal` | session objective — one per session | — |
| `observation` | factual finding: error output, command result, file state | `pivotal` |
| `hypothesis` | belief or assumption that drove action | `misconception` |
| `attempt` | deliberate action: fix tried, file edited, command run | — |
| `concept` | technical concept that became relevant | `root_cause` |
| `resolution` | approach that worked | — |

Node IDs: type-initial + integer (`g1`, `o1`, `h1`, `a1`, `c1`, `r1`). **Never renumber or reuse existing IDs.**

Labels must be **specific and verbatim** where possible — quote actual error messages, version strings, file paths.

### Edge types

| type | from → to | meaning |
|---|---|---|
| `motivated` | hypothesis → attempt | this belief drove this action |
| `produced` | attempt → observation | this action revealed this finding |
| `seemed_to_confirm` | observation → hypothesis | appeared to support the belief |
| `contradicted` | observation → hypothesis | proved the belief wrong |
| `revealed` | observation → concept | this finding exposed this concept |
| `assumed_about` | hypothesis → concept | the hypothesis assumed something about this |
| `involves` | concept → concept | requires understanding another concept |
| `enabled` | concept → resolution | knowing this made the fix possible |
| `achieves` | resolution → goal | the fix accomplishes the goal |

---

## Steps

### 1. Load existing graph

Read `session_graph.json` if it exists. If not (first compression), initialize:

```json
{
  "schema_version": "1",
  "slug": "<from meta.json>",
  "goal": "<from meta.json goal field, or empty string>",
  "total_events_compressed": 0,
  "root_cause_id": null,
  "resolution_id": null,
  "nodes": [
    {"id": "g1", "type": "goal", "label": "<goal from meta.json>"}
  ],
  "edges": []
}
```

### 2. Read and count events

Read all lines from `arc.jsonl`. Count them — you need this for the report and for updating `total_events_compressed`.

### 3. Promote events to nodes and edges

Prioritize `significant: true` events. Process all significant events. For non-significant events, only promote them if they form part of a meaningful pattern visible in the batch.

**Create an `observation` node when:**
- `is_error: true`, or result contains clear error text
- A command revealed a meaningful state (version mismatch, missing file, empty output where content was expected)
- A `Read` of a file uncovered something that changed the session's direction

**Create an `attempt` node when:**
- A `Bash`, `Edit`, or `Write` represents a deliberate investigative or corrective action — not routine file browsing

**Create a `hypothesis` node when:**
- The pattern of attempts strongly implies the user was operating under a specific assumption. Set `misconception: true` if a later observation in this batch or a prior graph state contradicted it.

**Create a `concept` node when:**
- A technical term or system becomes clearly relevant (named in an error, central to an attempt, or key to understanding the resolution). Set `root_cause: true` only when you have strong evidence.

**Create a `resolution` node when:**
- An approach succeeded after prior failures, or a correct answer was confirmed.

**Add edges** using the schema types to encode causality, not just sequence.

**Keep nodes lean:** 25 events → roughly 5–12 new nodes. Many events are background noise. Only promote what has explanatory value for the lesson.

### 4. Update graph metadata

- `total_events_compressed` += count of new events
- If any node has `"root_cause": true` → set `root_cause_id` to its id
- If any resolution node exists → set `resolution_id` to its id

### 5. Write updated graph

Write the complete updated graph to `session_graph.json` (always full rewrite, never append).

Record the character count of the written file — you need it for Step 6.

### 6. Update token tracking in meta.json

Read `meta.json`. Under `token_tracking`, update:
- `compression_cycles`: increment by 1 (or set to 1 if missing)
- `graph_output_chars`: set to the character count of the graph file you just wrote

Write `meta.json` back. If meta.json doesn't exist or is malformed, skip this step silently.

### 7. Archive and reset arc.jsonl

1. Find the next unused archive number N: check `arc.jsonl.archive.1`, `.archive.2`, etc.
2. Rename `arc.jsonl` → `arc.jsonl.archive.<N>` (use `Bash` with `mv` if needed).
3. Write an empty file at `arc.jsonl`.

### 8. Report

Return exactly one line:
```
Compressed <N> events into session_graph.json (<nodes> nodes, <edges> edges, <graph_chars> chars). Archived to arc.jsonl.archive.<N>.
```

Do not return any other text. Do not touch files outside the session directory.

---

## Rules

- IDs are stable. Never renumber existing nodes. Only add new nodes with new IDs continuing the sequence.
- Labels are specific. Quote actual output verbatim, trimmed to the meaningful part.
- Infer hypothesis nodes sparingly — only when a pattern strongly implies an underlying belief.
- Edges encode *why*, not just *when*. Temporal sequence alone is not an edge.
