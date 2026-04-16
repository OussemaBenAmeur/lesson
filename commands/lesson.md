---
description: Start a tracked /lesson learning session
argument-hint: [what you want to learn / what you're about to work on]
---

The user has invoked `/lesson` to start a tracked learning session. Their stated goal (may be empty):

> $ARGUMENTS

Your job is to set up the session state so that the PostToolUse hook begins tracking the problem-solving arc. Do the following — do not skip or reorder steps.

## 1. Generate a slug

Use the format `YYYYMMDD-HHMMSS` based on the current UTC timestamp. If the goal is non-empty, append a short dash-separated keyword from it (e.g., `20260416-1430-asyncio`). Keep the slug filesystem-safe (lowercase, alphanumerics and dashes only).

## 2. Create session directory

Create `.claude/lessons/sessions/<slug>/` in the current working directory. Also ensure `.claude/lessons/output/` exists (create it if missing) so the final lesson has a home.

## 3. Initialize session files

Inside `.claude/lessons/sessions/<slug>/`, write:

- **`meta.json`** — a JSON object with exactly these fields:
  ```json
  {
    "slug": "<slug>",
    "goal": "<user's goal or topic, or empty string>",
    "notes": "<same as goal — used by /lesson-done to calibrate generation depth and style>",
    "started_at": "<ISO 8601 UTC timestamp>",
    "cwd": "<absolute path of the current working directory>"
  }
  ```
  Both `goal` and `notes` are set to the full `$ARGUMENTS` text. `goal` is used for display in the lesson header; `notes` is read by `/lesson-done` as generation instructions. The user can include style hints directly in their argument: `/lesson asyncio blocking — explain from absolute scratch, I barely know Python` is valid and useful.
- **`arc.jsonl`** — empty file (zero bytes). This is where the hook will append events.
- **`summary.md`** — empty file. The compression subagent will populate this.
- **`counter`** — file containing the single character `0` (no newline).

Use the Write tool for each file. Do not use shell commands for this setup — Write is faster and cannot race.

## 4. Activate tracking

Write the active-session marker at `.claude/lessons/active-session` containing just the slug string (no trailing newline, no other content). The PostToolUse hook checks for this file on every tool call and begins logging once it exists.

## 5. Confirm to the user

Print a short confirmation, exactly in this shape:

```
✓ /lesson tracking active
  session: <slug>
  goal:    <goal or "(none)">
  log:     .claude/lessons/sessions/<slug>/

Work normally. When you're done, run /lesson-done to generate the lesson
(or just stop — the Stop hook will nudge you).

Tip: your argument also guides how the lesson is written. Examples:
  /lesson I barely know Linux — explain everything from first principles
  /lesson asyncio issue — I know Python well, skip basic async theory
  /lesson (no argument) — lesson will use a neutral depth
```

## Notes

- If `.claude/lessons/active-session` already exists, **do not clobber it**. Read the existing slug, tell the user there's already an active session, and ask whether to continue that one or abort and start fresh. Do not silently overwrite.
- If the user's goal argument is empty, still proceed — a goal is not required to track a session.
- Do not call any web tools, search tools, or other side-effecting tools during this setup. This command is pure state initialization.
