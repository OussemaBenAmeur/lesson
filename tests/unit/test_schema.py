"""Unit tests for Pydantic schema models."""

import json
import pytest
from lesson.graph.schema import Edge, EdgeType, Node, NodeType, RawEvent, SessionGraph


class TestNode:
    def test_flag_properties(self):
        n = Node(id="c1", type=NodeType.concept, label="test", flags={"root_cause": True})
        assert n.is_root_cause
        assert not n.is_misconception

    def test_serialization_roundtrip(self):
        n = Node(id="o1", type=NodeType.observation, label="error msg", flags={"pivotal": True})
        data = n.model_dump_json()
        n2 = Node.model_validate_json(data)
        assert n2.id == n.id
        assert n2.label == n.label
        assert n2.is_pivotal


class TestSessionGraph:
    def test_empty_factory(self):
        g = SessionGraph.empty("my-slug", "fix the bug")
        assert g.slug == "my-slug"
        assert len(g.nodes) == 1
        assert g.nodes[0].type == NodeType.goal

    def test_alloc_id_sequential(self):
        g = SessionGraph.empty("s", "goal")
        id1 = g.alloc_id(NodeType.observation)
        g.nodes.append(Node(id=id1, type=NodeType.observation, label="x"))
        id2 = g.alloc_id(NodeType.observation)
        assert id1 == "o1"
        assert id2 == "o2"

    def test_node_by_id(self):
        g = SessionGraph.empty("s", "goal")
        assert g.node_by_id("g1") is not None
        assert g.node_by_id("missing") is None

    def test_referential_integrity_validator_clears_bad_root_cause(self):
        g = SessionGraph(slug="s", goal="g", root_cause_id="nonexistent")
        assert g.root_cause_id is None

    def test_persistence(self, tmp_path):
        g = SessionGraph.empty("test-slug", "my goal")
        p = tmp_path / "graph.json"
        chars = g.save(p)
        assert chars > 0
        g2 = SessionGraph.load(p)
        assert g2.slug == g.slug
        assert len(g2.nodes) == len(g.nodes)

    def test_nodes_of_type(self):
        g = SessionGraph.empty("s", "g")
        g.nodes.append(Node(id="o1", type=NodeType.observation, label="obs"))
        g.nodes.append(Node(id="a1", type=NodeType.attempt, label="att"))
        assert len(g.nodes_of_type(NodeType.goal)) == 1
        assert len(g.nodes_of_type(NodeType.observation)) == 1


class TestRawEvent:
    def test_from_jsonl_line(self):
        line = '{"ts": 1700000001.0, "tool": "Bash", "args": "ls", "result_head": "file.py", "is_error": false, "significant": true}'
        ev = RawEvent.from_jsonl_line(line)
        assert ev is not None
        assert ev.tool == "Bash"
        assert ev.significant

    def test_bad_line_returns_none(self):
        assert RawEvent.from_jsonl_line("not json") is None
        assert RawEvent.from_jsonl_line("") is None

    def test_load_file(self, tmp_path):
        p = tmp_path / "arc.jsonl"
        p.write_text(
            '{"ts":1.0,"tool":"Bash","args":"ls","result_head":"ok","is_error":false,"significant":false}\n'
            'bad line\n'
            '{"ts":2.0,"tool":"Edit","args":"f","result_head":"","is_error":false,"significant":true}\n'
        )
        events = RawEvent.load_file(p)
        assert len(events) == 2  # bad line skipped
