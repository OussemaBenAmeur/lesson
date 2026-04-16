# /lesson — OpenCode Skill

You are equipped with a learning session tracker. When the user invokes `/lesson`, `/lesson-done`,
`/regenerate`, `/lesson resume`, `/lesson-profile`, `/lesson-index`, or `/lesson-map`,
follow the instructions below exactly.

---

## Session Tracking (Manual — No Hooks)

OpenCode does not support PostToolUse hooks. Log events yourself after each significant action.

Append to `.claude/lessons/sessions/<slug>/arc.jsonl`:
```json
{"ts": <unix_timestamp>, "tool": "<ToolName>", "args": "<brief args, max 200 chars>", "result_head": "<first 400 chars>", "is_error": <true|false>, "significant": <true|false>}
```

Mark `significant: true` when: error returned, file edited/written, error keywords found, or result
changed your understanding. At 25 events, build the graph inline (see "Graph Building").

---

## Commands

### `/lesson [notes]`

1. Slug: `YYYYMMDD-HHMMSS` (UTC). Append keyword from notes if non-empty.
2. Create `.claude/lessons/sessions/<slug>/` with `meta.json` (include `"platform":"opencode"`),
   empty `arc.jsonl`, `counter` = `0`.
3. Write slug to `.claude/lessons/active-session`. Confirm. Begin logging.

### `/lesson-done`

Load session. Quality guard (warn < 8 events, stop < 5 AND no nodes). Build graph inline.
Read profile. Decide web research. Generate from template. Write `output/<slug>.md`.
Run `render_pdf.py`. Update profile. Write `last-session`. Delete `active-session`.

### `/lesson resume`

Read `last-session` → write to `active-session`. Resume logging.

### `/regenerate [notes]`

Read `last-session`, re-generate with notes, overwrite `.md`, run PDF.

### `/lesson-profile`

Show `~/.claude/lessons/profile.json`.

### `/lesson-index` / `/lesson-map [flags]`

Build `index.html` / concept `map.html` from output lessons.

---

## Graph Building

```json
{
  "schema_version": "1", "slug": "<slug>", "goal": "<goal>",
  "total_events_compressed": 0, "root_cause_id": null, "resolution_id": null,
  "nodes": [{"id": "g1", "type": "goal", "label": "<goal>"}],
  "edges": []
}
```

Node types: `goal`, `observation`, `hypothesis`, `attempt`, `concept`, `resolution`
Edge types: `motivated`, `produced`, `revealed`, `contradicted`, `seemed_to_confirm`,
`assumed_about`, `involves`, `enabled`, `achieves`
IDs stable. Labels verbatim. 25 events → 5–12 nodes. Archive after compression.

---

## Lesson Generation

Fill `<plugin_root>/templates/lesson.md.tmpl`. YAML frontmatter first.
Foundations → concept → two mermaid diagrams → fix → quiz (3–5 visible Q&A) → resources.
Calibrate depth to `meta.json.notes`. Explain from first principles unless notes say otherwise.
