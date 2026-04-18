#!/usr/bin/env python3
"""Stop hook for the /lesson plugin.

Fires when Claude Code is about to stop. If the current project has an active
lesson session with enough tracked events, emits a single-line passive nudge
reminding the user to run /lesson-done. It never blocks the stop — users are in
charge of their exit.

Design notes:
- Honors the `stop_hook_active` flag to avoid infinite loops.
- Skips trivial sessions (< LESSON_STOP_MIN_EVENTS) so that interrupted or
  aborted sessions do not produce half-baked lessons.
- The hook never writes state and never blocks the stop.
- Any exception → exit 0 silently. Never interfere because of a bug here.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

MIN_EVENTS = int(os.environ.get("LESSON_STOP_MIN_EVENTS", "5"))


def _count_lines(path: Path) -> int:
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as fh:
            return sum(1 for _ in fh)
    except Exception:
        return 0


def main() -> int:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return 0
        event = json.loads(raw)
    except Exception:
        return 0

    if event.get("stop_hook_active"):
        return 0

    cwd = event.get("cwd") or os.getcwd()
    lessons_dir = Path(cwd) / ".claude" / "lessons"
    marker = lessons_dir / "active-session"
    if not marker.exists():
        return 0

    try:
        slug = marker.read_text().strip()
    except Exception:
        return 0
    if not slug:
        return 0

    session_dir = lessons_dir / "sessions" / slug
    if not session_dir.exists():
        return 0

    total = 0
    arc = session_dir / "arc.jsonl"
    if arc.exists():
        total += _count_lines(arc)
    try:
        for archive in session_dir.glob("arc.jsonl.archive*"):
            total += _count_lines(archive)
    except Exception:
        pass

    if total < MIN_EVENTS:
        return 0

    output = {
        "hookSpecificOutput": {
            "hookEventName": "Stop",
            "systemMessage": f"[/lesson] Session '{slug}' still active — run /lesson-done when ready.",
        }
    }
    try:
        print(json.dumps(output))
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
