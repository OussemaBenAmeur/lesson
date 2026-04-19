"""Shared Stop hook logic for platform-specific wrappers."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .adapter import _lessons_dir


def _min_events() -> int:
    return int(os.environ.get("LESSON_STOP_MIN_EVENTS", "5"))


def _count_lines(path: Path) -> int:
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as fh:
            return sum(1 for _ in fh)
    except Exception:
        return 0


def _stop_flag_set(raw_event: dict[str, Any]) -> bool:
    return bool(raw_event.get("stop_hook_active") or raw_event.get("stopHookActive"))


def build_stop_output(slug: str) -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "Stop",
            "systemMessage": f"[/lesson] Session '{slug}' still active — run /lesson-done when ready.",
        }
    }


def handle_stop(raw_event: dict[str, Any], platform: str) -> dict[str, Any] | None:
    try:
        if _stop_flag_set(raw_event):
            return None

        cwd = Path(raw_event.get("cwd") or os.getcwd())
        lessons_dir = _lessons_dir(cwd, platform)
        marker = lessons_dir / "active-session"
        if not marker.exists():
            return None

        slug = marker.read_text().strip()
        if not slug:
            return None

        session_dir = lessons_dir / "sessions" / slug
        if not session_dir.exists():
            return None

        total = 0
        arc = session_dir / "arc.jsonl"
        if arc.exists():
            total += _count_lines(arc)
        for archive in session_dir.glob("arc.jsonl.archive*"):
            total += _count_lines(archive)

        if total < _min_events():
            return None
        return build_stop_output(slug)
    except Exception:
        return None

