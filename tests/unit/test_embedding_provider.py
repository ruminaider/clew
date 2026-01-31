"""Tests for embedding provider abstraction."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from code_search.clients.base import EmbeddingProvider
from code_search.clients.voyage import VoyageEmbeddingProvider


class TestEmbeddingProviderABC:
    def test_cannot_instantiate_abc(self) -> None:
        with pytest.raises(TypeError):
            EmbeddingProvider()  # type: ignore[abstract]


class TestVoyageEmbeddingProvider:
    def test_dimensions(self) -> None:
        with patch("code_search.clients.voyage.voyageai"):
            provider = VoyageEmbeddingProvider(api_key="test-key")
        assert provider.dimensions == 1024

    def test_model_name(self) -> None:
        with patch("code_search.clients.voyage.voyageai"):
            provider = VoyageEmbeddingProvider(api_key="test-key")
        assert provider.model_name == "voyage-code-3"

    def test_custom_model(self) -> None:
        with patch("code_search.clients.voyage.voyageai"):
            provider = VoyageEmbeddingProvider(api_key="test-key", model="voyage-3")
        assert provider.model_name == "voyage-3"

    @pytest.mark.asyncio
    async def test_embed_returns_embeddings(self) -> None:
        mock_client = AsyncMock()
        mock_client.embed.return_value = Mock(embeddings=[[0.1] * 1024, [0.2] * 1024])

        with patch("code_search.clients.voyage.voyageai") as mock_voyage:
            mock_voyage.AsyncClient.return_value = mock_client
            provider = VoyageEmbeddingProvider(api_key="test-key")

        result = await provider.embed(["hello", "world"])
        assert len(result) == 2
        assert len(result[0]) == 1024

    @pytest.mark.asyncio
    async def test_embed_query_returns_single_vector(self) -> None:
        mock_client = AsyncMock()
        mock_client.embed.return_value = Mock(embeddings=[[0.1] * 1024])

        with patch("code_search.clients.voyage.voyageai") as mock_voyage:
            mock_voyage.AsyncClient.return_value = mock_client
            provider = VoyageEmbeddingProvider(api_key="test-key")

        result = await provider.embed_query("test query")
        assert len(result) == 1024
