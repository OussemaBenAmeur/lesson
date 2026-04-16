---
description: Generate an index of all lessons in .claude/lessons/output/
---

The user has invoked `/lesson-index`. Your job is to scan all generated lessons and write a single `index.html` that lists them in reverse-chronological order.

## Step 1 — Find all lessons

1. List all `.md` files in `.claude/lessons/output/` (excluding `index.html` and `map.html`). If the directory doesn't exist or is empty, tell the user "No lessons found — run /lesson-done to generate your first lesson." and stop.
2. For each `<slug>.md` found, read its YAML frontmatter (the block between the opening `---` and closing `---`). Extract:
   - `slug`
   - `concept` — the concept title
   - `date` — YYYY-MM-DD
   - `goal` — the session goal
   - `tags` — list of tags
   If frontmatter is missing or malformed, fall back to reading `.claude/lessons/sessions/<slug>/meta.json` for goal and date.

3. Sort all entries by `date` descending (most recent first).

## Step 2 — Write index.html

Write `.claude/lessons/output/index.html` with this structure:

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Lesson Index</title>
<style>
  * { box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    max-width: 760px;
    margin: 0 auto;
    padding: 2.5rem 1.5rem 5rem;
    color: #1a1a1a;
    background: #fff;
    line-height: 1.55;
  }
  h1 { font-size: 1.4rem; border-bottom: 3px solid #1a1a1a; padding-bottom: .4rem; margin-bottom: .25rem; }
  .subtitle { color: #aaa; font-size: .82rem; margin-bottom: 2rem; }
  .lesson-list { list-style: none; padding: 0; margin: 0; }
  .lesson-list li {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    padding: .9rem 0;
    border-bottom: 1px solid #f0f0f0;
    gap: 1rem;
  }
  .lesson-list li:last-child { border-bottom: none; }
  .lesson-title { font-weight: 600; }
  .lesson-title a { color: #1a1a1a; text-decoration: none; }
  .lesson-title a:hover { color: #0057b8; }
  .lesson-goal { font-size: .88rem; color: #666; margin-top: .15rem; }
  .lesson-tags { font-size: .78rem; color: #bbb; margin-top: .1rem; }
  .lesson-meta { font-size: .8rem; color: #bbb; white-space: nowrap; flex-shrink: 0; }
  .empty { color: #999; font-style: italic; }
</style>
</head>
<body>
<h1>Lessons</h1>
<p class="subtitle"><!-- N --> lessons · last updated <!-- DATE --></p>
<ul class="lesson-list">
<!-- one <li> per lesson, see format below -->
</ul>
</body>
</html>
```

Each lesson entry:
```html
<li>
  <div>
    <div class="lesson-title"><a href="<slug>.md"><concept title></a></div>
    <div class="lesson-goal"><goal text, or "(no goal)" if empty></div>
    <div class="lesson-tags"><tags as #tag #tag format, or empty></div>
  </div>
  <div class="lesson-meta"><date, YYYY-MM-DD></div>
</li>
```

Fill in the `<!-- N -->` count and `<!-- DATE -->` (today's date) in the subtitle.

## Step 3 — Report

Print:
```
✓ /lesson-index written
  file:    .claude/lessons/output/index.html
  lessons: <N>
```

## Notes

- This command is read-only with respect to sessions — it never modifies `active-session`, `last-session`, or any session directory.
- If a lesson `.html` file exists but the corresponding session directory does not, still include it in the index using whatever can be parsed from the HTML.
- Re-running `/lesson-index` overwrites the previous `index.html` — this is intentional.
