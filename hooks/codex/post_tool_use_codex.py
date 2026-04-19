#!/usr/bin/env python3
"""Codex PostToolUse hook for the /lesson plugin."""

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
from lesson.hooks.codex import extract_post_tool_use_event


def main() -> int:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return 0
        event = json.loads(raw)
    except Exception:
        return 0

    handle_post_tool_use(
        raw_event=event,
        platform="codex",
        extractor=extract_post_tool_use_event,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
