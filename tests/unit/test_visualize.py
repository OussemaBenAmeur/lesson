"""Unit tests for graph visualization (Mermaid, DOT, Plotly)."""

import pytest
from lesson.graph.schema import Edge, EdgeType, Node, NodeType, SessionGraph
from lesson.graph.visualize import to_dot, to_mermaid, to_plotly_html


def make_graph() -> SessionGraph:
    g = SessionGraph(slug="vis-test", goal="fix bug")
    g.nodes = [
        Node(id="g1", type=NodeType.goal, label="fix bug"),
        Node(id="a1", type=NodeType.attempt, label="edit main.py"),
        Node(id="o1", type=NodeType.observation, label="ImportError", flags={"pivotal": True}),
        Node(id="c1", type=NodeType.concept, label="Python path", flags={"root_cause": True}),
        Node(id="r1", type=NodeType.resolution, label="used venv"),
    ]
    g.edges = [
        Edge(from_id="g1", to_id="a1", type=EdgeType.motivated),
        Edge(from_id="a1", to_id="o1", type=EdgeType.produced),
        Edge(from_id="o1", to_id="c1", type=EdgeType.revealed),
        Edge(from_id="c1", to_id="r1", type=EdgeType.enabled),
    ]
    g.root_cause_id = "c1"
    g.resolution_id = "r1"
    return g


class TestToMermaid:
    def test_returns_string(self):
        g = make_graph()
        result = to_mermaid(g)
        assert isinstance(result, str)

    def test_contains_all_node_ids(self):
        g = make_graph()
        result = to_mermaid(g)
        for node in g.nodes:
            assert node.id in result

    def test_contains_flowchart_header(self):
        g = make_graph()
        result = to_mermaid(g)
        assert "flowchart" in result.lower() or "TD" in result

    def test_root_cause_annotated(self):
        g = make_graph()
        result = to_mermaid(g)
        assert "🎯" in result

    def test_edge_labels_present(self):
        g = make_graph()
        result = to_mermaid(g)
        assert "produced" in result or "revealed" in result

    def test_empty_graph(self):
        g = SessionGraph(slug="empty", goal="")
        result = to_mermaid(g)
        assert isinstance(result, str)

    def test_classdefs_present(self):
        g = make_graph()
        result = to_mermaid(g)
        assert "classDef" in result

    def test_custom_diagram_type(self):
        g = make_graph()
        result = to_mermaid(g, diagram_type="flowchart LR")
        assert result.startswith("flowchart LR")


class TestToDot:
    def test_returns_string(self):
        g = make_graph()
        result = to_dot(g)
        assert isinstance(result, str)

    def test_valid_dot_syntax(self):
        g = make_graph()
        result = to_dot(g)
        assert "digraph" in result
        assert result.strip().endswith("}")

    def test_contains_all_nodes(self):
        g = make_graph()
        result = to_dot(g)
        for node in g.nodes:
            assert node.id in result

    def test_contains_edge_arrows(self):
        g = make_graph()
        result = to_dot(g)
        assert "->" in result

    def test_empty_graph(self):
        g = SessionGraph(slug="empty", goal="")
        result = to_dot(g)
        assert "digraph" in result


class TestToPlotlyHtml:
    def test_returns_string(self):
        g = make_graph()
        result = to_plotly_html(g)
        assert isinstance(result, str)

    def test_contains_html_tags(self):
        g = make_graph()
        result = to_plotly_html(g)
        assert "<html" in result.lower() or "plotly" in result.lower()

    def test_empty_graph(self):
        g = SessionGraph(slug="empty", goal="")
        result = to_plotly_html(g)
        assert isinstance(result, str)
