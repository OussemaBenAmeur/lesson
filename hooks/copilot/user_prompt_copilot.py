#!/usr/bin/env python3
"""GitHub Copilot CLI userPromptSubmitted hook for the /lesson plugin."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SUPPORT_ROOT = Path(__file__).resolve().parent / "_support"
for candidate in (ROOT, SUPPORT_ROOT):
    if candidate.exists() and str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from lesson.hooks.prompt_capture import handle_user_prompt


def main() -> int:
    try:
        raw = sys.stdin.read()
        event = json.loads(raw) if raw.strip() else {}
    except Exception:
        event = {}

    handle_user_prompt(event, platform="copilot")
    return 0


if __name__ == "__main__":
    sys.exit(main())
