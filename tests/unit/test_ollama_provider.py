"""Tests for Ollama embedding provider."""

from __future__ import annotations

import httpx
import pytest

from clew.clients.ollama import OllamaEmbeddingProvider
from clew.exceptions import OllamaConnectionError, OllamaModelError


@pytest.fixture
def mock_embeddings() -> list[list[float]]:
    """Sample 4-dim embeddings for testing."""
    return [[0.1, 0.2, 0.3, 0.4], [0.5, 0.6, 0.7, 0.8]]


@pytest.fixture
def provider() -> OllamaEmbeddingProvider:
    return OllamaEmbeddingProvider(url="http://localhost:11434", model="test-model")


class TestOllamaEmbeddingProviderInit:
    def test_model_name(self, provider: OllamaEmbeddingProvider) -> None:
        assert provider.model_name == "test-model"

    def test_dimensions_unknown_before_first_call(self, provider: OllamaEmbeddingProvider) -> None:
        with pytest.raises(RuntimeError, match="Dimensions not yet known"):
            _ = provider.dimensions

    def test_default_model(self) -> None:
        p = OllamaEmbeddingProvider()
        assert p.model_name == "qwen3-embedding"

    def test_url_trailing_slash_stripped(self) -> None:
        p = OllamaEmbeddingProvider(url="http://localhost:11434/")
        assert p._url == "http://localhost:11434"


class TestOllamaEmbed:
    @pytest.mark.asyncio
    async def test_embed_returns_vectors(
        self, provider: OllamaEmbeddingProvider, mock_embeddings: list[list[float]]
    ) -> None:
        transport = httpx.MockTransport(
            lambda request: httpx.Response(200, json={"embeddings": mock_embeddings})
        )
        provider._client = httpx.AsyncClient(transport=transport)

        result = await provider.embed(["hello", "world"])
        assert result == mock_embeddings

    @pytest.mark.asyncio
    async def test_embed_autodetects_dimensions(
        self, provider: OllamaEmbeddingProvider, mock_embeddings: list[list[float]]
    ) -> None:
        transport = httpx.MockTransport(
            lambda request: httpx.Response(200, json={"embeddings": mock_embeddings})
        )
        provider._client = httpx.AsyncClient(transport=transport)

        await provider.embed(["hello"])
        assert provider.dimensions == 4

    @pytest.mark.asyncio
    async def test_embed_empty_list(self, provider: OllamaEmbeddingProvider) -> None:
        result = await provider.embed([])
        assert result == []

    @pytest.mark.asyncio
    async def test_embed_sends_correct_payload(
        self, provider: OllamaEmbeddingProvider, mock_embeddings: list[list[float]]
    ) -> None:
        captured_request: dict | None = None

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_request
            import json

            captured_request = json.loads(request.content)
            return httpx.Response(200, json={"embeddings": mock_embeddings})

        transport = httpx.MockTransport(handler)
        provider._client = httpx.AsyncClient(transport=transport)

        await provider.embed(["text1", "text2"])
        assert captured_request is not None
        assert captured_request["model"] == "test-model"
        assert captured_request["input"] == ["text1", "text2"]


class TestOllamaEmbedQuery:
    @pytest.mark.asyncio
    async def test_embed_query_returns_single_vector(
        self, provider: OllamaEmbeddingProvider
    ) -> None:
        embeddings = [[0.1, 0.2, 0.3]]
        transport = httpx.MockTransport(
            lambda request: httpx.Response(200, json={"embeddings": embeddings})
        )
        provider._client = httpx.AsyncClient(transport=transport)

        result = await provider.embed_query("hello")
        assert result == [0.1, 0.2, 0.3]


class TestOllamaErrorHandling:
    @pytest.mark.asyncio
    async def test_connection_error(self, provider: OllamaEmbeddingProvider) -> None:
        def raise_connect_error(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Connection refused")

        transport = httpx.MockTransport(raise_connect_error)
        provider._client = httpx.AsyncClient(transport=transport)

        with pytest.raises(OllamaConnectionError, match="Cannot connect to Ollama"):
            await provider.embed(["hello"])

    @pytest.mark.asyncio
    async def test_timeout_error(self, provider: OllamaEmbeddingProvider) -> None:
        def raise_timeout(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("Read timed out")

        transport = httpx.MockTransport(raise_timeout)
        provider._client = httpx.AsyncClient(transport=transport)

        with pytest.raises(OllamaConnectionError):
            await provider.embed(["hello"])

    @pytest.mark.asyncio
    async def test_model_not_found(self, provider: OllamaEmbeddingProvider) -> None:
        transport = httpx.MockTransport(
            lambda request: httpx.Response(404, json={"error": "model not found"})
        )
        provider._client = httpx.AsyncClient(transport=transport)

        with pytest.raises(OllamaModelError, match="not available"):
            await provider.embed(["hello"])

    @pytest.mark.asyncio
    async def test_server_error_raises(self, provider: OllamaEmbeddingProvider) -> None:
        transport = httpx.MockTransport(
            lambda request: httpx.Response(500, text="Internal Server Error")
        )
        provider._client = httpx.AsyncClient(transport=transport)

        with pytest.raises(httpx.HTTPStatusError):
            await provider.embed(["hello"])


class TestOllamaClose:
    @pytest.mark.asyncio
    async def test_close(self, provider: OllamaEmbeddingProvider) -> None:
        await provider.close()
        # Should not raise — verify client is closed
        assert provider._client.is_closed
