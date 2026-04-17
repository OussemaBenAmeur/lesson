"""EventGraphBuilder — converts raw arc.jsonl events into a SessionGraph.

Replaces the lesson-compress LLM subagent with a deterministic, sub-100ms
pipeline:
  1. Score all events (SignificanceScorer)
  2. Extract entities (NLPExtractor)
  3. Promote high-score events to graph nodes
  4. Deduplicate via semantic similarity (NodeEmbedder)
  5. Wire edges encoding causality (not just sequence)
  6. Detect root cause via betweenness centrality (algorithms.py)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from lesson.graph.schema import (
    Edge,
    EdgeType,
    Node,
    NodeType,
    RawEvent,
    SessionGraph,
)
from lesson.nlp.embedder import NodeEmbedder
from lesson.nlp.extractor import EntityKind, NLPExtractor
from lesson.nlp.scorer import SignificanceScorer

# Events with score >= this threshold are promoted to nodes
_SIGNIFICANCE_THRESHOLD = 0.25

# Max nodes to create per compression batch (keeps graph lean)
_MAX_NODES_PER_BATCH = 12

_EDIT_TOOLS = frozenset({"Edit", "Write", "NotebookEdit"})


@dataclass
class CompressionResult:
    graph: SessionGraph
    events_processed: int
    nodes_added: int
    edges_added: int
    elapsed_ms: float
    archive_n: int = 0


class EventGraphBuilder:
    """Build and incrementally update a SessionGraph from raw events.

    Usage::

        builder = EventGraphBuilder()
        result = builder.compress(events, existing_graph)
    """

    def __init__(
        self,
        threshold: float = _SIGNIFICANCE_THRESHOLD,
        max_nodes: int = _MAX_NODES_PER_BATCH,
        use_embedder: bool = True,
    ) -> None:
        self._threshold = threshold
        self._max_nodes = max_nodes
        self._scorer = SignificanceScorer()
        self._extractor = NLPExtractor()
        self._embedder = NodeEmbedder() if use_embedder else None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compress(
        self,
        events: list[RawEvent],
        graph: SessionGraph,
    ) -> CompressionResult:
        t0 = time.perf_counter()

        nodes_before = len(graph.nodes)
        edges_before = len(graph.edges)

        if not events:
            return CompressionResult(
                graph=graph,
                events_processed=0,
                nodes_added=0,
                edges_added=0,
                elapsed_ms=0.0,
            )

        # 1. Score
        scored = self._scorer.fit_score(events)

        # 2. Select top candidates (up to max_nodes budget)
        candidates = [
            (ev, score) for ev, score in scored
            if score >= self._threshold
        ][: self._max_nodes]

        # Keep temporal order for edge wiring
        candidates_ordered = sorted(candidates, key=lambda x: x[0].ts)

        # 3. Promote to nodes
        prev_node: Node | None = None
        prev_was_attempt = False

        for ev, score in candidates_ordered:
            node = self._promote(ev, score, graph)
            if node is None:
                continue

            # 4. Wire edges
            if prev_node is not None:
                self._wire_edge(prev_node, node, ev, graph)

            # Detect resolution: an attempt whose result has no error markers,
            # following a prior error observation
            if (
                node.type == NodeType.attempt
                and not ev.is_error
                and prev_was_attempt
                and self._has_prior_errors(graph)
                and not graph.nodes_of_type(NodeType.resolution)
            ):
                res = self._make_resolution(ev, node, graph)
                if res:
                    prev_node = res
                    prev_was_attempt = False
                    continue

            prev_node = node
            prev_was_attempt = node.type == NodeType.attempt

        # 5. Refresh root cause via centrality (imported lazily to avoid circulars)
        self._refresh_root_cause(graph)

        graph.total_events_compressed += len(events)

        elapsed_ms = (time.perf_counter() - t0) * 1000
        return CompressionResult(
            graph=graph,
            events_processed=len(events),
            nodes_added=len(graph.nodes) - nodes_before,
            edges_added=len(graph.edges) - edges_before,
            elapsed_ms=elapsed_ms,
        )

    # ------------------------------------------------------------------
    # Node promotion
    # ------------------------------------------------------------------

    def _promote(
        self,
        ev: RawEvent,
        score: float,
        graph: SessionGraph,
    ) -> Node | None:
        node_type = self._classify(ev)
        label = self._make_label(ev, node_type)
        if not label:
            return None

        # Dedup check
        same_type_nodes = graph.nodes_of_type(node_type)
        if self._embedder:
            dup = self._embedder.find_duplicate(label, same_type_nodes)
            if dup:
                return dup  # reuse existing node

        flags: dict = {}
        if ev.is_error and node_type == NodeType.observation:
            # Check if any attempt preceded this — makes it pivotal
            if graph.nodes_of_type(NodeType.attempt):
                flags["pivotal"] = True

        node = Node(
            id=graph.alloc_id(node_type),
            type=node_type,
            label=label,
            flags=flags,
        )
        graph.nodes.append(node)
        return node

    def _classify(self, ev: RawEvent) -> NodeType:
        if ev.is_error:
            return NodeType.observation
        if ev.tool in _EDIT_TOOLS:
            return NodeType.attempt
        if ev.tool == "Bash":
            # Bash with error-like output → observation; otherwise attempt
            lower = ev.result_head.lower()
            error_words = ["error", "failed", "not found", "exception", "traceback"]
            if any(w in lower for w in error_words):
                return NodeType.observation
            return NodeType.attempt
        if ev.tool in ("Read", "Glob", "Grep"):
            return NodeType.observation
        return NodeType.attempt

    def _make_label(self, ev: RawEvent, node_type: NodeType) -> str:
        if ev.is_error:
            # Use first non-empty line of result as label
            for line in ev.result_head.splitlines():
                line = line.strip()
                if line and len(line) > 3:
                    return line[:120]

        entities = self._extractor.extract(ev)

        # Concept candidates get priority as labels
        concepts = [e for e in entities if e.kind == EntityKind.error_code]
        if concepts:
            return concepts[0].text

        # File path for Read/Edit/Write
        paths = [e for e in entities if e.kind == EntityKind.file_path]
        if paths and ev.tool in _EDIT_TOOLS | {"Read"}:
            return f"{ev.tool} {paths[0].text}"

        # Package name for installs
        pkgs = [e for e in entities if e.kind == EntityKind.package]
        if pkgs:
            return f"install {pkgs[0].text}"

        # Bash: use command + first arg token
        if ev.tool == "Bash" and ev.args:
            return ev.args.strip()[:80]

        # Generic fallback
        return f"{ev.tool}: {ev.result_head[:60]}".strip(": ")

    # ------------------------------------------------------------------
    # Edge wiring
    # ------------------------------------------------------------------

    def _wire_edge(
        self,
        prev: Node,
        curr: Node,
        ev: RawEvent,
        graph: SessionGraph,
    ) -> None:
        edge_type = self._infer_edge_type(prev, curr, ev)
        if edge_type is None:
            return
        # Avoid duplicate edges
        for existing in graph.edges:
            if existing.from_id == prev.id and existing.to_id == curr.id:
                return
        graph.edges.append(Edge(from_id=prev.id, to_id=curr.id, type=edge_type))

    def _infer_edge_type(
        self,
        prev: Node,
        curr: Node,
        ev: RawEvent,
    ) -> EdgeType | None:
        p, c = prev.type, curr.type

        if p == NodeType.attempt and c == NodeType.observation:
            return EdgeType.produced
        if p == NodeType.observation and c == NodeType.attempt:
            return None  # no direct edge — will be mediated by hypothesis if any
        if p == NodeType.observation and c == NodeType.concept:
            return EdgeType.revealed
        if p == NodeType.hypothesis and c == NodeType.attempt:
            return EdgeType.motivated
        if p == NodeType.observation and c == NodeType.hypothesis:
            return EdgeType.contradicted if ev.is_error else EdgeType.seemed_to_confirm
        if p == NodeType.concept and c == NodeType.resolution:
            return EdgeType.enabled
        if p == NodeType.resolution and c == NodeType.goal:
            return EdgeType.achieves
        if p == NodeType.attempt and c == NodeType.resolution:
            return EdgeType.enabled

        return None

    # ------------------------------------------------------------------
    # Resolution detection
    # ------------------------------------------------------------------

    def _make_resolution(
        self,
        ev: RawEvent,
        trigger_node: Node,
        graph: SessionGraph,
    ) -> Node | None:
        label = f"resolved via {self._make_label(ev, NodeType.attempt)}"
        node = Node(
            id=graph.alloc_id(NodeType.resolution),
            type=NodeType.resolution,
            label=label[:120],
        )
        graph.nodes.append(node)
        graph.resolution_id = node.id

        # Wire: trigger_node → resolution → goal
        graph.edges.append(Edge(from_id=trigger_node.id, to_id=node.id, type=EdgeType.enabled))
        goal_nodes = graph.nodes_of_type(NodeType.goal)
        if goal_nodes:
            graph.edges.append(Edge(from_id=node.id, to_id=goal_nodes[0].id, type=EdgeType.achieves))

        return node

    def _has_prior_errors(self, graph: SessionGraph) -> bool:
        return any(n.is_pivotal or n.flags.get("pivotal") for n in graph.nodes)

    # ------------------------------------------------------------------
    # Root cause refresh
    # ------------------------------------------------------------------

    def _refresh_root_cause(self, graph: SessionGraph) -> None:
        from lesson.graph.algorithms import find_root_cause
        rc = find_root_cause(graph)
        if rc:
            # Clear old flags
            for n in graph.nodes:
                n.flags.pop("root_cause", None)
            rc.flags["root_cause"] = True
            graph.root_cause_id = rc.id
