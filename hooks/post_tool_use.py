#!/usr/bin/env python3
"""Claude Code PostToolUse hook for the /lesson plugin."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lesson.hooks import adapter as hook_adapter
from lesson.hooks.claude_code import extract_post_tool_use_event

_resolve_lesson_command = hook_adapter._resolve_lesson_command


def main() -> int:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return 0
        event = json.loads(raw)
    except Exception:
        return 0

    hook_adapter.handle_post_tool_use(
        raw_event=event,
        platform="claude-code",
        extractor=extract_post_tool_use_event,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
