# /lesson — GitHub Copilot CLI Skill

You are equipped with a learning session tracker. When the user invokes `/lesson`, `/lesson-done`,
`/regenerate`, `/lesson resume`, `/lesson-profile`, `/lesson-index`, or `/lesson-map`,
follow the instructions below exactly.

---

## Session Tracking (Manual — No Hooks)

GitHub Copilot CLI does not support PostToolUse hooks. You must log events yourself.

**After every significant tool call**, append one line to `.claude/lessons/sessions/<slug>/arc.jsonl`:
```json
{"ts": <unix_timestamp>, "tool": "<ToolName>", "args": "<brief args, max 200 chars>", "result_head": "<first 400 chars>", "is_error": <true|false>, "significant": <true|false>}
```

Mark `significant: true` when: error returned, file edited/written, error keywords in Bash result,
result changed your understanding.

**At 25 events**: build the session graph inline (see "Graph Building" below), archive `arc.jsonl`.

---

## Commands

### `/lesson [notes]`

1. Generate slug: `YYYYMMDD-HHMMSS` (UTC).
2. Create `.claude/lessons/sessions/<slug>/` with `meta.json`, empty `arc.jsonl`, `counter`.
   - `meta.json`: `{"slug":"<slug>","goal":"<notes>","notes":"<notes>","started_at":"<ISO8601>","cwd":"<abs_path>","platform":"copilot"}`
3. Write slug to `.claude/lessons/active-session`.
4. Confirm start. Begin manually logging events.

### `/lesson-done`

1. Read `active-session` → slug.
2. Load session data. Quality guard (warn if < 8 events, stop if < 5 AND no nodes).
3. Build graph inline from `arc.jsonl`.
4. Read `~/.claude/lessons/profile.json`.
5. Decide on web research. Generate lesson from template.
6. Write `.claude/lessons/output/<slug>.md`.
7. Run `python3 <plugin_root>/scripts/render_pdf.py .claude/lessons/output/<slug>.md`.
8. Update profile. Write `last-session`. Delete `active-session`.

### `/lesson resume`

Read `last-session` → write to `active-session`. Resume manual logging.

### `/regenerate [notes]`

Read `last-session`, re-generate lesson with new notes, overwrite `.md`, run PDF.

### `/lesson-profile`

Show `~/.claude/lessons/profile.json`: misconceptions (by count), concepts, token totals.

### `/lesson-index`

Scan `output/*.md`, read YAML frontmatter, write `index.html`.

### `/lesson-map [--last N] [--since DATE] [--tag KEYWORD]`

Build concept map from session graphs, write `map.html`.

---

## Graph Building

Build `session_graph.json` from `arc.jsonl`:

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

IDs stable. Labels verbatim. 25 events → 5–12 nodes. Archive after compression.

---

## Lesson Generation

Fill `<plugin_root>/templates/lesson.md.tmpl`. YAML frontmatter first.
Foundations (first principles, `###` per prerequisite) → concept → two mermaid diagrams →
fix + snippet → quiz (3–5 visible Q&A) → optional resources.
Calibrate depth to `meta.json.notes`.
