"""Voyage AI reranking integration.

Candidate limit is configurable via SearchConfig (default 30, Tradeoff B).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import voyageai


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
    """Determine if reranking should be skipped.

    Skip conditions (per DESIGN.md):
    1. Few candidates (<=threshold) — no benefit
    2. High confidence top result (>0.92)
    3. Low score variance (<0.1) — already well-ranked
    4. Exact identifier (PascalCase)
    5. File path query
    """
    if num_candidates <= no_rerank_threshold:
        return True
    if top_score > high_confidence_threshold:
        return True
    if score_variance < low_variance_threshold:
        return True
    if re.match(r"^[A-Z][a-zA-Z0-9]+$", query):
        return True
    if "/" in query or query.endswith((".py", ".ts", ".js")):
        return True
    return False


class RerankProvider:
    """Voyage AI reranking provider."""

    def __init__(self, api_key: str, model: str = "rerank-2.5") -> None:
        self._client = voyageai.Client(api_key=api_key)  # type: ignore[attr-defined]
        self._model = model

    def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int = 10,
    ) -> list[RerankResult]:
        """Rerank documents by relevance to query."""
        if not documents:
            return []

        result = self._client.rerank(
            query=query,
            documents=documents,
            model=self._model,
            top_k=top_k,
            truncation=True,
        )
        return [
            RerankResult(index=r.index, relevance_score=r.relevance_score) for r in result.results
        ]
