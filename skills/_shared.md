<!--
Shared platform-agnostic workflow. Concatenated onto each per-platform skill
file by `scripts/install.py`. Do not read this file directly — install.py does
the substitution of {{DATA_ROOT}} and {{PLATFORM}} at install time.
-->

## Session Tracking (Manual — No Hooks)

This platform does not support PostToolUse hooks. Log events yourself.

**After every significant tool call**, append one line to `{{DATA_ROOT}}/sessions/<slug>/arc.jsonl`:

```json
{"ts": <unix_timestamp>, "tool": "<ToolName>", "args": "<brief args, max 200 chars>", "result_head": "<first 400 chars>", "is_error": <true|false>, "significant": <true|false>}
```

Mark `significant: true` when: the tool returned an error, you edited/wrote a file, a Bash result contained error keywords or version strings, or the result changed your understanding. Do not log trivial reads.

**At 25 events**, build the graph inline (see "Graph Building") or run `lesson compress --cwd .` if the Python package is installed. Either way, never spawn an LLM subagent for compression.

---

## Commands

All commands below are silent while the session is active — only the explicit `/lesson*` commands and `/lesson-done` speak to the user. Do not nag about compression or outstanding work between invocations.

### `/lesson [notes]`

1. Generate slug: `YYYYMMDD-HHMMSS` (UTC). Append a keyword from notes if non-empty.
2. Create `{{DATA_ROOT}}/sessions/<slug>/` containing:
   - `meta.json`: `{"slug":"<slug>","goal":"<notes>","notes":"<notes>","started_at":"<ISO8601>","cwd":"<abs_path>","platform":"{{PLATFORM}}"}`
   - `arc.jsonl`: empty
   - `counter`: `0`
3. Write slug to `{{DATA_ROOT}}/active-session`.
4. Confirm: `✓ /lesson tracking active  session: <slug>  goal: <notes or "(none)">`.

If `active-session` already exists, ask before overwriting.

### `/lesson-done`

1. Read `{{DATA_ROOT}}/active-session` → slug. If missing, stop.
2. Load `meta.json`, `session_graph.json` (if present), `arc.jsonl`.
3. **Quality guard:** if total events < 8, warn and ask before continuing. If < 5 events AND the graph has no concept/observation nodes, stop.
4. Compress remaining `arc.jsonl` events into the graph (see "Graph Building"), or run `lesson compress --cwd .`.
5. Read `~/.claude/lessons/profile.json` for recurring misconceptions.
6. Decide whether web research is needed (skip for stable CS/OS/language concepts).
7. Fill `<plugin_root>/templates/lesson.md.tmpl` and write to `{{DATA_ROOT}}/output/<slug>.md`.
8. Run `python3 <plugin_root>/scripts/render_pdf.py {{DATA_ROOT}}/output/<slug>.md`.
9. Update `~/.claude/lessons/profile.json` (misconceptions, learned_concepts, token counts).
10. Write `last-session`, delete `active-session`.
11. Report: `✓ /lesson generated  concept: <title>  file: {{DATA_ROOT}}/output/<slug>.md`.

### `/lesson resume`

Read `last-session`, check for a conflicting `active-session`, write slug back to `active-session`. Resume logging.

### `/regenerate [notes]`

Reload the most recent session, apply new notes, overwrite `<slug>.md`, run `render_pdf.py`. Report the one-sentence diff.

### `/lesson-profile`

Display `~/.claude/lessons/profile.json`: recurring misconceptions (sorted by count), concepts learned (last 10), aggregate token estimates.

### `/lesson-index`

Scan `{{DATA_ROOT}}/output/*.md`, read YAML frontmatter, write a browsable `index.html`.

### `/lesson-map [--last N] [--since DATE] [--tag KEYWORD]`

Build a cross-lesson concept map from session graphs; write `map.html` with a Mermaid diagram.

---

## Graph Building (schema v2)

When compressing `arc.jsonl` into `session_graph.json`:

```json
{
  "schema_version": "2",
  "slug": "<slug>",
  "goal": "<goal>",
  "total_events_compressed": 0,
  "root_cause_id": null,
  "resolution_id": null,
  "nodes": [{"id": "g1", "type": "goal", "label": "<goal>", "flags": {}}],
  "edges": []
}
```

**Node types:** `goal`, `observation`, `hypothesis`, `attempt`, `concept`, `resolution`.
**Flags (dict on each node):** `{"pivotal": true}`, `{"misconception": true}`, `{"root_cause": true}`.
**Edge types:** `motivated`, `produced`, `revealed`, `contradicted`, `seemed_to_confirm`, `assumed_about`, `involves`, `enabled`, `achieves`.

**Rules:**
- Node IDs: type-initial + integer (`g1`, `o1`, `h1`, `a1`, `c1`, `r1`). Never renumber across cycles.
- Labels: verbatim from actual tool output. Quote error messages exactly.
- 25 raw events → roughly 5–12 new nodes. Most events are noise.
- Set `root_cause_id` when a concept is flagged `root_cause: true`.
- Set `resolution_id` when a resolution node is added.
- Archive consumed events: rename `arc.jsonl` → `arc.jsonl.archive.N`, reset to empty, reset counter to `0`.

---

## Lesson Template

Fill every `{{PLACEHOLDER}}` in `<plugin_root>/templates/lesson.md.tmpl`:

- YAML frontmatter first (slug, concept, date, goal, root_cause, tags).
- **Foundations:** bottom-up, first-principles, `###` per prerequisite.
- **Core concept:** 3–6 paragraphs.
- **Two Mermaid diagrams:** concept diagram + debug-path flowchart derived from the session graph.
- **Fix:** explanation plus verbatim fix snippet.
- **Quiz:** 3–5 Q&A pairs with answers immediately visible (no spoiler tags).
- **Resources:** only if web research was performed.

Calibrate depth to `meta.json.notes` — explain everything from scratch unless the notes say otherwise.
