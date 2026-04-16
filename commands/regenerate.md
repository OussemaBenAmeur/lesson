---
description: Regenerate the most recent /lesson with optional new notes
argument-hint: [notes about what to change, add, or focus on]
---

The user has invoked `/regenerate`. Your job is to regenerate the most recent lesson from its session data, applying any new notes or direction from `$ARGUMENTS`. The session hook does not need to be active — this reads from the saved session files.

## Step 1 — Find the session

1. Try `.claude/lessons/last-session` first. If it exists, read the slug from it (trimmed).
2. If `last-session` does not exist, try `.claude/lessons/active-session` as a fallback.
3. If neither exists, tell the user: "No session found. Run `/lesson` to start one, or `/lesson-done` to generate from the current session." Stop.
4. Let `<slug>` = the slug found above.
5. Verify `.claude/lessons/sessions/<slug>/` exists. If not, tell the user the session directory is missing and stop.

## Step 2 — Load session state

Read in order:
- `.claude/lessons/sessions/<slug>/meta.json`
- `.claude/lessons/sessions/<slug>/session_graph.json` — primary session data (if it exists)
- `.claude/lessons/sessions/<slug>/arc.jsonl` — events not yet compressed into the graph
- `.claude/lessons/sessions/<slug>/summary.md` — fallback if no graph exists (older format)

Also note whether `.claude/lessons/output/<slug>.md` already exists — it will be overwritten.

## Step 3 — Determine effective notes

The user may be regenerating because:
- The lesson was too shallow or too deep
- The foundations section assumed too much or too little
- The quiz was off, the diagrams were unclear, or the fix was incomplete
- They want a different framing or focus

**Effective notes** = `$ARGUMENTS` if non-empty, otherwise fall back to the `notes` field from `meta.json`.

If `$ARGUMENTS` is non-empty, treat it as overriding the original notes. Common forms:
- `"explain even more from scratch, I don't know what a kernel is"` — increase foundations depth
- `"I already understand the basics, cut the foundations shorter"` — trim foundations
- `"the quiz was too easy, make it harder"` — revise quiz difficulty
- `"the fix section was unclear, expand it"` — expand fix with more explanation
- `"add more detail about why DKMS solves this permanently"` — specific focus request
- No argument — regenerate fresh with the original notes (useful if the first output was low quality)

Note what changed in your internal reasoning so you can report it to the user.

## Step 4 — Generate

Follow the exact same generation flow as `/lesson-done` Steps 2–5 (Analyze, Decide web research, Load template, Fill lesson), but:
- Use the effective notes from Step 3 instead of raw meta.json notes
- Apply any specific changes the user asked for in `$ARGUMENTS`
- For web research: re-run it only if the original lesson included sources OR if the user's notes ask for it. If the original lesson had no sources and the user didn't ask for them, skip web research.

## Step 5 — Write output

1. Write the regenerated markdown to `.claude/lessons/output/<slug>.md` (overwriting the existing file). YAML frontmatter `---` block must be the absolute first content.
2. Do NOT modify `last-session` or `active-session`.
3. Print to the user:
   ```
   ✓ /lesson regenerated
     concept: <concept name>
     file:    .claude/lessons/output/<slug>.md
     changes: <1–2 sentences on what you changed vs. the original>
   ```

If generation fails: do not leave a partial file. Report the failure. The previous version is already overwritten at this point, so tell the user they can run `/regenerate` again.

## Notes

- Do not ask clarifying questions. Apply the notes, make judgment calls, state assumptions inline in the lesson text.
- If `$ARGUMENTS` is ambiguous (e.g., just "make it better"), interpret it as: go deeper on foundations, tighten the concept explanation, improve quiz question quality.
- The session data is fixed — you are only changing how it is interpreted and presented.
