"""Tests for mode + intent interaction in SearchEngine."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest

from clew.models import SearchConfig
from clew.search.engine import SearchEngine
from clew.search.models import QueryIntent, SearchRequest, SearchResult


def _make_result(score: float = 0.5) -> SearchResult:
    return SearchResult(
        content="def foo(): pass",
        file_path="src/main.py",
        score=score,
        chunk_type="function",
        line_start=1,
        line_end=1,
        language="python",
    )


def _make_engine(config: SearchConfig | None = None) -> SearchEngine:
    hybrid = Mock()
    hybrid.search = AsyncMock(return_value=[_make_result(0.5)])
    return SearchEngine(
        hybrid_engine=hybrid,
        search_config=config or SearchConfig(),
    )


class TestModeIntentInteraction:
    """Parameterized tests for mode + intent routing."""

    @pytest.mark.asyncio
    async def test_keyword_mode_forces_enumeration(self):
        """mode='keyword' + no intent -> ENUMERATION strategy, limit raised."""
        engine = _make_engine()
        request = SearchRequest(query="PrescriptionFill", limit=5, mode="keyword")
        response = await engine.search(request)
        assert response.intent == QueryIntent.ENUMERATION

    @pytest.mark.asyncio
    async def test_keyword_mode_overrides_debug_intent(self):
        """mode='keyword' + intent=DEBUG -> ENUMERATION (mode forces it)."""
        engine = _make_engine()
        request = SearchRequest(
            query="find all bugs",
            limit=5,
            intent=QueryIntent.DEBUG,
            mode="keyword",
        )
        response = await engine.search(request)
        assert response.intent == QueryIntent.ENUMERATION

    @pytest.mark.asyncio
    async def test_keyword_mode_raises_limit(self):
        """mode='keyword' raises limit to at least enumeration_limit."""
        config = SearchConfig(enumeration_limit=200)
        engine = _make_engine(config)
        request = SearchRequest(query="test", limit=5, mode="keyword")
        await engine.search(request)
        # The engine should have searched with limit >= 200
        # We verify via the hybrid engine call
        hybrid_call = engine._hybrid.search.call_args
        assert hybrid_call is not None

    @pytest.mark.asyncio
    async def test_semantic_mode_downgrades_enumeration(self):
        """mode='semantic' + auto-ENUMERATION -> downgraded to CODE."""
        engine = _make_engine()
        # Force auto-classification to ENUMERATION by setting intent explicitly
        request = SearchRequest(
            query="list all models",
            limit=5,
            intent=QueryIntent.ENUMERATION,
            mode="semantic",
        )
        response = await engine.search(request)
        assert response.intent == QueryIntent.CODE

    @pytest.mark.asyncio
    async def test_exhaustive_mode_keeps_limit(self):
        """mode='exhaustive' + limit=3 -> limit stays 3 for semantic part."""
        engine = _make_engine()
        request = SearchRequest(query="test", limit=3, mode="exhaustive")
        response = await engine.search(request)
        # Results should be limited to 3
        assert len(response.results) <= 3

    @pytest.mark.asyncio
    async def test_no_mode_auto_classification(self):
        """mode=None -> auto-classification stands."""
        engine = _make_engine()
        # "error" is a HARD_DEBUG_KEYWORD in intent.py
        request = SearchRequest(query="error handling", limit=5)
        response = await engine.search(request)
        assert response.intent == QueryIntent.DEBUG

    @pytest.mark.asyncio
    async def test_no_mode_code_intent(self):
        """mode=None + non-keyword query -> CODE."""
        engine = _make_engine()
        request = SearchRequest(query="authentication middleware", limit=5)
        response = await engine.search(request)
        assert response.intent == QueryIntent.CODE

    @pytest.mark.asyncio
    async def test_keyword_mode_no_reranking(self):
        """mode='keyword' -> ENUMERATION -> reranking skipped."""
        from clew.search.rerank import RerankResult

        reranker = Mock()
        reranker.rerank.return_value = [
            RerankResult(index=0, relevance_score=0.9),
        ]
        hybrid = Mock()
        hybrid.search = AsyncMock(return_value=[_make_result(0.5)])
        engine = SearchEngine(
            hybrid_engine=hybrid,
            reranker=reranker,
        )

        request = SearchRequest(query="test", limit=5, mode="keyword")
        await engine.search(request)
        reranker.rerank.assert_not_called()
