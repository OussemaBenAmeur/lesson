"""Codex hook payload normalization."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .adapter import NormalizedEvent, extract_result


def extract_post_tool_use_event(raw_event: dict[str, Any]) -> NormalizedEvent:
    cwd = Path(raw_event.get("cwd") or os.getcwd())
    tool_response = raw_event.get("tool_response")
    result_text, is_error = extract_result(tool_response)
    if isinstance(tool_response, dict) and not is_error:
        is_error = bool(tool_response.get("exit_code", 0))
    return NormalizedEvent(
        tool_name=raw_event.get("tool_name") or "Bash",
        tool_input=raw_event.get("tool_input") or {},
        result_text=result_text,
        is_error=is_error,
        cwd=cwd,
        session_id=raw_event.get("session_id"),
        event_id=raw_event.get("tool_call_id"),
    )
