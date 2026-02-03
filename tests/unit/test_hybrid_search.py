"""Tests for hybrid search engine with structural boosting."""

from unittest.mock import AsyncMock, Mock

import pytest

from code_search.search.hybrid import HybridSearchEngine
from code_search.search.models import QueryIntent, SearchResult


@pytest.fixture
def mock_qdrant() -> Mock:
    qdrant = Mock()
    qdrant.query_hybrid.return_value = [
        Mock(
            id="main.py::function::hello",
            score=0.9,
            payload={
                "content": "def hello(): pass",
                "file_path": "main.py",
                "chunk_type": "function",
                "line_start": 1,
                "line_end": 2,
                "language": "python",
                "class_name": "",
                "function_name": "hello",
                "signature": "def hello()",
                "app_name": "",
                "layer": "other",
                "chunk_id": "main.py::function::hello",
            },
        )
    ]
    return qdrant


@pytest.fixture
def mock_embedder() -> Mock:
    embedder = Mock()
    embedder.embed_query = AsyncMock(return_value=[0.1] * 1024)
    return embedder


@pytest.fixture
def engine(mock_qdrant: Mock, mock_embedder: Mock) -> HybridSearchEngine:
    return HybridSearchEngine(qdrant=mock_qdrant, embedder=mock_embedder)


class TestHybridSearch:
    async def test_returns_search_results(self, engine: HybridSearchEngine) -> None:
        results = await engine.search("hello function", collection="code")
        assert len(results) == 1
        assert isinstance(results[0], SearchResult)
        assert results[0].file_path == "main.py"

    async def test_embeds_query(self, engine: HybridSearchEngine, mock_embedder: Mock) -> None:
        await engine.search("test query")
        mock_embedder.embed_query.assert_awaited_once_with("test query")

    async def test_queries_qdrant_with_prefetches(
        self,
        engine: HybridSearchEngine,
        mock_qdrant: Mock,
    ) -> None:
        await engine.search("test query")
        mock_qdrant.query_hybrid.assert_called_once()
        call_kwargs = mock_qdrant.query_hybrid.call_args.kwargs
        prefetches = call_kwargs["prefetches"]
        # Base: dense + bm25 = 2 prefetches minimum
        assert len(prefetches) >= 2

    async def test_active_file_adds_module_boost(
        self,
        engine: HybridSearchEngine,
        mock_qdrant: Mock,
    ) -> None:
        """Tradeoff A: active_file triggers same-module structural boost."""
        await engine.search("test", active_file="backend/care/models.py")
        call_kwargs = mock_qdrant.query_hybrid.call_args.kwargs
        prefetches = call_kwargs["prefetches"]
        # Base (2) + module boost (1) = 3
        assert len(prefetches) >= 3

    async def test_debug_intent_adds_test_boost(
        self,
        engine: HybridSearchEngine,
        mock_qdrant: Mock,
    ) -> None:
        await engine.search("test", intent=QueryIntent.DEBUG)
        call_kwargs = mock_qdrant.query_hybrid.call_args.kwargs
        prefetches = call_kwargs["prefetches"]
        # Base (2) + debug test boost (1) = 3
        assert len(prefetches) >= 3

    async def test_debug_with_active_file_adds_both_boosts(
        self,
        engine: HybridSearchEngine,
        mock_qdrant: Mock,
    ) -> None:
        await engine.search(
            "fix bug",
            intent=QueryIntent.DEBUG,
            active_file="backend/care/views.py",
        )
        call_kwargs = mock_qdrant.query_hybrid.call_args.kwargs
        prefetches = call_kwargs["prefetches"]
        # Base (2) + module boost (1) + debug boost (1) = 4
        assert len(prefetches) >= 4

    async def test_empty_results(self, engine: HybridSearchEngine, mock_qdrant: Mock) -> None:
        mock_qdrant.query_hybrid.return_value = []
        results = await engine.search("nonexistent")
        assert results == []

    async def test_result_has_score(self, engine: HybridSearchEngine) -> None:
        results = await engine.search("hello")
        assert results[0].score == 0.9

    async def test_result_maps_all_metadata(self, engine: HybridSearchEngine) -> None:
        results = await engine.search("hello")
        r = results[0]
        assert r.function_name == "hello"
        assert r.language == "python"
        assert r.signature == "def hello()"
        assert r.chunk_id == "main.py::function::hello"

    async def test_respects_limit(self, engine: HybridSearchEngine, mock_qdrant: Mock) -> None:
        await engine.search("test", limit=5)
        call_kwargs = mock_qdrant.query_hybrid.call_args.kwargs
        assert call_kwargs["limit"] == 5
