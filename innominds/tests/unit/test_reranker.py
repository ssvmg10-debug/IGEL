"""Unit tests for knowledge_base.reranker (pure scoring functions)."""
import pytest
from unittest.mock import patch, MagicMock

from knowledge_base.reranker import (
    RerankItem,
    _score_by_rank_fallback,
    _normalize_scores,
)


# ── _score_by_rank_fallback ───────────────────────────────────────────────────

class TestScoreByRankFallback:

    def test_empty_list(self):
        assert _score_by_rank_fallback([]) == []

    def test_single_item_scores_one(self):
        items = [RerankItem(child_chunk_id="c1", passage="text")]
        result = _score_by_rank_fallback(items)
        assert len(result) == 1
        assert result[0] == ("c1", 1.0)

    def test_scores_decrease_by_rank(self):
        items = [
            RerankItem(child_chunk_id="c1", passage="first"),
            RerankItem(child_chunk_id="c2", passage="second"),
            RerankItem(child_chunk_id="c3", passage="third"),
        ]
        result = _score_by_rank_fallback(items)
        scores = [s for _, s in result]
        assert scores[0] > scores[1] > scores[2]

    def test_first_item_score_is_one(self):
        items = [
            RerankItem(child_chunk_id="c1", passage="a"),
            RerankItem(child_chunk_id="c2", passage="b"),
        ]
        result = _score_by_rank_fallback(items)
        assert result[0][1] == 1.0

    def test_preserves_chunk_ids(self):
        items = [
            RerankItem(child_chunk_id="alpha", passage="x"),
            RerankItem(child_chunk_id="beta", passage="y"),
        ]
        result = _score_by_rank_fallback(items)
        ids = [cid for cid, _ in result]
        assert "alpha" in ids
        assert "beta" in ids


# ── _normalize_scores ─────────────────────────────────────────────────────────

class TestNormalizeScores:

    def test_empty_list(self):
        assert _normalize_scores([]) == []

    def test_single_item_gets_half(self):
        result = _normalize_scores([("c1", 5.0)])
        assert result == [("c1", 0.5)]

    def test_normalizes_to_zero_one(self):
        pairs = [("c1", 10.0), ("c2", 5.0), ("c3", 0.0)]
        result = _normalize_scores(pairs)
        scores = [s for _, s in result]
        assert max(scores) == 1.0
        assert min(scores) == 0.0

    def test_equal_scores_all_half(self):
        pairs = [("c1", 3.0), ("c2", 3.0), ("c3", 3.0)]
        result = _normalize_scores(pairs)
        for _, score in result:
            assert score == 0.5

    def test_preserves_order(self):
        pairs = [("a", 1.0), ("b", 2.0), ("c", 3.0)]
        result = _normalize_scores(pairs)
        ids = [cid for cid, _ in result]
        assert ids == ["a", "b", "c"]

    def test_negative_scores(self):
        pairs = [("a", -10.0), ("b", 0.0), ("c", 10.0)]
        result = _normalize_scores(pairs)
        scores = [s for _, s in result]
        assert scores[0] == 0.0
        assert scores[2] == 1.0
