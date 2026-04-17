"""Significance scorer for raw arc.jsonl events.

Replaces the boolean _is_significant heuristic in hooks/post_tool_use.py with a
float-valued composite scorer: TF-IDF novelty + error signal + edit signal.
All computation is deterministic and LLM-free.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lesson.graph.schema import RawEvent

_EDIT_TOOLS = frozenset({"Edit", "Write", "NotebookEdit"})

_ERROR_PATTERNS = [
    "error", "failed", "not found", "no such file", "permission denied",
    "mismatch", "cannot", "unable to", "exception", "traceback", "fatal",
    "warning:", "refused", "denied", "unrecognized", "invalid", "undefined",
    "missing", "syntax error", "importerror", "modulenotfounderror",
    "typeerror", "valueerror", "keyerror", "attributeerror",
]

_VERSION_RE = re.compile(r"\b\d+\.\d+[\.\d]*\b")
_PATH_RE = re.compile(r"(?:/[\w.\-]+){2,}")
_HEX_RE = re.compile(r"\b[0-9a-f]{6,}\b")

# Weight constants — tuned empirically on synthetic sessions
_W_TFIDF = 0.40
_W_ERROR = 0.35
_W_EDIT = 0.15
_W_VERSION = 0.10


def _tokenize(text: str) -> list[str]:
    """Simple whitespace + punctuation tokenizer, lowercased."""
    return re.findall(r"[a-zA-Z_][\w]*", text.lower())


@dataclass
class TFIDFScorer:
    """Fit on a batch of texts; score each by normalized TF-IDF sum."""

    _idf: dict[str, float] = field(default_factory=dict)
    _fitted: bool = False

    def fit(self, texts: list[str]) -> "TFIDFScorer":
        n = len(texts)
        if n == 0:
            return self
        doc_freq: Counter[str] = Counter()
        for text in texts:
            doc_freq.update(set(_tokenize(text)))
        self._idf = {
            term: math.log((n + 1) / (df + 1)) + 1.0
            for term, df in doc_freq.items()
        }
        self._fitted = True
        return self

    def score(self, text: str) -> float:
        if not self._fitted or not self._idf:
            return 0.0
        tokens = _tokenize(text)
        if not tokens:
            return 0.0
        tf: Counter[str] = Counter(tokens)
        total = sum(tf[t] * self._idf.get(t, 0.0) for t in tf)
        return min(total / (len(tokens) * max(self._idf.values(), default=1.0)), 1.0)


class SignificanceScorer:
    """Composite significance scorer for a batch of RawEvents.

    Usage::

        scorer = SignificanceScorer()
        scored = scorer.fit_score(events)  # list of (event, float) sorted desc
    """

    def __init__(self, tfidf_weight: float = _W_TFIDF) -> None:
        self._tfidf_weight = tfidf_weight
        self._tfidf = TFIDFScorer()

    def fit(self, events: list["RawEvent"]) -> "SignificanceScorer":
        corpus = [f"{e.args} {e.result_head}" for e in events]
        self._tfidf.fit(corpus)
        return self

    def score_one(self, event: "RawEvent") -> float:
        text = f"{event.args} {event.result_head}"
        lower = text.lower()

        tfidf = self._tfidf.score(text)

        error_score = 0.0
        if event.is_error:
            error_score = 1.0
        elif any(p in lower for p in _ERROR_PATTERNS):
            error_score = 0.6

        edit_score = 1.0 if event.tool in _EDIT_TOOLS else 0.0

        version_score = 0.0
        if _VERSION_RE.search(text):
            version_score = 0.5
        if _PATH_RE.search(text):
            version_score = max(version_score, 0.3)

        composite = (
            _W_TFIDF * tfidf
            + _W_ERROR * error_score
            + _W_EDIT * edit_score
            + _W_VERSION * version_score
        )
        return min(composite, 1.0)

    def fit_score(self, events: list["RawEvent"]) -> list[tuple["RawEvent", float]]:
        """Fit on batch and return (event, score) pairs sorted descending."""
        self.fit(events)
        scored = [(e, self.score_one(e)) for e in events]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    def annotate(self, events: list["RawEvent"]) -> list["RawEvent"]:
        """Return events with .score set in-place (preserves original order)."""
        self.fit(events)
        for ev in events:
            ev.score = self.score_one(ev)
        return events
