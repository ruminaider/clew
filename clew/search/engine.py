"""Search orchestrator: enhance -> classify -> search -> rerank -> respond.

Returns SearchResponse with query_enhanced and total_candidates fields.
"""

from __future__ import annotations

import logging
import statistics
from typing import TYPE_CHECKING

from clew.models import SearchConfig

from .filters import build_qdrant_filter
from .intent import classify_intent
from .models import QueryIntent, SearchRequest, SearchResponse, SearchResult
from .rerank import should_skip_rerank

if TYPE_CHECKING:
    from clew.search.enhance import QueryEnhancer
    from clew.search.hybrid import HybridSearchEngine
    from clew.search.rerank import RerankProvider

logger = logging.getLogger(__name__)


class SearchEngine:
    """Top-level search orchestrator."""

    def __init__(
        self,
        hybrid_engine: HybridSearchEngine,
        reranker: RerankProvider | None = None,
        enhancer: QueryEnhancer | None = None,
        search_config: SearchConfig | None = None,
    ) -> None:
        self._hybrid = hybrid_engine
        self._reranker = reranker
        self._enhancer = enhancer
        self._config = search_config or SearchConfig()

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

        # Step 3: Use the collection from the request (user-specified or default)
        collection = request.collection

        # Step 4: Hybrid search with configurable candidate limit (Tradeoff B)
        query_filter = build_qdrant_filter(request.filters) if request.filters else None
        candidates = await self._hybrid.search(
            query=query_enhanced,
            collection=collection,
            limit=self._config.rerank_candidates,
            intent=intent,
            active_file=request.active_file,
            query_filter=query_filter,
        )

        total_candidates = len(candidates)

        if not candidates:
            return SearchResponse(
                results=[],
                query_enhanced=query_enhanced,
                total_candidates=0,
                intent=intent,
            )

        # Step 5: Rerank (if applicable)
        results = self._maybe_rerank(query_enhanced, candidates)

        # Step 5.4: Apply importance boost (before test demotion)
        results = self._apply_importance_boost(results)

        # Step 5.5: Demote test files
        results = self._apply_test_demotion(results, intent)
        results.sort(key=lambda r: r.score, reverse=True)

        # Step 5.6: Deduplicate overlapping results
        results = self._deduplicate(results)

        # Step 6: Apply limit
        results = results[: request.limit]

        return SearchResponse(
            results=results,
            query_enhanced=query_enhanced,
            total_candidates=total_candidates,
            intent=intent,
        )

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

    def _maybe_rerank(self, query: str, candidates: list[SearchResult]) -> list[SearchResult]:
        """Rerank candidates if conditions are met."""
        if not self._reranker:
            return candidates

        scores = [c.score for c in candidates]
        variance = statistics.variance(scores) if len(scores) > 1 else 0.0
        top_score = scores[0] if scores else 0.0

        if should_skip_rerank(
            query,
            len(candidates),
            top_score,
            variance,
            no_rerank_threshold=self._config.no_rerank_threshold,
            high_confidence_threshold=self._config.high_confidence_threshold,
            low_variance_threshold=self._config.low_variance_threshold,
        ):
            return candidates

        rerank_results = self._reranker.rerank(
            query=query,
            documents=[c.content for c in candidates],
            top_k=self._config.rerank_top_k,
        )

        reranked = [candidates[r.index] for r in rerank_results]
        # Update scores from reranker
        for result, rr in zip(reranked, rerank_results):
            result.score = rr.relevance_score

        return reranked
