#!/usr/bin/env python3
"""Codex Stop hook for the /lesson plugin."""

from __future__ import annotations

import sys
from pathlib import Path

LOCAL_STOP = Path(__file__).resolve().with_name("stop.py")
REPO_STOP = Path(__file__).resolve().parents[1] / "stop.py"
STOP_HOOK = LOCAL_STOP if LOCAL_STOP.exists() else REPO_STOP


def main() -> int:
    try:
        import runpy

        module = runpy.run_path(str(STOP_HOOK), run_name="__lesson_stop_hook__")
        return int(module["main"]())
    except Exception:
        return 0


if __name__ == "__main__":
    sys.exit(main())
