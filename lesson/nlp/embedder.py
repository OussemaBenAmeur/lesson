"""Semantic node deduplication via sentence-transformers.

Uses all-MiniLM-L6-v2 (~22MB, CPU-fast) to embed node labels and find
near-duplicates before graph insertion. Falls back to exact-string matching
if the model is unavailable.
"""

from __future__ import annotations

import numpy as np
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lesson.graph.schema import Node

_DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
_DEFAULT_THRESHOLD = 0.85


class NodeEmbedder:
    """Embed node labels and detect semantic near-duplicates.

    Usage::

        embedder = NodeEmbedder()
        dup = embedder.find_duplicate("ModuleNotFoundError", existing_nodes)
        if dup:
            # merge into dup instead of creating a new node
    """

    def __init__(
        self,
        model_name: str = _DEFAULT_MODEL,
        threshold: float = _DEFAULT_THRESHOLD,
    ) -> None:
        self._model_name = model_name
        self._threshold = threshold
        self._model = None
        self._cache: dict[str, np.ndarray] = {}

    def _load(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self._model_name)
            except Exception:
                self._model = False  # sentinel: unavailable

    def _encode(self, texts: list[str]) -> np.ndarray | None:
        self._load()
        if self._model is False:
            return None
        uncached = [t for t in texts if t not in self._cache]
        if uncached:
            vecs = self._model.encode(uncached, normalize_embeddings=True, show_progress_bar=False)
            for t, v in zip(uncached, vecs):
                self._cache[t] = v
        return np.vstack([self._cache[t] for t in texts])

    def _cosine(self, a: np.ndarray, b: np.ndarray) -> float:
        return float(np.dot(a, b))  # both are L2-normalized

    def find_duplicate(
        self,
        label: str,
        candidates: list["Node"],
        threshold: float | None = None,
    ) -> "Node | None":
        """Return the best-matching existing node, or None if no duplicate found.

        Falls back to case-insensitive exact match when embeddings unavailable.
        """
        if not candidates:
            return None
        t = threshold if threshold is not None else self._threshold
        label_lower = label.strip().lower()

        # Fast path: exact string match
        for node in candidates:
            if node.label.strip().lower() == label_lower:
                return node

        # Semantic similarity path
        all_labels = [label] + [n.label for n in candidates]
        vecs = self._encode(all_labels)
        if vecs is None:
            # No model — skip semantic dedup
            return None

        query_vec = vecs[0]
        best_score = 0.0
        best_node = None
        for node, vec in zip(candidates, vecs[1:]):
            s = self._cosine(query_vec, vec)
            if s > best_score:
                best_score = s
                best_node = node

        return best_node if best_score >= t else None

    def cluster(
        self,
        labels: list[str],
        threshold: float | None = None,
    ) -> list[list[int]]:
        """Cluster label indices by semantic similarity.

        Returns a list of clusters (each cluster = list of indices into labels).
        """
        if not labels:
            return []
        t = threshold if threshold is not None else self._threshold
        vecs = self._encode(labels)
        if vecs is None:
            return [[i] for i in range(len(labels))]

        clusters: list[list[int]] = []
        assigned = [False] * len(labels)
        for i in range(len(labels)):
            if assigned[i]:
                continue
            cluster = [i]
            assigned[i] = True
            for j in range(i + 1, len(labels)):
                if not assigned[j] and self._cosine(vecs[i], vecs[j]) >= t:
                    cluster.append(j)
                    assigned[j] = True
            clusters.append(cluster)
        return clusters
