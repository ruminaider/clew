"""Voyage AI embedding provider with retry and circuit breaker."""

from __future__ import annotations

import logging

import voyageai
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from clew.exceptions import SearchUnavailableError, VoyageAuthError

from .base import EmbeddingProvider
from .circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)

_circuit_breaker = CircuitBreaker("voyage", failure_threshold=3, cooldown_seconds=60.0)


def _is_retryable_voyage_error(error: BaseException) -> bool:
    """Check if a Voyage error is retryable (rate limit or server error)."""
    if isinstance(error, (ConnectionError, TimeoutError)):
        return True
    # voyageai raises generic exceptions with status info
    error_str = str(error).lower()
    if "429" in error_str or "rate limit" in error_str:
        return True
    if any(code in error_str for code in ("500", "502", "503", "504")):
        return True
    return False


class VoyageEmbeddingProvider(EmbeddingProvider):
    """Voyage AI embedding provider (default)."""

    def __init__(self, api_key: str, model: str = "voyage-code-3") -> None:
        self._client = voyageai.AsyncClient(api_key=api_key)  # type: ignore[attr-defined]
        self._model = model
        self._dimensions = 1024

    @property
    def dimensions(self) -> int:
        return self._dimensions

    @property
    def model_name(self) -> str:
        return self._model

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        reraise=True,
    )
    async def embed(self, texts: list[str], input_type: str = "document") -> list[list[float]]:
        if _circuit_breaker.is_open:
            raise SearchUnavailableError(
                "Voyage API circuit breaker is open. Retrying in 60s."
            )
        try:
            result = await self._client.embed(
                texts,
                model=self._model,
                input_type=input_type,
                truncation=True,
            )
            _circuit_breaker.record_success()
            return result.embeddings  # type: ignore[return-value]
        except Exception as e:
            error_str = str(e).lower()
            if "401" in error_str or "403" in error_str or "auth" in error_str:
                raise VoyageAuthError() from e
            _circuit_breaker.record_failure()
            if _is_retryable_voyage_error(e):
                raise
            raise

    async def embed_query(self, query: str) -> list[float]:
        embeddings = await self.embed([query], input_type="query")
        return embeddings[0]
