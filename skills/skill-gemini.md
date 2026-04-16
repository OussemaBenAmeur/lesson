# /lesson — Gemini CLI Skill

You are equipped with a learning session tracker. When the user invokes `/lesson`, `/lesson-done`,
`/regenerate`, `/lesson resume`, `/lesson-profile`, `/lesson-index`, or `/lesson-map`,
follow the instructions below exactly.

---

## Session Tracking

Gemini CLI supports a BeforeTool hook (`~/.gemini/settings.json`). When the hook is configured
(see install instructions), it pre-checks the session and logs events via `hooks/post_tool_use.py`.

**If the hook is NOT configured**, fall back to manual logging:
After every significant tool call, append one line to `.claude/lessons/sessions/<slug>/arc.jsonl`:
```json
{"ts": <unix_timestamp>, "tool": "<ToolName>", "args": "<brief args, max 200 chars>", "result_head": "<first 400 chars>", "is_error": <true|false>, "significant": <true|false>}
```

Mark `significant: true` when: error returned, file edited/written, error keywords in Bash output,
or result changed your understanding of the problem.

**Gemini parallel subagents:** Gemini supports running subagents. At 25 events, you may spawn
a compression subagent (type `lesson-compress`) if the platform supports it; otherwise build
the graph inline.

---

## Commands

### `/lesson [notes]`

1. Generate slug: `YYYYMMDD-HHMMSS` (UTC). Append keyword from notes if non-empty.
2. Create `.claude/lessons/sessions/<slug>/` with:
   - `meta.json`: `{"slug":"<slug>","goal":"<notes>","notes":"<notes>","started_at":"<ISO8601>","cwd":"<abs_path>","platform":"gemini"}`
   - `arc.jsonl`: empty
   - `counter`: `0`
3. Write slug to `.claude/lessons/active-session`
4. Confirm: `✓ /lesson tracking active  session: <slug>  goal: <notes or "(none)">`

If `active-session` already exists, ask before overwriting.

### `/lesson-done`

1. Read `active-session` → slug.
2. Load `meta.json`, `session_graph.json`, `arc.jsonl`.
3. Quality guard: warn if total events < 8; stop if < 5 events AND no concept/observation nodes.
4. Build or extend `session_graph.json` from remaining `arc.jsonl` events.
5. Read `~/.claude/lessons/profile.json` for recurring misconceptions.
6. Decide on web research (skip for stable CS/OS/language concepts).
7. Generate lesson from `<plugin_root>/templates/lesson.md.tmpl`.
8. Write to `.claude/lessons/output/<slug>.md`.
9. Run: `python3 <plugin_root>/scripts/render_pdf.py .claude/lessons/output/<slug>.md`
10. Update `~/.claude/lessons/profile.json`.
11. Write `last-session`, delete `active-session`.
12. Report: `✓ /lesson generated  file: .claude/lessons/output/<slug>.md`

### `/lesson resume`

Read `last-session` → write slug to `active-session`. Resume tracking (manual if no hook).

### `/regenerate [notes]`

Read `last-session`, reload session data, apply notes, re-generate `<slug>.md`, run `render_pdf.py`.

### `/lesson-profile`

Display `~/.claude/lessons/profile.json`: misconceptions, concepts, token estimates.

### `/lesson-index`

Scan `.claude/lessons/output/*.md`, write `index.html`.

### `/lesson-map [--last N] [--since DATE] [--tag KEYWORD]`

Build concept map from session graphs, write `map.html`.

---

## Graph Building (Inline)

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

IDs stable (never renumber). Labels verbatim. 25 events → 5–12 nodes.
Archive `arc.jsonl` → `arc.jsonl.archive.N` after compression.

---

## Install Hook (Optional)

To enable automatic event tracking, add to `~/.gemini/settings.json`:
```json
{
  "hooks": {
    "beforeTool": "python3 <plugin_root>/hooks/post_tool_use.py"
  }
}
```

---

## Lesson Generation

Fill `<plugin_root>/templates/lesson.md.tmpl`. YAML frontmatter first. Cover:
foundations (first principles), concept explanation, two mermaid diagrams, fix + snippet,
quiz (3–5 visible Q&A), optional resources. Calibrate depth to `meta.json.notes`.
