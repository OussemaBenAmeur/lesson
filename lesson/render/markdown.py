"""Markdown template utilities for lesson generation."""

from __future__ import annotations

import re
from pathlib import Path


def fill_template(template: str, replacements: dict[str, str]) -> str:
    """Replace {{PLACEHOLDER}} tokens in template with values."""
    result = template
    for key, value in replacements.items():
        result = result.replace("{{" + key + "}}", value)
    return result


def load_template(template_path: Path) -> str:
    return template_path.read_text(encoding="utf-8")


def remaining_placeholders(text: str) -> list[str]:
    """Return list of unfilled {{PLACEHOLDER}} tokens."""
    return re.findall(r"\{\{([A-Z_]+)\}\}", text)
