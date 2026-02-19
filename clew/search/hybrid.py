"""Hybrid search engine: dense + BM25 with RRF fusion and structural boosting.

Multi-prefetch approach per DESIGN.md:
- Intent-adaptive named vector selection (signature/semantic/body)
- Base BM25 (limit varies by intent)
- Same-module boost when active_file provided (limit=15)
- Confidence-based fallback expansion
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from qdrant_client import models

from clew.indexer.metadata import detect_app_name

from .models import QueryIntent, SearchResult
from .tokenize import text_to_sparse_vector

if TYPE_CHECKING:
    from clew.clients.base import EmbeddingProvider
    from clew.clients.qdrant import QdrantManager

logger = logging.getLogger(__name__)


class HybridSearchEngine:
    """Perform hybrid dense + sparse search with RRF fusion and structural boosting."""

    def __init__(
        self,
        qdrant: QdrantManager,
        embedder: EmbeddingProvider,
        enumeration_limit: int = 200,
    ) -> None:
        self._qdrant = qdrant
        self._embedder = embedder
        self._enumeration_limit = enumeration_limit

    async def search(
        self,
        query: str,
        collection: str = "code",
        limit: int = 30,
        intent: QueryIntent | None = None,
        active_file: str | None = None,
        query_filter: models.Filter | None = None,
    ) -> list[SearchResult]:
        """Execute hybrid search with structural boosting and return ranked results."""
        # Embed query
        dense_vector = await self._embedder.embed_query(query)

        # Generate sparse query vector (raw term counts)
        sparse = text_to_sparse_vector(query)
        sparse_vector = models.SparseVector(indices=sparse.indices, values=sparse.values)

        # Build multi-prefetch with structural boosts
        prefetches = self._build_prefetches(
            dense_vector,
            sparse_vector,
            active_file,
            intent,
        )

        # Execute hybrid search via Qdrant
        points = self._qdrant.query_hybrid(
            collection=collection,
            prefetches=prefetches,
            limit=limit,
            query_filter=query_filter,
        )

        results = [self._point_to_result(p) for p in points]

        # Confidence-based fallback: expand to all vectors when primary is low
        confidence_threshold = float(os.environ.get("CLEW_CONFIDENCE_THRESHOLD", "0.65"))
        if results and results[0].score < confidence_threshold:
            results = self._expand_search(
                dense_vector, sparse_vector, results, collection, limit, query_filter
            )

        return results

    def _expand_search(
        self,
        dense_vector: list[float],
        sparse_vector: models.SparseVector,
        primary_results: list[SearchResult],
        collection: str,
        limit: int,
        query_filter: models.Filter | None,
    ) -> list[SearchResult]:
        """Fan out to all vectors when primary confidence is low."""
        all_prefetches = [
            models.Prefetch(query=dense_vector, using="signature", limit=20),
            models.Prefetch(query=dense_vector, using="semantic", limit=20),
            models.Prefetch(query=dense_vector, using="body", limit=20),
            models.Prefetch(query=sparse_vector, using="bm25", limit=30),
        ]

        expansion_points = self._qdrant.query_hybrid(
            collection=collection,
            prefetches=all_prefetches,
            limit=limit,
            query_filter=query_filter,
        )

        expansion_results = [self._point_to_result(p) for p in expansion_points]

        # Merge: keep max score per chunk_id
        merged: dict[str, SearchResult] = {}
        for result in primary_results + expansion_results:
            key = result.chunk_id or f"{result.file_path}:{result.line_start}"
            existing = merged.get(key)
            if existing is None or result.score > existing.score:
                merged[key] = result

        combined = sorted(merged.values(), key=lambda r: r.score, reverse=True)
        return combined[:limit]

    # Intent-to-vector mapping: which named vector to query per intent
    _INTENT_VECTOR_MAP: dict[QueryIntent, str] = {
        QueryIntent.LOCATION: "signature",
        QueryIntent.CODE: "semantic",
        QueryIntent.DEBUG: "semantic",
        QueryIntent.DOCS: "semantic",
        QueryIntent.ENUMERATION: "semantic",
    }

    def _build_prefetches(
        self,
        dense_vector: list[float],
        sparse_vector: models.SparseVector,
        active_file: str | None,
        intent: QueryIntent | None,
    ) -> list[models.Prefetch]:
        """Build multi-prefetch list with intent-adaptive vector selection."""
        # ENUMERATION uses dedicated BM25-heavy prefetches (no module boost)
        if intent == QueryIntent.ENUMERATION:
            return self._build_enumeration_prefetches(dense_vector, sparse_vector)

        primary_vector = self._INTENT_VECTOR_MAP.get(intent or QueryIntent.CODE, "semantic")
        bm25_limit = 50 if intent == QueryIntent.LOCATION else 30

        prefetches: list[models.Prefetch] = [
            models.Prefetch(query=dense_vector, using=primary_vector, limit=30),
            models.Prefetch(query=sparse_vector, using="bm25", limit=bm25_limit),
        ]

        # Structural boost: same module gets extra candidates (Tradeoff A)
        if active_file:
            app_name = detect_app_name(active_file)
            if app_name:
                prefetches.append(
                    models.Prefetch(
                        query=dense_vector,
                        using=primary_vector,
                        filter=models.Filter(
                            must=[
                                models.FieldCondition(
                                    key="app_name",
                                    match=models.MatchValue(value=app_name),
                                )
                            ]
                        ),
                        limit=15,
                    )
                )

        return prefetches

    def _build_enumeration_prefetches(
        self,
        dense_vector: list[float],
        sparse_vector: models.SparseVector,
    ) -> list[models.Prefetch]:
        """Build 70/30 BM25/dense prefetches for ENUMERATION intent.

        BM25 gets a much larger limit than dense. RRF fusion then naturally
        weights BM25 higher because it contributes more candidates.
        """
        return [
            models.Prefetch(query=sparse_vector, using="bm25", limit=self._enumeration_limit),
            models.Prefetch(query=dense_vector, using="semantic", limit=60),
        ]

    @staticmethod
    def _point_to_result(point: models.ScoredPoint) -> SearchResult:
        """Convert Qdrant ScoredPoint to SearchResult."""
        payload = point.payload or {}
        return SearchResult(
            content=payload.get("content", ""),
            file_path=payload.get("file_path", ""),
            score=point.score,
            chunk_type=payload.get("chunk_type", ""),
            line_start=payload.get("line_start", 0),
            line_end=payload.get("line_end", 0),
            language=payload.get("language", ""),
            class_name=payload.get("class_name", ""),
            function_name=payload.get("function_name", ""),
            signature=payload.get("signature", ""),
            app_name=payload.get("app_name", ""),
            layer=payload.get("layer", ""),
            chunk_id=payload.get("chunk_id", ""),
            docstring=payload.get("docstring", ""),
            is_test=payload.get("is_test", False),
            importance_score=payload.get("importance_score", 0.0),
        )
