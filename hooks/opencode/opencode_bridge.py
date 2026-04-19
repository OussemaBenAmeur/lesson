#!/usr/bin/env python3
"""Bridge OpenCode plugin events into the shared hook adapter."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SUPPORT_ROOT = Path(__file__).resolve().parent / "_support"
for candidate in (ROOT, SUPPORT_ROOT):
    if candidate.exists() and str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from lesson.hooks.adapter import handle_post_tool_use
from lesson.hooks.opencode import extract_post_tool_use_event
from lesson.hooks.session_start import handle_session_start
from lesson.hooks.stop import handle_stop


def main() -> int:
    kind = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        raw = sys.stdin.read()
        event = json.loads(raw) if raw.strip() else {}
    except Exception:
        event = {}

    if kind == "postToolUse":
        handle_post_tool_use(
            raw_event=event,
            platform="opencode",
            extractor=extract_post_tool_use_event,
        )
    elif kind == "sessionStart":
        handle_session_start(event, platform="opencode")
    elif kind == "stop":
        handle_stop(event, platform="opencode")
    return 0


if __name__ == "__main__":
    sys.exit(main())
