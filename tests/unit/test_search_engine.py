"""Tests for the search orchestrator."""

from unittest.mock import AsyncMock, Mock

import pytest

from code_search.models import SearchConfig
from code_search.search.engine import SearchEngine
from code_search.search.models import QueryIntent, SearchRequest, SearchResponse, SearchResult


@pytest.fixture
def mock_hybrid() -> Mock:
    hybrid = Mock()
    hybrid.search = AsyncMock(
        return_value=[
            SearchResult(
                content="def hello(): pass",
                file_path="main.py",
                score=0.9,
                chunk_type="function",
                function_name="hello",
            ),
            SearchResult(content="def world(): pass", file_path="other.py", score=0.7),
        ]
    )
    return hybrid


@pytest.fixture
def mock_reranker() -> Mock:
    from code_search.search.rerank import RerankResult

    reranker = Mock()
    reranker.rerank.return_value = [
        RerankResult(index=1, relevance_score=0.95),
        RerankResult(index=0, relevance_score=0.80),
    ]
    return reranker


@pytest.fixture
def enhancer() -> Mock:
    e = Mock()
    e.enhance.return_value = "enhanced query"
    return e


@pytest.fixture
def search_config() -> SearchConfig:
    return SearchConfig()


@pytest.fixture
def engine(
    mock_hybrid: Mock, mock_reranker: Mock, enhancer: Mock, search_config: SearchConfig,
) -> SearchEngine:
    return SearchEngine(
        hybrid_engine=mock_hybrid,
        reranker=mock_reranker,
        enhancer=enhancer,
        search_config=search_config,
    )


class TestSearchEngine:
    async def test_returns_search_response(self, engine: SearchEngine) -> None:
        response = await engine.search(SearchRequest(query="hello"))
        assert isinstance(response, SearchResponse)
        assert len(response.results) > 0

    async def test_response_has_query_enhanced(self, engine: SearchEngine) -> None:
        response = await engine.search(SearchRequest(query="hello"))
        assert response.query_enhanced == "enhanced query"

    async def test_response_has_total_candidates(self, engine: SearchEngine) -> None:
        response = await engine.search(SearchRequest(query="hello"))
        assert response.total_candidates == 2  # 2 mock candidates

    async def test_response_has_intent(self, engine: SearchEngine) -> None:
        response = await engine.search(SearchRequest(query="fix the auth bug"))
        assert response.intent == QueryIntent.DEBUG

    async def test_enhances_query(self, engine: SearchEngine, enhancer: Mock) -> None:
        await engine.search(SearchRequest(query="original"))
        enhancer.enhance.assert_called_once_with("original")

    async def test_classifies_intent(self, engine: SearchEngine, mock_hybrid: Mock) -> None:
        await engine.search(SearchRequest(query="fix the auth bug"))
        call_kwargs = mock_hybrid.search.call_args.kwargs
        assert call_kwargs["intent"] == QueryIntent.DEBUG

    async def test_passes_active_file(self, engine: SearchEngine, mock_hybrid: Mock) -> None:
        await engine.search(
            SearchRequest(query="test", active_file="backend/care/models.py"),
        )
        call_kwargs = mock_hybrid.search.call_args.kwargs
        assert call_kwargs["active_file"] == "backend/care/models.py"

    async def test_reranks_results(self, engine: SearchEngine, mock_reranker: Mock) -> None:
        # Scores must have high variance (>0.1) to avoid skip-rerank
        scores = [0.9, 0.85, 0.1, 0.8, 0.05, 0.75, 0.02, 0.7, 0.6, 0.03, 0.5, 0.04, 0.4, 0.3, 0.2]
        engine._hybrid.search = AsyncMock(
            return_value=[
                SearchResult(content=f"content {i}", file_path=f"f{i}.py", score=s)
                for i, s in enumerate(scores)
            ]
        )
        await engine.search(SearchRequest(query="how does auth work"))
        mock_reranker.rerank.assert_called_once()

    async def test_respects_limit(self, engine: SearchEngine) -> None:
        response = await engine.search(SearchRequest(query="test", limit=1))
        assert len(response.results) <= 1

    async def test_skips_rerank_when_few_results(
        self, engine: SearchEngine, mock_hybrid: Mock, mock_reranker: Mock,
    ) -> None:
        mock_hybrid.search = AsyncMock(
            return_value=[SearchResult(content="x", file_path="f.py", score=0.5)]
        )
        await engine.search(SearchRequest(query="test"))
        mock_reranker.rerank.assert_not_called()

    async def test_docs_intent_overrides_collection(
        self, engine: SearchEngine, mock_hybrid: Mock,
    ) -> None:
        """DOCS intent should search docs collection."""
        await engine.search(SearchRequest(query="what is the prescription model"))
        call_kwargs = mock_hybrid.search.call_args.kwargs
        assert call_kwargs["collection"] == "docs"

    async def test_uses_configurable_rerank_candidates(
        self, mock_hybrid: Mock, mock_reranker: Mock, enhancer: Mock,
    ) -> None:
        """Tradeoff B: rerank_candidates comes from SearchConfig."""
        config = SearchConfig(rerank_candidates=50)
        engine = SearchEngine(
            hybrid_engine=mock_hybrid, reranker=mock_reranker,
            enhancer=enhancer, search_config=config,
        )
        await engine.search(SearchRequest(query="test"))
        call_kwargs = mock_hybrid.search.call_args.kwargs
        assert call_kwargs["limit"] == 50
