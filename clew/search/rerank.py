"""Voyage AI reranking integration with retry and circuit breaker."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import voyageai
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from clew.clients.circuit_breaker import CircuitBreaker
from clew.exceptions import SearchUnavailableError

logger = logging.getLogger(__name__)

_circuit_breaker = CircuitBreaker("rerank", failure_threshold=3, cooldown_seconds=60.0)


@dataclass
class RerankResult:
    """A reranked document with its new score."""

    index: int
    relevance_score: float


def should_skip_rerank(
    query: str,
    num_candidates: int,
    top_score: float,
    score_variance: float,
    *,
    no_rerank_threshold: int = 10,
    high_confidence_threshold: float = 0.92,
    low_variance_threshold: float = 0.1,
) -> bool:
    """Determine if reranking should be skipped."""
    if num_candidates <= no_rerank_threshold:
        return True
    if top_score > high_confidence_threshold:
        return True
    if score_variance < low_variance_threshold:
        return True
    if "/" in query or query.endswith((".py", ".ts", ".js")):
        return True
    return False


class RerankProvider:
    """Voyage AI reranking provider with retry and circuit breaker."""

    def __init__(self, api_key: str, model: str = "rerank-2.5") -> None:
        self._client = voyageai.Client(api_key=api_key)  # type: ignore[attr-defined]
        self._model = model

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        reraise=True,
    )
    def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int = 10,
    ) -> list[RerankResult]:
        """Rerank documents by relevance to query."""
        if not documents:
            return []

        if _circuit_breaker.is_open:
            raise SearchUnavailableError("Rerank API circuit breaker is open. Retrying in 60s.")

        try:
            result = self._client.rerank(
                query=query,
                documents=documents,
                model=self._model,
                top_k=top_k,
                truncation=True,
            )
            _circuit_breaker.record_success()
            return [
                RerankResult(index=r.index, relevance_score=r.relevance_score)
                for r in result.results
            ]
        except Exception:
            _circuit_breaker.record_failure()
            raise
