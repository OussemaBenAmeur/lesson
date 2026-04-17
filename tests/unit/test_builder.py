"""Unit tests for EventGraphBuilder."""

import pytest
from lesson.graph.builder import EventGraphBuilder
from lesson.graph.schema import NodeType, RawEvent, SessionGraph


def make_event(**kwargs) -> RawEvent:
    defaults = {
        "tool": "Bash", "args": "", "result_head": "",
        "is_error": False, "significant": False, "ts": 1700000000.0,
    }
    defaults.update(kwargs)
    return RawEvent(**defaults)


def load_fixture(name: str) -> list[RawEvent]:
    from pathlib import Path
    p = Path(__file__).parent.parent / "fixtures" / name
    return RawEvent.load_file(p)


@pytest.fixture
def builder():
    return EventGraphBuilder(use_embedder=False)  # no heavy model in unit tests


class TestEventGraphBuilder:
    def test_empty_events_returns_unchanged_graph(self, builder):
        g = SessionGraph.empty("test", "fix bug")
        result = builder.compress([], g)
        assert result.events_processed == 0
        assert result.nodes_added == 0

    def test_error_event_creates_observation(self, builder):
        g = SessionGraph.empty("test", "fix bug")
        events = [make_event(result_head="ModuleNotFoundError", is_error=True)]
        result = builder.compress(events, g)
        obs_nodes = result.graph.nodes_of_type(NodeType.observation)
        assert len(obs_nodes) >= 1

    def test_edit_event_creates_attempt(self, builder):
        g = SessionGraph.empty("test", "fix bug")
        events = [
            make_event(tool="Edit", args='{"file_path": "app.py"}', result_head="edited"),
        ]
        result = builder.compress(events, g)
        attempt_nodes = result.graph.nodes_of_type(NodeType.attempt)
        assert len(attempt_nodes) >= 1

    def test_total_events_updated(self, builder):
        g = SessionGraph.empty("test", "fix bug")
        events = [make_event(is_error=True, result_head="error")] * 5
        result = builder.compress(events, g)
        assert result.graph.total_events_compressed == 5

    def test_elapsed_ms_positive(self, builder):
        g = SessionGraph.empty("test", "fix")
        events = [make_event(is_error=True, result_head="error")]
        result = builder.compress(events, g)
        assert result.elapsed_ms >= 0.0

    def test_react_fixture(self, builder):
        events = load_fixture("react_useeffect_arc.jsonl")
        assert len(events) > 0
        g = SessionGraph.empty("react-test", "fix useEffect infinite loop")
        result = builder.compress(events, g)
        # Should produce at least 2 nodes beyond the initial goal node
        assert result.nodes_added >= 2

    def test_python_import_fixture(self, builder):
        events = load_fixture("python_import_arc.jsonl")
        g = SessionGraph.empty("python-test", "fix ModuleNotFoundError")
        result = builder.compress(events, g)
        # Multiple errors → should produce observation nodes
        obs = result.graph.nodes_of_type(NodeType.observation)
        assert len(obs) >= 1

    def test_node_ids_are_unique(self, builder):
        events = load_fixture("python_import_arc.jsonl")
        g = SessionGraph.empty("test", "fix")
        result = builder.compress(events, g)
        ids = [n.id for n in result.graph.nodes]
        assert len(ids) == len(set(ids)), "Duplicate node IDs detected"

    def test_graph_is_valid_after_compress(self, builder):
        from lesson.graph.algorithms import is_valid
        events = load_fixture("react_useeffect_arc.jsonl")
        g = SessionGraph.empty("test", "fix")
        result = builder.compress(events, g)
        ok, issues = is_valid(result.graph)
        assert ok, f"Invalid graph: {issues}"

    def test_incremental_compression(self, builder):
        """Two compressions should not break ID stability."""
        events = load_fixture("python_import_arc.jsonl")
        half = len(events) // 2
        g = SessionGraph.empty("test", "fix")

        r1 = builder.compress(events[:half], g)
        ids_after_first = {n.id for n in r1.graph.nodes}

        r2 = builder.compress(events[half:], r1.graph)
        ids_after_second = {n.id for n in r2.graph.nodes}

        # All IDs from first compression must survive
        assert ids_after_first.issubset(ids_after_second)
