"""Graph visualization: DOT, Mermaid, and Plotly export.

All output is generated deterministically from the SessionGraph structure —
never by asking an LLM to write diagram code.
"""

from __future__ import annotations

from lesson.graph.schema import EdgeType, NodeType, SessionGraph

# Node colors by type (used in DOT and Plotly)
_NODE_COLORS = {
    NodeType.goal: "#4A90D9",
    NodeType.observation: "#E8A838",
    NodeType.hypothesis: "#D9534F",
    NodeType.attempt: "#5CB85C",
    NodeType.concept: "#9B59B6",
    NodeType.resolution: "#1ABC9C",
}

_MERMAID_SHAPES = {
    NodeType.goal: ("([", "])"),
    NodeType.observation: ("[", "]"),
    NodeType.hypothesis: ("{", "}"),
    NodeType.attempt: ("(", ")"),
    NodeType.concept: ("[[", "]]"),
    NodeType.resolution: ("[(", ")]"),
}

_MERMAID_EDGE_LABELS = {
    EdgeType.motivated: "motivated",
    EdgeType.produced: "produced",
    EdgeType.revealed: "revealed",
    EdgeType.contradicted: "contradicted ⚠",
    EdgeType.seemed_to_confirm: "seemed to confirm",
    EdgeType.assumed_about: "assumed about",
    EdgeType.involves: "involves",
    EdgeType.enabled: "enabled",
    EdgeType.achieves: "achieves",
}


# ------------------------------------------------------------------
# Mermaid
# ------------------------------------------------------------------

def to_mermaid(graph: SessionGraph, diagram_type: str = "flowchart TD") -> str:
    """Generate a Mermaid diagram string from the SessionGraph.

    The output is raw Mermaid syntax (no fences — the markdown template adds them).
    """
    lines = [diagram_type]

    for node in graph.nodes:
        open_b, close_b = _MERMAID_SHAPES.get(node.type, ("[", "]"))
        label = node.label.replace('"', "'")[:60]
        flag_suffix = ""
        if node.is_root_cause:
            flag_suffix = " 🎯"
        if node.is_misconception:
            flag_suffix = " ⚠"
        lines.append(f'    {node.id}{open_b}"{label}{flag_suffix}"{close_b}')

    lines.append("")
    for edge in graph.edges:
        label = _MERMAID_EDGE_LABELS.get(edge.type, edge.type.value)
        lines.append(f"    {edge.from_id} -->|{label}| {edge.to_id}")

    # Add classDef styling
    lines.append("")
    lines.append("    classDef goal fill:#4A90D9,color:#fff")
    lines.append("    classDef observation fill:#E8A838,color:#fff")
    lines.append("    classDef hypothesis fill:#D9534F,color:#fff")
    lines.append("    classDef attempt fill:#5CB85C,color:#fff")
    lines.append("    classDef concept fill:#9B59B6,color:#fff")
    lines.append("    classDef resolution fill:#1ABC9C,color:#fff")

    for node in graph.nodes:
        lines.append(f"    class {node.id} {node.type.value}")

    return "\n".join(lines)


# ------------------------------------------------------------------
# DOT (Graphviz)
# ------------------------------------------------------------------

def to_dot(graph: SessionGraph) -> str:
    """Generate a Graphviz DOT string from the SessionGraph."""
    lines = ['digraph session {', '    rankdir=TD;', '    node [fontname="Helvetica"];']

    for node in graph.nodes:
        color = _NODE_COLORS.get(node.type, "#aaaaaa")
        label = node.label.replace('"', "'")[:60]
        shape = "box"
        if node.type == NodeType.goal:
            shape = "ellipse"
        elif node.type == NodeType.concept:
            shape = "diamond"
        elif node.type == NodeType.resolution:
            shape = "doubleoctagon"
        lines.append(
            f'    {node.id} [label="{label}" shape={shape} '
            f'style=filled fillcolor="{color}" fontcolor=white];'
        )

    for edge in graph.edges:
        label = _MERMAID_EDGE_LABELS.get(edge.type, edge.type.value)
        style = "dashed" if edge.type == EdgeType.contradicted else "solid"
        lines.append(f'    {edge.from_id} -> {edge.to_id} [label="{label}" style={style}];')

    lines.append("}")
    return "\n".join(lines)


# ------------------------------------------------------------------
# Plotly (interactive HTML)
# ------------------------------------------------------------------

def to_plotly_html(graph: SessionGraph, title: str = "Session Graph") -> str:
    """Generate a self-contained interactive HTML file via plotly.

    Falls back to an empty HTML page if plotly is not installed.
    """
    try:
        import plotly.graph_objects as go
        import networkx as nx
        from lesson.graph.algorithms import to_nx
    except ImportError:
        return f"<html><body><p>plotly/networkx required for interactive graph</p></body></html>"

    G = to_nx(graph)
    if G.number_of_nodes() == 0:
        return "<html><body><p>Empty graph</p></body></html>"

    pos = nx.spring_layout(G, seed=42)

    node_x, node_y, node_text, node_color, node_hover = [], [], [], [], []
    for node in graph.nodes:
        if node.id not in pos:
            continue
        x, y = pos[node.id]
        node_x.append(x)
        node_y.append(y)
        node_text.append(node.id)
        node_color.append(_NODE_COLORS.get(node.type, "#aaaaaa"))
        flags = ", ".join(k for k, v in node.flags.items() if v)
        node_hover.append(
            f"<b>{node.id}</b> [{node.type.value}]<br>{node.label[:80]}"
            + (f"<br><i>{flags}</i>" if flags else "")
        )

    edge_x, edge_y = [], []
    for edge in graph.edges:
        if edge.from_id not in pos or edge.to_id not in pos:
            continue
        x0, y0 = pos[edge.from_id]
        x1, y1 = pos[edge.to_id]
        edge_x += [x0, x1, None]
        edge_y += [y0, y1, None]

    edge_trace = go.Scatter(
        x=edge_x, y=edge_y,
        mode="lines",
        line=dict(width=1, color="#888"),
        hoverinfo="none",
    )
    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode="markers+text",
        hoverinfo="text",
        text=node_text,
        textposition="top center",
        hovertext=node_hover,
        marker=dict(size=18, color=node_color, line=dict(width=1, color="#333")),
    )

    fig = go.Figure(
        data=[edge_trace, node_trace],
        layout=go.Layout(
            title=title,
            showlegend=False,
            hovermode="closest",
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            margin=dict(l=20, r=20, t=40, b=20),
        ),
    )
    return fig.to_html(full_html=True, include_plotlyjs="cdn")
