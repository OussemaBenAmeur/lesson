"""GitHub Copilot CLI hook payload normalization."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .adapter import NormalizedEvent, extract_result


def extract_post_tool_use_event(raw_event: dict[str, Any]) -> NormalizedEvent:
    cwd = Path(raw_event.get("cwd") or os.getcwd())
    tool_response = raw_event.get("toolOutput") or raw_event.get("tool_output") or raw_event.get("toolResponse")
    result_text, is_error = extract_result(tool_response)
    if not is_error:
        is_error = bool(raw_event.get("exitCode") or raw_event.get("exit_code"))
    return NormalizedEvent(
        tool_name=raw_event.get("toolName") or raw_event.get("tool_name") or "unknown",
        tool_input=raw_event.get("toolInput") or raw_event.get("tool_input") or {},
        result_text=result_text,
        is_error=is_error,
        cwd=cwd,
        session_id=raw_event.get("sessionId") or raw_event.get("session_id"),
        event_id=raw_event.get("toolCallId") or raw_event.get("tool_call_id"),
    )
