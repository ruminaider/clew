"""Tests for local reranking providers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from clew.search.rerank_base import RerankResult
from clew.search.rerank_local import FlashRankRerankProvider, NoopRerankProvider


class TestNoopRerankProvider:
    @pytest.fixture
    def provider(self) -> NoopRerankProvider:
        return NoopRerankProvider()

    def test_model_name(self, provider: NoopRerankProvider) -> None:
        assert provider.model_name == "noop"

    def test_rerank_empty(self, provider: NoopRerankProvider) -> None:
        assert provider.rerank("query", []) == []

    def test_rerank_preserves_order(self, provider: NoopRerankProvider) -> None:
        results = provider.rerank("query", ["doc1", "doc2", "doc3"])
        indices = [r.index for r in results]
        assert indices == [0, 1, 2]

    def test_rerank_decaying_scores(self, provider: NoopRerankProvider) -> None:
        results = provider.rerank("query", ["a", "b", "c"])
        scores = [r.relevance_score for r in results]
        assert scores[0] > scores[1] > scores[2]
        assert scores[0] == pytest.approx(1.0)

    def test_rerank_respects_top_k(self, provider: NoopRerankProvider) -> None:
        results = provider.rerank("query", ["a", "b", "c", "d", "e"], top_k=3)
        assert len(results) == 3

    def test_rerank_top_k_larger_than_docs(self, provider: NoopRerankProvider) -> None:
        results = provider.rerank("query", ["a", "b"], top_k=10)
        assert len(results) == 2

    def test_rerank_single_document(self, provider: NoopRerankProvider) -> None:
        results = provider.rerank("query", ["only"])
        assert len(results) == 1
        assert results[0].index == 0
        assert results[0].relevance_score == 1.0

    def test_returns_rerank_results(self, provider: NoopRerankProvider) -> None:
        results = provider.rerank("query", ["a"])
        assert isinstance(results[0], RerankResult)


class TestFlashRankRerankProvider:
    def test_import_error_without_flashrank(self) -> None:
        with patch.dict("sys.modules", {"flashrank": None}):
            with pytest.raises(ImportError, match="FlashRank is required"):
                FlashRankRerankProvider()

    def test_model_name(self) -> None:
        provider = FlashRankRerankProvider.__new__(FlashRankRerankProvider)
        provider._model_name = "test-model"
        provider._ranker = MagicMock()
        assert provider.model_name == "test-model"

    def test_rerank_empty_documents(self) -> None:
        with patch.dict("sys.modules", {"flashrank": MagicMock()}):
            provider = FlashRankRerankProvider.__new__(FlashRankRerankProvider)
            provider._model_name = "test"
            provider._ranker = MagicMock()
            assert provider.rerank("query", []) == []

    def test_rerank_calls_flashrank(self) -> None:
        mock_ranker = MagicMock()
        mock_ranker.rerank.return_value = [
            {"id": 1, "text": "doc2", "score": 0.95},
            {"id": 0, "text": "doc1", "score": 0.80},
        ]

        provider = FlashRankRerankProvider.__new__(FlashRankRerankProvider)
        provider._model_name = "test"
        provider._ranker = mock_ranker

        # Mock the flashrank import in rerank method
        mock_flashrank = MagicMock()
        with patch.dict("sys.modules", {"flashrank": mock_flashrank}):
            results = provider.rerank("query", ["doc1", "doc2"])

        assert len(results) == 2
        assert results[0].index == 1
        assert results[0].relevance_score == 0.95
        assert results[1].index == 0
        assert results[1].relevance_score == 0.80

    def test_rerank_respects_top_k(self) -> None:
        mock_ranker = MagicMock()
        mock_ranker.rerank.return_value = [
            {"id": 0, "text": "d1", "score": 0.9},
            {"id": 1, "text": "d2", "score": 0.8},
            {"id": 2, "text": "d3", "score": 0.7},
        ]

        provider = FlashRankRerankProvider.__new__(FlashRankRerankProvider)
        provider._model_name = "test"
        provider._ranker = mock_ranker

        mock_flashrank = MagicMock()
        with patch.dict("sys.modules", {"flashrank": mock_flashrank}):
            results = provider.rerank("query", ["d1", "d2", "d3"], top_k=2)

        assert len(results) == 2
