"""PDF renderer — thin wrapper around scripts/render_pdf.py.

Kept as a pass-through so the package can expose a clean API while
the rendering logic lives in scripts/render_pdf.py (which must always exit 0).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def render(md_path: Path, plugin_root: Path | None = None) -> bool:
    """Render markdown to PDF. Returns True on success, False on failure.

    Never raises — failure is silently logged to stderr.
    """
    if plugin_root is None:
        plugin_root = Path(__file__).parent.parent.parent

    script = plugin_root / "scripts" / "render_pdf.py"
    if not script.exists():
        return False

    try:
        result = subprocess.run(
            [sys.executable, str(script), str(md_path)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.stdout:
            print(result.stdout, end="")
        return result.returncode == 0
    except Exception as exc:
        print(f"PDF render failed: {exc}", file=sys.stderr)
        return False
