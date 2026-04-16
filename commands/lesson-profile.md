---
description: Display your learner profile — misconceptions, concepts learned, and token usage
---

The user has invoked `/lesson-profile`. Read `~/.claude/lessons/profile.json` and print a readable summary. Do not modify any files.

## Step 1 — Load profile

Read `~/.claude/lessons/profile.json`.

If the file does not exist: print the following and stop.
```
No learner profile yet. Run /lesson-done to generate your first lesson — the profile is built automatically.
```

## Step 2 — Print summary

Print exactly in this shape (adapt counts and rows to actual data):

```
Learning profile — <total_sessions> session(s) across all projects

Recurring misconceptions (appeared more than once):
  — <concept>    ×<count>    last: <last_seen>
  (none yet)

All misconceptions encountered (<N> total):
  — <concept>    <last_seen>    <project short name>
  ...

Concepts learned (<N> total):
  — <concept>    <date>
  ...

Token usage (estimated ±20%):
  All sessions:  <total_estimated> tokens  (~$<cost> at Sonnet 4 pricing)
  Sessions:      <sessions>
  Avg/session:   <avg> tokens
```

**Pricing note:** Use $3 per million input tokens + $15 per million output tokens for Sonnet 4. For the estimate here, use a blended rate of ~$5 per million tokens (since the plugin's calls are mostly input-heavy). Format as `$0.09` not `$0.094`.

**Formatting rules:**
- Sort misconceptions by count descending, then by last_seen descending
- Sort concepts learned by date descending (most recent first)
- Truncate concept labels to 60 chars if longer
- If total_sessions is 0, show "(none yet)" for all sections
- If a section has more than 10 entries, show the top 10 and print `  ... and <N> more`

## Step 3 — Show last session token detail (if available)

Find the slug in `~/.claude/lessons/last-session` (or `.claude/lessons/last-session` in cwd). Read the corresponding `sessions/<slug>/meta.json`. If it has a `token_tracking` field, print:

```
Last session (<slug>):
  arc logged:        <arc_input_chars> chars  (~<tokens> tokens)
  compression:       <compression_cycles> cycle(s)
  web research:      <web_fetch_chars> chars  (~<tokens> tokens)  [or "none"]
  lesson output:     <lesson_output_chars> chars  (~<tokens> tokens)
  ─────────────────────────────────────────────────
  estimated total:   <total> tokens  (~$<cost>)
```

If `token_tracking` is missing or empty, skip this section silently.

## Notes

- This command is entirely read-only.
- Costs shown are estimates, not billing data. Do not present them as exact.
- If the profile exists but is malformed JSON, print: "Profile file at ~/.claude/lessons/profile.json appears corrupted. You can delete it — it will be rebuilt after the next /lesson-done."
