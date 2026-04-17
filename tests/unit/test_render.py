"""Unit tests for render utilities."""

import pytest
from lesson.render.markdown import fill_template, load_template, remaining_placeholders
from pathlib import Path


class TestFillTemplate:
    def test_basic_replacement(self):
        t = "Hello {{NAME}}, you are {{AGE}}."
        result = fill_template(t, {"NAME": "Alice", "AGE": "30"})
        assert result == "Hello Alice, you are 30."

    def test_partial_fill_leaves_remaining(self):
        t = "{{A}} and {{B}}"
        result = fill_template(t, {"A": "x"})
        assert "{{B}}" in result
        assert "{{A}}" not in result

    def test_empty_value(self):
        t = "{{PREFIX}}rest"
        result = fill_template(t, {"PREFIX": ""})
        assert result == "rest"

    def test_no_placeholders(self):
        t = "no placeholders here"
        result = fill_template(t, {"X": "y"})
        assert result == t


class TestRemainingPlaceholders:
    def test_finds_all(self):
        t = "{{A}} and {{B}} and {{C}}"
        result = remaining_placeholders(t)
        assert set(result) == {"A", "B", "C"}

    def test_empty_when_none(self):
        assert remaining_placeholders("no placeholders") == []

    def test_after_fill(self):
        t = "{{A}} and {{B}}"
        filled = fill_template(t, {"A": "x"})
        assert remaining_placeholders(filled) == ["B"]


class TestLoadTemplate:
    def test_loads_file(self, tmp_path):
        p = tmp_path / "tmpl.md"
        p.write_text("{{HELLO}} world")
        result = load_template(p)
        assert result == "{{HELLO}} world"
