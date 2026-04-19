"""Sidecar capture for user prompt events that must not enter arc.jsonl."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

from .adapter import _lessons_dir

PROMPT_HEAD_CAP = 512


def _extract_prompt_text(raw_event: dict[str, Any]) -> str:
    for key in ("prompt", "userPrompt", "user_prompt", "message", "text"):
        value = raw_event.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def handle_user_prompt(raw_event: dict[str, Any], platform: str) -> None:
    try:
        prompt_text = _extract_prompt_text(raw_event)
        if not prompt_text:
            return

        cwd = Path(raw_event.get("cwd") or os.getcwd())
        lessons_dir = _lessons_dir(cwd, platform)
        marker = lessons_dir / "active-session"
        if not marker.exists():
            return

        slug = marker.read_text().strip()
        if not slug:
            return

        session_dir = lessons_dir / "sessions" / slug
        if not session_dir.exists():
            return

        prompt_hash = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()
        entry = {
            "ts": raw_event.get("ts") or time.time(),
            "session_id": raw_event.get("sessionId") or raw_event.get("session_id"),
            "prompt_text_head": prompt_text[:PROMPT_HEAD_CAP],
            "prompt_hash": prompt_hash,
        }
        prompts_path = session_dir / "prompts.jsonl"
        entry_json = json.dumps(entry, ensure_ascii=True)
        with prompts_path.open("a", encoding="utf-8") as fh:
            fh.write(entry_json + "\n")
    except Exception:
        return
