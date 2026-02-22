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
    """Test _compute_confidence using gap ratio (scale-invariant).

    gap_ratio = (top - 5th) / top
    HIGH >= 0.30, MEDIUM >= 0.20, LOW < 0.20
    """

    def test_empty_results_returns_low(self):
        engine = _make_engine()
        confidence, label, suggestion = engine._compute_confidence([])
        assert confidence == 0.0
        assert label == "low"
        assert suggestion == SuggestionType.TRY_EXHAUSTIVE

    def test_high_confidence_peaky_distribution(self):
        """Clear winner: top=1.0, 5th=0.3 → gap_ratio=0.70 → HIGH."""
        engine = _make_engine()
        results = [
            _make_result(1.0),
            _make_result(0.6),
            _make_result(0.5),
            _make_result(0.4),
            _make_result(0.3),
        ]
        confidence, label, suggestion = engine._compute_confidence(results)
        assert confidence == pytest.approx(0.70, abs=0.01)
        assert label == "high"
        assert suggestion == SuggestionType.NONE

    def test_medium_confidence_moderate_spread(self):
        """Moderate spread: top=1.0, 5th=0.75 → gap_ratio=0.25 → MEDIUM."""
        engine = _make_engine()
        results = [
            _make_result(1.0),
            _make_result(0.9),
            _make_result(0.85),
            _make_result(0.8),
            _make_result(0.75),
        ]
        confidence, label, suggestion = engine._compute_confidence(results)
        assert confidence == pytest.approx(0.25, abs=0.01)
        assert label == "medium"
        assert suggestion == SuggestionType.TRY_KEYWORD

    def test_low_confidence_flat_distribution(self):
        """Flat distribution: top=0.5, 5th=0.45 → gap_ratio=0.10 → LOW."""
        engine = _make_engine()
        results = [
            _make_result(0.50),
            _make_result(0.49),
            _make_result(0.48),
            _make_result(0.47),
            _make_result(0.45),
        ]
        confidence, label, suggestion = engine._compute_confidence(results)
        assert confidence == pytest.approx(0.10, abs=0.01)
        assert label == "low"
        assert suggestion == SuggestionType.TRY_EXHAUSTIVE

    def test_borderline_high(self):
        """Exactly at high threshold: gap_ratio=0.30 → HIGH."""
        engine = _make_engine()
        results = [
            _make_result(1.0),
            _make_result(0.9),
            _make_result(0.8),
            _make_result(0.75),
            _make_result(0.70),
        ]
        confidence, label, suggestion = engine._compute_confidence(results)
        assert confidence == pytest.approx(0.30, abs=0.01)
        assert label == "high"

    def test_borderline_medium(self):
        """Just above medium threshold: gap_ratio≈0.21 → MEDIUM."""
        engine = _make_engine()
        results = [
            _make_result(1.0),
            _make_result(0.95),
            _make_result(0.90),
            _make_result(0.85),
            _make_result(0.79),
        ]
        confidence, label, suggestion = engine._compute_confidence(results)
        assert confidence == pytest.approx(0.21, abs=0.01)
        assert label == "medium"

    def test_scale_invariant_small_scores(self):
        """Gap ratio works the same with small RRF-scale scores."""
        engine = _make_engine()
        results = [
            _make_result(0.10),
            _make_result(0.06),
            _make_result(0.05),
            _make_result(0.04),
            _make_result(0.03),
        ]
        confidence, label, suggestion = engine._compute_confidence(results)
        # gap_ratio = (0.10 - 0.03) / 0.10 = 0.70 → HIGH
        assert confidence == pytest.approx(0.70, abs=0.01)
        assert label == "high"

    def test_scale_invariant_large_scores(self):
        """Gap ratio works the same with large reranker scores."""
        engine = _make_engine()
        results = [
            _make_result(1.5),
            _make_result(0.9),
            _make_result(0.7),
            _make_result(0.6),
            _make_result(0.45),
        ]
        confidence, label, suggestion = engine._compute_confidence(results)
        # gap_ratio = (1.5 - 0.45) / 1.5 = 0.70 → HIGH
        assert confidence == pytest.approx(0.70, abs=0.01)
        assert label == "high"

    def test_fewer_than_5_results_uses_last(self):
        """With fewer than 5 results, anchor is the last available score."""
        engine = _make_engine()
        results = [_make_result(1.0), _make_result(0.5)]
        confidence, label, suggestion = engine._compute_confidence(results)
        # gap_ratio = (1.0 - 0.5) / 1.0 = 0.50 → HIGH
        assert confidence == pytest.approx(0.50, abs=0.01)
        assert label == "high"

    def test_single_result_uses_zero_anchor(self):
        """Single result: anchor=0 → gap_ratio=1.0 → HIGH."""
        engine = _make_engine()
        results = [_make_result(0.90)]
        confidence, label, suggestion = engine._compute_confidence(results)
        assert confidence == pytest.approx(1.0, abs=0.01)
        assert label == "high"
        assert suggestion == SuggestionType.NONE

    def test_zero_top_score_returns_low(self):
        """Top score of 0 returns low confidence."""
        engine = _make_engine()
        results = [_make_result(0.0)]
        confidence, label, suggestion = engine._compute_confidence(results)
        assert confidence == 0.0
        assert label == "low"
        assert suggestion == SuggestionType.TRY_EXHAUSTIVE


class TestMaybeRerank:
    """Test _maybe_rerank returns tuple and ENUMERATION skipping."""

    def test_no_reranker_returns_false(self):
        engine = _make_engine()
        candidates = [_make_result(0.9)]
        results, was_reranked = engine._maybe_rerank("test", candidates)
        assert results == candidates
        assert was_reranked is False

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
    async def test_no_project_root_no_escalation(self):
        """project_root=None never runs grep."""
        engine = _make_engine_with_grep(project_root=None)
        request = SearchRequest(query="webhook handler code")

        with patch("clew.search.engine.SearchEngine._run_grep_async") as mock_grep:
            mock_grep.return_value = []
            response = await engine.search(request)

        mock_grep.assert_not_awaited()
        assert response.auto_escalated is False

    @pytest.mark.asyncio
    async def test_high_confidence_no_post_escalation(self):
        """High confidence CODE query does not trigger post-hoc grep escalation."""
        # Peaky distribution: gap_ratio = (1.0 - 0.3) / 1.0 = 0.70 → HIGH
        results = [
            _make_result(1.0, file_path="a.py", line_start=1, line_end=10),
            _make_result(0.7, file_path="b.py", line_start=1, line_end=10),
            _make_result(0.5, file_path="c.py", line_start=1, line_end=10),
            _make_result(0.4, file_path="d.py", line_start=1, line_end=10),
            _make_result(0.3, file_path="e.py", line_start=1, line_end=10),
            _make_result(0.1, file_path="f.py", line_start=1, line_end=10),
        ]
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
    async def test_medium_confidence_code_no_post_hoc_grep(self):
        """Medium confidence CODE query does NOT trigger post-hoc grep.

        Only TRY_EXHAUSTIVE (low confidence) triggers grep.
        Medium confidence (TRY_KEYWORD) is good enough.
        """
        # Moderate spread: gap_ratio = (1.0 - 0.75) / 1.0 = 0.25 → MEDIUM
        results = [
            _make_result(1.0, file_path="a.py", line_start=1, line_end=10),
            _make_result(0.9, file_path="b.py", line_start=1, line_end=10),
            _make_result(0.85, file_path="c.py", line_start=1, line_end=10),
            _make_result(0.8, file_path="d.py", line_start=1, line_end=10),
            _make_result(0.75, file_path="e.py", line_start=1, line_end=10),
            _make_result(0.7, file_path="f.py", line_start=1, line_end=10),
        ]
        engine = _make_engine_with_grep(semantic_results=results)
        request = SearchRequest(query="webhook handling code")

        with patch("clew.search.engine.SearchEngine._run_grep_async") as mock_grep:
            mock_grep.return_value = []
            response = await engine.search(request)

        mock_grep.assert_not_awaited()
        assert response.auto_escalated is False

    @pytest.mark.asyncio
    async def test_medium_confidence_location_no_post_hoc_grep(self):
        """LOCATION intent never triggers post-hoc grep regardless of confidence."""
        # Moderate spread: gap_ratio = (1.0 - 0.75) / 1.0 = 0.25 → MEDIUM
        results = [
            _make_result(1.0, file_path="a.py", line_start=1, line_end=10),
            _make_result(0.9, file_path="b.py", line_start=1, line_end=10),
            _make_result(0.85, file_path="c.py", line_start=1, line_end=10),
            _make_result(0.8, file_path="d.py", line_start=1, line_end=10),
            _make_result(0.75, file_path="e.py", line_start=1, line_end=10),
            _make_result(0.7, file_path="f.py", line_start=1, line_end=10),
        ]
        engine = _make_engine_with_grep(semantic_results=results)
        request = SearchRequest(query="find the checkout handler", intent=QueryIntent.LOCATION)

        with patch("clew.search.engine.SearchEngine._run_grep_async") as mock_grep:
            mock_grep.return_value = []
            response = await engine.search(request)

        mock_grep.assert_not_awaited()
        assert response.auto_escalated is False

    @pytest.mark.asyncio
    async def test_grep_results_appended_with_source_grep(self):
        """Merged grep results retain source='grep' after post-hoc escalation."""
        # Flat distribution: gap_ratio = (0.50 - 0.45) / 0.50 = 0.10 → LOW
        semantic = [
            _make_result(0.50, file_path="a.py", line_start=1, line_end=10),
            _make_result(0.49, file_path="b.py", line_start=1, line_end=10),
            _make_result(0.48, file_path="c.py", line_start=1, line_end=10),
            _make_result(0.47, file_path="d.py", line_start=1, line_end=10),
            _make_result(0.45, file_path="e.py", line_start=1, line_end=10),
            _make_result(0.44, file_path="f.py", line_start=1, line_end=10),
        ]
        engine = _make_engine_with_grep(semantic_results=semantic)
        request = SearchRequest(query="webhook handler code")

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


class TestShouldPostHocGrep:
    """Test _should_post_hoc_grep decision logic (V4.1)."""

    def test_low_confidence_code_triggers(self):
        engine = _make_engine_with_grep()
        assert (
            engine._should_post_hoc_grep(SuggestionType.TRY_EXHAUSTIVE, QueryIntent.CODE, None)
            is True
        )

    def test_medium_confidence_code_no_trigger(self):
        """V4.2: TRY_KEYWORD (medium) no longer triggers grep escalation."""
        engine = _make_engine_with_grep()
        assert (
            engine._should_post_hoc_grep(SuggestionType.TRY_KEYWORD, QueryIntent.CODE, None)
            is False
        )

    def test_high_confidence_no_trigger(self):
        engine = _make_engine_with_grep()
        assert engine._should_post_hoc_grep(SuggestionType.NONE, QueryIntent.CODE, None) is False

    def test_location_low_confidence_triggers(self):
        """LOCATION with LOW confidence escalates (enumeration queries route here)."""
        engine = _make_engine_with_grep()
        assert (
            engine._should_post_hoc_grep(SuggestionType.TRY_EXHAUSTIVE, QueryIntent.LOCATION, None)
            is True
        )

    def test_location_medium_confidence_no_trigger(self):
        """LOCATION with MEDIUM confidence does not escalate."""
        engine = _make_engine_with_grep()
        assert (
            engine._should_post_hoc_grep(SuggestionType.TRY_KEYWORD, QueryIntent.LOCATION, None)
            is False
        )

    def test_debug_intent_excluded(self):
        engine = _make_engine_with_grep()
        assert (
            engine._should_post_hoc_grep(SuggestionType.TRY_EXHAUSTIVE, QueryIntent.DEBUG, None)
            is False
        )

    def test_docs_intent_low_triggers(self):
        """V4.2: DOCS with TRY_EXHAUSTIVE still triggers grep."""
        engine = _make_engine_with_grep()
        assert (
            engine._should_post_hoc_grep(SuggestionType.TRY_EXHAUSTIVE, QueryIntent.DOCS, None)
            is True
        )

    def test_docs_intent_medium_no_trigger(self):
        """V4.2: DOCS with TRY_KEYWORD no longer triggers grep."""
        engine = _make_engine_with_grep()
        assert (
            engine._should_post_hoc_grep(SuggestionType.TRY_KEYWORD, QueryIntent.DOCS, None)
            is False
        )

    def test_explicit_mode_blocks(self):
        engine = _make_engine_with_grep()
        assert (
            engine._should_post_hoc_grep(
                SuggestionType.TRY_EXHAUSTIVE, QueryIntent.CODE, "semantic"
            )
            is False
        )

    def test_no_project_root_blocks(self):
        engine = _make_engine_with_grep(project_root=None)
        assert (
            engine._should_post_hoc_grep(SuggestionType.TRY_EXHAUSTIVE, QueryIntent.CODE, None)
            is False
        )

    def test_auto_escalation_disabled_blocks(self):
        config = SearchConfig(auto_escalation_enabled=False)
        engine = _make_engine_with_grep(config=config)
        assert (
            engine._should_post_hoc_grep(SuggestionType.TRY_EXHAUSTIVE, QueryIntent.CODE, None)
            is False
        )


class TestMergeGrepResults:
    """Test _merge_grep_results deduplication and capping."""

    def test_deduplicates_by_file_and_line(self):
        engine = _make_engine_with_grep()
        semantic = [_make_result(0.8, file_path="a.py", line_start=5, line_end=10)]
        grep = [
            SearchResult(
                content="x",
                file_path="a.py",
                score=0.0,
                line_start=7,
                line_end=7,
                source="grep",
            ),
            SearchResult(
                content="y",
                file_path="b.py",
                score=0.0,
                line_start=1,
                line_end=1,
                source="grep",
            ),
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
            SearchResult(
                content="x",
                file_path="a.py",
                score=0.0,
                line_start=1,
                line_end=1,
                source="grep",
            ),
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
