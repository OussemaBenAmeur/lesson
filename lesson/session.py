"""SessionManager — create, resume, and close lesson sessions."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path


def _slugify(text: str) -> str:
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_-]+", "-", slug)
    slug = slug[:50].strip("-")
    ts = str(int(time.time()))[-6:]
    return f"{slug}-{ts}" if slug else f"session-{ts}"


class SessionManager:
    """Manage lesson session lifecycle inside a project directory."""

    def __init__(self, cwd: Path | str | None = None) -> None:
        self._cwd = Path(cwd) if cwd else Path.cwd()
        self._lessons_dir = self._cwd / ".claude" / "lessons"

    @property
    def lessons_dir(self) -> Path:
        return self._lessons_dir

    @property
    def active_marker(self) -> Path:
        return self._lessons_dir / "active-session"

    @property
    def last_marker(self) -> Path:
        return self._lessons_dir / "last-session"

    # ------------------------------------------------------------------
    # Read state
    # ------------------------------------------------------------------

    def active_slug(self) -> str | None:
        if not self.active_marker.exists():
            return None
        slug = self.active_marker.read_text().strip()
        return slug or None

    def session_dir(self, slug: str) -> Path:
        return self._lessons_dir / "sessions" / slug

    def meta(self, slug: str) -> dict:
        p = self.session_dir(slug) / "meta.json"
        if not p.exists():
            return {}
        return json.loads(p.read_text(encoding="utf-8"))

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def create(self, goal: str, notes: str = "", platform: str = "claude-code") -> str:
        slug = _slugify(goal)
        sdir = self.session_dir(slug)
        sdir.mkdir(parents=True, exist_ok=True)

        meta = {
            "slug": slug,
            "goal": goal,
            "notes": notes,
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "cwd": str(self._cwd),
            "platform": platform,
            "token_tracking": {
                "arc_input_chars": 0,
                "compression_cycles": 0,
                "graph_output_chars": 0,
            },
        }
        (sdir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        (sdir / "arc.jsonl").touch()
        (sdir / "counter").write_text("0")

        # Write active-session marker
        self._lessons_dir.mkdir(parents=True, exist_ok=True)
        self.active_marker.write_text(slug)
        return slug

    def resume(self, slug: str | None = None) -> str | None:
        if slug is None:
            if not self.last_marker.exists():
                return None
            slug = self.last_marker.read_text().strip()
        if not slug:
            return None
        if not self.session_dir(slug).exists():
            return None
        self.active_marker.write_text(slug)
        return slug

    def close(self, slug: str) -> None:
        """Mark session as closed (move active → last-session)."""
        self.last_marker.write_text(slug)
        if self.active_marker.exists():
            self.active_marker.unlink()

    # ------------------------------------------------------------------
    # Arc log helpers
    # ------------------------------------------------------------------

    def arc_path(self, slug: str) -> Path:
        return self.session_dir(slug) / "arc.jsonl"

    def graph_path(self, slug: str) -> Path:
        return self.session_dir(slug) / "session_graph.json"

    def counter_path(self, slug: str) -> Path:
        return self.session_dir(slug) / "counter"

    def arc_event_count(self, slug: str) -> int:
        total = 0
        arc = self.arc_path(slug)
        if arc.exists():
            total += sum(1 for _ in arc.open(encoding="utf-8", errors="ignore"))
        for archive in self.session_dir(slug).glob("arc.jsonl.archive*"):
            try:
                total += sum(1 for _ in archive.open(encoding="utf-8", errors="ignore"))
            except Exception:
                pass
        return total

    def update_token_tracking(self, slug: str, **kwargs) -> None:
        meta_path = self.session_dir(slug) / "meta.json"
        if not meta_path.exists():
            return
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        tt = meta.setdefault("token_tracking", {})
        for k, v in kwargs.items():
            tt[k] = tt.get(k, 0) + v
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
