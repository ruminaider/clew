"""Ollama embedding provider for local/offline operation."""

from __future__ import annotations

import logging

import httpx

from clew.exceptions import OllamaConnectionError, OllamaModelError

from .base import EmbeddingProvider

logger = logging.getLogger(__name__)

# Default Ollama model: qwen3-embedding produces 1024-dim vectors,
# matching Voyage voyage-code-3 for dimension-compatible switching.
DEFAULT_MODEL = "qwen3-embedding"
DEFAULT_URL = "http://localhost:11434"


class OllamaEmbeddingProvider(EmbeddingProvider):
    """Ollama embedding provider for local/offline operation.

    Uses Ollama's /api/embed endpoint with batch input support.
    Dimensions are auto-detected from the first embedding response.
    """

    def __init__(
        self,
        url: str = DEFAULT_URL,
        model: str = DEFAULT_MODEL,
        timeout: float = 120.0,
    ) -> None:
        self._url = url.rstrip("/")
        self._model = model
        self._timeout = timeout
        self._dimensions: int | None = None
        self._client = httpx.AsyncClient(timeout=timeout)

    @property
    def dimensions(self) -> int:
        if self._dimensions is None:
            raise RuntimeError(
                "Dimensions not yet known. Call embed() or embed_query() first."
            )
        return self._dimensions

    @property
    def model_name(self) -> str:
        return self._model

    async def embed(self, texts: list[str], input_type: str = "document") -> list[list[float]]:
        """Embed a batch of texts via Ollama /api/embed.

        Ollama doesn't distinguish input_type (query vs document),
        so the parameter is accepted but ignored for API compatibility.
        """
        if not texts:
            return []

        try:
            response = await self._client.post(
                f"{self._url}/api/embed",
                json={"model": self._model, "input": texts},
            )
        except httpx.ConnectError as e:
            raise OllamaConnectionError(self._url, e) from e
        except httpx.TimeoutException as e:
            raise OllamaConnectionError(self._url, e) from e

        if response.status_code == 404:
            raise OllamaModelError(self._model, self._url)

        response.raise_for_status()
        data = response.json()
        embeddings: list[list[float]] = data["embeddings"]

        # Auto-detect dimensions from first response
        if self._dimensions is None and embeddings:
            self._dimensions = len(embeddings[0])
            logger.info(
                "Ollama model %s: detected %d dimensions", self._model, self._dimensions
            )

        return embeddings

    async def embed_query(self, query: str) -> list[float]:
        """Embed a single query string."""
        embeddings = await self.embed([query], input_type="query")
        return embeddings[0]

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()
