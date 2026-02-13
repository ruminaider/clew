"""Tests for Voyage reranking integration."""

from unittest.mock import Mock, patch

import pytest

from clew.search.rerank import RerankProvider, RerankResult, should_skip_rerank


class TestShouldSkipRerank:
    def test_few_candidates(self) -> None:
        assert (
            should_skip_rerank(
                "query",
                num_candidates=5,
                top_score=0.5,
                score_variance=0.5,
            )
            is True
        )

    def test_at_threshold_skipped(self) -> None:
        assert (
            should_skip_rerank(
                "query",
                num_candidates=10,
                top_score=0.5,
                score_variance=0.5,
                no_rerank_threshold=10,
            )
            is True
        )

    def test_high_confidence_top(self) -> None:
        assert (
            should_skip_rerank(
                "query",
                num_candidates=50,
                top_score=0.95,
                score_variance=0.5,
                high_confidence_threshold=0.92,
            )
            is True
        )

    def test_low_variance(self) -> None:
        assert (
            should_skip_rerank(
                "query",
                num_candidates=50,
                top_score=0.5,
                score_variance=0.05,
                low_variance_threshold=0.1,
            )
            is True
        )

    def test_pascal_case_identifier_not_skipped(self) -> None:
        """PascalCase queries should NOT skip reranking (V2 fix)."""
        assert (
            should_skip_rerank(
                "UserModel",
                num_candidates=50,
                top_score=0.5,
                score_variance=0.5,
            )
            is False
        )

    def test_pascal_case_multi_word_not_skipped(self) -> None:
        """Multi-word PascalCase like PrescriptionFill should rerank."""
        assert (
            should_skip_rerank(
                "PrescriptionFill",
                num_candidates=50,
                top_score=0.5,
                score_variance=0.5,
            )
            is False
        )

    def test_file_path(self) -> None:
        assert (
            should_skip_rerank(
                "src/auth.py",
                num_candidates=50,
                top_score=0.5,
                score_variance=0.5,
            )
            is True
        )

    def test_normal_query_not_skipped(self) -> None:
        assert (
            should_skip_rerank(
                "how does auth work",
                num_candidates=50,
                top_score=0.5,
                score_variance=0.5,
            )
            is False
        )


class TestRerankProvider:
    @pytest.fixture
    def mock_voyage(self) -> Mock:
        client = Mock()
        client.rerank.return_value = Mock(
            results=[
                Mock(index=2, relevance_score=0.95),
                Mock(index=0, relevance_score=0.80),
            ]
        )
        return client

    @pytest.fixture
    def provider(self, mock_voyage: Mock) -> RerankProvider:
        with patch("clew.search.rerank.voyageai") as mock_module:
            mock_module.Client.return_value = mock_voyage
            return RerankProvider(api_key="test-key")

    def test_rerank_returns_results(self, provider: RerankProvider, mock_voyage: Mock) -> None:
        results = provider.rerank("query", ["doc1", "doc2", "doc3"])
        assert len(results) == 2
        assert results[0].index == 2
        assert results[0].relevance_score == 0.95

    def test_rerank_empty_documents(self, provider: RerankProvider) -> None:
        results = provider.rerank("query", [])
        assert results == []

    def test_rerank_calls_client(self, provider: RerankProvider, mock_voyage: Mock) -> None:
        provider.rerank("my query", ["doc1"], top_k=5)
        mock_voyage.rerank.assert_called_once_with(
            query="my query",
            documents=["doc1"],
            model="rerank-2.5",
            top_k=5,
            truncation=True,
        )

    def test_result_dataclass(self) -> None:
        r = RerankResult(index=3, relevance_score=0.88)
        assert r.index == 3
        assert r.relevance_score == 0.88
