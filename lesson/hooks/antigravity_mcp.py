"""Minimal stdio MCP server for Antigravity session capture."""

from __future__ import annotations

import json
import sys
from typing import Any

from .adapter import handle_post_tool_use
from .antigravity import extract_record_event
from .stop import handle_stop

PROTOCOL_VERSION = "2024-11-05"


def _tool_definitions() -> list[dict[str, Any]]:
    return [
        {
            "name": "lesson.record_event",
            "description": "Record one tool event into the active lesson session.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "tool_name": {"type": "string"},
                    "tool_input": {},
                    "result_text": {"type": "string"},
                    "is_error": {"type": "boolean"},
                    "cwd": {"type": "string"},
                    "session_id": {"type": "string"},
                    "event_id": {"type": "string"},
                },
                "required": ["tool_name", "tool_input", "result_text", "is_error"],
            },
        },
        {
            "name": "lesson.finalize_session",
            "description": "Run the session-end lesson finalizer logic without blocking the agent.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "cwd": {"type": "string"},
                    "stop_hook_active": {"type": "boolean"},
                },
                "required": [],
            },
        },
    ]


def _text_result(text: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}]}


def _handle_tools_call(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name == "lesson.record_event":
        handle_post_tool_use(arguments, platform="antigravity", extractor=extract_record_event)
        return _text_result("recorded")
    if name == "lesson.finalize_session":
        handle_stop(arguments, platform="antigravity")
        return _text_result("finalized")
    raise ValueError(f"Unknown tool: {name}")


def _handle_request(request: dict[str, Any]) -> dict[str, Any] | None:
    method = request.get("method")
    request_id = request.get("id")
    params = request.get("params", {})

    if method == "notifications/initialized":
        return None
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "lesson-antigravity", "version": "0.1.0"},
            },
        }
    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": _tool_definitions()}}
    if method == "tools/call":
        result = _handle_tools_call(params.get("name", ""), params.get("arguments", {}))
        return {"jsonrpc": "2.0", "id": request_id, "result": result}
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def main() -> int:
    try:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            request_id: Any = None
            try:
                request = json.loads(line)
                if isinstance(request, dict):
                    request_id = request.get("id")
                response = _handle_request(request)
            except Exception as exc:
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32000, "message": str(exc)},
                }
            if response is not None:
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
