"""Property-based tests using Hypothesis.

These verify invariants that must hold across all possible inputs,
not just the hand-crafted fixtures.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from lesson.graph.algorithms import is_valid
from lesson.graph.builder import EventGraphBuilder
from lesson.graph.schema import NodeType, RawEvent, SessionGraph

# Strategy: generate a list of RawEvents
_TOOLS = ["Bash", "Edit", "Write", "Read", "Glob", "Grep"]
_RESULTS = [
    "ModuleNotFoundError: no module named 'foo'",
    "Successfully installed package-1.2.3",
    "error: ENOENT: no such file",
    "Compiled successfully.",
    "Traceback (most recent call last):",
    "done",
    "",
    "fatal: repository not found",
    "1.0.0 version mismatch",
]

raw_event_strategy = st.builds(
    RawEvent,
    tool=st.sampled_from(_TOOLS),
    args=st.text(max_size=80),
    result_head=st.sampled_from(_RESULTS),
    is_error=st.booleans(),
    significant=st.booleans(),
    ts=st.floats(min_value=1_700_000_000.0, max_value=1_800_000_000.0, allow_nan=False),
)


@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
@given(events=st.lists(raw_event_strategy, min_size=0, max_size=30))
def test_graph_always_valid_after_compression(events):
    """For any input, the resulting graph must pass structural validation."""
    g = SessionGraph.empty("prop-test", "property test goal")
    builder = EventGraphBuilder(use_embedder=False, threshold=0.0)
    result = builder.compress(events, g)
    ok, issues = is_valid(result.graph)
    assert ok, f"Invalid graph for {len(events)} events: {issues}"


@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
@given(events=st.lists(raw_event_strategy, min_size=1, max_size=30))
def test_no_duplicate_node_ids(events):
    """Node IDs must always be unique."""
    g = SessionGraph.empty("prop-test", "goal")
    builder = EventGraphBuilder(use_embedder=False, threshold=0.0)
    result = builder.compress(events, g)
    ids = [n.id for n in result.graph.nodes]
    assert len(ids) == len(set(ids)), f"Duplicate IDs: {ids}"


@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
@given(events=st.lists(raw_event_strategy, min_size=0, max_size=30))
def test_total_events_compressed_matches_input(events):
    """total_events_compressed must equal len(events) after one compression."""
    g = SessionGraph.empty("prop-test", "goal")
    builder = EventGraphBuilder(use_embedder=False, threshold=0.0)
    result = builder.compress(events, g)
    assert result.graph.total_events_compressed == len(events)


@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
@given(events=st.lists(raw_event_strategy, min_size=0, max_size=30))
def test_root_cause_id_points_to_existing_concept(events):
    """If root_cause_id is set, it must reference an actual concept node."""
    g = SessionGraph.empty("prop-test", "goal")
    builder = EventGraphBuilder(use_embedder=False, threshold=0.0)
    result = builder.compress(events, g)
    graph = result.graph
    if graph.root_cause_id:
        node = graph.node_by_id(graph.root_cause_id)
        assert node is not None, "root_cause_id references nonexistent node"
        assert node.type == NodeType.concept, f"root_cause_id points to {node.type}, not concept"


@settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
@given(
    events1=st.lists(raw_event_strategy, min_size=1, max_size=15),
    events2=st.lists(raw_event_strategy, min_size=1, max_size=15),
)
def test_incremental_compression_preserves_ids(events1, events2):
    """IDs assigned in the first compression must survive the second."""
    g = SessionGraph.empty("prop-test", "goal")
    builder = EventGraphBuilder(use_embedder=False, threshold=0.0)

    r1 = builder.compress(events1, g)
    ids_after_first = {n.id for n in r1.graph.nodes}

    r2 = builder.compress(events2, r1.graph)
    ids_after_second = {n.id for n in r2.graph.nodes}

    assert ids_after_first.issubset(ids_after_second), (
        f"IDs disappeared: {ids_after_first - ids_after_second}"
    )
