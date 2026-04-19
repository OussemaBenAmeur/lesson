"""OpenCode hook payload normalization."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .adapter import NormalizedEvent, extract_result


def extract_post_tool_use_event(raw_event: dict[str, Any]) -> NormalizedEvent:
    cwd = Path(raw_event.get("cwd") or os.getcwd())
    tool_response = raw_event.get("tool_response") or raw_event.get("toolResponse")
    result_text, is_error = extract_result(tool_response)
    return NormalizedEvent(
        tool_name=raw_event.get("tool_name") or raw_event.get("toolName") or "unknown",
        tool_input=raw_event.get("tool_input") or raw_event.get("toolInput") or {},
        result_text=result_text,
        is_error=is_error,
        cwd=cwd,
        session_id=raw_event.get("session_id") or raw_event.get("sessionId"),
        event_id=raw_event.get("tool_call_id") or raw_event.get("toolCallId"),
    )
