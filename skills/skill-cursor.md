---
description: /lesson — turn any working session into a textbook-quality lesson
alwaysApply: true
---

# /lesson Skill for Cursor

You are equipped with a learning session tracker. When the user invokes `/lesson`, `/lesson-done`,
`/regenerate`, `/lesson resume`, `/lesson-profile`, `/lesson-index`, or `/lesson-map`,
follow the instructions below exactly.

---

## Session Tracking (Manual — No Hooks)

Cursor does not support PostToolUse hooks. You must log events yourself.

**After every significant tool call**, append one line to `.cursor/lessons/sessions/<slug>/arc.jsonl`:
```json
{"ts": <unix_timestamp>, "tool": "<ToolName>", "args": "<brief args, max 200 chars>", "result_head": "<first 400 chars>", "is_error": <true|false>, "significant": <true|false>}
```

Mark `significant: true` when: tool returned an error, you edited/wrote a file, Bash result contained
error keywords or version strings, or the result changed your understanding.

**Graph compression:** When `arc.jsonl` reaches 25 lines, build the graph inline (see "Graph Building").

**Note:** Lesson data is stored in `.cursor/lessons/` (not `.claude/lessons/`) when running in Cursor.
The learner profile remains at `~/.claude/lessons/profile.json` (shared across platforms).

---

## Commands

### `/lesson [notes]`

1. Generate slug: `YYYYMMDD-HHMMSS` (UTC). Append keyword from notes if non-empty.
2. Create `.cursor/lessons/sessions/<slug>/` with:
   - `meta.json`: `{"slug":"<slug>","goal":"<notes>","notes":"<notes>","started_at":"<ISO8601>","cwd":"<abs_path>","platform":"cursor"}`
   - `arc.jsonl`: empty
   - `counter`: `0`
3. Write slug to `.cursor/lessons/active-session`
4. Confirm: `✓ /lesson tracking active  session: <slug>  goal: <notes or "(none)">`
5. Begin manually logging events to `arc.jsonl` after each significant action.

### `/lesson-done`

1. Read `.cursor/lessons/active-session` → slug.
2. Load `meta.json`, `session_graph.json` (if exists), `arc.jsonl`.
3. Quality guard: warn if total events < 8; stop if < 5 events AND no concept/observation nodes.
4. Build graph inline from remaining `arc.jsonl`.
5. Read `~/.claude/lessons/profile.json` for recurring misconceptions.
6. Decide on web research (skip for stable CS/OS concepts).
7. Generate lesson from `<plugin_root>/templates/lesson.md.tmpl`.
8. Write to `.cursor/lessons/output/<slug>.md`.
9. Run: `python3 <plugin_root>/scripts/render_pdf.py .cursor/lessons/output/<slug>.md`
10. Update `~/.claude/lessons/profile.json`.
11. Write `last-session`, delete `active-session`.
12. Report: `✓ /lesson generated  file: .cursor/lessons/output/<slug>.md`

### `/lesson resume`

Read `last-session` → write slug to `active-session`. Resume manual event logging.

### `/regenerate [notes]`

Read `last-session`, reload session data, apply notes, re-generate and overwrite `<slug>.md`,
run `render_pdf.py`. Report what changed.

### `/lesson-profile`

Read `~/.claude/lessons/profile.json`. Show misconceptions, concepts, token estimates.

### `/lesson-index`

Scan `.cursor/lessons/output/*.md`, read YAML frontmatter, write `index.html`.

### `/lesson-map [--last N] [--since DATE] [--tag KEYWORD]`

Build concept map from session graphs. Write `map.html` with mermaid diagram.

---

## Graph Building

When compressing `arc.jsonl` into `session_graph.json`:

```json
{
  "schema_version": "1", "slug": "<slug>", "goal": "<goal>",
  "total_events_compressed": 0, "root_cause_id": null, "resolution_id": null,
  "nodes": [{"id": "g1", "type": "goal", "label": "<goal>"}],
  "edges": []
}
```

Node types: `goal`, `observation`, `hypothesis`, `attempt`, `concept`, `resolution`
Flags: `pivotal`, `misconception`, `root_cause`
Edge types: `motivated`, `produced`, `revealed`, `contradicted`, `seemed_to_confirm`,
`assumed_about`, `involves`, `enabled`, `achieves`

Rules: IDs stable (never renumber). Labels verbatim. 25 events → 5–12 nodes max.
Archive `arc.jsonl` → `arc.jsonl.archive.N` after compression.

---

## Lesson Generation

Fill `<plugin_root>/templates/lesson.md.tmpl`. YAML frontmatter first. Cover:
foundations (first principles, `###` per prerequisite), core concept, two mermaid diagrams
(concept diagram + debug path flowchart), fix + snippet, quiz (3–5 visible Q&A), resources.
Calibrate depth to `meta.json.notes`.
