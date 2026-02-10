"""Tests for the search orchestrator."""

from unittest.mock import AsyncMock, Mock

import pytest

from clew.models import SearchConfig
from clew.search.engine import SearchEngine
from clew.search.models import QueryIntent, SearchRequest, SearchResponse, SearchResult


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
    from clew.search.rerank import RerankResult

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
    mock_hybrid: Mock,
    mock_reranker: Mock,
    enhancer: Mock,
    search_config: SearchConfig,
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
        self,
        engine: SearchEngine,
        mock_hybrid: Mock,
        mock_reranker: Mock,
    ) -> None:
        mock_hybrid.search = AsyncMock(
            return_value=[SearchResult(content="x", file_path="f.py", score=0.5)]
        )
        await engine.search(SearchRequest(query="test"))
        mock_reranker.rerank.assert_not_called()

    async def test_docs_intent_uses_request_collection(
        self,
        engine: SearchEngine,
        mock_hybrid: Mock,
    ) -> None:
        """DOCS intent should respect request.collection, not auto-override."""
        await engine.search(SearchRequest(query="what is the prescription model"))
        call_kwargs = mock_hybrid.search.call_args.kwargs
        assert call_kwargs["collection"] == "code"

    async def test_explicit_collection_respected(
        self,
        engine: SearchEngine,
        mock_hybrid: Mock,
    ) -> None:
        """Explicit collection in request is always used."""
        await engine.search(
            SearchRequest(query="what is the prescription model", collection="docs")
        )
        call_kwargs = mock_hybrid.search.call_args.kwargs
        assert call_kwargs["collection"] == "docs"

    async def test_uses_configurable_rerank_candidates(
        self,
        mock_hybrid: Mock,
        mock_reranker: Mock,
        enhancer: Mock,
    ) -> None:
        """Tradeoff B: rerank_candidates comes from SearchConfig."""
        config = SearchConfig(rerank_candidates=50)
        engine = SearchEngine(
            hybrid_engine=mock_hybrid,
            reranker=mock_reranker,
            enhancer=enhancer,
            search_config=config,
        )
        await engine.search(SearchRequest(query="test"))
        call_kwargs = mock_hybrid.search.call_args.kwargs
        assert call_kwargs["limit"] == 50

    async def test_passes_filters_to_hybrid(self, engine: SearchEngine, mock_hybrid: Mock) -> None:
        request = SearchRequest(query="test", filters={"language": "python"})
        await engine.search(request)
        call_kwargs = mock_hybrid.search.call_args.kwargs
        qf = call_kwargs["query_filter"]
        assert qf is not None
        assert len(qf.must) == 1
        assert qf.must[0].key == "language"

    async def test_invalid_filter_raises(self, engine: SearchEngine) -> None:
        from clew.exceptions import InvalidFilterError

        request = SearchRequest(query="test", filters={"invalid_key": "val"})
        with pytest.raises(InvalidFilterError):
            await engine.search(request)


class TestPointToResultDocstring:
    """Test docstring extraction from Qdrant payload."""

    def test_point_to_result_extracts_docstring(self) -> None:
        """Verify docstring is pulled from Qdrant payload into SearchResult."""
        from unittest.mock import Mock

        from clew.search.hybrid import HybridSearchEngine

        point = Mock()
        point.score = 0.9
        point.payload = {
            "content": "def foo(): pass",
            "file_path": "src/main.py",
            "docstring": "Do the foo thing.",
            "signature": "def foo():",
        }

        result = HybridSearchEngine._point_to_result(point)
        assert result.docstring == "Do the foo thing."

    def test_point_to_result_docstring_defaults_empty(self) -> None:
        """Verify docstring defaults to empty string when not in payload."""
        from unittest.mock import Mock

        from clew.search.hybrid import HybridSearchEngine

        point = Mock()
        point.score = 0.9
        point.payload = {
            "content": "def foo(): pass",
            "file_path": "src/main.py",
        }

        result = HybridSearchEngine._point_to_result(point)
        assert result.docstring == ""


class TestDeduplication:
    """Tests for SearchEngine._deduplicate."""

    def test_removes_duplicates_same_range(self) -> None:
        """Two results with the same file_path/line_start/line_end: keep higher score."""
        results = [
            SearchResult(
                content="def hello(): pass",
                file_path="main.py",
                score=0.8,
                chunk_type="function",
                line_start=1,
                line_end=5,
            ),
            SearchResult(
                content="def hello(): pass",
                file_path="main.py",
                score=0.9,
                chunk_type="method",
                line_start=1,
                line_end=5,
            ),
        ]
        deduped = SearchEngine._deduplicate(results)
        assert len(deduped) == 1
        assert deduped[0].score == 0.9
        assert deduped[0].chunk_type == "method"

    def test_keeps_different_ranges(self) -> None:
        """Two results from same file but different line ranges are both kept."""
        results = [
            SearchResult(
                content="def hello(): pass",
                file_path="main.py",
                score=0.9,
                line_start=1,
                line_end=5,
            ),
            SearchResult(
                content="def world(): pass",
                file_path="main.py",
                score=0.8,
                line_start=10,
                line_end=15,
            ),
        ]
        deduped = SearchEngine._deduplicate(results)
        assert len(deduped) == 2

    def test_preserves_order(self) -> None:
        """Results maintain score-based ordering after dedup."""
        results = [
            SearchResult(content="a", file_path="a.py", score=0.9, line_start=1, line_end=5),
            SearchResult(content="b", file_path="b.py", score=0.7, line_start=1, line_end=5),
            SearchResult(content="a_dup", file_path="a.py", score=0.5, line_start=1, line_end=5),
        ]
        deduped = SearchEngine._deduplicate(results)
        assert len(deduped) == 2
        # The higher-scored 'a' should remain, 'a_dup' should be dropped
        file_paths = [r.file_path for r in deduped]
        assert "a.py" in file_paths
        assert "b.py" in file_paths
        # The a.py result should have the higher score
        a_result = next(r for r in deduped if r.file_path == "a.py")
        assert a_result.score == 0.9

    def test_empty_results(self) -> None:
        """Handles empty list gracefully."""
        deduped = SearchEngine._deduplicate([])
        assert deduped == []
