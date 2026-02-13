"""Tests for Qdrant collection manager."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from clew.clients.qdrant import QdrantManager


def _collection(name: str) -> SimpleNamespace:
    """Create a mock collection with a proper .name attribute."""
    return SimpleNamespace(name=name)


@pytest.fixture
def mock_client() -> Mock:
    client = Mock()
    client.get_collections.return_value = Mock(collections=[])
    client.create_collection = Mock()
    client.upsert = Mock()
    client.count.return_value = Mock(count=42)
    client.query_points.return_value = Mock(points=[])
    client.delete = Mock()
    return client


@pytest.fixture
def manager(mock_client: Mock) -> QdrantManager:
    with patch("clew.clients.qdrant.QdrantClient", return_value=mock_client):
        return QdrantManager(url="http://localhost:6333")


class TestEnsureCollection:
    def test_creates_when_missing(self, manager: QdrantManager, mock_client: Mock) -> None:
        manager.ensure_collection("code")
        mock_client.create_collection.assert_called_once()

    def test_skips_when_exists(self, manager: QdrantManager, mock_client: Mock) -> None:
        mock_client.get_collections.return_value = Mock(collections=[_collection("code")])
        manager.ensure_collection("code")
        mock_client.create_collection.assert_not_called()

    def test_creates_with_named_vectors_and_bm25_sparse(
        self,
        manager: QdrantManager,
        mock_client: Mock,
    ) -> None:
        """Collection must have 3 named vectors and bm25 sparse vector."""
        manager.ensure_collection("code", dense_dim=1024)
        call_kwargs = mock_client.create_collection.call_args
        vectors_config = call_kwargs.kwargs["vectors_config"]
        assert "signature" in vectors_config
        assert "semantic" in vectors_config
        assert "body" in vectors_config
        assert "bm25" in call_kwargs.kwargs["sparse_vectors_config"]


class TestUpsertPoints:
    def test_delegates_to_client(self, manager: QdrantManager, mock_client: Mock) -> None:
        points = [Mock()]
        manager.upsert_points("code", points)
        mock_client.upsert.assert_called_once_with(collection_name="code", points=points)


class TestDeleteByFilePath:
    def test_deletes_points_by_filter(self, manager: QdrantManager, mock_client: Mock) -> None:
        manager.delete_by_file_path("code", "backend/models.py")
        mock_client.delete.assert_called_once()
        call_args = mock_client.delete.call_args
        assert call_args.kwargs["collection_name"] == "code"


class TestQueryHybrid:
    def test_returns_points(self, manager: QdrantManager, mock_client: Mock) -> None:
        from qdrant_client import models

        mock_client.query_points.return_value = Mock(
            points=[Mock(id="1", score=0.9, payload={"content": "hello"})]
        )
        results = manager.query_hybrid(
            "code",
            prefetches=[
                models.Prefetch(query=[0.1] * 1024, using="dense", limit=30),
            ],
        )
        assert len(results) == 1
        mock_client.query_points.assert_called_once()

    def test_passes_limit(self, manager: QdrantManager, mock_client: Mock) -> None:
        from qdrant_client import models

        mock_client.query_points.return_value = Mock(points=[])
        manager.query_hybrid(
            "code",
            prefetches=[models.Prefetch(query=[0.1] * 1024, using="dense", limit=30)],
            limit=20,
        )
        call_kwargs = mock_client.query_points.call_args.kwargs
        assert call_kwargs["limit"] == 20


class TestDeleteCollection:
    def test_deletes_existing_collection(self, manager: QdrantManager, mock_client: Mock) -> None:
        mock_client.get_collections.return_value = Mock(collections=[_collection("code")])
        manager.delete_collection("code")
        mock_client.delete_collection.assert_called_once_with(collection_name="code")

    def test_noop_when_collection_missing(self, manager: QdrantManager, mock_client: Mock) -> None:
        mock_client.get_collections.return_value = Mock(collections=[])
        manager.delete_collection("code")
        mock_client.delete_collection.assert_not_called()


class TestHealthCheck:
    def test_returns_true_when_healthy(self, manager: QdrantManager) -> None:
        assert manager.health_check() is True

    def test_returns_error_string_on_failure(
        self, manager: QdrantManager, mock_client: Mock
    ) -> None:
        mock_client.get_collections.side_effect = Exception("connection refused")
        result = manager.health_check()
        assert result != True  # noqa: E712
        assert isinstance(result, str)
        assert "connection refused" in result


class TestCollectionInfo:
    def test_collection_exists(self, manager: QdrantManager, mock_client: Mock) -> None:
        mock_client.get_collections.return_value = Mock(collections=[_collection("code")])
        assert manager.collection_exists("code") is True
        assert manager.collection_exists("other") is False

    def test_collection_count(self, manager: QdrantManager) -> None:
        assert manager.collection_count("code") == 42
