---
description: Generate a concept map across all (or selected) lessons
argument-hint: [--last N] [--since YYYY-MM-DD] [--slugs slug1,slug2,...] [--tag keyword]
---

The user has invoked `/lesson-map`. Your job is to read a set of lessons, extract their concepts and relationships, and write a single `map.html` that visualizes how concepts across those lessons connect.

## Step 1 — Parse flags from `$ARGUMENTS`

Supported flags (all optional — if none given, include all lessons):

- `--last N` — include only the N most recent lessons (by `started_at`)
- `--since YYYY-MM-DD` — include only lessons started on or after this date
- `--slugs slug1,slug2,...` — include only the listed slugs (comma-separated, no spaces)
- `--tag keyword` — include only lessons whose goal or concept title contains `keyword` (case-insensitive)

Flags can be combined. Combined flags are ANDed (a lesson must satisfy all active filters).

If `$ARGUMENTS` is empty or only whitespace, include all lessons.

## Step 2 — Discover and filter lessons

1. List all `.md` files in `.claude/lessons/output/` (excluding `index.html` and `map.html`).
2. For each `<slug>.md`, read its YAML frontmatter to extract: `concept`, `date`, `goal`, `tags`. If frontmatter is missing, fall back to `.claude/lessons/sessions/<slug>/meta.json` for goal and date, and use the filename as the concept title.
3. Apply the parsed filters from Step 1 to produce the working set.
4. If the working set is empty after filtering, tell the user "No lessons match the given filters." and stop.
5. If only one lesson is in the working set, tell the user "A concept map needs at least two lessons. Add more sessions or broaden the filter." and stop.

## Step 3 — Extract concepts and relationships

For each lesson in the working set:

1. Extract concepts using two sources, in priority order:
   - **`session_graph.json`** (if it exists at `.claude/lessons/sessions/<slug>/session_graph.json`): read all `concept` type nodes. The node with `root_cause: true` is the primary concept; others are prerequisites. Also read the `tags` array from the graph's metadata or from the lesson frontmatter.
   - **Lesson `.md` file** (fallback or supplement): read the `concept` field from YAML frontmatter as the primary concept. Scan `### ` headings in the Foundations section as prerequisite concepts. Scan `**bold**` terms and `` `code` `` literals in the concept explanation as keywords.

   Prefer graph data when available — concept nodes have structured labels that are more reliable than parsed headings.

2. Build a flat list of all unique concepts across all lessons.

3. Identify relationships:
   - **Teaches**: lesson → its primary concept (directed)
   - **Requires**: primary concept → each of its foundation concepts (directed, meaning "this concept builds on")
   - **Shared foundation**: two lessons share the same foundation concept (undirected link between those lessons or concepts)
   - **Keyword overlap**: two primary concepts share significant technical keywords (indicates conceptual proximity — add a weak link)

Use your judgment to merge near-duplicate concept names (e.g., "Linux kernel" and "the Linux kernel" → "Linux kernel"). Keep the merged set lean — prefer fewer, well-named nodes over many nearly-identical ones.

## Step 4 — Build the mermaid graph

Produce a mermaid `graph LR` (left-to-right) diagram with:

- **Lesson nodes**: labeled with the slug date + short concept title (e.g., `20260416["Kernel Module\nVersion Matching"]`). Style: `fill:#e8f0fe,stroke:#4a80d4`.
- **Concept nodes**: foundation and shared concepts. Style: `fill:#fff,stroke:#999`.
- **Edges**:
  - Lesson → primary concept: solid arrow, labeled "teaches"
  - Primary concept → foundation concept: dashed arrow, labeled "requires"
  - Lesson ↔ lesson (shared foundation): dotted line, labeled with the shared concept name

Keep the graph readable. If there are more than 15 nodes, collapse small foundation clusters (concepts appearing in only one lesson and not shared) into a single "..." node per lesson to avoid clutter.

## Step 5 — Write map.html

Write `.claude/lessons/output/map.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Lesson Concept Map</title>
<script type="module">
import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';
mermaid.initialize({ startOnLoad: true, theme: 'neutral' });
</script>
<style>
  * { box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    max-width: 1100px;
    margin: 0 auto;
    padding: 2rem 1.5rem 5rem;
    color: #1a1a1a;
    background: #fff;
    line-height: 1.55;
  }
  h1 { font-size: 1.4rem; border-bottom: 3px solid #1a1a1a; padding-bottom: .4rem; margin-bottom: .25rem; }
  .subtitle { color: #aaa; font-size: .82rem; margin-bottom: 2rem; }
  .mermaid { margin: 2rem 0; }
  .legend { margin-top: 2rem; font-size: .85rem; color: #666; }
  .legend ul { padding-left: 1.25rem; }
  .legend li { margin: .3rem 0; }
  .lesson-list { margin-top: 2.5rem; }
  .lesson-list table { border-collapse: collapse; width: 100%; font-size: .88rem; }
  .lesson-list th { text-align: left; border-bottom: 2px solid #ddd; padding: .4rem .6rem; color: #555; }
  .lesson-list td { padding: .45rem .6rem; border-bottom: 1px solid #f0f0f0; }
  .lesson-list a { color: #0057b8; text-decoration: none; }
  .lesson-list a:hover { text-decoration: underline; }
  .footer-meta { color: #bbb; font-size: .8rem; text-align: center; margin-top: 3rem; }
</style>
</head>
<body>

<h1>Lesson Concept Map</h1>
<p class="subtitle"><!-- N --> lessons · <!-- filter description or "all lessons" --> · generated <!-- DATE --></p>

<div class="mermaid">
<!-- MERMAID GRAPH HERE -->
</div>

<div class="legend">
<strong>Legend</strong>
<ul>
<li>Blue boxes — lessons (click title to open)</li>
<li>White boxes — concepts (foundations and primaries)</li>
<li>Solid arrow — lesson teaches this concept</li>
<li>Dashed arrow — concept requires this foundation</li>
<li>Dotted line — shared foundation between lessons</li>
</ul>
</div>

<div class="lesson-list">
<h2 style="font-size:1rem;text-transform:uppercase;letter-spacing:.08em;color:#777;">Included Lessons</h2>
<table>
<tr><th>Date</th><th>Concept</th><th>Goal</th></tr>
<!-- one <tr> per lesson -->
<!-- <tr><td>YYYY-MM-DD</td><td><a href="slug.md">concept title</a></td><td>goal text</td></tr> -->
</table>
</div>

<p class="footer-meta">Generated by <code>/lesson-map</code></p>

</body>
</html>
```

Fill in all placeholders. The `<!-- filter description -->` should describe which filters were active, e.g. "last 5 lessons", "since 2026-01-01", "all lessons".

## Step 6 — Report

Print:
```
✓ /lesson-map written
  file:    .claude/lessons/output/map.html
  lessons: <N> included
  filters: <active filters, or "none">
  concepts: <total unique concept nodes>
```

## Notes

- This command is entirely read-only with respect to session state.
- Re-running overwrites the previous `map.html`.
- If a lesson HTML file can't be read (corrupted, partial write), skip it and note it in the report.
- The graph is meant to show intellectual connections, not a perfect taxonomy. Prefer signal over completeness — a readable graph with 10 well-chosen nodes beats an unreadable one with 40.
