"""Tests for SearchEngine confidence computation, rerank behavior, and auto-escalation."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from clew.models import SearchConfig
from clew.search.engine import SearchEngine
from clew.search.models import QueryIntent, SearchRequest, SearchResult, SuggestionType


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
            _make_result(0.07),
            _make_result(0.005),  # big gap from #5
        ]
        confidence, label, suggestion = engine._compute_confidence(results, was_reranked=False)
        # confidence = scores[4] - scores[5] = 0.07 - 0.005 = 0.065
        assert confidence == pytest.approx(0.065, abs=1e-9)
        assert label == "high"  # 0.065 >= 0.06 (rrf high threshold)

    def test_rrf_medium_confidence(self):
        engine = _make_engine()
        results = [
            _make_result(0.10),
            _make_result(0.09),
            _make_result(0.08),
            _make_result(0.07),
            _make_result(0.06),
            _make_result(0.03),  # moderate gap from #5
        ]
        confidence, label, suggestion = engine._compute_confidence(results, was_reranked=False)
        # confidence = 0.06 - 0.03 = 0.03
        assert confidence == pytest.approx(0.03, abs=1e-9)
        assert label == "medium"  # 0.03 >= 0.02 and < 0.06

    def test_rrf_low_confidence(self):
        engine = _make_engine()
        results = [
            _make_result(0.10),
            _make_result(0.09),
            _make_result(0.08),
            _make_result(0.07),
            _make_result(0.06),
            _make_result(0.05),  # tiny gap
        ]
        confidence, label, suggestion = engine._compute_confidence(results, was_reranked=False)
        # confidence = 0.06 - 0.05 = 0.01
        assert confidence == pytest.approx(0.01, abs=1e-9)
        assert label == "low"  # 0.01 < 0.02

    def test_rrf_fewer_than_6_results(self):
        """When fewer than 6 results, use last score as confidence."""
        engine = _make_engine()
        results = [_make_result(0.10), _make_result(0.08), _make_result(0.07)]
        confidence, label, suggestion = engine._compute_confidence(results, was_reranked=False)
        assert confidence == pytest.approx(0.07, abs=1e-9)
        assert label == "high"  # 0.07 >= 0.06

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


def _make_engine_with_grep(
    *,
    project_root: Path | None = Path("/project"),
    config: SearchConfig | None = None,
    enricher: Mock | None = None,
    semantic_results: list[SearchResult] | None = None,
) -> SearchEngine:
    """Create a SearchEngine with mock hybrid engine and optional grep support."""
    hybrid = Mock()
    results = semantic_results if semantic_results is not None else [_make_result(0.8)]
    hybrid.search = AsyncMock(return_value=results)
    return SearchEngine(
        hybrid_engine=hybrid,
        search_config=config or SearchConfig(),
        project_root=project_root,
        enricher=enricher,
    )


class TestAutoEscalation:
    """Test autonomous grep escalation behavior."""

    @pytest.mark.asyncio
    async def test_enumeration_triggers_grep(self):
        """ENUMERATION intent with project_root triggers grep, results have source='grep'."""
        engine = _make_engine_with_grep()
        request = SearchRequest(query="find all url routes", intent=QueryIntent.ENUMERATION)

        with patch("clew.search.engine.SearchEngine._run_grep_async") as mock_grep:
            mock_grep.return_value = [
                SearchResult(
                    content="urlpatterns = [",
                    file_path="src/urls.py",
                    score=0.0,
                    line_start=5,
                    line_end=5,
                    source="grep",
                )
            ]
            response = await engine.search(request)

        mock_grep.assert_awaited_once()
        grep_results = [r for r in response.results if r.source == "grep"]
        assert len(grep_results) >= 1
        assert response.auto_escalated is True
        assert response.mode_used == "exhaustive"

    @pytest.mark.asyncio
    async def test_semantic_mode_no_escalation(self):
        """mode='semantic' prevents grep even for ENUMERATION intent."""
        engine = _make_engine_with_grep()
        request = SearchRequest(
            query="find all models",
            intent=QueryIntent.ENUMERATION,
            mode="semantic",
        )

        with patch("clew.search.engine.SearchEngine._run_grep_async") as mock_grep:
            mock_grep.return_value = []
            response = await engine.search(request)

        mock_grep.assert_not_awaited()
        assert response.auto_escalated is False

    @pytest.mark.asyncio
    async def test_keyword_mode_no_escalation(self):
        """mode='keyword' prevents grep even for ENUMERATION intent."""
        engine = _make_engine_with_grep()
        request = SearchRequest(
            query="find all models",
            intent=QueryIntent.ENUMERATION,
            mode="keyword",
        )

        with patch("clew.search.engine.SearchEngine._run_grep_async") as mock_grep:
            mock_grep.return_value = []
            response = await engine.search(request)

        mock_grep.assert_not_awaited()
        assert response.auto_escalated is False

    @pytest.mark.asyncio
    async def test_no_project_root_no_escalation(self):
        """project_root=None never runs grep."""
        engine = _make_engine_with_grep(project_root=None)
        request = SearchRequest(query="find all url routes", intent=QueryIntent.ENUMERATION)

        with patch("clew.search.engine.SearchEngine._run_grep_async") as mock_grep:
            mock_grep.return_value = []
            response = await engine.search(request)

        mock_grep.assert_not_awaited()
        assert response.auto_escalated is False

    @pytest.mark.asyncio
    async def test_high_confidence_no_post_escalation(self):
        """High confidence CODE query does not trigger post-hoc grep escalation."""
        # Return enough results to get high confidence
        results = [_make_result(0.9 - i * 0.05) for i in range(10)]
        engine = _make_engine_with_grep(semantic_results=results)
        request = SearchRequest(query="handle payment", intent=QueryIntent.CODE)

        with patch("clew.search.engine.SearchEngine._run_grep_async") as mock_grep:
            mock_grep.return_value = []
            response = await engine.search(request)

        # CODE intent should not trigger proactive grep, and high confidence
        # should not trigger post-hoc escalation
        mock_grep.assert_not_awaited()
        assert response.auto_escalated is False

    @pytest.mark.asyncio
    async def test_grep_results_appended_with_source_grep(self):
        """Merged grep results retain source='grep'."""
        semantic = [_make_result(0.8, file_path="src/main.py", line_start=1, line_end=10)]
        engine = _make_engine_with_grep(semantic_results=semantic)
        request = SearchRequest(query="find all url routes", intent=QueryIntent.ENUMERATION)

        grep_hit = SearchResult(
            content="path('/api/', views.api)",
            file_path="src/urls.py",
            score=0.0,
            line_start=20,
            line_end=20,
            source="grep",
        )

        with patch("clew.search.engine.SearchEngine._run_grep_async") as mock_grep:
            mock_grep.return_value = [grep_hit]
            response = await engine.search(request)

        # Should have semantic + grep results
        sources = {r.source for r in response.results}
        assert "grep" in sources
        assert "semantic" in sources

    @pytest.mark.asyncio
    async def test_enricher_called_on_results(self):
        """When enricher is provided, enrich() is called on results."""
        mock_enricher = Mock()
        enriched = [_make_result(0.8, context="Called by: handler")]
        mock_enricher.enrich.return_value = enriched

        engine = _make_engine_with_grep(enricher=mock_enricher)
        request = SearchRequest(query="process order")

        response = await engine.search(request)

        mock_enricher.enrich.assert_called_once()
        assert response.results[0].context == "Called by: handler"

    @pytest.mark.asyncio
    async def test_no_enricher_works(self):
        """When enricher is None, results are returned without enrichment."""
        engine = _make_engine_with_grep(enricher=None)
        request = SearchRequest(query="process order")

        response = await engine.search(request)

        assert len(response.results) >= 1
        assert response.results[0].context == ""


class TestShouldAugmentWithGrep:
    """Test _should_augment_with_grep decision logic."""

    def test_enumeration_with_project_root(self):
        engine = _make_engine_with_grep()
        assert engine._should_augment_with_grep(QueryIntent.ENUMERATION, None) is True

    def test_code_intent_no_augment(self):
        engine = _make_engine_with_grep()
        assert engine._should_augment_with_grep(QueryIntent.CODE, None) is False

    def test_no_project_root(self):
        engine = _make_engine_with_grep(project_root=None)
        assert engine._should_augment_with_grep(QueryIntent.ENUMERATION, None) is False

    def test_semantic_mode_blocks(self):
        engine = _make_engine_with_grep()
        assert engine._should_augment_with_grep(QueryIntent.ENUMERATION, "semantic") is False

    def test_keyword_mode_blocks(self):
        engine = _make_engine_with_grep()
        assert engine._should_augment_with_grep(QueryIntent.ENUMERATION, "keyword") is False

    def test_exhaustive_mode_allows(self):
        engine = _make_engine_with_grep()
        assert engine._should_augment_with_grep(QueryIntent.ENUMERATION, "exhaustive") is True

    def test_auto_escalation_disabled(self):
        config = SearchConfig(auto_escalation_enabled=False)
        engine = _make_engine_with_grep(config=config)
        assert engine._should_augment_with_grep(QueryIntent.ENUMERATION, None) is False


class TestMergeGrepResults:
    """Test _merge_grep_results deduplication and capping."""

    def test_deduplicates_by_file_and_line(self):
        engine = _make_engine_with_grep()
        semantic = [_make_result(0.8, file_path="a.py", line_start=5, line_end=10)]
        grep = [
            SearchResult(content="x", file_path="a.py", score=0.0, line_start=7, line_end=7, source="grep"),
            SearchResult(content="y", file_path="b.py", score=0.0, line_start=1, line_end=1, source="grep"),
        ]
        merged = engine._merge_grep_results(semantic, grep)
        # a.py:7 is within 5-10 so should be deduped, b.py:1 should remain
        assert len(merged) == 2
        file_paths = [r.file_path for r in merged]
        assert "a.py" in file_paths
        assert "b.py" in file_paths

    def test_empty_grep_returns_semantic_only(self):
        engine = _make_engine_with_grep()
        semantic = [_make_result(0.8)]
        merged = engine._merge_grep_results(semantic, [])
        assert len(merged) == 1

    def test_empty_semantic_returns_grep_only(self):
        engine = _make_engine_with_grep()
        grep = [
            SearchResult(content="x", file_path="a.py", score=0.0, line_start=1, line_end=1, source="grep"),
        ]
        merged = engine._merge_grep_results([], grep)
        assert len(merged) == 1
        assert merged[0].source == "grep"

    def test_grep_response_cap_enforced(self):
        """Merged grep results are capped at grep_response_cap."""
        config = SearchConfig(grep_response_cap=10)
        engine = _make_engine_with_grep(config=config)
        semantic = [_make_result(0.8)]
        grep = [
            SearchResult(
                content=f"line {i}",
                file_path=f"file_{i}.py",
                score=0.0,
                line_start=1,
                line_end=1,
                source="grep",
            )
            for i in range(50)
        ]
        merged = engine._merge_grep_results(semantic, grep)
        # 1 semantic + 10 capped grep = 11
        assert len(merged) == 11
        grep_count = sum(1 for r in merged if r.source == "grep")
        assert grep_count == 10
