"""Shared pytest fixtures."""

from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_python_file() -> str:
    """Sample Python source for testing."""
    return (FIXTURES_DIR / "python" / "sample_models.py").read_text()


@pytest.fixture
def mock_voyage_client() -> Mock:
    """Mock Voyage API client."""
    client = Mock()
    client.embed = AsyncMock(return_value=Mock(embeddings=[[0.1] * 1024]))
    client.rerank = AsyncMock(return_value=Mock(results=[Mock(index=0, relevance_score=0.95)]))
    return client


@pytest.fixture
def mock_qdrant_client() -> Mock:
    """Mock Qdrant client."""
    client = Mock()
    client.get_collections = Mock(return_value=Mock(collections=[]))
    client.create_collection = Mock()
    client.upsert = Mock()
    client.query_points = Mock(return_value=[])
    return client


@pytest.fixture
def temp_cache_dir(tmp_path: Path) -> Path:
    """Temporary directory for SQLite caches."""
    cache_dir = tmp_path / ".clew"
    cache_dir.mkdir()
    return cache_dir
