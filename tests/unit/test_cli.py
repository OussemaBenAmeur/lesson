"""Unit tests for the Typer CLI using the test runner."""

import pytest
from pathlib import Path
from typer.testing import CliRunner
from lesson.cli import app

runner = CliRunner()


@pytest.fixture
def project_dir(tmp_path):
    return tmp_path


class TestStartCommand:
    def test_start_creates_session(self, project_dir):
        result = runner.invoke(app, ["start", "fix useEffect loop", "--cwd", str(project_dir)])
        assert result.exit_code == 0
        assert "Started session" in result.output

    def test_start_shows_goal(self, project_dir):
        result = runner.invoke(app, ["start", "fix the bug", "--cwd", str(project_dir)])
        assert "fix the bug" in result.output

    def test_start_with_notes(self, project_dir):
        result = runner.invoke(app, ["start", "fix bug", "--notes", "use Python 3.11", "--cwd", str(project_dir)])
        assert result.exit_code == 0

    def test_start_fails_if_already_active(self, project_dir):
        runner.invoke(app, ["start", "first session", "--cwd", str(project_dir)])
        result = runner.invoke(app, ["start", "second session", "--cwd", str(project_dir)])
        assert result.exit_code != 0
        assert "already" in result.output.lower()


class TestStatsCommand:
    def test_stats_no_session(self, project_dir):
        result = runner.invoke(app, ["stats", "--cwd", str(project_dir)])
        assert result.exit_code != 0
        assert "No active session" in result.output

    def test_stats_no_graph_yet(self, project_dir):
        runner.invoke(app, ["start", "fix bug", "--cwd", str(project_dir)])
        result = runner.invoke(app, ["stats", "--cwd", str(project_dir)])
        assert "No session_graph" in result.output or result.exit_code == 0


class TestCompressCommand:
    def test_compress_no_session(self, project_dir):
        result = runner.invoke(app, ["compress", "--cwd", str(project_dir)])
        assert result.exit_code != 0
        assert "No active session" in result.output

    def test_compress_empty_arc(self, project_dir):
        runner.invoke(app, ["start", "fix bug", "--cwd", str(project_dir)])
        result = runner.invoke(app, ["compress", "--cwd", str(project_dir)])
        assert "empty" in result.output.lower() or result.exit_code == 0

    def test_compress_with_events(self, project_dir, tmp_path):
        from lesson.session import SessionManager
        sm = SessionManager(project_dir)
        slug = sm.create("fix bug")
        sm.arc_path(slug).write_text(
            '{"ts":1.0,"tool":"Bash","args":"python main.py","result_head":"ModuleNotFoundError: numpy","is_error":true,"significant":true}\n'
            '{"ts":2.0,"tool":"Edit","args":"requirements.txt","result_head":"edited","is_error":false,"significant":true}\n'
        )
        result = runner.invoke(app, ["compress", "--cwd", str(project_dir), "--no-embed"])
        assert result.exit_code == 0
        assert "Compressed" in result.output


class TestResumeCommand:
    def test_resume_no_last(self, project_dir):
        result = runner.invoke(app, ["resume", "--cwd", str(project_dir)])
        assert result.exit_code != 0

    def test_resume_after_close(self, project_dir):
        from lesson.session import SessionManager
        sm = SessionManager(project_dir)
        slug = sm.create("fix bug")
        sm.close(slug)
        result = runner.invoke(app, ["resume", "--cwd", str(project_dir)])
        assert result.exit_code == 0
        assert "Resumed" in result.output


class TestGraphCommand:
    def test_graph_no_session(self, project_dir):
        result = runner.invoke(app, ["graph", "--cwd", str(project_dir)])
        assert result.exit_code != 0

    def test_graph_mermaid_output(self, project_dir):
        from lesson.session import SessionManager
        from lesson.graph.schema import SessionGraph, Node, NodeType
        sm = SessionManager(project_dir)
        slug = sm.create("fix bug")
        # Write a minimal graph
        g = SessionGraph.empty(slug, "fix bug")
        g.save(sm.graph_path(slug))
        result = runner.invoke(app, ["graph", "--mermaid", "--cwd", str(project_dir)])
        assert result.exit_code == 0
        assert "flowchart" in result.output.lower() or "g1" in result.output

    def test_graph_dot_output(self, project_dir):
        from lesson.session import SessionManager
        from lesson.graph.schema import SessionGraph
        sm = SessionManager(project_dir)
        slug = sm.create("fix bug")
        g = SessionGraph.empty(slug, "fix bug")
        g.save(sm.graph_path(slug))
        result = runner.invoke(app, ["graph", "--dot", "--cwd", str(project_dir)])
        assert result.exit_code == 0
        assert "digraph" in result.output
