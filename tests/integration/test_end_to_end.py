"""End-to-end integration tests for the code-search pipeline.

These tests verify the full pipeline: index -> search -> results.
They mock external services (Qdrant, Voyage) but test real file processing,
chunking, metadata extraction, and pipeline wiring.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest

from code_search.indexer.change_detector import ChangeDetector


@pytest.fixture
def mock_qdrant():
    """Mock QdrantManager that stores points in memory."""
    qdrant = Mock()
    qdrant.health_check.return_value = True
    qdrant.collection_exists.return_value = True
    qdrant.ensure_collection = Mock()

    # Store upserted points
    stored_points: list = []

    def upsert_points(collection, points):
        stored_points.extend(points)

    qdrant.upsert_points = Mock(side_effect=upsert_points)
    qdrant.delete_by_file_path = Mock()
    qdrant._stored_points = stored_points

    # Mock query_hybrid to return stored points as search results
    def query_hybrid(collection, prefetches, limit=30, query_filter=None):
        results = []
        for p in stored_points[:limit]:
            scored = Mock()
            scored.score = 0.9
            scored.payload = p.payload
            results.append(scored)
        return results

    qdrant.query_hybrid = Mock(side_effect=query_hybrid)
    qdrant.collection_count.return_value = 0

    return qdrant


@pytest.fixture
def mock_embedder():
    """Mock EmbeddingProvider that returns deterministic vectors."""
    embedder = Mock()
    embedder.dimensions = 1024
    embedder.model_name = "test-model"

    async def embed(texts, input_type="document"):
        return [[0.1] * 1024 for _ in texts]

    embedder.embed = AsyncMock(side_effect=embed)

    async def embed_query(text):
        return [0.1] * 1024

    embedder.embed_query = AsyncMock(side_effect=embed_query)

    return embedder


@pytest.mark.integration
class TestIndexThenSearch:
    """Test the full index -> search pipeline."""

    async def test_index_creates_chunks(self, sample_project, mock_qdrant, mock_embedder):
        """Index sample files and verify chunks are created."""
        from code_search.indexer.pipeline import IndexingPipeline

        pipeline = IndexingPipeline(qdrant=mock_qdrant, embedder=mock_embedder)

        files = list(sample_project.rglob("*.py"))
        result = await pipeline.index_files(files, collection="code")

        assert result.files_processed == 3  # models.py, auth.py, utils.py
        assert result.chunks_created > 0
        assert result.errors == []
        assert mock_qdrant.upsert_points.called

    async def test_index_then_search(self, sample_project, mock_qdrant, mock_embedder):
        """Index files then search returns relevant results."""
        from code_search.indexer.pipeline import IndexingPipeline
        from code_search.search.engine import SearchEngine
        from code_search.search.hybrid import HybridSearchEngine
        from code_search.search.models import SearchRequest

        # Index
        pipeline = IndexingPipeline(qdrant=mock_qdrant, embedder=mock_embedder)
        files = list(sample_project.rglob("*.py"))
        await pipeline.index_files(files, collection="code")

        # Search
        hybrid = HybridSearchEngine(qdrant=mock_qdrant, embedder=mock_embedder)
        engine = SearchEngine(hybrid_engine=hybrid)

        request = SearchRequest(query="authenticate user", limit=5)
        response = await engine.search(request)

        assert len(response.results) > 0
        assert response.query_enhanced is not None
        assert response.intent is not None

    async def test_index_typescript_files(self, sample_project, mock_qdrant, mock_embedder):
        """TypeScript files are indexed successfully."""
        from code_search.indexer.pipeline import IndexingPipeline

        pipeline = IndexingPipeline(qdrant=mock_qdrant, embedder=mock_embedder)

        files = list(sample_project.rglob("*.ts"))
        result = await pipeline.index_files(files, collection="code")

        assert result.files_processed == 1  # api.ts
        assert result.chunks_created > 0

    async def test_indexed_chunks_have_metadata(self, sample_project, mock_qdrant, mock_embedder):
        """Indexed chunks contain expected metadata fields."""
        from code_search.indexer.pipeline import IndexingPipeline

        pipeline = IndexingPipeline(qdrant=mock_qdrant, embedder=mock_embedder)

        files = list(sample_project.rglob("*.py"))
        await pipeline.index_files(files, collection="code")

        # Check that points were stored with expected payload keys
        assert len(mock_qdrant._stored_points) > 0
        point = mock_qdrant._stored_points[0]
        payload = point.payload
        assert "content" in payload
        assert "file_path" in payload
        assert "language" in payload
        assert "chunk_type" in payload
        assert "indexed_at" in payload
        assert payload["language"] == "python"


@pytest.mark.integration
class TestChangeDetection:
    """Test change detection with real file operations."""

    def test_fresh_index_detects_all_as_added(self, sample_project, temp_cache_dir):
        """First-time indexing detects all files as added."""
        from code_search.indexer.cache import CacheDB

        cache = CacheDB(temp_cache_dir)
        detector = ChangeDetector(sample_project, cache)

        files = [str(p) for p in sample_project.rglob("*.py")]
        result = detector.detect_changes(files)

        # All files should be "added" (no previous hashes)
        assert result.source == "hash"
        assert len(result.added) == len(files)
        assert result.modified == []

    def test_unchanged_files_detected(self, sample_project, temp_cache_dir):
        """Files with cached hashes are detected as unchanged."""
        from code_search.indexer.cache import CacheDB
        from code_search.indexer.file_hash import FileHashTracker

        cache = CacheDB(temp_cache_dir)
        tracker = FileHashTracker(cache)

        # Simulate a previous index by caching hashes
        files = [str(p) for p in sample_project.rglob("*.py")]
        for f in files:
            h = tracker.compute_hash(f)
            tracker.update_hash(f, h, ["chunk1"])

        # Now detect changes -- all should be unchanged
        detector = ChangeDetector(sample_project, cache)
        result = detector.detect_changes(files)

        assert result.source == "hash"
        assert result.added == []
        assert result.modified == []
        assert len(result.unchanged) == len(files)

    def test_modified_file_detected(self, sample_project, temp_cache_dir):
        """Modified files are detected after content changes."""
        from code_search.indexer.cache import CacheDB
        from code_search.indexer.file_hash import FileHashTracker

        cache = CacheDB(temp_cache_dir)
        tracker = FileHashTracker(cache)

        auth_file = sample_project / "src" / "auth.py"
        auth_path = str(auth_file)

        # Cache original hash
        h = tracker.compute_hash(auth_path)
        tracker.update_hash(auth_path, h, ["chunk1"])

        # Modify the file
        auth_file.write_text("# modified content\n")

        # Detect changes
        detector = ChangeDetector(sample_project, cache)
        result = detector.detect_changes([auth_path])

        assert result.source == "hash"
        assert auth_path in result.modified


@pytest.mark.integration
class TestMCPToolsWithMockedBackend:
    """Test MCP tools with mocked factory components."""

    async def test_mcp_search_tool(self, sample_project):
        """MCP search tool returns structured output."""
        from code_search.mcp_server import search
        from code_search.search.models import SearchResult

        mock_result = SearchResult(
            file_path="src/auth.py",
            content="def authenticate(): pass",
            score=0.9,
            chunk_type="function",
            line_start=3,
            line_end=7,
            language="python",
            class_name="",
            function_name="authenticate",
        )
        mock_response = Mock(results=[mock_result])

        mock_components = Mock()
        mock_components.search_engine.search = AsyncMock(return_value=mock_response)

        with patch("code_search.mcp_server._get_components", return_value=mock_components):
            results = await search("authenticate")

        assert isinstance(results, list)
        assert len(results) == 1
        assert results[0]["file_path"] == "src/auth.py"
        assert results[0]["function_name"] == "authenticate"

    async def test_mcp_get_context_reads_real_file(self, sample_project):
        """MCP get_context reads real files from disk."""
        from code_search.mcp_server import get_context

        mock_components = Mock()
        mock_components.search_engine.search = AsyncMock(return_value=Mock(results=[]))

        file_path = str(sample_project / "src" / "models.py")

        with patch("code_search.mcp_server._get_components", return_value=mock_components):
            result = await get_context(file_path)

        assert result["file_path"] == file_path
        assert "User" in result["content"]
        assert result["language"] == "python"

    async def test_mcp_index_status(self):
        """MCP index_status returns structured status."""
        from code_search.mcp_server import index_status

        mock_components = Mock()
        mock_components.qdrant.health_check.return_value = True
        mock_components.qdrant.collection_exists.return_value = True
        mock_components.qdrant.collection_count.return_value = 100
        mock_components.cache.get_last_indexed_commit.return_value = "abc123"

        with patch("code_search.mcp_server._get_components", return_value=mock_components):
            result = await index_status(action="status")

        assert result["qdrant_healthy"] is True
        assert result["indexed"] is True
        assert result["last_commit"] == "abc123"

    async def test_mcp_search_returns_error_on_failure(self):
        """MCP search tool returns error dict on exception."""
        from code_search.exceptions import QdrantConnectionError
        from code_search.mcp_server import search

        mock_components = Mock()
        mock_components.search_engine.search = AsyncMock(
            side_effect=QdrantConnectionError(
                "http://localhost:6333", Exception("connection refused")
            )
        )

        with patch("code_search.mcp_server._get_components", return_value=mock_components):
            result = await search("test query")

        assert isinstance(result, dict)
        assert "error" in result
        assert "fix" in result

    async def test_mcp_get_context_missing_file(self):
        """MCP get_context returns error for missing file."""
        from code_search.mcp_server import get_context

        mock_components = Mock()

        with patch("code_search.mcp_server._get_components", return_value=mock_components):
            result = await get_context("/nonexistent/file.py")

        assert "error" in result
        assert "fix" in result
