"""Antigravity MCP payload normalization."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .adapter import NormalizedEvent


def extract_record_event(raw_event: dict[str, Any]) -> NormalizedEvent:
    cwd = Path(raw_event.get("cwd") or os.getcwd())
    return NormalizedEvent(
        tool_name=raw_event.get("tool_name") or "unknown",
        tool_input=raw_event.get("tool_input") or {},
        result_text=str(raw_event.get("result_text") or ""),
        is_error=bool(raw_event.get("is_error")),
        cwd=cwd,
        session_id=raw_event.get("session_id"),
        event_id=raw_event.get("event_id"),
    )
