"""Qdrant vector database client wrapper with retry resilience."""

from __future__ import annotations

import logging

from qdrant_client import QdrantClient, models
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from clew.exceptions import QdrantConnectionError

logger = logging.getLogger(__name__)


class QdrantManager:
    """Manage Qdrant collections and point operations."""

    def __init__(self, url: str = "http://localhost:6333", api_key: str | None = None) -> None:
        self._url = url
        self._client = self._connect(url, api_key)

    @staticmethod
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=2),
        retry=retry_if_exception_type((ConnectionError, TimeoutError, OSError)),
        reraise=True,
    )
    def _connect(url: str, api_key: str | None) -> QdrantClient:
        try:
            return QdrantClient(url=url, api_key=api_key)
        except (ConnectionError, TimeoutError, OSError):
            raise
        except Exception as e:
            raise QdrantConnectionError(url, e) from e

    @property
    def client(self) -> QdrantClient:
        return self._client

    def ensure_collection(self, name: str, dense_dim: int = 1024) -> None:
        """Create collection with dense + BM25 sparse vectors if it doesn't exist."""
        existing = [c.name for c in self._client.get_collections().collections]
        if name in existing:
            logger.debug("Collection '%s' already exists", name)
            return

        self._client.create_collection(
            collection_name=name,
            vectors_config={
                "dense": models.VectorParams(
                    size=dense_dim,
                    distance=models.Distance.COSINE,
                )
            },
            sparse_vectors_config={
                "bm25": models.SparseVectorParams(
                    modifier=models.Modifier.IDF,
                )
            },
        )
        logger.info(
            "Created collection '%s' (dense=%d dims, sparse=bm25+IDF)",
            name,
            dense_dim,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=2),
        retry=retry_if_exception_type((ConnectionError, TimeoutError, OSError)),
        reraise=True,
    )
    def upsert_points(self, collection: str, points: list[models.PointStruct]) -> None:
        """Upsert points into a collection."""
        self._client.upsert(collection_name=collection, points=points)

    def delete_by_file_path(self, collection: str, file_path: str) -> None:
        """Delete all points matching a file_path."""
        self._client.delete(
            collection_name=collection,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="file_path",
                            match=models.MatchValue(value=file_path),
                        )
                    ]
                )
            ),
        )
        logger.debug(
            "Deleted points for file_path='%s' from '%s'",
            file_path,
            collection,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=2),
        retry=retry_if_exception_type((ConnectionError, TimeoutError, OSError)),
        reraise=True,
    )
    def query_hybrid(
        self,
        collection: str,
        prefetches: list[models.Prefetch],
        limit: int = 30,
        query_filter: models.Filter | None = None,
    ) -> list[models.ScoredPoint]:
        """Perform hybrid search with multi-prefetch and RRF fusion."""
        result = self._client.query_points(
            collection_name=collection,
            prefetch=prefetches,
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=limit,
            with_payload=True,
            query_filter=query_filter,
        )
        return result.points

    def collection_exists(self, name: str) -> bool:
        """Check if a collection exists."""
        return name in [c.name for c in self._client.get_collections().collections]

    def collection_count(self, name: str) -> int:
        """Get the number of points in a collection."""
        return self._client.count(collection_name=name).count

    def health_check(self) -> bool | str:
        """Check if Qdrant is reachable. Returns True if healthy, error string if not."""
        try:
            self._client.get_collections()
            return True
        except Exception as e:
            logger.warning("Qdrant health check failed: %s", e)
            return str(e)
