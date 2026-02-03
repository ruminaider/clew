"""Tests for the indexing pipeline."""

from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from code_search.indexer.pipeline import (
    IndexingPipeline,
    IndexingResult,
    _detect_language,
    _is_test_file,
)


class TestDetectLanguage:
    def test_python(self) -> None:
        assert _detect_language("models.py") == "python"

    def test_typescript(self) -> None:
        assert _detect_language("app.ts") == "typescript"

    def test_tsx(self) -> None:
        assert _detect_language("Component.tsx") == "tsx"

    def test_javascript(self) -> None:
        assert _detect_language("index.js") == "javascript"

    def test_markdown(self) -> None:
        assert _detect_language("README.md") == "markdown"

    def test_unknown(self) -> None:
        assert _detect_language("data.csv") == "unknown"


class TestIsTestFile:
    def test_test_prefix(self) -> None:
        assert _is_test_file("tests/test_auth.py") is True

    def test_test_directory(self) -> None:
        assert _is_test_file("tests/unit/test_models.py") is True

    def test_spec_suffix(self) -> None:
        assert _is_test_file("src/auth.spec.ts") is True

    def test_not_test(self) -> None:
        assert _is_test_file("src/models.py") is False


class TestIndexingResult:
    def test_create(self) -> None:
        result = IndexingResult(files_processed=10, chunks_created=50, files_skipped=2)
        assert result.files_processed == 10


class TestIndexingPipeline:
    @pytest.fixture
    def mock_qdrant(self) -> Mock:
        qdrant = Mock()
        qdrant.ensure_collection = Mock()
        qdrant.upsert_points = Mock()
        qdrant.delete_by_file_path = Mock()
        return qdrant

    @pytest.fixture
    def mock_embedder(self) -> Mock:
        embedder = Mock()
        embedder.embed = AsyncMock(side_effect=lambda texts, **kwargs: [[0.1] * 1024] * len(texts))
        embedder.model_name = "voyage-code-3"
        embedder.dimensions = 1024
        return embedder

    @pytest.fixture
    def pipeline(self, mock_qdrant: Mock, mock_embedder: Mock) -> IndexingPipeline:
        return IndexingPipeline(
            qdrant=mock_qdrant,
            embedder=mock_embedder,
            batch_size=10,
        )

    async def test_index_single_file(
        self,
        pipeline: IndexingPipeline,
        mock_qdrant: Mock,
        tmp_path: Path,
    ) -> None:
        f = tmp_path / "hello.py"
        f.write_text("def hello():\n    return 'world'\n")
        result = await pipeline.index_files([f], collection="code")
        assert result.files_processed == 1
        assert result.chunks_created >= 1
        mock_qdrant.upsert_points.assert_called()

    async def test_skips_empty_file(self, pipeline: IndexingPipeline, tmp_path: Path) -> None:
        f = tmp_path / "empty.py"
        f.write_text("")
        result = await pipeline.index_files([f], collection="code")
        assert result.files_processed == 0

    async def test_embeds_chunks(
        self,
        pipeline: IndexingPipeline,
        mock_embedder: Mock,
        tmp_path: Path,
    ) -> None:
        f = tmp_path / "code.py"
        f.write_text("x = 1\ny = 2\n")
        await pipeline.index_files([f], collection="code")
        mock_embedder.embed.assert_called()

    async def test_point_id_is_deterministic_uuid(
        self,
        pipeline: IndexingPipeline,
        mock_qdrant: Mock,
        tmp_path: Path,
    ) -> None:
        """Point IDs should be deterministic UUIDs (Qdrant requirement)."""
        import uuid

        f = tmp_path / "models.py"
        f.write_text("x = 1\n")
        await pipeline.index_files([f], collection="code")
        points = mock_qdrant.upsert_points.call_args[0][1]
        for point in points:
            # ID should be a valid UUID string
            uuid.UUID(point.id)  # raises ValueError if not valid
            # Structured chunk_id should be in the payload instead
            assert "::" in point.payload["chunk_id"]

    async def test_payload_has_metadata_fields(
        self,
        pipeline: IndexingPipeline,
        mock_qdrant: Mock,
        tmp_path: Path,
    ) -> None:
        f = tmp_path / "models.py"
        f.write_text("x = 1\n")
        await pipeline.index_files([f], collection="code")
        points = mock_qdrant.upsert_points.call_args[0][1]
        payload = points[0].payload
        assert "app_name" in payload
        assert "layer" in payload
        assert "chunk_id" in payload
        assert "is_test" in payload
        assert "source_type" in payload

    async def test_sparse_vector_uses_bm25_name(
        self,
        pipeline: IndexingPipeline,
        mock_qdrant: Mock,
        tmp_path: Path,
    ) -> None:
        """Sparse vector key must be 'bm25', not 'sparse'."""
        f = tmp_path / "code.py"
        f.write_text("x = 1\n")
        await pipeline.index_files([f], collection="code")
        points = mock_qdrant.upsert_points.call_args[0][1]
        vector = points[0].vector
        assert "bm25" in vector
        assert "dense" in vector

    async def test_result_accumulates(self, pipeline: IndexingPipeline, tmp_path: Path) -> None:
        for i in range(3):
            (tmp_path / f"file{i}.py").write_text(f"x = {i}\n")
        files = list(tmp_path.glob("*.py"))
        result = await pipeline.index_files(files, collection="code")
        assert result.files_processed == 3

    async def test_deletes_stale_chunks(
        self,
        pipeline: IndexingPipeline,
        mock_qdrant: Mock,
        tmp_path: Path,
    ) -> None:
        """Modified files should have old chunks deleted first."""
        f = tmp_path / "models.py"
        f.write_text("x = 1\n")
        await pipeline.index_files([f], collection="code", delete_before_upsert=True)
        mock_qdrant.delete_by_file_path.assert_called()
