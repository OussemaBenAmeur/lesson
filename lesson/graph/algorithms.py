"""Graph algorithms for session knowledge graphs using networkx.

All functions accept a SessionGraph and return results in terms of the
original schema types (Node, Edge) — never raw networkx objects.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import networkx as nx

from lesson.graph.schema import EdgeType, Node, NodeType, SessionGraph

if TYPE_CHECKING:
    pass


# ------------------------------------------------------------------
# Conversion
# ------------------------------------------------------------------

def to_nx(graph: SessionGraph) -> nx.DiGraph:
    """Convert SessionGraph to a networkx DiGraph."""
    G = nx.DiGraph()
    for node in graph.nodes:
        G.add_node(node.id, node=node, type=node.type.value, label=node.label)
    for edge in graph.edges:
        G.add_edge(edge.from_id, edge.to_id, type=edge.type.value)
    return G


# ------------------------------------------------------------------
# Root cause detection
# ------------------------------------------------------------------

def find_root_cause(graph: SessionGraph) -> Node | None:
    """Return the concept node that is most central to the debugging arc.

    Uses betweenness centrality on concept nodes only. Falls back to the
    concept node with the most incoming 'revealed' edges if the graph has
    no paths (disconnected).
    """
    concept_nodes = graph.nodes_of_type(NodeType.concept)
    if not concept_nodes:
        return None
    if len(concept_nodes) == 1:
        return concept_nodes[0]

    G = to_nx(graph)
    concept_ids = {n.id for n in concept_nodes}

    try:
        centrality = nx.betweenness_centrality(G, normalized=True)
        best_id = max(concept_ids, key=lambda nid: centrality.get(nid, 0.0))
        return graph.node_by_id(best_id)
    except Exception:
        pass

    # Fallback: most incoming 'revealed' edges
    incoming = {n.id: 0 for n in concept_nodes}
    for edge in graph.edges:
        if edge.type == EdgeType.revealed and edge.to_id in incoming:
            incoming[edge.to_id] += 1
    best_id = max(incoming, key=lambda k: incoming[k])
    return graph.node_by_id(best_id)


# ------------------------------------------------------------------
# Causal chain
# ------------------------------------------------------------------

def find_causal_chain(graph: SessionGraph) -> list[Node]:
    """Return the shortest path from the goal node to the resolution node.

    Returns an empty list if no path exists.
    """
    goal_nodes = graph.nodes_of_type(NodeType.goal)
    if not goal_nodes or not graph.resolution_id:
        return []

    G = to_nx(graph)
    try:
        path_ids = nx.shortest_path(G, goal_nodes[0].id, graph.resolution_id)
        return [graph.node_by_id(nid) for nid in path_ids if graph.node_by_id(nid)]
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return []


# ------------------------------------------------------------------
# Misconception detection
# ------------------------------------------------------------------

def find_misconceptions(graph: SessionGraph) -> list[Node]:
    """Return hypothesis nodes that have at least one 'contradicted' incoming edge."""
    contradicted_ids = {
        e.to_id for e in graph.edges if e.type == EdgeType.contradicted
    }
    return [
        n for n in graph.nodes
        if n.type == NodeType.hypothesis and n.id in contradicted_ids
    ]


# ------------------------------------------------------------------
# Pivotal observations
# ------------------------------------------------------------------

def find_pivotal_observations(graph: SessionGraph) -> list[Node]:
    """Return observation nodes on the causal chain or flagged as pivotal."""
    chain = {n.id for n in find_causal_chain(graph)}
    return [
        n for n in graph.nodes
        if n.type == NodeType.observation
        and (n.id in chain or n.is_pivotal)
    ]


# ------------------------------------------------------------------
# Community detection (for /lesson-map)
# ------------------------------------------------------------------

def detect_communities(graph: SessionGraph) -> list[list[Node]]:
    """Partition graph nodes into communities using the Louvain algorithm.

    Returns a list of communities, each community is a list of Node objects.
    Falls back to weakly connected components if Louvain is unavailable.
    """
    G = to_nx(graph).to_undirected()
    if G.number_of_nodes() == 0:
        return []

    try:
        from networkx.algorithms.community import louvain_communities
        raw = louvain_communities(G)
    except (ImportError, AttributeError):
        raw = list(nx.weakly_connected_components(to_nx(graph)))

    communities: list[list[Node]] = []
    for community_ids in raw:
        nodes = [graph.node_by_id(nid) for nid in community_ids if graph.node_by_id(nid)]
        if nodes:
            communities.append(nodes)
    return communities


# ------------------------------------------------------------------
# Graph health metrics
# ------------------------------------------------------------------

def graph_metrics(graph: SessionGraph) -> dict:
    """Return a dict of health metrics for the graph."""
    G = to_nx(graph)
    n = G.number_of_nodes()
    e = G.number_of_edges()

    is_dag = nx.is_directed_acyclic_graph(G)

    # Orphan nodes (no edges at all)
    orphans = [nid for nid in G.nodes if G.degree(nid) == 0]

    # Weakly connected components
    wcc = list(nx.weakly_connected_components(G))

    return {
        "nodes": n,
        "edges": e,
        "is_dag": is_dag,
        "orphan_count": len(orphans),
        "orphan_ids": orphans,
        "weakly_connected_components": len(wcc),
        "has_root_cause": graph.root_cause_id is not None,
        "has_resolution": graph.resolution_id is not None,
        "concept_count": len(graph.nodes_of_type(NodeType.concept)),
        "observation_count": len(graph.nodes_of_type(NodeType.observation)),
        "attempt_count": len(graph.nodes_of_type(NodeType.attempt)),
    }


# ------------------------------------------------------------------
# DAG validation
# ------------------------------------------------------------------

def is_valid(graph: SessionGraph) -> tuple[bool, list[str]]:
    """Validate graph structure. Returns (ok, list_of_issues)."""
    issues: list[str] = []
    node_ids = {n.id for n in graph.nodes}

    # Referential integrity
    for edge in graph.edges:
        if edge.from_id not in node_ids:
            issues.append(f"Edge {edge.from_id}→{edge.to_id}: from_id missing")
        if edge.to_id not in node_ids:
            issues.append(f"Edge {edge.from_id}→{edge.to_id}: to_id missing")

    # Duplicate IDs
    ids = [n.id for n in graph.nodes]
    seen: set[str] = set()
    for nid in ids:
        if nid in seen:
            issues.append(f"Duplicate node ID: {nid}")
        seen.add(nid)

    # root_cause_id / resolution_id consistency
    if graph.root_cause_id and graph.root_cause_id not in node_ids:
        issues.append(f"root_cause_id {graph.root_cause_id} not in nodes")
    if graph.resolution_id and graph.resolution_id not in node_ids:
        issues.append(f"resolution_id {graph.resolution_id} not in nodes")

    return len(issues) == 0, issues
