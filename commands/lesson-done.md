---
description: Generate a textbook-quality lesson from the tracked /lesson session
---

The user has invoked `/lesson-done`. Your job is to turn the tracked session into a markdown lesson grounded in their actual debugging session. Follow every step exactly.

## Step 1 — Load session state

1. Read `.claude/lessons/active-session`. If it does not exist, tell the user "No active /lesson session — run /lesson first" and stop.
2. Let `<slug>` = contents of that file (trimmed).
3. Read `.claude/lessons/sessions/<slug>/meta.json` — goal, notes, cwd.
4. **Primary input — the session graph:**
   Read `.claude/lessons/sessions/<slug>/session_graph.json` if it exists.
   If it does not exist (session was too short to trigger compression, or first generation before the new format), fall back to reading `summary.md` and `arc.jsonl` directly and skip the graph-based analysis in Step 2.
5. Also read the tail of `arc.jsonl` (last ~200 lines) — these are events since the last compression that are not yet in the graph. You will need to incorporate them.

---

## Step 2 — Analyze (graph-assisted)

If `session_graph.json` exists, most of the analysis is already done. Read the graph and extract:

- **Root cause concept** — the node where `root_cause: true`, or `nodes[root_cause_id]`. This is the fundamental concept the lesson teaches.
- **Misconception** — the hypothesis node where `misconception: true`. This is what the user believed wrongly.
- **Pivot moments** — observation nodes where `pivotal: true`. These are the key turning points.
- **Resolution** — the node at `resolution_id`. This is what fixed it.
- **Prerequisite concepts** — concept nodes connected to the root cause via `involves` edges. These become the Foundations section. Also think beyond the graph: what does a user need to know before the root cause concept makes sense? Add any missing prerequisites.
- **Causal chain** — traverse edges from `g1` through attempts and observations to the resolution. This becomes the debug path diagram.

If the graph is sparse or missing, derive the above from `summary.md` + `arc.jsonl` the same way as the previous version of this command: identify core problem, misconception, fundamental concept, and prerequisites manually.

Also read `notes` from `meta.json`. These guide generation depth and style (e.g., "explain from scratch", "I know Linux basics"). Apply throughout.

Pick exactly one fundamental concept to teach. If tempted to pick two, pick the more upstream one.

---

## Step 3 — Decide whether to do web research

Ask explicitly: **can this concept be explained accurately from general knowledge, or does it require external sources?**

**Do web research when:**
- The concept involves specific version numbers, compatibility matrices, or release timing
- The concept is distribution-specific, tool-specific, or involves third-party library internals
- The concept is niche or not fully covered by general knowledge
- The session graph contains error messages that likely have documented community context
- The user's notes request citations or external references

**Skip web research when:**
- The concept is a fundamental programming, OS, or CS concept explainable accurately from general knowledge
- The concept is a core, stable language or standard library feature
- The graph + general knowledge is sufficient to explain it correctly and completely

If doing research:
1. `WebSearch` with a specific query — include language, tool, version, platform where relevant
2. Pick 3–5 authoritative sources (official docs, well-known technical writing). Skip listicles.
3. `WebFetch` each. Extract 2–4 short quotes for inline citation.
4. If no useful results: report to user and stop. Do not write a lesson from memory alone when grounding is needed.

---

## Step 4 — Load the template

Read `${CLAUDE_PLUGIN_ROOT}/templates/lesson.md.tmpl`. If that env var is not set, look for it at `../../templates/lesson.md.tmpl` relative to this command file.

---

## Step 5 — Fill the lesson

Fill every `{{PLACEHOLDER}}` in the template. The YAML frontmatter `---` block must be the very first content in the output file.

### `{{SLUG}}`, `{{DATE}}`, `{{GOAL}}`
From meta.json. DATE formatted as YYYY-MM-DD.

### `{{CONCEPT_TITLE}}`
Short noun phrase naming the root cause concept. E.g., "Kernel Module / Userspace Version Coupling in Linux".

### `{{ROOT_CAUSE_LABEL}}`
The `label` field of the root cause concept node. One sentence, lowercase, no trailing period. Used in YAML frontmatter.

### `{{TAGS}}`
3–7 lowercase kebab-case tags derived from the concept nodes in the graph (and the overall topic). Comma-separated, no quotes. E.g.: `linux, kernel-module, nvidia, driver, dkms, version-matching`

### `{{NARRATIVE_GOAL}}`
1–3 sentences. What the user was trying to accomplish. No jargon yet.

### `{{NARRATIVE_BREAKDOWN}}` and `{{REAL_SNIPPET_OR_ERROR}}`
Where it broke. Pull the actual error output from the first significant `observation` node in the graph (or from arc.jsonl if no graph). Quote verbatim — do not paraphrase error messages.

### `{{FOUNDATIONS}}`

This is the most important section. Write a self-contained, bottom-up explanation of every prerequisite concept identified in Step 2. Rules:

- **Start from first principles.** Every concept the user needs to understand the lesson gets its own section, starting from the simplest. If the root cause concept is "kernel module version coupling", prerequisites include: what is the Linux kernel, what is a kernel module, what is userspace vs kernelspace, what is ABI, what does "loading" a module mean. Do not skip rungs.
- Format each as a level-3 heading followed by 2–4 paragraphs:
  ```
  ### What the Linux kernel is

  The kernel is the core program...

  ### Kernel modules (.ko files)

  A kernel module is a compiled binary...
  ```
- Build up sequentially — simpler, more general first. Each section may reference terms defined above it.
- Define every abbreviation before using it.
- Be concrete. Use analogies. Quote actual commands or paths from the session where they illustrate a point.
- Calibrate depth to the user's notes. "Explain from absolute scratch" → more sections, deeper. "I know Linux basics" → trim the obvious ones.

### `{{CONCEPT_EXPLANATION}}`
The core concept, explained now that the foundations are in place. Use terms defined above freely. Include inline citations if web research was done: `[source name](URL)`. 3–6 paragraphs. Specific and technical — no hand-waving.

### `{{CONCEPT_DIAGRAM}}`
A mermaid diagram illustrating the concept structure. Write only raw mermaid syntax — no code fences (the template wraps it). Choose the most appropriate type:
- `sequenceDiagram` for protocols or call sequences
- `stateDiagram-v2` for state machines
- `classDiagram` for component relationships
- `flowchart TD/LR` for data or control flow (use only when others don't fit better)

Annotate with actual version numbers, file paths, or component names from the session graph where possible.

### `{{MISCONCEPTION_CONNECTION}}`
Connect the user's specific wrong belief (from the `misconception: true` hypothesis node) to the concept. Name the exact moment in the session where that belief led them astray. Reference the `pivotal` observation nodes that corrected it.

### `{{DEBUG_PATH_DIAGRAM}}`
A `flowchart TD` mermaid diagram of the user's actual debugging arc. Derive this directly from the graph: traverse from the goal node through attempts and observations to the resolution. Each node in the diagram maps to a graph node. Annotate the `misconception` hypothesis node with ⚠. This diagram should be recognizable to the user as their own session — generic paths are useless.

### `{{FIX_EXPLANATION}}`
The fix explained in terms of the concept. Why does this work, given what the concept says? Connect back to the foundations. Not just "run this command" — explain the mechanism.

### `{{FIX_SNIPPET}}`
The actual fix: commands, code, or config. Verbatim from the resolution node or session data.

### `{{QUIZ}}`
3–5 questions that test genuine understanding. Answers immediately follow each question — visible, not hidden. Format:

```
**Q1: What does `lsmod` tell you that `ls /lib/modules/` does not?**
Whether the module is actually loaded into the running kernel. Files on disk are inert until loaded — presence in `/lib/modules/` means the binary is there, not that the kernel is using it.

**Q2: Why can a .ko file exist for kernel 6.17 but fail to load on kernel 6.17?**
...
```

Design rules:
- "What would happen if..." and "Why does..." are better than "What is the name of..."
- At least one question should reference the user's specific session scenario
- Answers must be self-contained — 2–4 sentences, complete and correct
- Do not test memorization of command names

### `{{RESOURCES_SECTION}}`
If web research was done:
```
## Resources

- [Title](URL) — one sentence on what this adds beyond the lesson
- [Title](URL) — ...
```

If no web research: empty string `""` (the section is omitted entirely).

---

## Step 6 — Write output and clean up

1. Write the filled markdown to `.claude/lessons/output/<slug>.md`. The YAML frontmatter `---` block must be the absolute first content — nothing before it.
   Create the `output/` directory if it doesn't exist.
2. Write `<slug>` (no trailing newline) to `.claude/lessons/last-session`. This lets `/regenerate` and `/lesson resume` find the session after `active-session` is deleted.
3. Delete `.claude/lessons/active-session`.
4. Print to the user:
   ```
   ✓ /lesson generated
     concept: <concept title>
     file:    .claude/lessons/output/<slug>.md
   ```

If any step fails: do not leave a partial file in `output/`. Clean up, report the failure, leave `active-session` in place for retry.

---

## Notes

- Do not ask clarifying questions. Use the session data and graph. State assumptions inline if ambiguous.
- Do not invoke `/lesson-done` recursively.
- If the user passed arguments to this command, treat them as generation notes overriding meta.json notes.
- Tone throughout: direct, technical, textbook voice. No motivational filler. Past tense for session events. Present tense for concept explanations.
