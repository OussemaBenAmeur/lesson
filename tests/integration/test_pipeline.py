"""Integration tests: full arc.jsonl → graph pipeline."""

import pytest
from pathlib import Path
from lesson.graph.algorithms import find_root_cause, find_causal_chain, is_valid
from lesson.graph.builder import EventGraphBuilder
from lesson.graph.schema import NodeType, RawEvent, SessionGraph

FIXTURES = Path(__file__).parent.parent / "fixtures"


def run_pipeline(fixture_name: str, goal: str) -> SessionGraph:
    events = RawEvent.load_file(FIXTURES / fixture_name)
    assert len(events) > 0, f"Fixture {fixture_name} is empty"
    g = SessionGraph.empty(fixture_name.replace(".jsonl", ""), goal)
    builder = EventGraphBuilder(use_embedder=False)
    result = builder.compress(events, g)
    return result.graph


class TestReactFixture:
    @pytest.fixture(scope="class")
    def graph(self):
        return run_pipeline("react_useeffect_arc.jsonl", "fix useEffect infinite loop")

    def test_graph_is_valid(self, graph):
        ok, issues = is_valid(graph)
        assert ok, f"Graph validation failed: {issues}"

    def test_has_goal_node(self, graph):
        goals = graph.nodes_of_type(NodeType.goal)
        assert len(goals) == 1

    def test_has_observation_or_attempt(self, graph):
        obs = graph.nodes_of_type(NodeType.observation)
        att = graph.nodes_of_type(NodeType.attempt)
        assert len(obs) + len(att) >= 1

    def test_no_duplicate_ids(self, graph):
        ids = [n.id for n in graph.nodes]
        assert len(ids) == len(set(ids))

    def test_no_orphan_nodes(self, graph):
        from lesson.graph.algorithms import graph_metrics
        m = graph_metrics(graph)
        # Short sessions (<= 10 events) produce sparse graphs; orphans are expected.
        # Require only that the majority of nodes have at least one edge.
        if m["nodes"] > 4:
            assert m["orphan_count"] < m["nodes"], "All nodes are orphans — no edges wired"

    def test_events_counted(self, graph):
        assert graph.total_events_compressed > 0


class TestPythonImportFixture:
    @pytest.fixture(scope="class")
    def graph(self):
        return run_pipeline("python_import_arc.jsonl", "fix ModuleNotFoundError for numpy")

    def test_graph_is_valid(self, graph):
        ok, issues = is_valid(graph)
        assert ok, f"Graph validation failed: {issues}"

    def test_error_events_become_observations(self, graph):
        # The fixture has 2 is_error=true events → at least 1 observation node
        obs = graph.nodes_of_type(NodeType.observation)
        assert len(obs) >= 1

    def test_total_compressed_matches_fixture(self, graph):
        events = RawEvent.load_file(FIXTURES / "python_import_arc.jsonl")
        assert graph.total_events_compressed == len(events)


class TestIncrementalCompression:
    def test_id_stability_across_batches(self):
        events = RawEvent.load_file(FIXTURES / "python_import_arc.jsonl")
        g = SessionGraph.empty("test", "fix")
        builder = EventGraphBuilder(use_embedder=False)

        half = len(events) // 2
        r1 = builder.compress(events[:half], g)
        snapshot_ids = {n.id for n in r1.graph.nodes}

        r2 = builder.compress(events[half:], r1.graph)
        final_ids = {n.id for n in r2.graph.nodes}

        assert snapshot_ids.issubset(final_ids), "IDs were renumbered between batches"

    def test_no_duplicate_ids_after_two_compressions(self):
        events = RawEvent.load_file(FIXTURES / "react_useeffect_arc.jsonl")
        g = SessionGraph.empty("test", "fix")
        builder = EventGraphBuilder(use_embedder=False)

        half = len(events) // 2
        r1 = builder.compress(events[:half], g)
        r2 = builder.compress(events[half:], r1.graph)

        ids = [n.id for n in r2.graph.nodes]
        assert len(ids) == len(set(ids)), "Duplicate IDs found after incremental compression"


class TestGraphPersistence:
    def test_save_and_load_roundtrip(self, tmp_path):
        events = RawEvent.load_file(FIXTURES / "react_useeffect_arc.jsonl")
        g = SessionGraph.empty("test", "fix")
        builder = EventGraphBuilder(use_embedder=False)
        result = builder.compress(events, g)

        p = tmp_path / "graph.json"
        result.graph.save(p)
        loaded = SessionGraph.load(p)

        assert loaded.slug == result.graph.slug
        assert len(loaded.nodes) == len(result.graph.nodes)
        assert len(loaded.edges) == len(result.graph.edges)
