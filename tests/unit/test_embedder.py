"""Unit tests for NodeEmbedder (fallback path — no model required)."""

import pytest
from lesson.graph.schema import Node, NodeType
from lesson.nlp.embedder import NodeEmbedder


def make_node(label: str, ntype: NodeType = NodeType.concept) -> Node:
    return Node(id="c1", type=ntype, label=label)


class TestNodeEmbedderFallback:
    """Tests that use exact-string matching (no model loaded)."""

    @pytest.fixture
    def embedder(self):
        e = NodeEmbedder()
        e._model = False  # force fallback: no model
        return e

    def test_exact_match_found(self, embedder):
        candidates = [make_node("ModuleNotFoundError"), make_node("Python path")]
        dup = embedder.find_duplicate("ModuleNotFoundError", candidates)
        assert dup is not None
        assert dup.label == "ModuleNotFoundError"

    def test_exact_match_case_insensitive(self, embedder):
        candidates = [make_node("modulenotfounderror")]
        dup = embedder.find_duplicate("ModuleNotFoundError", candidates)
        assert dup is not None

    def test_no_match(self, embedder):
        candidates = [make_node("Python path"), make_node("venv")]
        dup = embedder.find_duplicate("completely different", candidates)
        assert dup is None

    def test_empty_candidates(self, embedder):
        dup = embedder.find_duplicate("anything", [])
        assert dup is None

    def test_cluster_without_model(self, embedder):
        labels = ["label A", "label B", "label C"]
        clusters = embedder.cluster(labels)
        # Without model, each label is its own cluster
        assert len(clusters) == 3
        flat = [i for c in clusters for i in c]
        assert sorted(flat) == [0, 1, 2]

    def test_cluster_empty(self, embedder):
        assert embedder.cluster([]) == []

    def test_find_duplicate_no_candidates_returns_none(self, embedder):
        assert embedder.find_duplicate("x", []) is None
