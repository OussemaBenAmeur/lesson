---
description: Generate a textbook-quality lesson from the tracked /lesson session
---

The user has invoked `/lesson-done`. Your job is to turn the tracked session into a single markdown lesson grounded in their actual code, errors, and attempts. Follow every step. Do not skip research. Do not generate a lesson from memory alone.

## Step 1 — Load session state

1. Read `.claude/lessons/active-session`. If it does not exist, tell the user "No active /lesson session — run /lesson first" and stop.
2. Let `<slug>` = contents of that file (trimmed).
3. Read, in order:
   - `.claude/lessons/sessions/<slug>/meta.json` — goal, start time, cwd
   - `.claude/lessons/sessions/<slug>/summary.md` — compressed running summary (may be empty if no compression has happened yet)
   - `.claude/lessons/sessions/<slug>/arc.jsonl` — raw events since last compression. If very long, read the last ~500 lines only; the rest is already in summary.md.
   - Optionally, list `.claude/lessons/sessions/<slug>/arc.jsonl.archive*` and peek at them only if you need older context that's missing from summary.md.

## Step 2 — Analyze the arc

Before touching the web, decide three things. Write them down in your working memory — you do not have to show the user.

- **Core problem** — what was the user actually trying to do? Not the surface symptom; the real goal.
- **Underlying misconception** — what mental model was wrong or missing? Be specific: "thought async functions suspend on CPU work" is good; "didn't understand async" is useless.
- **Fundamental concept** — the *one* concept that, taught cleanly, collapses the whole problem. This is the subject of the lesson.

Pick exactly one fundamental concept. If you're tempted to teach two, pick the more upstream one. The other can go in "further reading."

## Step 3 — Research the concept

1. Use `WebSearch` with a deliberate query — include the language, framework, library, or domain. Not "async" — "python asyncio event loop blocking cpu bound".
2. Scan results. Pick **3–5** authoritative sources. Prioritize:
   - Official documentation (language, framework, standard)
   - Well-known technical writing (authors, blogs with track records)
   - Seminal papers or standards documents
   Skip listicles, SEO blogspam, and outdated tutorials.
3. Use `WebFetch` on each chosen source. Extract 2–4 short quotes that will appear in the lesson as direct citations.
4. If `WebSearch` returns nothing useful, report that to the user and stop — do **not** write a lesson from memory alone. The grounding is the point.

## Step 4 — Load the template

Read `${CLAUDE_PLUGIN_ROOT}/templates/lesson.md.tmpl`. If that env var is not set, look for the template at `../../templates/lesson.md.tmpl` relative to this command file. This is the scaffold you will fill in.

## Step 5 — Fill the lesson

Produce the finished markdown by filling the template. Rules:

- **Grounding over abstraction.** Every section that can reference the session's actual content should. Pull real file paths, real error messages, real code snippets from `arc.jsonl` / `summary.md`. Quote them verbatim in code fences. Show the user their own work reflected back.
- **Concept explanation, cited.** In the "The concept" section, explain it in plain language, then back each non-trivial claim with an inline link to one of your fetched sources (`[MDN](https://…)`). A lesson without citations is not grounded.
- **Two mermaid diagrams, mandatory.**
  - **Concept diagram.** Textbook-style illustration of the concept: states, transitions, relationships. Use whichever mermaid diagram type fits (flowchart, sequenceDiagram, stateDiagram, classDiagram). Do not default to a boring flowchart if another type is clearer.
  - **Debug path diagram.** A flowchart of the user's actual debugging arc: nodes are attempts/hypotheses, edges are transitions, annotate the node where the misconception led them astray. This diagram is only interesting if it's specific.
- **Closing exercise.** One concrete task grounded in the user's own code. Not a generic textbook exercise. It should require applying the concept correctly and producing something they can verify.
- **Curated resources.** 3–5 bullet points, one line each, linking the sources you fetched. Order by priority, best first.

Keep tone direct and technical. No motivational filler. No "in conclusion" paragraphs. Textbook voice, not blog voice.

## Step 6 — Write and clean up

1. Write the finished lesson to `.claude/lessons/output/<slug>.md`. Create the `output/` directory if it does not exist.
2. Delete `.claude/lessons/active-session`. The session is done; future tool calls should not be tracked against this slug.
3. Print to the user, exactly in this shape:
   ```
   ✓ /lesson generated
     concept: <one-line name of the fundamental concept>
     file:    .claude/lessons/output/<slug>.md
   ```
4. If any step fails partway (e.g., you cannot fetch enough sources), do **not** leave a half-written file in `output/`. Clean up, report the failure plainly, and leave `active-session` in place so the user can retry.

## Notes

- Do not ask the user clarifying questions during this flow. You have the session data; use it. If something is genuinely ambiguous, make a call and state your assumption inline in the lesson.
- Do not invoke `/lesson-done` recursively. One shot.
- If the user passed arguments (unusual for this command), treat them as hints about which concept to focus on — override your own analysis only if their hint is clearly more upstream than what you picked.
