"""Hybrid search engine: dense + BM25 with RRF fusion and structural boosting.

Multi-prefetch approach per DESIGN.md:
- Base dense (limit=30)
- Base BM25 (limit=30)
- Same-module boost when active_file provided (limit=15)
- Debug intent test-file boost (limit=10)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from qdrant_client import models

from code_search.indexer.metadata import detect_app_name

from .models import QueryIntent, SearchResult
from .tokenize import text_to_sparse_vector

if TYPE_CHECKING:
    from code_search.clients.base import EmbeddingProvider
    from code_search.clients.qdrant import QdrantManager

logger = logging.getLogger(__name__)


class HybridSearchEngine:
    """Perform hybrid dense + sparse search with RRF fusion and structural boosting."""

    def __init__(self, qdrant: QdrantManager, embedder: EmbeddingProvider) -> None:
        self._qdrant = qdrant
        self._embedder = embedder

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

        return [self._point_to_result(p) for p in points]

    def _build_prefetches(
        self,
        dense_vector: list[float],
        sparse_vector: models.SparseVector,
        active_file: str | None,
        intent: QueryIntent | None,
    ) -> list[models.Prefetch]:
        """Build multi-prefetch list with structural boosting.

        Per DESIGN.md lines 588-621.
        """
        prefetches: list[models.Prefetch] = [
            # Base semantic search
            models.Prefetch(query=dense_vector, using="dense", limit=30),
            # Base keyword search
            models.Prefetch(query=sparse_vector, using="bm25", limit=30),
        ]

        # Structural boost: same module gets extra candidates (Tradeoff A)
        if active_file:
            app_name = detect_app_name(active_file)
            if app_name:
                prefetches.append(
                    models.Prefetch(
                        query=dense_vector,
                        using="dense",
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

        # Intent-based boost: debug queries get more test files
        if intent == QueryIntent.DEBUG:
            prefetches.append(
                models.Prefetch(
                    query=dense_vector,
                    using="dense",
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="is_test",
                                match=models.MatchValue(value=True),
                            )
                        ]
                    ),
                    limit=10,
                )
            )

        return prefetches

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
        )
