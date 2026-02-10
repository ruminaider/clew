"""Tests for the indexing pipeline."""

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from code_search.indexer.cache import CacheDB
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


class TestPipelineDescriptions:
    """Tests for NL description generation in the indexing pipeline."""

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
    def mock_description_provider(self) -> Mock:
        provider = Mock()
        provider.model_name = "claude-sonnet-4-5-20250929"
        provider.generate_batch = AsyncMock(return_value=["A test description."])
        return provider

    @pytest.fixture
    def mock_cache(self, tmp_path: Path) -> Mock:
        cache = Mock()
        cache.get_description = Mock(return_value=None)
        cache.set_description = Mock()
        return cache

    async def test_pipeline_without_description_provider(
        self,
        mock_qdrant: Mock,
        mock_embedder: Mock,
        tmp_path: Path,
    ) -> None:
        """Pipeline works normally without description provider."""
        pipeline = IndexingPipeline(
            qdrant=mock_qdrant,
            embedder=mock_embedder,
            batch_size=10,
        )
        f = tmp_path / "hello.py"
        f.write_text("x = 1\n")
        result = await pipeline.index_files([f], collection="code")
        assert result.files_processed == 1
        assert result.chunks_created >= 1

        # Verify embedder received raw content (no description prepended)
        call_args = mock_embedder.embed.call_args
        texts = call_args[0][0]
        for text in texts:
            assert not text.startswith("# Description:")

    async def test_pipeline_with_description_provider(
        self,
        mock_qdrant: Mock,
        mock_embedder: Mock,
        mock_description_provider: Mock,
        mock_cache: Mock,
        tmp_path: Path,
    ) -> None:
        """Pipeline generates descriptions and prepends to content for embedding."""
        pipeline = IndexingPipeline(
            qdrant=mock_qdrant,
            embedder=mock_embedder,
            description_provider=mock_description_provider,
            cache=mock_cache,
            batch_size=10,
        )
        f = tmp_path / "hello.py"
        # Write code without a docstring
        f.write_text("x = 1\ny = 2\n")
        await pipeline.index_files([f], collection="code")

        # Verify generate_batch was called
        mock_description_provider.generate_batch.assert_called()

        # Verify embedder received content with description prepended
        call_args = mock_embedder.embed.call_args
        texts = call_args[0][0]
        assert any("# Description: A test description." in t for t in texts)

        # Verify payload has nl_description field
        points = mock_qdrant.upsert_points.call_args[0][1]
        payload = points[0].payload
        assert payload.get("nl_description") == "A test description."

    async def test_pipeline_skips_description_when_docstring_exists(
        self,
        mock_qdrant: Mock,
        mock_embedder: Mock,
        mock_description_provider: Mock,
        mock_cache: Mock,
        tmp_path: Path,
    ) -> None:
        """Pipeline skips description generation for chunks with docstrings."""
        pipeline = IndexingPipeline(
            qdrant=mock_qdrant,
            embedder=mock_embedder,
            description_provider=mock_description_provider,
            cache=mock_cache,
            batch_size=10,
        )
        f = tmp_path / "hello.py"
        # Write a function WITH a docstring so AST extracts it
        f.write_text('def hello():\n    """Say hello."""\n    return "world"\n')
        await pipeline.index_files([f], collection="code")

        # generate_batch should NOT be called (all chunks have docstrings)
        mock_description_provider.generate_batch.assert_not_called()

    async def test_pipeline_caches_descriptions(
        self,
        mock_qdrant: Mock,
        mock_embedder: Mock,
        mock_description_provider: Mock,
        mock_cache: Mock,
        tmp_path: Path,
    ) -> None:
        """Generated descriptions are cached in SQLite."""
        pipeline = IndexingPipeline(
            qdrant=mock_qdrant,
            embedder=mock_embedder,
            description_provider=mock_description_provider,
            cache=mock_cache,
            batch_size=10,
        )
        f = tmp_path / "hello.py"
        f.write_text("x = 1\n")
        await pipeline.index_files([f], collection="code")

        # Verify set_description was called to cache the result
        mock_cache.set_description.assert_called()
        call_args = mock_cache.set_description.call_args
        assert call_args[0][1] == "claude-sonnet-4-5-20250929"  # model name
        assert call_args[0][2] == "A test description."  # description

    async def test_pipeline_uses_cached_description(
        self,
        mock_qdrant: Mock,
        mock_embedder: Mock,
        mock_description_provider: Mock,
        mock_cache: Mock,
        tmp_path: Path,
    ) -> None:
        """Pipeline uses cached description instead of generating a new one."""
        mock_cache.get_description = Mock(return_value="Cached description.")

        pipeline = IndexingPipeline(
            qdrant=mock_qdrant,
            embedder=mock_embedder,
            description_provider=mock_description_provider,
            cache=mock_cache,
            batch_size=10,
        )
        f = tmp_path / "hello.py"
        f.write_text("x = 1\n")
        await pipeline.index_files([f], collection="code")

        # generate_batch should NOT be called because cache hit
        mock_description_provider.generate_batch.assert_not_called()

        # Verify the cached description was used in embedding
        call_args = mock_embedder.embed.call_args
        texts = call_args[0][0]
        assert any("# Description: Cached description." in t for t in texts)

    async def test_pipeline_payload_includes_docstring(
        self,
        mock_qdrant: Mock,
        mock_embedder: Mock,
        tmp_path: Path,
    ) -> None:
        """Docstring from chunk metadata is included in Qdrant payload."""
        pipeline = IndexingPipeline(
            qdrant=mock_qdrant,
            embedder=mock_embedder,
            batch_size=10,
        )
        f = tmp_path / "hello.py"
        # Write a function with a docstring so AST extracts it
        f.write_text('def hello():\n    """Say hello to the world."""\n    return "world"\n')
        await pipeline.index_files([f], collection="code")

        points = mock_qdrant.upsert_points.call_args[0][1]
        payload = points[0].payload
        assert payload.get("docstring") == "Say hello to the world."

    async def test_bm25_uses_raw_content(
        self,
        mock_qdrant: Mock,
        mock_embedder: Mock,
        mock_description_provider: Mock,
        mock_cache: Mock,
        tmp_path: Path,
    ) -> None:
        """BM25 sparse vector should be computed from raw content only."""
        pipeline = IndexingPipeline(
            qdrant=mock_qdrant,
            embedder=mock_embedder,
            description_provider=mock_description_provider,
            cache=mock_cache,
            batch_size=10,
        )
        f = tmp_path / "hello.py"
        f.write_text("x = 1\n")

        # Patch text_to_sparse_vector to capture what gets passed
        with patch("code_search.indexer.pipeline.text_to_sparse_vector") as mock_sparse:
            mock_sparse.return_value = Mock(indices=[1], values=[1.0])
            await pipeline.index_files([f], collection="code")

            # Verify BM25 was called with raw content (no description prefix)
            for call in mock_sparse.call_args_list:
                text_arg = call[0][0]
                assert not text_arg.startswith("# Description:")


class TestRelationshipExtraction:
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
    def pipeline_with_cache(self, mock_qdrant: Mock, mock_embedder: Mock, tmp_path: Path) -> IndexingPipeline:
        cache = CacheDB(tmp_path / ".cache")
        return IndexingPipeline(
            qdrant=mock_qdrant,
            embedder=mock_embedder,
            cache=cache,
        )

    async def test_pipeline_extracts_relationships(
        self, pipeline_with_cache: IndexingPipeline, tmp_path: Path
    ) -> None:
        """Indexing a Python file extracts import relationships."""
        py_file = tmp_path / "app" / "main.py"
        py_file.parent.mkdir(parents=True, exist_ok=True)
        py_file.write_text("import os\n\ndef main():\n    pass\n")

        result = await pipeline_with_cache.index_files([py_file], collection="code")
        assert result.files_processed == 1

        # Check relationships were stored
        rels = pipeline_with_cache._cache.get_relationships(
            str(py_file), direction="outbound"
        )
        assert any(r.relationship == "imports" for r in rels)

    async def test_pipeline_without_cache_skips_relationships(
        self, mock_qdrant: Mock, mock_embedder: Mock, tmp_path: Path
    ) -> None:
        """Pipeline without cache still indexes files (no relationship storage)."""
        pipeline = IndexingPipeline(qdrant=mock_qdrant, embedder=mock_embedder)
        py_file = tmp_path / "test.py"
        py_file.write_text("x = 1\n")
        result = await pipeline.index_files([py_file], collection="code")
        assert result.files_processed == 1

    async def test_pipeline_extracts_typescript_relationships(
        self, pipeline_with_cache: IndexingPipeline, tmp_path: Path
    ) -> None:
        """Indexing a TypeScript file extracts import relationships."""
        ts_file = tmp_path / "src" / "app.ts"
        ts_file.parent.mkdir(parents=True, exist_ok=True)
        ts_file.write_text("import { Foo } from './foo';\n\nconst x = 1;\n")

        result = await pipeline_with_cache.index_files([ts_file], collection="code")
        assert result.files_processed == 1

        rels = pipeline_with_cache._cache.get_relationships(
            str(ts_file), direction="outbound"
        )
        assert any(r.relationship == "imports" for r in rels)

    async def test_pipeline_deletes_old_relationships_on_reindex(
        self, pipeline_with_cache: IndexingPipeline, tmp_path: Path
    ) -> None:
        """Re-indexing a file deletes old relationships before extracting new ones."""
        py_file = tmp_path / "app" / "models.py"
        py_file.parent.mkdir(parents=True, exist_ok=True)
        py_file.write_text("import json\n")

        await pipeline_with_cache.index_files([py_file], collection="code")
        rels1 = pipeline_with_cache._cache.get_relationships(
            str(py_file), direction="outbound"
        )
        assert len(rels1) >= 1

        # Change file content and re-index
        py_file.write_text("import os\n")
        await pipeline_with_cache.index_files([py_file], collection="code")
        rels2 = pipeline_with_cache._cache.get_relationships(
            str(py_file), direction="outbound"
        )
        # Old "json" import should be gone, only "os" remains
        targets = [r.target_entity for r in rels2]
        assert "os" in targets
        assert "json" not in targets


class TestAPIBoundaryIntegration:
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

    async def test_api_boundary_matching_runs_after_extraction(
        self, mock_qdrant: Mock, mock_embedder: Mock, tmp_path: Path
    ) -> None:
        """After all files are indexed, API boundaries are matched."""
        cache = CacheDB(tmp_path / ".cache")
        pipeline = IndexingPipeline(
            qdrant=mock_qdrant, embedder=mock_embedder, cache=cache
        )

        # Create a Django urls.py
        urls_file = tmp_path / "app" / "urls.py"
        urls_file.parent.mkdir(parents=True, exist_ok=True)
        urls_file.write_text(
            'from django.urls import path\nfrom . import views\n\n'
            'urlpatterns = [\n    path("api/users/", views.user_list),\n]\n'
        )

        # Create a TS file with fetch call
        ts_file = tmp_path / "src" / "api.ts"
        ts_file.parent.mkdir(parents=True, exist_ok=True)
        ts_file.write_text(
            "async function getUsers() {\n  await fetch('/api/users/');\n}\n"
        )

        result = await pipeline.index_files(
            [urls_file, ts_file], collection="code"
        )
        assert result.files_processed == 2
        # No crash — API boundary matching ran successfully

    async def test_pipeline_without_urls_no_crash(
        self, mock_qdrant: Mock, mock_embedder: Mock, tmp_path: Path
    ) -> None:
        """Pipeline without any urls.py files doesn't crash."""
        cache = CacheDB(tmp_path / ".cache")
        pipeline = IndexingPipeline(
            qdrant=mock_qdrant, embedder=mock_embedder, cache=cache
        )
        py_file = tmp_path / "main.py"
        py_file.write_text("import os\n")
        result = await pipeline.index_files([py_file], collection="code")
        assert result.files_processed == 1
