"""Graph quality metrics for evaluating compression pipeline output.

Used by benchmark.py to compare algorithmic compression against LLM baseline.
All metrics are computed without requiring a trained model.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from lesson.graph.schema import NodeType, SessionGraph


@dataclass
class GraphQualityReport:
    """Quality metrics for a predicted graph vs. a gold-standard graph."""

    node_precision: float = 0.0
    node_recall: float = 0.0
    node_f1: float = 0.0
    edge_accuracy: float = 0.0
    compression_ratio: float = 0.0
    has_root_cause: bool = False
    has_resolution: bool = False
    is_dag: bool = False
    orphan_count: int = 0
    graph_quality_score: float = 0.0

    def summary(self) -> str:
        return (
            f"F1={self.node_f1:.3f} "
            f"edge_acc={self.edge_accuracy:.3f} "
            f"compress={self.compression_ratio:.2f} "
            f"quality={self.graph_quality_score:.3f}"
        )


def _label_set(graph: SessionGraph, node_type: NodeType | None = None) -> set[str]:
    nodes = graph.nodes if node_type is None else graph.nodes_of_type(node_type)
    return {n.label.lower().strip() for n in nodes}


def _token_overlap(a: str, b: str) -> float:
    """Jaccard similarity between token sets of two strings."""
    ta = set(a.lower().split())
    tb = set(b.lower().split())
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _fuzzy_match(label: str, gold_labels: set[str], threshold: float = 0.4) -> bool:
    """True if label has token overlap ≥ threshold with any gold label."""
    for gold in gold_labels:
        if _token_overlap(label, gold) >= threshold:
            return True
    return False


def node_precision_recall(predicted: SessionGraph, gold: SessionGraph) -> tuple[float, float]:
    """Compute node-level precision and recall using fuzzy label matching."""
    pred_labels = _label_set(predicted)
    gold_labels = _label_set(gold)

    if not pred_labels:
        return 0.0, 0.0
    if not gold_labels:
        return 0.0, 0.0

    # Precision: how many predicted nodes match a gold node?
    true_positives_p = sum(1 for l in pred_labels if _fuzzy_match(l, gold_labels))
    precision = true_positives_p / len(pred_labels)

    # Recall: how many gold nodes are covered by predictions?
    true_positives_r = sum(1 for l in gold_labels if _fuzzy_match(l, pred_labels))
    recall = true_positives_r / len(gold_labels)

    return precision, recall


def f1(precision: float, recall: float) -> float:
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def edge_accuracy(predicted: SessionGraph, gold: SessionGraph) -> float:
    """Fraction of gold edge types present in predicted graph."""
    if not gold.edges:
        return 1.0
    gold_types = {e.type for e in gold.edges}
    pred_types = {e.type for e in predicted.edges}
    return len(gold_types & pred_types) / len(gold_types)


def compression_ratio(n_events: int, graph: SessionGraph) -> float:
    """Nodes created per event. Lower = more aggressive compression."""
    if n_events == 0:
        return 0.0
    non_goal = [n for n in graph.nodes if n.type != NodeType.goal]
    return len(non_goal) / n_events


def graph_quality_score(
    node_f1: float,
    edge_acc: float,
    has_root_cause: bool,
    has_resolution: bool,
    orphan_count: int,
) -> float:
    """Weighted composite quality score in [0, 1]."""
    orphan_penalty = min(orphan_count * 0.05, 0.3)
    rc_bonus = 0.1 if has_root_cause else 0.0
    res_bonus = 0.1 if has_resolution else 0.0

    score = (
        0.50 * node_f1
        + 0.25 * edge_acc
        + rc_bonus
        + res_bonus
        - orphan_penalty
    )
    return max(0.0, min(1.0, score))


def evaluate(
    predicted: SessionGraph,
    gold: SessionGraph,
    n_input_events: int,
) -> GraphQualityReport:
    """Compute full quality report for a predicted graph."""
    from lesson.graph.algorithms import graph_metrics

    prec, rec = node_precision_recall(predicted, gold)
    f1_score = f1(prec, rec)
    edge_acc = edge_accuracy(predicted, gold)
    c_ratio = compression_ratio(n_input_events, predicted)

    metrics = graph_metrics(predicted)

    qs = graph_quality_score(
        node_f1=f1_score,
        edge_acc=edge_acc,
        has_root_cause=metrics["has_root_cause"],
        has_resolution=metrics["has_resolution"],
        orphan_count=metrics["orphan_count"],
    )

    return GraphQualityReport(
        node_precision=prec,
        node_recall=rec,
        node_f1=f1_score,
        edge_accuracy=edge_acc,
        compression_ratio=c_ratio,
        has_root_cause=metrics["has_root_cause"],
        has_resolution=metrics["has_resolution"],
        is_dag=metrics["is_dag"],
        orphan_count=metrics["orphan_count"],
        graph_quality_score=qs,
    )
