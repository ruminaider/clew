"""Abstract base class for reranking providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class RerankResult:
    """A reranked document with its new score."""

    index: int
    relevance_score: float


class RerankProvider(ABC):
    """Abstract base class for reranking providers."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model identifier."""
        ...

    @abstractmethod
    def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int = 10,
    ) -> list[RerankResult]:
        """Rerank documents by relevance to query.

        Args:
            query: The search query.
            documents: List of document texts to rerank.
            top_k: Maximum number of results to return.

        Returns:
            List of RerankResult sorted by relevance_score descending.
        """
        ...
