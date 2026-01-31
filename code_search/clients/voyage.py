"""Voyage AI embedding provider."""

from __future__ import annotations

import voyageai

from .base import EmbeddingProvider


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

    async def embed(self, texts: list[str], input_type: str = "document") -> list[list[float]]:
        result = await self._client.embed(
            texts,
            model=self._model,
            input_type=input_type,
            truncation=True,
        )
        return result.embeddings  # type: ignore[return-value]

    async def embed_query(self, query: str) -> list[float]:
        embeddings = await self.embed([query], input_type="query")
        return embeddings[0]
