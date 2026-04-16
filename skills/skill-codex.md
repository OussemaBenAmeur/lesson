# /lesson — Codex Skill

You are equipped with a learning session tracker. When the user invokes a lesson command
(prefix: `$` for Codex, e.g. `$lesson`, `$lesson-done`), follow the instructions below exactly.

---

## Session Tracking (Manual — No Hooks)

Codex does not support PostToolUse hooks. You must log events yourself.

**After every significant tool call**, append one line to `.claude/lessons/sessions/<slug>/arc.jsonl`:
```json
{"ts": <unix_timestamp>, "tool": "<ToolName>", "args": "<brief args summary, max 200 chars>", "result_head": "<first 400 chars of result>", "is_error": <true|false>, "significant": <true|false>}
```

Mark `significant: true` when:
- The tool returned an error or non-zero exit
- You edited or wrote a file (`Edit`, `Write`)
- A Bash result contained error keywords or version strings
- The result changed your understanding of the problem

Do not log every read — only log when something meaningful was discovered or changed.

**Graph compression:** When `arc.jsonl` reaches 25 lines, build the graph yourself inline
(see "Graph Building" section below) rather than spawning a subagent.

---

## Commands

### `$lesson [notes]`

Start a tracked learning session.

1. Generate slug: `YYYYMMDD-HHMMSS` (UTC). Append a keyword from notes if non-empty.
2. Create `.claude/lessons/sessions/<slug>/` with:
   - `meta.json`: `{"slug":"<slug>","goal":"<notes>","notes":"<notes>","started_at":"<ISO8601>","cwd":"<abs_path>"}`
   - `arc.jsonl`: empty
   - `counter`: `0`
3. Write slug to `.claude/lessons/active-session`
4. Confirm: `✓ /lesson tracking active  session: <slug>  goal: <notes or "(none)">`
5. **Begin manually logging events** to `arc.jsonl` after each significant action.

If `active-session` already exists, ask before overwriting.

### `$lesson-done`

Generate a lesson from the tracked session.

1. Read `active-session` → slug. If missing, stop.
2. Read `meta.json`, `session_graph.json` (if exists), `arc.jsonl`.
3. **Quality guard:** If total events (graph `total_events_compressed` + `arc.jsonl` lines) < 8,
   warn user and wait for confirmation before continuing. If 0 concept+observation nodes AND < 5 events, stop.
4. **Build graph inline** (see "Graph Building" below) from remaining `arc.jsonl` events.
5. Read `~/.claude/lessons/profile.json` for recurring misconception detection.
6. Decide whether web research is needed (skip for well-known CS/OS concepts).
7. Generate lesson using the template at `<plugin_root>/templates/lesson.md.tmpl`.
8. Write to `.claude/lessons/output/<slug>.md`.
9. Run PDF generation: `python3 <plugin_root>/scripts/render_pdf.py .claude/lessons/output/<slug>.md`
10. Update `~/.claude/lessons/profile.json` (misconceptions, learned_concepts, token counts).
11. Write `last-session`, delete `active-session`.
12. Report: `✓ /lesson generated  concept: <title>  file: .claude/lessons/output/<slug>.md`

### `$lesson resume`

Resume the last session.

1. Read `last-session` → slug.
2. Check for conflicting `active-session`. If present and different slug, ask before overwriting.
3. Write slug back to `active-session`.
4. Report: `✓ Session <slug> resumed — tracking active again.`

### `$regenerate [notes]`

Regenerate the most recent lesson with optional new direction.

1. Read `last-session` → slug. If missing, try `active-session`.
2. Load `session_graph.json`, `arc.jsonl`, `meta.json`.
3. Use `notes` arg (if given) as generation notes; otherwise fall back to `meta.json.notes`.
4. Re-generate lesson and overwrite `.claude/lessons/output/<slug>.md`.
5. Run `render_pdf.py` again.
6. Report: `✓ /lesson regenerated  concept: <title>  changes: <1-2 sentences>`

### `$lesson-profile`

Show learning profile from `~/.claude/lessons/profile.json`. Display:
- Recurring misconceptions (sorted by count desc)
- Concepts learned (sorted by date desc, last 10)
- Token usage (estimated, from aggregate_tokens)

### `$lesson-index`

Scan `.claude/lessons/output/*.md`, read YAML frontmatter, write `index.html` listing all lessons.

### `$lesson-map [--last N] [--since DATE] [--tag KEYWORD]`

Generate a concept map from lesson session graphs. Write `map.html` with a mermaid diagram.

---

## Graph Building

When compressing `arc.jsonl` into `session_graph.json` (either at threshold or at lesson-done):

**Schema:**
```json
{
  "schema_version": "1",
  "slug": "<slug>",
  "goal": "<goal>",
  "total_events_compressed": 0,
  "root_cause_id": null,
  "resolution_id": null,
  "nodes": [{"id": "g1", "type": "goal", "label": "<goal>"}],
  "edges": []
}
```

Node types: `goal`, `observation` (errors/findings), `hypothesis` (assumptions), `attempt` (deliberate actions),
`concept` (technical concepts), `resolution` (what worked)

Node flags: `pivotal: true` (key turning point), `misconception: true` (wrong assumption), `root_cause: true`

Edge types: `motivated`, `produced`, `revealed`, `contradicted`, `seemed_to_confirm`,
`assumed_about`, `involves`, `enabled`, `achieves`

**Rules:**
- Node IDs: type-initial + integer (`g1`, `o1`, `h1`, `a1`, `c1`, `r1`). Never renumber.
- Labels: verbatim from actual output. Quote error messages exactly.
- 25 events → roughly 5–12 new nodes. Most events are noise.
- Set `root_cause_id` when a concept with `root_cause: true` is identified.
- Set `resolution_id` when a resolution node is added.
- Archive consumed events: rename `arc.jsonl` → `arc.jsonl.archive.N`, reset to empty.

---

## Lesson Template

Generate lessons using `<plugin_root>/templates/lesson.md.tmpl`. Fill all `{{PLACEHOLDER}}`s:
- YAML frontmatter first (slug, concept, date, goal, root_cause, tags)
- Foundations: bottom-up, first principles, every prerequisite with `###` heading
- Core concept explanation (3–6 paragraphs)
- Two mermaid diagrams: concept diagram + debug path flowchart
- Fix explanation + verbatim fix snippet
- Quiz: 3–5 Q&A pairs (no HTML, answers visible immediately)
- Resources section if web research was done

Calibrate depth to `meta.json.notes`. Explain everything from scratch unless notes say otherwise.
