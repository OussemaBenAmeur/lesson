#!/usr/bin/env python3
"""Cursor postToolUse hook for the /lesson plugin."""

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
from lesson.hooks.cursor import extract_post_tool_use_event


def main() -> int:
    try:
        raw = sys.stdin.read()
        event = json.loads(raw) if raw.strip() else {}
    except Exception:
        event = {}

    handle_post_tool_use(
        raw_event=event,
        platform="cursor",
        extractor=extract_post_tool_use_event,
    )
    try:
        print(json.dumps({"permission": "allow"}))
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
