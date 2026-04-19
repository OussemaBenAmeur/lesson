"""Shared SessionStart hook logic for platform-specific wrappers."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .adapter import _lessons_dir


def _extract_session_id(raw_event: dict[str, Any]) -> str | None:
    for key in ("session_id", "sessionId", "conversation_id", "conversationId"):
        value = raw_event.get(key)
        if value:
            return str(value)
    return None


def handle_session_start(raw_event: dict[str, Any], platform: str) -> None:
    try:
        cwd = Path(raw_event.get("cwd") or os.getcwd())
        lessons_dir = _lessons_dir(cwd, platform)
        marker = lessons_dir / "active-session"
        if not marker.exists():
            return

        slug = marker.read_text().strip()
        if not slug:
            return

        session_dir = lessons_dir / "sessions" / slug
        meta_path = session_dir / "meta.json"
        if not meta_path.exists():
            return

        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        hook_state = meta.setdefault("hook_state", {})
        hook_state["platform"] = platform

        session_id = _extract_session_id(raw_event)
        if session_id:
            hook_state["session_id"] = session_id

        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        return
