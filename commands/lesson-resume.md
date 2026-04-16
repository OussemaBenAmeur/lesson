---
description: Resume tracking on the most recent /lesson session
---

The user has invoked `/lesson resume`. Your job is to reactivate tracking on the most recent session so that the PostToolUse hook picks up where it left off.

## Step 1 — Find the session to resume

1. Check `.claude/lessons/last-session`. If it exists, read the slug.
2. If `last-session` doesn't exist, tell the user: "No previous session found. Use `/lesson <topic>` to start a new one." and stop.
3. Let `<slug>` = slug from `last-session`.
4. Verify `.claude/lessons/sessions/<slug>/` exists. If not: "Session directory for `<slug>` not found — it may have been deleted." and stop.

## Step 2 — Check for an already-active session

Read `.claude/lessons/active-session` if it exists.

- If it contains `<slug>` — tracking is already active on this session. Tell the user: "Session `<slug>` is already active. No change made." and stop.
- If it contains a *different* slug — there is a different session currently active. Tell the user which slug is active and ask: "There's an active session for `<other-slug>`. Resume `<slug>` instead? This will deactivate the current session (it will NOT be deleted — you can resume it again later)." Wait for confirmation before proceeding.

## Step 3 — Read session state to report context

Before reactivating, read:
- `.claude/lessons/sessions/<slug>/meta.json` — goal, start time
- `.claude/lessons/sessions/<slug>/counter` — events since last compression
- Count lines in `.claude/lessons/sessions/<slug>/arc.jsonl` (current uncompressed events)
- Count lines across all `.claude/lessons/sessions/<slug>/arc.jsonl.archive*` files (previously compressed events)

Total events tracked so far = archive lines + current arc lines.

## Step 4 — Reactivate

Write `<slug>` (no trailing newline) to `.claude/lessons/active-session`.

The PostToolUse hook will now resume appending events to the existing `arc.jsonl`. New events merge with prior session data — when `/lesson-done` runs, it reads `summary.md` (which has all prior compressed content) plus the live `arc.jsonl`. Nothing is lost.

## Step 5 — Confirm

Print exactly:
```
✓ /lesson tracking resumed
  session: <slug>
  goal:    <goal or "(none)">
  started: <started_at, formatted as YYYY-MM-DD HH:MM UTC>
  events:  <total events tracked so far>

Picking up where you left off. Run /lesson-done when you're done.
```

## Notes

- This command never deletes or modifies session data. It only writes `active-session`.
- `/lesson resume` always resumes the session in `last-session`. There is no way to resume an arbitrary older session by name via this command — if the user wants to resume a specific older slug, they can write `active-session` manually: `echo -n <slug> > .claude/lessons/active-session`.
- If the user resumes a session and then runs `/lesson-done`, the resulting lesson will cover the full arc: everything before the pause and everything after.
