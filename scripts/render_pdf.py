#!/usr/bin/env python3
"""
render_pdf.py — Convert a /lesson markdown file to PDF with mermaid rendered as SVG.

Pipeline:
  1. Extract mermaid blocks from the .md
  2. Render each to .svg via npx @mermaid-js/mermaid-cli mmdc (if available)
  3. Replace mermaid fences in markdown with ![](path-to-svg) image refs
  4. Convert modified markdown → PDF via pandoc or chromium headless

Graceful degradation:
  - mmdc unavailable  → mermaid blocks stay as code blocks in PDF
  - no PDF engine     → print helpful install hint, exit 0 (never fails the lesson)

The .md is always the canonical output. This script only adds the .pdf alongside it.

Usage:
    python3 render_pdf.py <path/to/lesson.md>
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


# ---------------------------------------------------------------------------
# Tool detection
# ---------------------------------------------------------------------------

def _which(cmd: str) -> str | None:
    try:
        r = subprocess.run(["which", cmd], capture_output=True, text=True, timeout=5)
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        return None


def _mmdc_available() -> bool:
    """Check if npx + mermaid-cli is usable. May download mmdc on first call."""
    try:
        r = subprocess.run(
            ["npx", "--yes", "--quiet", "@mermaid-js/mermaid-cli", "mmdc", "--version"],
            capture_output=True, text=True, timeout=45,
        )
        return r.returncode == 0
    except Exception:
        return False


def _find_pdf_engine() -> tuple[str, list[str]] | None:
    """
    Return (tool, args_prefix) for the first available PDF engine, or None.
    Tries: pandoc+weasyprint, pandoc+wkhtmltopdf, pandoc+xelatex,
           chromium headless, wkhtmltopdf standalone.
    """
    pandoc = _which("pandoc")
    if pandoc:
        for engine in ("weasyprint", "wkhtmltopdf", "xelatex", "pdflatex"):
            if _which(engine):
                return ("pandoc", [pandoc, "--pdf-engine", engine])

    for browser in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable"):
        if _which(browser):
            return ("chromium", [browser])

    return None


# ---------------------------------------------------------------------------
# Mermaid rendering
# ---------------------------------------------------------------------------

def _render_mermaid_block(code: str, out_svg: Path) -> bool:
    """Render one mermaid diagram to SVG. Returns True on success."""
    with tempfile.NamedTemporaryFile(
        suffix=".mmd", mode="w", encoding="utf-8", delete=False
    ) as f:
        f.write(code)
        mmd_path = f.name
    try:
        r = subprocess.run(
            [
                "npx", "--yes", "--quiet", "@mermaid-js/mermaid-cli", "mmdc",
                "-i", mmd_path,
                "-o", str(out_svg),
                "--backgroundColor", "white",
            ],
            capture_output=True, text=True, timeout=60,
        )
        return r.returncode == 0 and out_svg.exists() and out_svg.stat().st_size > 0
    except Exception:
        return False
    finally:
        try:
            os.unlink(mmd_path)
        except Exception:
            pass


def _replace_mermaid_blocks(md_text: str, tmpdir: Path, use_mmdc: bool) -> str:
    """
    Replace ```mermaid...``` blocks with either:
      - ![](path/to/diagram-N.svg)   if mmdc rendering succeeded
      - ```\n...\n```                 plain code block fallback
    """
    counter = [0]

    def replacer(match: re.Match) -> str:
        code = match.group(1).strip()
        counter[0] += 1
        if use_mmdc:
            svg_path = tmpdir / f"diagram-{counter[0]}.svg"
            if _render_mermaid_block(code, svg_path):
                return f"![]({svg_path})"
        # Fallback: plain fenced code block (renders as code in PDF)
        return f"```\n{code}\n```"

    return re.sub(r"```mermaid\s*\n(.*?)```", replacer, md_text, flags=re.DOTALL)


# ---------------------------------------------------------------------------
# PDF conversion
# ---------------------------------------------------------------------------

def _md_to_pdf_via_pandoc(md_path: Path, pdf_path: Path, engine_args: list[str]) -> bool:
    try:
        r = subprocess.run(
            [
                *engine_args,
                str(md_path),
                "-f", "markdown+yaml_metadata_block",
                "--variable", "geometry:margin=1.8cm",
                "--variable", "fontsize=11pt",
                "--variable", "linestretch=1.4",
                "-o", str(pdf_path),
            ],
            capture_output=True, text=True, timeout=120,
        )
        return r.returncode == 0 and pdf_path.exists() and pdf_path.stat().st_size > 0
    except Exception:
        return False


def _md_to_pdf_via_chromium(md_path: Path, pdf_path: Path, browser_path: str) -> bool:
    """Convert via chromium: md → minimal HTML → headless print-to-pdf."""
    # Build minimal HTML around the markdown content
    content = md_path.read_text(encoding="utf-8")
    # Strip YAML frontmatter for clean display
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            content = parts[2]

    # Escape for embedding in a <pre> (last-resort path — pandoc should catch this first)
    escaped = content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<style>
  body {{ font-family: monospace; font-size: 10pt; padding: 2cm; }}
  pre {{ white-space: pre-wrap; }}
</style></head>
<body><pre>{escaped}</pre></body></html>"""

    with tempfile.NamedTemporaryFile(
        suffix=".html", mode="w", encoding="utf-8", delete=False
    ) as f:
        f.write(html)
        tmp_html = f.name
    try:
        r = subprocess.run(
            [
                browser_path,
                "--headless=new",
                "--no-sandbox",
                "--disable-gpu",
                f"--print-to-pdf={pdf_path}",
                "--print-to-pdf-no-header",
                f"file://{tmp_html}",
            ],
            capture_output=True, text=True, timeout=120,
        )
        return r.returncode == 0 and pdf_path.exists() and pdf_path.stat().st_size > 0
    except Exception:
        return False
    finally:
        try:
            os.unlink(tmp_html)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: render_pdf.py <path/to/lesson.md>", file=sys.stderr)
        return 1

    md_path = Path(sys.argv[1]).resolve()
    if not md_path.exists():
        print(f"render_pdf: file not found: {md_path}", file=sys.stderr)
        return 1

    pdf_path = md_path.with_suffix(".pdf")

    # --- check tools ---
    engine_info = _find_pdf_engine()
    if engine_info is None:
        print(
            "  pdf: skipped — no PDF engine found\n"
            "       install one of: pandoc+weasyprint, pandoc+wkhtmltopdf, "
            "pandoc+xelatex, chromium"
        )
        return 0

    engine_name, engine_args = engine_info

    use_mmdc = _mmdc_available()
    if not use_mmdc:
        print("  mermaid: mmdc unavailable — diagrams will appear as code blocks in PDF")

    # --- process ---
    md_text = md_path.read_text(encoding="utf-8")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Replace mermaid blocks
        processed_md = _replace_mermaid_blocks(md_text, tmpdir_path, use_mmdc)

        # Write processed markdown to temp file
        tmp_md = tmpdir_path / "lesson_processed.md"
        tmp_md.write_text(processed_md, encoding="utf-8")

        # Convert to PDF
        success = False
        if engine_name == "pandoc":
            success = _md_to_pdf_via_pandoc(tmp_md, pdf_path, engine_args)
        elif engine_name == "chromium":
            success = _md_to_pdf_via_chromium(tmp_md, pdf_path, engine_args[0])

    if success:
        size_kb = pdf_path.stat().st_size // 1024
        print(f"  pdf: {pdf_path} ({size_kb} KB)")
        return 0
    else:
        print(
            f"  pdf: conversion failed (engine: {engine_name})\n"
            f"       the .md lesson is still at {md_path}"
        )
        return 0  # Never fail — the .md is the canonical output


if __name__ == "__main__":
    sys.exit(main())
