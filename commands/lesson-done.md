---
description: Generate a textbook-quality lesson from the tracked /lesson session
---

The user has invoked `/lesson-done`. Your job is to turn the tracked session into a grounded, foundational markdown lesson. Follow every step exactly and in order.

---

## Step 1 — Load session state

1. Read `.claude/lessons/active-session`. If missing: tell the user "No active /lesson session — run /lesson first" and stop.
2. Let `<slug>` = contents of that file (trimmed).
3. Read in order:
   - `.claude/lessons/sessions/<slug>/meta.json` — goal, notes, cwd, token_tracking
   - `.claude/lessons/sessions/<slug>/session_graph.json` — primary session data (if it exists)
   - `.claude/lessons/sessions/<slug>/arc.jsonl` — events not yet compressed (last ~200 lines if long)
   - `.claude/lessons/sessions/<slug>/summary.md` — fallback only if no graph exists (older format)
4. Read `notes` from `meta.json`. Apply throughout: these guide depth, assumed knowledge level, and focus.

---

## Step 2 — Quality guard

Count total tracked events:
- `total_events_compressed` from `session_graph.json` (or 0 if no graph)
- Plus line count of `arc.jsonl`

**If the graph has 0 concept nodes AND 0 observation nodes AND total events < 5:**
Stop. Tell the user: "Session has too little data for a useful lesson — keep working and run /lesson-done when you've made more progress."

**If total events < `LESSON_MIN_EVENTS` (default: 8, env var configurable):**
Warn: "This session is short (<N> events). The lesson may be thin. Continue anyway? (Run /lesson-done again to confirm, or keep working.)"
Then stop and wait — do not proceed unless the user confirms by running `/lesson-done` again or explicitly says to continue.

---

## Step 3 — Analyze

If `session_graph.json` exists, the analysis is largely pre-computed. Read directly:

- **Root cause concept** — node at `root_cause_id`, or the concept node with `"root_cause": true`
- **Misconception** — hypothesis node with `"misconception": true`
- **Pivot moments** — observation nodes with `"pivotal": true`
- **Resolution** — node at `resolution_id`
- **Prerequisite concepts** — concept nodes connected to root cause via `involves` edges, plus any additional prerequisites you identify that are missing from the graph
- **Causal chain** — traverse edges from goal through attempts and observations to resolution

If the graph is missing or sparse (no concept/resolution nodes), fall back to analyzing `arc.jsonl` + `summary.md` directly: identify core problem, misconception, fundamental concept, and prerequisites manually.

Pick exactly one fundamental concept to teach. If the graph already names it via `root_cause_id`, use that. If ambiguous, pick the most upstream one.

**Also read `~/.claude/lessons/profile.json` (the global learner profile).**
- Check if the current root cause concept or misconception appears in `profile.misconceptions`
- If found with count ≥ 1: note this — the lesson will include a `{{RECURRING_NOTE}}` callout
- Check `profile.learned_concepts` for related past lessons to reference

---

## Step 4 — Decide whether to do web research

Ask explicitly: can this concept be explained accurately from general knowledge, or does it need external sources?

**Do web research when:**
- The concept involves specific version numbers, compatibility matrices, or release timing
- The concept is distribution-specific, tool-specific, or involves third-party library internals
- The concept is niche or sparsely documented in general knowledge
- The session graph contains specific error messages with likely community context
- The user's notes request citations

**Skip web research when:**
- The concept is a fundamental programming / OS / CS concept accurately explainable from general knowledge
- The concept is a core, stable language or standard library feature
- The session graph + general knowledge is sufficient and complete

If doing research:
1. `WebSearch` with a specific query including language, tool, version, platform
2. Pick 3–5 authoritative sources (official docs, well-known technical writing). Skip listicles.
3. `WebFetch` each. Extract 2–4 short quotes for inline citation.
4. Track total characters fetched — needed for token_tracking.
5. If no useful results found: report to the user and stop. Do not generate from memory alone when grounding is needed.

Record `web_fetch_chars` = total characters across all fetched pages.

---

## Step 5 — Load template

Read `${CLAUDE_PLUGIN_ROOT}/templates/lesson.md.tmpl`. If that env var is not set, look for it at `../../templates/lesson.md.tmpl` relative to this command file.

---

## Step 6 — Fill the lesson

Fill every `{{PLACEHOLDER}}` in the template. The YAML frontmatter `---` block must be the absolute first content in the output.

### `{{SLUG}}`, `{{DATE}}`, `{{GOAL}}`
From meta.json. DATE as YYYY-MM-DD.

### `{{CONCEPT_TITLE}}`
Short noun phrase naming the root cause concept. E.g., "Kernel Module / Userspace Version Coupling in Linux".

### `{{ROOT_CAUSE_LABEL}}`
The `label` of the root cause concept node, lowercased, no trailing period. Used in YAML frontmatter.

### `{{TAGS}}`
3–7 lowercase kebab-case tags derived from the concept nodes and topic. Comma-separated, no quotes. E.g.: `linux, kernel-module, nvidia, driver, dkms, version-matching`

### `{{RECURRING_NOTE}}`
- If the current misconception or concept **appeared in `profile.misconceptions` with count ≥ 1**:
  ```
  > **Pattern detected:** You've encountered a similar misconception before
  > (last seen: <last_seen>, session [`<slug>`](./<slug>.md)).
  > This lesson explains why it keeps appearing.
  ```
- If a related concept is in `profile.learned_concepts`:
  ```
  > **See also:** You have a prior lesson on a related concept —
  > [`<concept>`](./<slug>.md) (<date>).
  ```
- If neither applies: set `{{RECURRING_NOTE}}` to empty string `""`.

### `{{NARRATIVE_GOAL}}`
1–3 sentences. What the user was trying to do. No jargon.

### `{{NARRATIVE_BREAKDOWN}}` and `{{REAL_SNIPPET_OR_ERROR}}`
Where it broke. Pull the actual error from the first significant observation node (or arc.jsonl). Quote verbatim — never paraphrase error messages.

### `{{FOUNDATIONS}}`
Self-contained, bottom-up explanation of every prerequisite concept. Start from absolute first principles. Each prerequisite gets a `### heading` followed by 2–4 paragraphs. Build sequentially — simpler concepts first. Define every abbreviation before use. Calibrate depth to user's notes.

### `{{CONCEPT_EXPLANATION}}`
The core concept, explained after foundations are in place. Use terms already defined. Include inline citations if web research was done: `[source](URL)`. 3–6 paragraphs.

### `{{CONCEPT_DIAGRAM}}`
Raw mermaid syntax only (no fences — the template adds them). Choose the most appropriate diagram type: `sequenceDiagram`, `stateDiagram-v2`, `classDiagram`, or `flowchart TD/LR`. Use actual version numbers, file paths, or component names from the session graph.

### `{{MISCONCEPTION_CONNECTION}}`
Connect the misconception node's belief to the concept. Name the exact moment in the session (from `pivotal` observation nodes) where it was corrected.

### `{{DEBUG_PATH_DIAGRAM}}`
Raw mermaid `flowchart TD` syntax. Derive directly from graph edges — traverse from goal through attempts and observations to resolution. Annotate the misconception hypothesis node with ⚠. Use the actual node labels from the graph. This diagram should be recognizable to the user as their own session.

### `{{FIX_EXPLANATION}}`
The fix explained in terms of the concept. Why does it work mechanically, given what the foundations say?

### `{{FIX_SNIPPET}}`
The actual fix: commands, code, or config. Verbatim from the resolution node or session data.

### `{{QUIZ}}`
3–5 questions with immediately visible answers. Format:

```
**Q1: [question]**
[answer — 2–4 sentences, direct and complete]

**Q2: [question]**
[answer]
```

Questions should test understanding ("Why does..." "What would happen if..."), not memorization. At least one must reference the user's specific scenario.

### `{{RESOURCES_SECTION}}`
If web research was done:
```
## Resources

- [Title](URL) — one sentence on what this adds beyond the lesson
```
If no web research: empty string `""`.

---

## Step 7 — Compute token estimates and write to meta.json

Before writing the lesson, compute token tracking estimates. Read from `meta.json.token_tracking` what the hook and compression subagent already recorded, then add the remaining estimates:

```
web_fetch_chars     = total chars fetched in Step 4 (0 if no research)
lesson_output_chars = len(filled lesson markdown)

estimated_tokens:
  hook_logged          = arc_input_chars / 4
  compression_input    = (arc_input_chars + graph_output_chars * compression_cycles) / 4
  compression_output   = graph_output_chars / 4
  lesson_done_input    = (graph_output_chars + web_fetch_chars + template_chars) / 4
                         where template_chars ≈ len(template file)
  lesson_done_output   = lesson_output_chars / 4
  web_research         = web_fetch_chars / 4
  total                = sum of all above
```

Write the updated `token_tracking` back to `meta.json`.

---

## Step 8 — Write output, update profile, generate PDF

1. **Write lesson:** `.claude/lessons/output/<slug>.md`. YAML frontmatter `---` must be the absolute first content. Create `output/` if it doesn't exist.

2. **Generate PDF:** Run via Bash:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/render_pdf.py .claude/lessons/output/<slug>.md
   ```
   Print whatever the script outputs. If it fails or the env var is unset, skip silently — never let PDF failure block the lesson.

3. **Update learner profile** at `~/.claude/lessons/profile.json`:
   - Create the file if it doesn't exist (initialize with schema_version, empty arrays, total_sessions=0)
   - Append to `misconceptions`: the misconception node label, date, slug, project (cwd from meta.json). If the same concept already exists in the array, increment its `count` and update `last_seen` and `slug`.
   - Append to `learned_concepts`: the root cause concept label, date, slug. Skip if already present with same slug.
   - Increment `total_sessions` by 1
   - Update `aggregate_tokens.total_estimated` by adding `token_tracking.estimated_tokens.total`
   - Update `aggregate_tokens.sessions` by incrementing by 1

4. **Write `last-session`:** Write `<slug>` (no trailing newline) to `.claude/lessons/last-session`.

5. **Delete `active-session`.**

6. **Report** to the user:
   ```
   ✓ /lesson generated
     concept: <concept title>
     file:    .claude/lessons/output/<slug>.md
     tokens:  ~<total> estimated  (~$<cost> at Sonnet pricing)
   ```
   Cost = total_tokens × $0.000005 (blended $5/M rate). Format as `$0.09`.

If any step fails: do not leave a partial `.md` file. Clean up, report the failure plainly, leave `active-session` in place for retry. (The profile update and PDF are best-effort — failures there do not block the lesson.)

---

## Notes

- Do not ask clarifying questions. Use the session data and graph. State assumptions inline if ambiguous.
- Do not invoke `/lesson-done` recursively.
- If the user passed arguments to this command, treat them as generation notes overriding `meta.json` notes.
- Tone: direct, technical, textbook voice. No motivational filler. Past tense for session events, present tense for concept explanations.
