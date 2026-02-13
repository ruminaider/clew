"""Tests for hybrid search engine with structural boosting."""

from unittest.mock import AsyncMock, Mock

import pytest

from clew.search.hybrid import HybridSearchEngine
from clew.search.models import QueryIntent, SearchResult


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

    async def test_debug_intent_no_test_boost(
        self,
        engine: HybridSearchEngine,
        mock_qdrant: Mock,
    ) -> None:
        """DEBUG intent should NOT inject test-file boost prefetch (V2 fix)."""
        await engine.search("test", intent=QueryIntent.DEBUG)
        call_kwargs = mock_qdrant.query_hybrid.call_args.kwargs
        prefetches = call_kwargs["prefetches"]
        # Base only (2) — no debug test boost
        assert len(prefetches) == 2
        # Verify no prefetch has is_test filter
        for pf in prefetches:
            if pf.filter:
                for cond in pf.filter.must or []:
                    assert cond.key != "is_test"

    async def test_debug_with_active_file_only_module_boost(
        self,
        engine: HybridSearchEngine,
        mock_qdrant: Mock,
    ) -> None:
        """DEBUG + active_file should only get module boost, not test boost."""
        await engine.search(
            "fix bug",
            intent=QueryIntent.DEBUG,
            active_file="backend/care/views.py",
        )
        call_kwargs = mock_qdrant.query_hybrid.call_args.kwargs
        prefetches = call_kwargs["prefetches"]
        # Base (2) + module boost (1) = 3, no debug test boost
        assert len(prefetches) == 3

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

    async def test_passes_query_filter_to_qdrant(
        self,
        engine: HybridSearchEngine,
        mock_qdrant: Mock,
    ) -> None:
        from qdrant_client import models

        qf = models.Filter(
            must=[models.FieldCondition(key="language", match=models.MatchValue(value="python"))]
        )
        await engine.search("test", query_filter=qf)
        call_kwargs = mock_qdrant.query_hybrid.call_args.kwargs
        assert call_kwargs["query_filter"] is qf

    async def test_no_filter_passes_none(
        self,
        engine: HybridSearchEngine,
        mock_qdrant: Mock,
    ) -> None:
        await engine.search("test")
        call_kwargs = mock_qdrant.query_hybrid.call_args.kwargs
        assert call_kwargs["query_filter"] is None


class TestIntentAdaptiveVectors:
    """Tests for V2 query-adaptive vector selection (S5)."""

    async def test_location_intent_uses_signature_vector(
        self, engine: HybridSearchEngine, mock_qdrant: Mock
    ) -> None:
        await engine.search("PrescriptionFill", intent=QueryIntent.LOCATION)
        prefetches = mock_qdrant.query_hybrid.call_args.kwargs["prefetches"]
        dense_pf = prefetches[0]
        assert dense_pf.using == "signature"

    async def test_code_intent_uses_semantic_vector(
        self, engine: HybridSearchEngine, mock_qdrant: Mock
    ) -> None:
        await engine.search("user auth handler", intent=QueryIntent.CODE)
        prefetches = mock_qdrant.query_hybrid.call_args.kwargs["prefetches"]
        dense_pf = prefetches[0]
        assert dense_pf.using == "semantic"

    async def test_debug_intent_uses_semantic_vector(
        self, engine: HybridSearchEngine, mock_qdrant: Mock
    ) -> None:
        await engine.search("error in payment", intent=QueryIntent.DEBUG)
        prefetches = mock_qdrant.query_hybrid.call_args.kwargs["prefetches"]
        dense_pf = prefetches[0]
        assert dense_pf.using == "semantic"

    async def test_docs_intent_uses_semantic_vector(
        self, engine: HybridSearchEngine, mock_qdrant: Mock
    ) -> None:
        await engine.search("explain auth flow", intent=QueryIntent.DOCS)
        prefetches = mock_qdrant.query_hybrid.call_args.kwargs["prefetches"]
        dense_pf = prefetches[0]
        assert dense_pf.using == "semantic"

    async def test_location_intent_bm25_limit_50(
        self, engine: HybridSearchEngine, mock_qdrant: Mock
    ) -> None:
        await engine.search("PrescriptionFill", intent=QueryIntent.LOCATION)
        prefetches = mock_qdrant.query_hybrid.call_args.kwargs["prefetches"]
        bm25_pf = prefetches[1]
        assert bm25_pf.using == "bm25"
        assert bm25_pf.limit == 50

    async def test_code_intent_bm25_limit_30(
        self, engine: HybridSearchEngine, mock_qdrant: Mock
    ) -> None:
        await engine.search("user auth handler", intent=QueryIntent.CODE)
        prefetches = mock_qdrant.query_hybrid.call_args.kwargs["prefetches"]
        bm25_pf = prefetches[1]
        assert bm25_pf.using == "bm25"
        assert bm25_pf.limit == 30

    async def test_no_intent_defaults_to_semantic(
        self, engine: HybridSearchEngine, mock_qdrant: Mock
    ) -> None:
        await engine.search("test query", intent=None)
        prefetches = mock_qdrant.query_hybrid.call_args.kwargs["prefetches"]
        dense_pf = prefetches[0]
        assert dense_pf.using == "semantic"

    async def test_module_boost_uses_primary_vector(
        self, engine: HybridSearchEngine, mock_qdrant: Mock
    ) -> None:
        """Module boost prefetch should use the same primary vector as the intent."""
        await engine.search(
            "PrescriptionFill",
            intent=QueryIntent.LOCATION,
            active_file="backend/care/models.py",
        )
        prefetches = mock_qdrant.query_hybrid.call_args.kwargs["prefetches"]
        # Third prefetch is the module boost
        module_pf = prefetches[2]
        assert module_pf.using == "signature"


class TestImportanceScoreReading:
    """Tests for reading importance_score from Qdrant payload (S5)."""

    def test_importance_score_read_from_payload(self) -> None:
        point = Mock()
        point.score = 0.9
        point.payload = {
            "content": "def foo(): pass",
            "file_path": "main.py",
            "importance_score": 0.75,
        }
        result = HybridSearchEngine._point_to_result(point)
        assert result.importance_score == 0.75

    def test_importance_score_defaults_to_zero(self) -> None:
        point = Mock()
        point.score = 0.9
        point.payload = {
            "content": "def foo(): pass",
            "file_path": "main.py",
        }
        result = HybridSearchEngine._point_to_result(point)
        assert result.importance_score == 0.0


class TestConfidenceFallback:
    """Tests for confidence-based fallback expansion (S6)."""

    @staticmethod
    def _make_point(chunk_id: str, score: float) -> Mock:
        point = Mock()
        point.score = score
        point.payload = {
            "content": f"def {chunk_id}(): pass",
            "file_path": f"{chunk_id}.py",
            "chunk_id": chunk_id,
        }
        return point

    async def test_low_confidence_triggers_expansion(
        self, mock_qdrant: Mock, mock_embedder: Mock
    ) -> None:
        """When top score < threshold, expansion search should be triggered."""
        # First call returns low-confidence results
        low_conf_point = self._make_point("low_conf", 0.4)
        expansion_point = self._make_point("expansion_hit", 0.55)

        mock_qdrant.query_hybrid.side_effect = [
            [low_conf_point],  # primary search
            [expansion_point, low_conf_point],  # expansion search
        ]

        engine = HybridSearchEngine(qdrant=mock_qdrant, embedder=mock_embedder)
        await engine.search("obscure query")

        # query_hybrid called twice: primary + expansion
        assert mock_qdrant.query_hybrid.call_count == 2

    async def test_high_confidence_skips_expansion(
        self, mock_qdrant: Mock, mock_embedder: Mock
    ) -> None:
        """When top score >= threshold, no expansion happens."""
        high_conf_point = self._make_point("good_hit", 0.9)
        mock_qdrant.query_hybrid.return_value = [high_conf_point]

        engine = HybridSearchEngine(qdrant=mock_qdrant, embedder=mock_embedder)
        results = await engine.search("well-known function")

        # Only one call — no expansion
        assert mock_qdrant.query_hybrid.call_count == 1
        assert len(results) == 1

    async def test_expansion_merges_and_deduplicates(
        self, mock_qdrant: Mock, mock_embedder: Mock
    ) -> None:
        """Expansion merges primary + expanded results, keeps max score per chunk_id."""
        primary_point = self._make_point("shared", 0.4)
        expansion_shared = self._make_point("shared", 0.6)  # higher score
        expansion_new = self._make_point("new_hit", 0.5)

        mock_qdrant.query_hybrid.side_effect = [
            [primary_point],  # primary search (low confidence)
            [expansion_shared, expansion_new],  # expansion
        ]

        engine = HybridSearchEngine(qdrant=mock_qdrant, embedder=mock_embedder)
        results = await engine.search("ambiguous query")

        # Should have 2 unique results: shared (max score 0.6) and new_hit (0.5)
        assert len(results) == 2
        chunk_ids = [r.chunk_id for r in results]
        assert "shared" in chunk_ids
        assert "new_hit" in chunk_ids
        # shared should have the higher score
        shared_result = next(r for r in results if r.chunk_id == "shared")
        assert shared_result.score == 0.6
        # Results sorted by score descending
        assert results[0].score >= results[1].score

    async def test_expansion_uses_all_vectors(self, mock_qdrant: Mock, mock_embedder: Mock) -> None:
        """Expansion prefetches should query all 3 named vectors + BM25."""
        low_conf_point = self._make_point("low", 0.3)
        mock_qdrant.query_hybrid.side_effect = [
            [low_conf_point],  # primary
            [low_conf_point],  # expansion
        ]

        engine = HybridSearchEngine(qdrant=mock_qdrant, embedder=mock_embedder)
        await engine.search("rare query")

        expansion_call = mock_qdrant.query_hybrid.call_args_list[1]
        prefetches = expansion_call.kwargs["prefetches"]
        using_names = {pf.using for pf in prefetches}
        assert using_names == {"signature", "semantic", "body", "bm25"}

    async def test_empty_results_no_expansion(self, mock_qdrant: Mock, mock_embedder: Mock) -> None:
        """Empty primary results should not trigger expansion."""
        mock_qdrant.query_hybrid.return_value = []

        engine = HybridSearchEngine(qdrant=mock_qdrant, embedder=mock_embedder)
        results = await engine.search("nothing matches")

        assert mock_qdrant.query_hybrid.call_count == 1
        assert results == []

    async def test_custom_confidence_threshold(
        self, mock_qdrant: Mock, mock_embedder: Mock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """CLEW_CONFIDENCE_THRESHOLD env var should control the threshold."""
        monkeypatch.setenv("CLEW_CONFIDENCE_THRESHOLD", "0.80")

        # Score of 0.75 is below 0.80 threshold
        point = self._make_point("medium", 0.75)
        mock_qdrant.query_hybrid.side_effect = [
            [point],  # primary
            [point],  # expansion triggered because 0.75 < 0.80
        ]

        engine = HybridSearchEngine(qdrant=mock_qdrant, embedder=mock_embedder)
        await engine.search("test query")

        assert mock_qdrant.query_hybrid.call_count == 2
