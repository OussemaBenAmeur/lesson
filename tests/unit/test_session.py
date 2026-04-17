"""Unit tests for SessionManager."""

import json
import time
import pytest
from pathlib import Path
from lesson.session import SessionManager, _slugify


class TestSlugify:
    def test_basic(self):
        s = _slugify("fix useEffect infinite loop")
        assert "fix" in s
        assert " " not in s

    def test_empty_string(self):
        s = _slugify("")
        assert s.startswith("session-")

    def test_long_input_truncated(self):
        s = _slugify("a" * 200)
        assert len(s) < 80

    def test_special_chars_removed(self):
        s = _slugify("fix: (bug) in module!")
        assert "(" not in s
        assert "!" not in s


class TestSessionManager:
    @pytest.fixture
    def sm(self, tmp_path):
        return SessionManager(tmp_path)

    def test_create_returns_slug(self, sm):
        slug = sm.create("fix the bug")
        assert slug
        assert isinstance(slug, str)

    def test_create_writes_meta(self, sm):
        slug = sm.create("fix the bug", notes="use venv")
        meta = sm.meta(slug)
        assert meta["goal"] == "fix the bug"
        assert meta["notes"] == "use venv"
        assert "started_at" in meta

    def test_create_writes_active_marker(self, sm):
        slug = sm.create("fix the bug")
        assert sm.active_marker.exists()
        assert sm.active_marker.read_text().strip() == slug

    def test_active_slug_returns_slug(self, sm):
        slug = sm.create("fix")
        assert sm.active_slug() == slug

    def test_active_slug_none_when_no_marker(self, sm):
        assert sm.active_slug() is None

    def test_create_arc_jsonl_exists(self, sm):
        slug = sm.create("fix")
        assert sm.arc_path(slug).exists()

    def test_create_counter_exists(self, sm):
        slug = sm.create("fix")
        assert sm.counter_path(slug).exists()

    def test_close_moves_marker(self, sm):
        slug = sm.create("fix")
        sm.close(slug)
        assert not sm.active_marker.exists()
        assert sm.last_marker.exists()
        assert sm.last_marker.read_text().strip() == slug

    def test_resume_from_last(self, sm):
        slug = sm.create("fix")
        sm.close(slug)
        resumed = sm.resume()
        assert resumed == slug
        assert sm.active_slug() == slug

    def test_resume_specific_slug(self, sm):
        slug = sm.create("fix")
        sm.close(slug)
        result = sm.resume(slug)
        assert result == slug

    def test_resume_nonexistent_returns_none(self, sm):
        assert sm.resume("nonexistent-slug") is None

    def test_arc_event_count_empty(self, sm):
        slug = sm.create("fix")
        assert sm.arc_event_count(slug) == 0

    def test_arc_event_count_with_lines(self, sm):
        slug = sm.create("fix")
        sm.arc_path(slug).write_text(
            '{"ts":1.0,"tool":"Bash","args":"ls","result_head":"ok","is_error":false,"significant":false}\n'
            '{"ts":2.0,"tool":"Edit","args":"f","result_head":"","is_error":false,"significant":true}\n'
        )
        assert sm.arc_event_count(slug) == 2

    def test_update_token_tracking(self, sm):
        slug = sm.create("fix")
        sm.update_token_tracking(slug, arc_input_chars=100)
        meta = sm.meta(slug)
        assert meta["token_tracking"]["arc_input_chars"] == 100

    def test_update_token_tracking_accumulates(self, sm):
        slug = sm.create("fix")
        sm.update_token_tracking(slug, arc_input_chars=100)
        sm.update_token_tracking(slug, arc_input_chars=50)
        meta = sm.meta(slug)
        assert meta["token_tracking"]["arc_input_chars"] == 150

    def test_session_dir_path(self, sm):
        slug = sm.create("fix")
        expected = sm.lessons_dir / "sessions" / slug
        assert sm.session_dir(slug) == expected
