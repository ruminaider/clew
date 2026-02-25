"""Local reranking providers for offline operation."""

from __future__ import annotations

import logging

from .rerank_base import RerankProvider, RerankResult

logger = logging.getLogger(__name__)


class NoopRerankProvider(RerankProvider):
    """No-op reranker that preserves original order with decaying scores.

    Used as the ultimate fallback when no reranking API or local model
    is available. Returns documents in their original order with synthetic
    scores that decay linearly, preserving the ordering from the hybrid
    search engine.
    """

    @property
    def model_name(self) -> str:
        return "noop"

    def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int = 10,
    ) -> list[RerankResult]:
        if not documents:
            return []
        n = min(top_k, len(documents))
        return [
            RerankResult(index=i, relevance_score=1.0 - (i / max(n, 1)))
            for i in range(n)
        ]


class FlashRankRerankProvider(RerankProvider):
    """FlashRank cross-encoder reranker using ONNX inference.

    Requires the `flashrank` package (optional dependency).
    Uses ms-marco-MiniLM-L-12-v2 by default (~60MB, no PyTorch needed).
    """

    def __init__(
        self,
        model_name: str = "ms-marco-MiniLM-L-12-v2",
        max_length: int = 512,
    ) -> None:
        try:
            from flashrank import Ranker
        except ImportError as e:
            raise ImportError(
                "FlashRank is required for local reranking. "
                "Install with: pip install clewdex[offline]"
            ) from e

        self._model_name = model_name
        self._ranker = Ranker(model_name=model_name, max_length=max_length)

    @property
    def model_name(self) -> str:
        return self._model_name

    def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int = 10,
    ) -> list[RerankResult]:
        if not documents:
            return []

        from flashrank import RerankRequest

        passages = [{"id": i, "text": doc} for i, doc in enumerate(documents)]
        request = RerankRequest(query=query, passages=passages)
        results = self._ranker.rerank(request)

        return [
            RerankResult(index=r["id"], relevance_score=r["score"])
            for r in results[:top_k]
        ]
