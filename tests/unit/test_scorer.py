"""Unit tests for SignificanceScorer."""

import pytest
from lesson.graph.schema import RawEvent
from lesson.nlp.scorer import SignificanceScorer, TFIDFScorer


def make_event(**kwargs) -> RawEvent:
    defaults = {"tool": "Bash", "args": "", "result_head": "", "is_error": False, "significant": False}
    defaults.update(kwargs)
    return RawEvent(**defaults)


class TestTFIDFScorer:
    def test_fit_returns_self(self):
        scorer = TFIDFScorer()
        assert scorer.fit(["hello world", "foo bar"]) is scorer

    def test_score_zero_before_fit(self):
        scorer = TFIDFScorer()
        assert scorer.score("hello") == 0.0

    def test_score_range(self):
        scorer = TFIDFScorer()
        texts = ["ModuleNotFoundError numpy", "pip install numpy", "python main.py", "ls /tmp"]
        scorer.fit(texts)
        for t in texts:
            s = scorer.score(t)
            assert 0.0 <= s <= 1.0, f"score {s} out of range for: {t}"

    def test_rare_terms_score_higher(self):
        scorer = TFIDFScorer()
        common = ["error error error error"] * 5 + ["unique_term_xyz"]
        scorer.fit(common)
        rare_score = scorer.score("unique_term_xyz")
        common_score = scorer.score("error error error")
        # rare token should score higher than omnipresent token
        assert rare_score > common_score

    def test_empty_corpus(self):
        scorer = TFIDFScorer()
        scorer.fit([])
        assert scorer.score("anything") == 0.0


class TestSignificanceScorer:
    def test_error_event_scores_high(self):
        ev = make_event(result_head="Traceback (most recent call last):", is_error=True)
        scorer = SignificanceScorer()
        scored = scorer.fit_score([ev])
        assert scored[0][1] > 0.3

    def test_edit_event_scores_above_plain_read(self):
        edit_ev = make_event(tool="Edit", args='{"file_path": "main.py"}', result_head="edited")
        read_ev = make_event(tool="Read", args='{"file_path": "config.json"}', result_head="contents")
        scorer = SignificanceScorer()
        scored = scorer.fit_score([edit_ev, read_ev])
        scores = {id(ev): s for ev, s in scored}
        assert scores[id(edit_ev)] > scores[id(read_ev)]

    def test_version_string_boosts_score(self):
        with_version = make_event(result_head="numpy 1.24.3 installed")
        without = make_event(result_head="done")
        scorer = SignificanceScorer()
        scored = scorer.fit_score([with_version, without])
        scores = {id(ev): s for ev, s in scored}
        assert scores[id(with_version)] > scores[id(without)]

    def test_fit_score_sorted_descending(self):
        events = [
            make_event(result_head="ModuleNotFoundError", is_error=True),
            make_event(result_head="ls output"),
            make_event(tool="Edit", args="file.py"),
        ]
        scorer = SignificanceScorer()
        scored = scorer.fit_score(events)
        scores = [s for _, s in scored]
        assert scores == sorted(scores, reverse=True)

    def test_annotate_preserves_order(self):
        events = [make_event(result_head=f"event {i}") for i in range(5)]
        scorer = SignificanceScorer()
        annotated = scorer.annotate(events)
        assert annotated is events  # in-place
        assert all(isinstance(e.score, float) for e in annotated)

    def test_all_scores_in_range(self):
        events = [
            make_event(is_error=True, result_head="fatal error"),
            make_event(tool="Write", args="path.py"),
            make_event(result_head="1.2.3 version mismatch"),
            make_event(result_head=""),
        ]
        scorer = SignificanceScorer()
        for ev, score in scorer.fit_score(events):
            assert 0.0 <= score <= 1.0, f"score {score} out of [0,1]"
