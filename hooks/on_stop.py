#!/usr/bin/env python3
"""Stop hook — the only thing this plugin runs while you work.

Fires each time Claude finishes a turn and hands control back. It does two
cheap things and nothing else:

  1. If enough has happened since the last look, start a background analysis
     of the session transcript. Detached, silent, never blocks.
  2. If that analysis left an offer waiting, print it — one line.

It never calls a model itself, never reads the transcript, and never writes to
the conversation except that single offer line.

Lessons from the version this replaces:
  - It must never crash. Any exception exits 0.
  - It must never speak unless there is something genuinely worth saying.
  - The background process MUST run with `--bare`, which skips hooks. Without
    that it would trigger this same hook and recurse forever.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HOME = Path(os.path.expanduser("~")) / ".claude" / "lesson"
STATE = HOME / "state.json"
OFFER = HOME / "pending-lesson.json"
LOCK = HOME / "analysis.lock"

# Don't look more often than this. Analysis is not urgent, and a user who is
# iterating quickly should not trigger one on every keystroke-sized turn.
MIN_TURNS_BETWEEN = int(os.environ.get("LESSON_MIN_TURNS", "12"))
MIN_SECONDS_BETWEEN = int(os.environ.get("LESSON_MIN_SECONDS", "900"))
LOCK_STALE_SECONDS = 1800


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, data) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(path)
    except Exception:
        pass


def _enabled() -> bool:
    """Off unless the user has been through onboarding. Never assume consent."""
    return (HOME / "graph.json").exists()


def _speak(offer: dict) -> None:
    """Hand the offer to Claude.

    This output is context for Claude, not text shown to the user, so it has to
    say what to do with it. The offer file deliberately survives: the user has
    not answered yet, and `/lesson yes` needs to know which node they meant.
    """
    line = offer.get("line")
    node = offer.get("node")
    if not line or not node:
        return
    instruction = (
        "[lesson] End your reply with exactly this line, on its own, and nothing "
        f"after it:\n\n{line}\n\n"
        "If they accept, run `/lesson yes`. If they decline, delete "
        f"{OFFER} and do not raise it again. If they ignore it and keep working, "
        "drop it silently — never repeat it, never mention it twice."
    )
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "Stop",
            "additionalContext": instruction,
        }
    }))


def _lock_held() -> bool:
    try:
        if not LOCK.exists():
            return False
        if time.time() - LOCK.stat().st_mtime > LOCK_STALE_SECONDS:
            LOCK.unlink(missing_ok=True)
            return False
        return True
    except Exception:
        return False


def _spawn(transcript: str, session_id: str) -> None:
    """Run the analysis in a detached `claude --bare -p` process.

    `--bare` is load-bearing: it skips hooks, so the analysis process does not
    fire this hook again. Removing it causes infinite recursion.
    """
    exe = shutil.which("claude")
    if not exe:
        return

    prompt_file = Path(__file__).resolve().parent.parent / "analysis" / "watch.md"
    if not prompt_file.exists():
        return

    prompt = (
        f"{prompt_file.read_text(encoding='utf-8')}\n\n"
        f"---\n"
        f"TRANSCRIPT: {transcript}\n"
        f"SESSION_ID: {session_id}\n"
        f"GRAPH: {HOME / 'graph.json'}\n"
        f"PENDING_FILE: {OFFER}\n"
    )

    try:
        LOCK.parent.mkdir(parents=True, exist_ok=True)
        LOCK.write_text(str(time.time()))
        subprocess.Popen(
            [exe, "--bare", "-p", prompt],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
            cwd=str(HOME),
        )
    except Exception:
        LOCK.unlink(missing_ok=True)


def main() -> int:
    if not _enabled():
        return 0

    try:
        raw = sys.stdin.read()
        event = json.loads(raw) if raw.strip() else {}
    except Exception:
        event = {}

    # 1. Anything waiting to be said? Say it exactly once, ever.
    #    The file stays — the user has not answered yet — but `offered_at`
    #    guarantees it is never raised a second time.
    offer = _read_json(OFFER, None)
    if isinstance(offer, dict) and not offer.get("offered_at"):
        offer["offered_at"] = time.time()
        _write_json(OFFER, offer)
        _speak(offer)
        return 0

    # 2. Decide whether it's worth looking at the transcript again.
    state = _read_json(STATE, {})
    turns = int(state.get("turns_since_analysis", 0)) + 1
    last = float(state.get("last_analysis_ts", 0))
    state["turns_since_analysis"] = turns

    transcript = event.get("transcript_path") or ""
    session_id = event.get("session_id") or ""

    ready = (
        turns >= MIN_TURNS_BETWEEN
        and (time.time() - last) >= MIN_SECONDS_BETWEEN
        and transcript
        and Path(transcript).exists()
        and not _lock_held()
    )

    if ready:
        state["turns_since_analysis"] = 0
        state["last_analysis_ts"] = time.time()
        _write_json(STATE, state)
        _spawn(transcript, session_id)
    else:
        _write_json(STATE, state)

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        # Never, under any circumstances, break the user's session.
        sys.exit(0)
