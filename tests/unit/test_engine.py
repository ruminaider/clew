"""Tests for SearchEngine confidence computation and rerank behavior."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest

from clew.models import SearchConfig
from clew.search.engine import SearchEngine
from clew.search.models import QueryIntent, SearchResult, SuggestionType


def _make_result(score: float, **kwargs) -> SearchResult:
    """Create a SearchResult with given score."""
    defaults = {
        "content": "def foo(): pass",
        "file_path": "src/main.py",
        "chunk_type": "function",
        "line_start": 1,
        "line_end": 1,
        "language": "python",
    }
    defaults.update(kwargs)
    return SearchResult(score=score, **defaults)


def _make_engine(config: SearchConfig | None = None) -> SearchEngine:
    """Create a SearchEngine with a mock hybrid engine."""
    hybrid = Mock()
    hybrid.search = AsyncMock(return_value=[])
    return SearchEngine(
        hybrid_engine=hybrid,
        search_config=config or SearchConfig(),
    )


class TestComputeConfidence:
    """Test _compute_confidence method."""

    def test_empty_results_returns_low(self):
        engine = _make_engine()
        confidence, label, suggestion = engine._compute_confidence([], was_reranked=False)
        assert confidence == 0.0
        assert label == "low"
        assert suggestion == SuggestionType.TRY_EXHAUSTIVE

    def test_reranked_high_confidence(self):
        engine = _make_engine()
        results = [_make_result(0.85), _make_result(0.3)]
        confidence, label, suggestion = engine._compute_confidence(results, was_reranked=True)
        assert confidence == 0.85
        assert label == "high"

    def test_reranked_medium_confidence(self):
        engine = _make_engine()
        results = [_make_result(0.5), _make_result(0.1)]
        confidence, label, suggestion = engine._compute_confidence(results, was_reranked=True)
        assert confidence == 0.5
        assert label == "medium"

    def test_reranked_low_confidence(self):
        engine = _make_engine()
        results = [_make_result(0.2), _make_result(0.05)]
        confidence, label, suggestion = engine._compute_confidence(results, was_reranked=True)
        assert confidence == 0.2
        assert label == "low"
        assert suggestion == SuggestionType.TRY_EXHAUSTIVE

    def test_rrf_high_confidence(self):
        """RRF path uses score gap of top-5 vs rest."""
        engine = _make_engine()
        # 6+ results needed to compute gap between #5 and #6
        results = [
            _make_result(0.10),
            _make_result(0.09),
            _make_result(0.08),
            _make_result(0.07),
            _make_result(0.06),
            _make_result(0.01),  # big gap from #5
        ]
        confidence, label, suggestion = engine._compute_confidence(results, was_reranked=False)
        # confidence = scores[4] - scores[5] = 0.06 - 0.01 = 0.05
        assert confidence == pytest.approx(0.05, abs=1e-9)
        assert label == "high"  # 0.05 >= 0.03 (rrf high threshold)

    def test_rrf_medium_confidence(self):
        engine = _make_engine()
        results = [
            _make_result(0.10),
            _make_result(0.09),
            _make_result(0.08),
            _make_result(0.07),
            _make_result(0.06),
            _make_result(0.045),  # small gap from #5
        ]
        confidence, label, suggestion = engine._compute_confidence(results, was_reranked=False)
        # confidence = 0.06 - 0.045 = 0.015
        assert confidence == pytest.approx(0.015, abs=1e-9)
        assert label == "medium"

    def test_rrf_low_confidence(self):
        engine = _make_engine()
        results = [
            _make_result(0.10),
            _make_result(0.09),
            _make_result(0.08),
            _make_result(0.07),
            _make_result(0.06),
            _make_result(0.055),  # tiny gap
        ]
        confidence, label, suggestion = engine._compute_confidence(results, was_reranked=False)
        # confidence = 0.06 - 0.055 = 0.005
        assert confidence == pytest.approx(0.005, abs=1e-9)
        assert label == "low"

    def test_rrf_fewer_than_6_results(self):
        """When fewer than 6 results, use last score as confidence."""
        engine = _make_engine()
        results = [_make_result(0.10), _make_result(0.08), _make_result(0.05)]
        confidence, label, suggestion = engine._compute_confidence(results, was_reranked=False)
        assert confidence == pytest.approx(0.05, abs=1e-9)
        assert label == "high"  # 0.05 >= 0.03

    def test_ambiguity_detection(self):
        """Small gap between #1 and #2 triggers LOW_CONFIDENCE."""
        engine = _make_engine()
        results = [_make_result(0.80), _make_result(0.79)]
        confidence, label, suggestion = engine._compute_confidence(results, was_reranked=True)
        assert suggestion == SuggestionType.LOW_CONFIDENCE

    def test_no_ambiguity_with_large_gap(self):
        """Large gap between #1 and #2 does not trigger ambiguity."""
        engine = _make_engine()
        results = [_make_result(0.90), _make_result(0.70)]
        confidence, label, suggestion = engine._compute_confidence(results, was_reranked=True)
        assert suggestion == SuggestionType.NONE

    def test_single_result_no_ambiguity(self):
        engine = _make_engine()
        results = [_make_result(0.90)]
        confidence, label, suggestion = engine._compute_confidence(results, was_reranked=True)
        assert suggestion == SuggestionType.NONE
        assert label == "high"


class TestMaybeRerank:
    """Test _maybe_rerank returns tuple and ENUMERATION skipping."""

    def test_no_reranker_returns_false(self):
        engine = _make_engine()
        candidates = [_make_result(0.9)]
        results, was_reranked = engine._maybe_rerank("test", candidates)
        assert results == candidates
        assert was_reranked is False

    def test_enumeration_skips_rerank(self):
        """ENUMERATION intent skips reranking even with reranker present."""
        reranker = Mock()
        engine = SearchEngine(
            hybrid_engine=Mock(),
            reranker=reranker,
        )
        candidates = [_make_result(0.5) for _ in range(20)]
        results, was_reranked = engine._maybe_rerank(
            "find all models", candidates, intent=QueryIntent.ENUMERATION
        )
        assert was_reranked is False
        reranker.rerank.assert_not_called()

    def test_reranking_returns_true(self):
        """When reranking happens, returns True."""
        from clew.search.rerank import RerankResult

        reranker = Mock()
        reranker.rerank.return_value = [
            RerankResult(index=1, relevance_score=0.9),
            RerankResult(index=0, relevance_score=0.7),
        ]
        config = SearchConfig(
            no_rerank_threshold=1,
            high_confidence_threshold=0.99,
            low_variance_threshold=0.001,
        )
        engine = SearchEngine(
            hybrid_engine=Mock(),
            reranker=reranker,
            search_config=config,
        )
        candidates = [_make_result(0.5), _make_result(0.4)]
        results, was_reranked = engine._maybe_rerank(
            "test query", candidates, intent=QueryIntent.CODE
        )
        assert was_reranked is True
        assert results[0].score == 0.9
        assert results[1].score == 0.7

    def test_skip_conditions_return_false(self):
        """When skip conditions are met, returns False even with reranker."""
        reranker = Mock()
        engine = SearchEngine(
            hybrid_engine=Mock(),
            reranker=reranker,
            search_config=SearchConfig(no_rerank_threshold=50),
        )
        candidates = [_make_result(0.9)]
        results, was_reranked = engine._maybe_rerank("test", candidates, intent=QueryIntent.CODE)
        assert was_reranked is False
        reranker.rerank.assert_not_called()
