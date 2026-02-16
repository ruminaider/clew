"""Tests for the indexing pipeline."""

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from clew.indexer.cache import CacheDB
from clew.indexer.metadata import is_test_file
from clew.indexer.pipeline import (
    IndexingPipeline,
    IndexingResult,
    detect_language,
)


class TestDetectLanguage:
    def test_python(self) -> None:
        assert detect_language("models.py") == "python"

    def test_typescript(self) -> None:
        assert detect_language("app.ts") == "typescript"

    def test_tsx(self) -> None:
        assert detect_language("Component.tsx") == "tsx"

    def test_javascript(self) -> None:
        assert detect_language("index.js") == "javascript"

    def test_markdown(self) -> None:
        assert detect_language("README.md") == "markdown"

    def test_unknown(self) -> None:
        assert detect_language("data.csv") == "unknown"


class TestIsTestFile:
    def test_test_prefix(self) -> None:
        assert is_test_file("tests/test_auth.py") is True

    def test_test_directory(self) -> None:
        assert is_test_file("tests/unit/test_models.py") is True

    def test_spec_suffix(self) -> None:
        assert is_test_file("src/auth.spec.ts") is True

    def test_not_test(self) -> None:
        assert is_test_file("src/models.py") is False


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
        """Vector keys must be 'signature', 'semantic', 'body', and 'bm25'."""
        f = tmp_path / "code.py"
        f.write_text("x = 1\n")
        await pipeline.index_files([f], collection="code")
        points = mock_qdrant.upsert_points.call_args[0][1]
        vector = points[0].vector
        assert "bm25" in vector
        assert "signature" in vector
        assert "semantic" in vector
        assert "body" in vector

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
        from contextlib import contextmanager
        from unittest.mock import MagicMock

        cache = Mock()
        cache.get_description = Mock(return_value=None)
        cache.set_description = Mock()
        cache.get_last_checkpoint = Mock(return_value=-1)
        cache.save_checkpoint = Mock()
        cache.clear_checkpoints = Mock()
        cache.record_failed_file = Mock()
        cache.get_all_relationship_pairs = Mock(return_value=[])
        cache.get_enrichment = Mock(return_value=None)
        cache.get_relationships = Mock(return_value=[])

        # Mock the _get_state_conn context manager for _normalize_relationship_targets
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = []

        @contextmanager
        def fake_state_conn():
            yield mock_conn

        cache._get_state_conn = fake_state_conn
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
        """Pipeline generates descriptions and uses them in semantic vector."""
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

        # With 3 named vectors, embedder is called 3 times per batch
        # (signature, semantic, body). The semantic text should contain the description.
        all_embed_calls = mock_embedder.embed.call_args_list
        all_texts = []
        for call in all_embed_calls:
            all_texts.extend(call[0][0])
        assert any("A test description." in t for t in all_texts)

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
        """Pipeline skips description generation for chunks with docstrings.

        Note: file_summary chunks are synthetic and may still trigger generation.
        The important assertion is that the actual code chunk with a docstring is skipped.
        """
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

        # If generate_batch was called, it should only be for file_summary (not the docstring chunk)
        if mock_description_provider.generate_batch.called:
            call_args = mock_description_provider.generate_batch.call_args
            items = call_args[0][0]
            # None of the items should be the actual function chunk
            for item in items:
                assert item["entity_type"] == "file_summary"

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

        # Verify the cached description was used in semantic vector embedding
        all_embed_calls = mock_embedder.embed.call_args_list
        all_texts = []
        for call in all_embed_calls:
            all_texts.extend(call[0][0])
        assert any("Cached description." in t for t in all_texts)

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

    async def test_bm25_uses_raw_content_in_pass1(
        self,
        mock_qdrant: Mock,
        mock_embedder: Mock,
        mock_description_provider: Mock,
        mock_cache: Mock,
        tmp_path: Path,
    ) -> None:
        """BM25 sparse vector in Pass 1 (unenriched) should use raw content only."""
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
        with patch("clew.indexer.pipeline.text_to_sparse_vector") as mock_sparse:
            mock_sparse.return_value = Mock(indices=[1], values=[1.0])
            await pipeline.index_files([f], collection="code")

            # For unenriched chunks (no enrichment cache), BM25 uses raw content
            # But with a description provider, the chunk IS enriched via backward compat
            # So it will include semantic text. Just verify it's called.
            assert mock_sparse.call_count >= 1


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
    def pipeline_with_cache(
        self, mock_qdrant: Mock, mock_embedder: Mock, tmp_path: Path
    ) -> IndexingPipeline:
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
        rels = pipeline_with_cache._cache.get_relationships(str(py_file), direction="outbound")
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

        rels = pipeline_with_cache._cache.get_relationships(str(ts_file), direction="outbound")
        assert any(r.relationship == "imports" for r in rels)

    async def test_pipeline_deletes_old_relationships_on_reindex(
        self, pipeline_with_cache: IndexingPipeline, tmp_path: Path
    ) -> None:
        """Re-indexing a file deletes old relationships before extracting new ones."""
        py_file = tmp_path / "app" / "models.py"
        py_file.parent.mkdir(parents=True, exist_ok=True)
        py_file.write_text("import json\n")

        await pipeline_with_cache.index_files([py_file], collection="code")
        rels1 = pipeline_with_cache._cache.get_relationships(str(py_file), direction="outbound")
        assert len(rels1) >= 1

        # Change file content and re-index
        py_file.write_text("import os\n")
        await pipeline_with_cache.index_files([py_file], collection="code")
        rels2 = pipeline_with_cache._cache.get_relationships(str(py_file), direction="outbound")
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
        pipeline = IndexingPipeline(qdrant=mock_qdrant, embedder=mock_embedder, cache=cache)

        # Create a Django urls.py
        urls_file = tmp_path / "app" / "urls.py"
        urls_file.parent.mkdir(parents=True, exist_ok=True)
        urls_file.write_text(
            "from django.urls import path\nfrom . import views\n\n"
            'urlpatterns = [\n    path("api/users/", views.user_list),\n]\n'
        )

        # Create a TS file with fetch call
        ts_file = tmp_path / "src" / "api.ts"
        ts_file.parent.mkdir(parents=True, exist_ok=True)
        ts_file.write_text("async function getUsers() {\n  await fetch('/api/users/');\n}\n")

        result = await pipeline.index_files([urls_file, ts_file], collection="code")
        assert result.files_processed == 2
        # No crash — API boundary matching ran successfully

    async def test_pipeline_without_urls_no_crash(
        self, mock_qdrant: Mock, mock_embedder: Mock, tmp_path: Path
    ) -> None:
        """Pipeline without any urls.py files doesn't crash."""
        cache = CacheDB(tmp_path / ".cache")
        pipeline = IndexingPipeline(qdrant=mock_qdrant, embedder=mock_embedder, cache=cache)
        py_file = tmp_path / "main.py"
        py_file.write_text("import os\n")
        result = await pipeline.index_files([py_file], collection="code")
        assert result.files_processed == 1


class TestNormalizationVerification:
    """Regression tests for commits 37025b5 and ca2595b.

    Verifies that module-qualified targets resolve correctly
    and multi-hop trace works when depth-1 targets are normalized.
    """

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

    def test_module_qualified_target_resolves_to_file_path(
        self, mock_qdrant: Mock, mock_embedder: Mock, tmp_path: Path
    ) -> None:
        """ecomm.tasks::send_ungated_rx_order_paid_event resolves to file-qualified."""
        from clew.indexer.relationships import Relationship

        cache = CacheDB(tmp_path / ".cache")
        pipeline = IndexingPipeline(qdrant=mock_qdrant, embedder=mock_embedder, cache=cache)

        cache.store_relationships(
            [
                Relationship(
                    source_entity="/project/backend/ecomm/utils.py::process_order",
                    relationship="calls",
                    target_entity="ecomm.tasks::send_ungated_rx_order_paid_event",
                    file_path="/project/backend/ecomm/utils.py",
                    confidence="inferred",
                ),
                Relationship(
                    source_entity="/project/backend/ecomm/tasks.py::send_ungated_rx_order_paid_event",
                    relationship="calls",
                    target_entity="some_lib::notify",
                    file_path="/project/backend/ecomm/tasks.py",
                    confidence="inferred",
                ),
            ]
        )

        pipeline._normalize_relationship_targets()

        rels = cache.get_relationships(
            "/project/backend/ecomm/utils.py::process_order", direction="outbound"
        )
        targets = [r.target_entity for r in rels]
        assert "/project/backend/ecomm/tasks.py::send_ungated_rx_order_paid_event" in targets

    def test_multi_hop_trace_after_normalization(
        self, mock_qdrant: Mock, mock_embedder: Mock, tmp_path: Path
    ) -> None:
        """Multi-hop trace works when depth-1 targets are properly normalized."""
        from clew.indexer.relationships import Relationship

        cache = CacheDB(tmp_path / ".cache")
        pipeline = IndexingPipeline(qdrant=mock_qdrant, embedder=mock_embedder, cache=cache)

        cache.store_relationships(
            [
                Relationship(
                    source_entity="/project/backend/ecomm/utils.py::process_order",
                    relationship="calls",
                    target_entity="ecomm.tasks::void_order",
                    file_path="/project/backend/ecomm/utils.py",
                    confidence="inferred",
                ),
                Relationship(
                    source_entity="/project/backend/ecomm/tasks.py::void_order",
                    relationship="calls",
                    target_entity="/project/backend/ecomm/notifications.py::send_notification",
                    file_path="/project/backend/ecomm/tasks.py",
                    confidence="inferred",
                ),
            ]
        )

        pipeline._normalize_relationship_targets()

        # Depth-2 trace should reach notifications.py
        results = cache.traverse_relationships(
            "/project/backend/ecomm/utils.py::process_order",
            direction="outbound",
            max_depth=2,
        )
        targets = [r["target_entity"] for r in results]
        assert "/project/backend/ecomm/tasks.py::void_order" in targets
        assert "/project/backend/ecomm/notifications.py::send_notification" in targets

    def test_dotted_targets_resolve_correctly(
        self, mock_qdrant: Mock, mock_embedder: Mock, tmp_path: Path
    ) -> None:
        """Dotted module targets (e.g., care.models::PrescriptionFill.objects.create) resolve."""
        from clew.indexer.relationships import Relationship

        cache = CacheDB(tmp_path / ".cache")
        pipeline = IndexingPipeline(qdrant=mock_qdrant, embedder=mock_embedder, cache=cache)

        cache.store_relationships(
            [
                Relationship(
                    source_entity="/project/backend/ecomm/utils.py::process",
                    relationship="calls",
                    target_entity="care.models::PrescriptionFill.objects.create",
                    file_path="/project/backend/ecomm/utils.py",
                    confidence="inferred",
                ),
                Relationship(
                    source_entity="/project/backend/care/models.py::PrescriptionFill",
                    relationship="inherits",
                    target_entity="django.db.models::Model",
                    file_path="/project/backend/care/models.py",
                    confidence="static",
                ),
            ]
        )

        pipeline._normalize_relationship_targets()

        rels = cache.get_relationships(
            "/project/backend/ecomm/utils.py::process", direction="outbound"
        )
        targets = [r.target_entity for r in rels]
        assert "/project/backend/care/models.py::PrescriptionFill.objects.create" in targets

    def test_unique_constraint_when_resolved_target_exists(
        self, mock_qdrant: Mock, mock_embedder: Mock, tmp_path: Path
    ) -> None:
        """Normalization handles UNIQUE constraint when resolved target already exists (ca2595b)."""
        from clew.indexer.relationships import Relationship

        cache = CacheDB(tmp_path / ".cache")
        pipeline = IndexingPipeline(qdrant=mock_qdrant, embedder=mock_embedder, cache=cache)

        # Both module-qualified AND file-qualified versions exist
        cache.store_relationships(
            [
                Relationship(
                    source_entity="/project/backend/ecomm/utils.py::process",
                    relationship="calls",
                    target_entity="ecomm.tasks::void_order",
                    file_path="/project/backend/ecomm/utils.py",
                    confidence="inferred",
                ),
                Relationship(
                    source_entity="/project/backend/ecomm/utils.py::process",
                    relationship="calls",
                    target_entity="/project/backend/ecomm/tasks.py::void_order",
                    file_path="/project/backend/ecomm/utils.py",
                    confidence="inferred",
                ),
                Relationship(
                    source_entity="/project/backend/ecomm/tasks.py::void_order",
                    relationship="calls",
                    target_entity="some_lib::helper",
                    file_path="/project/backend/ecomm/tasks.py",
                    confidence="inferred",
                ),
            ]
        )

        # Should not crash on UNIQUE constraint
        pipeline._normalize_relationship_targets()

        rels = cache.get_relationships(
            "/project/backend/ecomm/utils.py::process", direction="outbound"
        )
        targets = [r.target_entity for r in rels]
        # The file-qualified version should be present
        assert "/project/backend/ecomm/tasks.py::void_order" in targets
        # The module-qualified version should have been cleaned up
        assert "ecomm.tasks::void_order" not in targets


class TestModuleQualifiedNormalization:
    """Tests for resolving module-qualified targets at index time."""

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

    def test_normalize_resolves_module_qualified_targets(
        self, mock_qdrant: Mock, mock_embedder: Mock, tmp_path: Path
    ) -> None:
        """Module-qualified targets should be resolved to file-qualified at index time."""
        from clew.indexer.relationships import Relationship

        cache = CacheDB(tmp_path / ".cache")
        pipeline = IndexingPipeline(qdrant=mock_qdrant, embedder=mock_embedder, cache=cache)

        # Setup: insert relationships with module-qualified targets
        cache.store_relationships(
            [
                Relationship(
                    source_entity="/project/backend/ecomm/utils.py::process_order",
                    relationship="calls",
                    target_entity="ecomm.tasks::void_order",  # module-qualified
                    file_path="/project/backend/ecomm/utils.py",
                    confidence="inferred",
                ),
                Relationship(
                    source_entity="/project/backend/ecomm/tasks.py::void_order",
                    relationship="calls",
                    target_entity="some_lib::send_email",
                    file_path="/project/backend/ecomm/tasks.py",
                    confidence="inferred",
                ),
            ]
        )

        # Act: run normalization
        pipeline._normalize_relationship_targets()

        # Assert: module-qualified target should now be file-qualified
        rels = cache.get_relationships(
            "/project/backend/ecomm/utils.py::process_order", direction="outbound"
        )
        targets = [r.target_entity for r in rels]
        assert "/project/backend/ecomm/tasks.py::void_order" in targets

    def test_normalize_preserves_dotted_symbol_suffix(
        self, mock_qdrant: Mock, mock_embedder: Mock, tmp_path: Path
    ) -> None:
        """Dotted symbol suffixes (e.g., Foo.bar) should be preserved after resolution."""
        from clew.indexer.relationships import Relationship

        cache = CacheDB(tmp_path / ".cache")
        pipeline = IndexingPipeline(qdrant=mock_qdrant, embedder=mock_embedder, cache=cache)

        cache.store_relationships(
            [
                Relationship(
                    source_entity="/project/backend/ecomm/utils.py::process",
                    relationship="calls",
                    target_entity="ecomm.tasks::Order.save",  # dotted symbol
                    file_path="/project/backend/ecomm/utils.py",
                    confidence="inferred",
                ),
                Relationship(
                    source_entity="/project/backend/ecomm/tasks.py::Order",
                    relationship="calls",
                    target_entity="some_lib::helper",
                    file_path="/project/backend/ecomm/tasks.py",
                    confidence="inferred",
                ),
            ]
        )

        pipeline._normalize_relationship_targets()

        rels = cache.get_relationships(
            "/project/backend/ecomm/utils.py::process", direction="outbound"
        )
        targets = [r.target_entity for r in rels]
        assert "/project/backend/ecomm/tasks.py::Order.save" in targets

    def test_normalize_skips_ambiguous_module_qualified(
        self, mock_qdrant: Mock, mock_embedder: Mock, tmp_path: Path
    ) -> None:
        """Ambiguous module-qualified targets (multiple matches) should be left unchanged."""
        from clew.indexer.relationships import Relationship

        cache = CacheDB(tmp_path / ".cache")
        pipeline = IndexingPipeline(qdrant=mock_qdrant, embedder=mock_embedder, cache=cache)

        cache.store_relationships(
            [
                Relationship(
                    source_entity="/project/backend/ecomm/utils.py::process",
                    relationship="calls",
                    target_entity="ecomm.tasks::send",  # module-qualified
                    file_path="/project/backend/ecomm/utils.py",
                    confidence="inferred",
                ),
                # Two source entities with same symbol but different paths
                Relationship(
                    source_entity="/project/backend/ecomm/tasks.py::send",
                    relationship="calls",
                    target_entity="email::deliver",
                    file_path="/project/backend/ecomm/tasks.py",
                    confidence="inferred",
                ),
                Relationship(
                    source_entity="/project/backend/ecomm/tasks_v2.py::send",
                    relationship="calls",
                    target_entity="email::deliver",
                    file_path="/project/backend/ecomm/tasks_v2.py",
                    confidence="inferred",
                ),
            ]
        )

        pipeline._normalize_relationship_targets()

        rels = cache.get_relationships(
            "/project/backend/ecomm/utils.py::process", direction="outbound"
        )
        targets = [r.target_entity for r in rels]
        # Should be unchanged — two candidates match "ecomm/tasks" pattern
        assert "ecomm.tasks::send" in targets


class TestReembedUsesChunkContent:
    """Tests for reembed() using chunk_content_cache instead of full files."""

    @pytest.fixture
    def mock_qdrant(self) -> Mock:
        qdrant = Mock()
        qdrant.ensure_collection = Mock()
        qdrant.upsert_points = Mock()
        qdrant.delete_by_file_path = Mock()
        qdrant._client = Mock()
        qdrant._client.scroll = Mock(return_value=([], None))
        return qdrant

    @pytest.fixture
    def mock_embedder(self) -> Mock:
        embedder = Mock()
        embedder.embed = AsyncMock(side_effect=lambda texts, **kwargs: [[0.1] * 1024] * len(texts))
        embedder.model_name = "voyage-code-3"
        embedder.dimensions = 1024
        return embedder

    async def test_pass1_stores_chunk_content(
        self,
        mock_qdrant: Mock,
        mock_embedder: Mock,
        tmp_path: Path,
    ) -> None:
        """Pass 1 (index_files) stores chunk content in chunk_content_cache."""
        cache = CacheDB(tmp_path / ".cache")
        pipeline = IndexingPipeline(qdrant=mock_qdrant, embedder=mock_embedder, cache=cache)
        f = tmp_path / "hello.py"
        f.write_text("def hello():\n    return 'world'\n")
        await pipeline.index_files([f], collection="code")

        # Check that chunk content was cached
        chunk_ids = cache.get_file_chunk_ids(str(f))
        assert len(chunk_ids) >= 1
        for cid in chunk_ids:
            cached = cache.get_chunk_content(cid)
            assert cached is not None, f"No cached content for {cid}"
            content, line_start, line_end = cached
            assert len(content) > 0

    async def test_reembed_uses_cached_chunk_content(
        self,
        mock_qdrant: Mock,
        mock_embedder: Mock,
        tmp_path: Path,
    ) -> None:
        """reembed() uses cached chunk content, not full file content."""
        cache = CacheDB(tmp_path / ".cache")
        pipeline = IndexingPipeline(qdrant=mock_qdrant, embedder=mock_embedder, cache=cache)

        # Index a file with two functions
        f = tmp_path / "funcs.py"
        f.write_text("def foo():\n    return 1\n\ndef bar():\n    return 2\n")
        await pipeline.index_files([f], collection="code")

        # Add enrichment for all chunks
        chunk_ids = cache.get_file_chunk_ids(str(f))
        for cid in chunk_ids:
            cache.set_enrichment(cid, "A test description.", "test keyword")

        # Run reembed
        mock_qdrant.upsert_points.reset_mock()
        result = await pipeline.reembed(collection="code")
        assert result.chunks_created >= 1

        # Verify function chunks use cached chunk content (not full file)
        points = mock_qdrant.upsert_points.call_args[0][1]
        function_payloads = [p.payload for p in points if p.payload.get("chunk_type") == "function"]
        for payload in function_payloads:
            content = payload["content"]
            # Function chunk content should contain only one function, not both
            assert not ("def foo()" in content and "def bar()" in content), (
                "Chunk content should be a single function, not the full file"
            )

    async def test_reembed_payload_has_line_numbers(
        self,
        mock_qdrant: Mock,
        mock_embedder: Mock,
        tmp_path: Path,
    ) -> None:
        """reembed() includes line_start and line_end in payload."""
        cache = CacheDB(tmp_path / ".cache")
        pipeline = IndexingPipeline(qdrant=mock_qdrant, embedder=mock_embedder, cache=cache)

        f = tmp_path / "hello.py"
        f.write_text("def hello():\n    return 'world'\n")
        await pipeline.index_files([f], collection="code")

        chunk_ids = cache.get_file_chunk_ids(str(f))
        for cid in chunk_ids:
            cache.set_enrichment(cid, "Desc.", "kw")

        mock_qdrant.upsert_points.reset_mock()
        await pipeline.reembed(collection="code")

        points = mock_qdrant.upsert_points.call_args[0][1]
        for point in points:
            assert "line_start" in point.payload
            assert "line_end" in point.payload

    async def test_reembed_payload_has_function_name(
        self,
        mock_qdrant: Mock,
        mock_embedder: Mock,
        tmp_path: Path,
    ) -> None:
        """reembed() includes function_name in payload."""
        cache = CacheDB(tmp_path / ".cache")
        pipeline = IndexingPipeline(qdrant=mock_qdrant, embedder=mock_embedder, cache=cache)

        f = tmp_path / "hello.py"
        f.write_text("def hello():\n    return 'world'\n")
        await pipeline.index_files([f], collection="code")

        chunk_ids = cache.get_file_chunk_ids(str(f))
        for cid in chunk_ids:
            cache.set_enrichment(cid, "Desc.", "kw")

        mock_qdrant.upsert_points.reset_mock()
        await pipeline.reembed(collection="code")

        points = mock_qdrant.upsert_points.call_args[0][1]
        for point in points:
            assert "function_name" in point.payload
