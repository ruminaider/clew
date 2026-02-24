"""Search orchestrator: enhance -> classify -> search -> rerank -> respond.

Returns SearchResponse with query_enhanced and total_candidates fields.
"""

from __future__ import annotations

import dataclasses
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from clew.models import SearchConfig

from .filters import build_qdrant_filter
from .intent import classify_intent
from .models import (
    QueryIntent,
    SearchRequest,
    SearchResponse,
    SearchResult,
    SuggestionType,
)
from .rerank import should_skip_rerank

if TYPE_CHECKING:
    from clew.search.enhance import QueryEnhancer
    from clew.search.enrichment import ResultEnricher
    from clew.search.hybrid import HybridSearchEngine
    from clew.search.rerank import RerankProvider
    from clew.search.telemetry import QueryTelemetry

logger = logging.getLogger(__name__)


class SearchEngine:
    """Top-level search orchestrator."""

    def __init__(
        self,
        hybrid_engine: HybridSearchEngine,
        reranker: RerankProvider | None = None,
        enhancer: QueryEnhancer | None = None,
        search_config: SearchConfig | None = None,
        project_root: Path | None = None,
        enricher: ResultEnricher | None = None,
        telemetry: QueryTelemetry | None = None,
    ) -> None:
        self._hybrid = hybrid_engine
        self._reranker = reranker
        self._enhancer = enhancer
        self._config = search_config or SearchConfig()
        self._project_root = project_root
        self._enricher = enricher
        self._telemetry = telemetry

    async def search(self, request: SearchRequest) -> SearchResponse:
        """Execute full search pipeline and return SearchResponse."""
        query = request.query

        # Step 1: Enhance query
        query_enhanced = query
        if self._enhancer:
            query_enhanced = self._enhancer.enhance(query)

        # Step 2: Classify intent (on original query, not enhanced)
        intent = request.intent or classify_intent(query)
        logger.debug("Intent classified: query=%r intent=%s", query, intent.value)

        # Step 2.5: Mode routing — override intent based on explicit mode
        effective_request = request
        if request.mode == "keyword":
            intent = QueryIntent.ENUMERATION
            new_limit = max(request.limit, self._config.enumeration_limit)
            effective_request = dataclasses.replace(request, limit=new_limit)
        elif request.mode == "semantic":
            if intent == QueryIntent.ENUMERATION:
                intent = QueryIntent.CODE
        # mode="exhaustive" and mode=None: no override needed

        # Step 3: Use the collection from the request (user-specified or default)
        collection = effective_request.collection

        # Step 4: Hybrid search with configurable candidate limit (Tradeoff B)
        query_filter = (
            build_qdrant_filter(effective_request.filters) if effective_request.filters else None
        )
        candidates = await self._hybrid.search(
            query=query_enhanced,
            collection=collection,
            limit=self._config.rerank_candidates,
            intent=intent,
            active_file=effective_request.active_file,
            query_filter=query_filter,
        )

        total_candidates = len(candidates)

        if not candidates:
            return SearchResponse(
                results=[],
                query_enhanced=query_enhanced,
                total_candidates=0,
                intent=intent,
                confidence=0.0,
                confidence_label="low",
                suggestion_type=SuggestionType.TRY_EXHAUSTIVE,
            )

        # Step 5: Rerank (if applicable)
        results, was_reranked = self._maybe_rerank(query_enhanced, candidates, intent=intent)

        # Step 5.4: Apply importance boost (before test demotion)
        results = self._apply_importance_boost(results)

        # Step 5.5: Demote test files
        results = self._apply_test_demotion(results, intent)
        results.sort(key=lambda r: r.score, reverse=True)

        # Step 5.6: Deduplicate overlapping results
        results = self._deduplicate(results)

        # Step 6: Apply limit
        results = results[: effective_request.limit]

        # Step 7: Compute confidence
        confidence, confidence_label, suggestion_type = self._compute_confidence(results)

        # Step 8: Grep augmentation (explicit mode only)
        mode_used = "semantic"
        auto_escalated = False

        if effective_request.mode == "exhaustive" and self._project_root is not None:
            grep_search_results = await self._run_grep_async(query_enhanced, intent)
            if grep_search_results:
                results = self._merge_grep_results(results, grep_search_results)
            mode_used = "exhaustive"

        # Step 8.5: Record telemetry
        if self._telemetry is not None:
            self._telemetry.record(
                query=query,
                intent=intent.value,
                mode_used=mode_used,
                result_count=len(results),
                top_score=results[0].score if results else 0.0,
                z_score=confidence,
                confidence_label=confidence_label,
                reranked=was_reranked,
            )

        # Step 9: Enrich results with relationship context
        if self._enricher:
            results = self._enricher.enrich(results[:5]) + results[5:]

        return SearchResponse(
            results=results,
            query_enhanced=query_enhanced,
            total_candidates=total_candidates,
            intent=intent,
            confidence=confidence,
            confidence_label=confidence_label,
            suggestion_type=suggestion_type,
            mode_used=mode_used,
            auto_escalated=auto_escalated,
        )

    async def _run_grep_async(self, query: str, intent: QueryIntent) -> list[SearchResult]:
        """Run grep search and return results as SearchResult objects.

        Uses generate_grep_patterns + run_grep + dedup. Returns empty list
        on any failure (grep is best-effort).
        """
        if self._project_root is None:
            return []

        try:
            from clew.search.grep import generate_grep_patterns, run_grep

            patterns = generate_grep_patterns(query, [], intent)
            if not patterns:
                return []

            grep_results = await run_grep(
                patterns,
                self._project_root,
                timeout=self._config.grep_timeout,
                max_count=self._config.grep_max_count,
            )

            # Convert GrepResult -> SearchResult
            search_results: list[SearchResult] = []
            for gr in grep_results:
                search_results.append(
                    SearchResult(
                        content=gr.line_content,
                        file_path=gr.file_path,
                        score=0.0,
                        line_start=gr.line_number,
                        line_end=gr.line_number,
                        source="grep",
                    )
                )

            return search_results
        except Exception:
            logger.debug("Grep augmentation failed", exc_info=True)
            return []

    def _merge_grep_results(
        self,
        semantic_results: list[SearchResult],
        grep_results: list[SearchResult],
    ) -> list[SearchResult]:
        """Merge grep results into semantic results, deduplicating by file+line.

        Caps merged grep results at grep_response_cap to prevent noise.
        """
        # Build set of covered file+line ranges from semantic results
        covered: set[tuple[str, int]] = set()
        for r in semantic_results:
            for line in range(r.line_start, r.line_end + 1):
                covered.add((r.file_path, line))

        # Add non-overlapping grep results up to cap
        cap = self._config.grep_response_cap
        merged = list(semantic_results)
        added = 0
        for gr in grep_results:
            if added >= cap:
                break
            if (gr.file_path, gr.line_start) not in covered:
                merged.append(gr)
                added += 1

        return merged

    @staticmethod
    def _deduplicate(results: list[SearchResult]) -> list[SearchResult]:
        """Remove duplicate results covering the same code range.

        When two results share the same file_path and identical line ranges,
        keep the one with the higher score.
        """
        seen: dict[tuple[str, int, int], SearchResult] = {}
        for result in results:
            key = (result.file_path, result.line_start, result.line_end)
            existing = seen.get(key)
            if existing is None or result.score > existing.score:
                seen[key] = result
        return list(seen.values())

    @staticmethod
    def _apply_importance_boost(results: list[SearchResult]) -> list[SearchResult]:
        """Apply importance-based score boost (1.0x to 1.25x).

        Files with higher importance (more inbound edges) get a mild
        score boost to surface central code above peripheral code.
        """
        for result in results:
            if result.importance_score > 0:
                boost = 1.0 + (result.importance_score * 0.25)
                result.score *= boost
        return results

    def _apply_test_demotion(
        self, results: list[SearchResult], intent: QueryIntent
    ) -> list[SearchResult]:
        """Apply multiplicative score demotion to test file results.

        DEBUG intent gets a mild penalty (0.95); other intents get a stronger
        penalty (0.80) so production code ranks higher.
        """
        factor = (
            self._config.test_demotion_debug_factor
            if intent == QueryIntent.DEBUG
            else self._config.test_demotion_factor
        )
        demoted = 0
        for result in results:
            if result.is_test:
                result.score *= factor
                demoted += 1
        if demoted:
            logger.debug("Applied test demotion factor=%.2f to %d results", factor, demoted)
        return results

    def _compute_confidence(self, results: list[SearchResult]) -> tuple[float, str, SuggestionType]:
        """Compute confidence using statistical self-calibration (Z-score).

        Measures whether the top result stands out statistically from the pack,
        using the result set's own score distribution as the reference.
        No fixed thresholds tied to score ranges — each query self-calibrates.

        Method:
        1. Compute consecutive score gaps between adjacent results
        2. Calculate mean and std of these gaps
        3. Measure "signal gap" = top score - anchor (5th result)
        4. Z-score = (signal_gap - expected_gap) / (std_gap * sqrt(anchor_idx))

        High Z (>= 1.0) → top result stands out → high confidence
        Medium Z (>= 0.0) → moderate separation → grep might help
        Low Z (< 0.0) → flat distribution → grep likely helps
        """
        if not results or len(results) < 3:
            return 0.0, "low", SuggestionType.TRY_EXHAUSTIVE

        top = results[0].score
        if top <= 0:
            return 0.0, "low", SuggestionType.TRY_EXHAUSTIVE

        scores = [r.score for r in results[: min(10, len(results))]]

        # Compute consecutive gaps between results
        gaps = [scores[i] - scores[i + 1] for i in range(len(scores) - 1)]

        if not gaps or all(g == 0 for g in gaps):
            return 0.0, "low", SuggestionType.TRY_EXHAUSTIVE

        mean_gap = sum(gaps) / len(gaps)
        variance = sum((g - mean_gap) ** 2 for g in gaps) / len(gaps)
        std_gap = variance**0.5

        # The "signal" gap: top result vs anchor (5th result)
        anchor_idx = min(4, len(results) - 1)
        signal_gap = top - results[anchor_idx].score

        # Expected gap over anchor_idx positions
        expected_gap = mean_gap * anchor_idx

        if std_gap > 1e-9:
            z_score = (signal_gap - expected_gap) / (std_gap * (anchor_idx**0.5))
        else:
            # All gaps identical — uniform distribution means no standout result.
            # Return negative Z (low confidence) unless signal genuinely exceeds expected.
            z_score = -1.0 if signal_gap <= expected_gap + 1e-9 else 2.0

        # Z-score thresholds grounded in statistical meaning:
        # 1.5 = "1.5 standard deviations above expected" — strong standout
        # 0.5 = "0.5 standard deviations above expected" — mild standout
        high_t = self._config.z_score_high_threshold
        med_t = self._config.z_score_medium_threshold

        if z_score >= high_t:
            return z_score, "high", SuggestionType.NONE
        elif z_score >= med_t:
            return z_score, "medium", SuggestionType.TRY_KEYWORD
        else:
            return z_score, "low", SuggestionType.TRY_EXHAUSTIVE

    def _maybe_rerank(
        self,
        query: str,
        candidates: list[SearchResult],
        *,
        intent: QueryIntent | None = None,
    ) -> tuple[list[SearchResult], bool]:
        """Rerank candidates if conditions are met.

        Returns (results, was_reranked) tuple.
        """
        if not self._reranker:
            return candidates, False

        scores = [c.score for c in candidates]
        top_score = scores[0] if scores else 0.0

        if should_skip_rerank(
            query,
            len(candidates),
            top_score,
            no_rerank_threshold=self._config.no_rerank_threshold,
            high_confidence_threshold=self._config.high_confidence_threshold,
        ):
            return candidates, False

        rerank_results = self._reranker.rerank(
            query=query,
            documents=[c.content for c in candidates],
            top_k=self._config.rerank_top_k,
        )

        reranked = [candidates[r.index] for r in rerank_results]
        # Update scores from reranker
        for result, rr in zip(reranked, rerank_results):
            result.score = rr.relevance_score

        return reranked, True
