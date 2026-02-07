"""Tests for SQLite caching layer."""

from pathlib import Path

import pytest

from code_search.indexer.cache import CacheDB


class TestCacheDB:
    @pytest.fixture
    def cache(self, temp_cache_dir: Path) -> CacheDB:
        return CacheDB(temp_cache_dir)

    def test_init_creates_databases(self, cache: CacheDB) -> None:
        assert (cache.cache_dir / "cache.db").exists()
        assert (cache.cache_dir / "state.db").exists()

    def test_init_creates_directory(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "nested" / "cache"
        CacheDB(cache_dir)
        assert cache_dir.exists()


class TestEmbeddingCache:
    @pytest.fixture
    def cache(self, temp_cache_dir: Path) -> CacheDB:
        return CacheDB(temp_cache_dir)

    def test_get_missing_embedding_returns_none(self, cache: CacheDB) -> None:
        result = cache.get_embedding("hash123", "voyage-code-3")
        assert result is None

    def test_set_and_get_embedding(self, cache: CacheDB) -> None:
        embedding = b"\x00\x01\x02\x03"
        cache.set_embedding("hash123", "voyage-code-3", embedding, 42)
        result = cache.get_embedding("hash123", "voyage-code-3")
        assert result == embedding

    def test_different_models_are_separate(self, cache: CacheDB) -> None:
        cache.set_embedding("hash123", "model-a", b"embed-a", 10)
        cache.set_embedding("hash123", "model-b", b"embed-b", 10)
        assert cache.get_embedding("hash123", "model-a") == b"embed-a"
        assert cache.get_embedding("hash123", "model-b") == b"embed-b"

    def test_upsert_replaces_existing(self, cache: CacheDB) -> None:
        cache.set_embedding("hash123", "voyage-code-3", b"old", 10)
        cache.set_embedding("hash123", "voyage-code-3", b"new", 15)
        assert cache.get_embedding("hash123", "voyage-code-3") == b"new"


class TestChunkCache:
    @pytest.fixture
    def cache(self, temp_cache_dir: Path) -> CacheDB:
        return CacheDB(temp_cache_dir)

    def test_get_missing_file_hash_returns_none(self, cache: CacheDB) -> None:
        result = cache.get_file_hash("nonexistent.py")
        assert result is None

    def test_set_and_get_file_hash(self, cache: CacheDB) -> None:
        cache.set_file_chunks("models.py", "abc123", ["chunk1", "chunk2"])
        result = cache.get_file_hash("models.py")
        assert result == "abc123"

    def test_get_file_chunk_ids(self, cache: CacheDB) -> None:
        cache.set_file_chunks("models.py", "abc123", ["chunk1", "chunk2"])
        chunk_ids = cache.get_file_chunk_ids("models.py")
        assert chunk_ids == ["chunk1", "chunk2"]

    def test_update_file_replaces_old(self, cache: CacheDB) -> None:
        cache.set_file_chunks("models.py", "hash1", ["old_chunk"])
        cache.set_file_chunks("models.py", "hash2", ["new_chunk"])
        assert cache.get_file_hash("models.py") == "hash2"
        assert cache.get_file_chunk_ids("models.py") == ["new_chunk"]


class TestIndexState:
    @pytest.fixture
    def cache(self, temp_cache_dir: Path) -> CacheDB:
        return CacheDB(temp_cache_dir)

    def test_get_missing_commit_returns_none(self, cache: CacheDB) -> None:
        assert cache.get_last_indexed_commit("code") is None

    def test_set_and_get_commit(self, cache: CacheDB) -> None:
        cache.set_last_indexed_commit("code", "abc123def")
        assert cache.get_last_indexed_commit("code") == "abc123def"

    def test_update_commit(self, cache: CacheDB) -> None:
        cache.set_last_indexed_commit("code", "abc123")
        cache.set_last_indexed_commit("code", "def456")
        assert cache.get_last_indexed_commit("code") == "def456"

    def test_different_collections_independent(self, cache: CacheDB) -> None:
        cache.set_last_indexed_commit("code", "abc123")
        cache.set_last_indexed_commit("docs", "def456")
        assert cache.get_last_indexed_commit("code") == "abc123"
        assert cache.get_last_indexed_commit("docs") == "def456"


class TestDescriptionCache:
    """Test NL description caching."""

    @pytest.fixture
    def cache(self, temp_cache_dir: Path) -> CacheDB:
        return CacheDB(temp_cache_dir)

    def test_get_description_missing(self, cache: CacheDB) -> None:
        result = cache.get_description("abc123", "claude-sonnet-4-5-20250929")
        assert result is None

    def test_set_and_get_description(self, cache: CacheDB) -> None:
        cache.set_description("abc123", "claude-sonnet-4-5-20250929", "Validates email format.")
        result = cache.get_description("abc123", "claude-sonnet-4-5-20250929")
        assert result == "Validates email format."

    def test_description_keyed_by_model(self, cache: CacheDB) -> None:
        cache.set_description("abc123", "model-a", "Description A")
        cache.set_description("abc123", "model-b", "Description B")
        assert cache.get_description("abc123", "model-a") == "Description A"
        assert cache.get_description("abc123", "model-b") == "Description B"

    def test_description_upsert(self, cache: CacheDB) -> None:
        cache.set_description("abc123", "model-a", "Old")
        cache.set_description("abc123", "model-a", "New")
        assert cache.get_description("abc123", "model-a") == "New"


class TestRelationshipStore:
    @pytest.fixture
    def cache(self, temp_cache_dir: Path) -> CacheDB:
        return CacheDB(temp_cache_dir)

    def test_store_and_get_relationships(self, cache: CacheDB) -> None:
        from code_search.indexer.relationships import Relationship

        rels = [
            Relationship("a.py::Foo", "imports", "b.py::Bar", "a.py"),
            Relationship("a.py::Foo", "inherits", "c.py::Base", "a.py"),
        ]
        cache.store_relationships(rels)
        result = cache.get_relationships("a.py::Foo", direction="outbound")
        assert len(result) == 2

    def test_get_relationships_inbound(self, cache: CacheDB) -> None:
        from code_search.indexer.relationships import Relationship

        rels = [
            Relationship("a.py::main", "calls", "b.py::helper", "a.py"),
        ]
        cache.store_relationships(rels)
        result = cache.get_relationships("b.py::helper", direction="inbound")
        assert len(result) == 1
        assert result[0].source_entity == "a.py::main"

    def test_get_relationships_both_directions(self, cache: CacheDB) -> None:
        from code_search.indexer.relationships import Relationship

        rels = [
            Relationship("a.py::Foo", "imports", "b.py::Bar", "a.py"),
            Relationship("c.py::Baz", "calls", "a.py::Foo", "c.py"),
        ]
        cache.store_relationships(rels)
        result = cache.get_relationships("a.py::Foo", direction="both")
        assert len(result) == 2

    def test_delete_relationships_by_file(self, cache: CacheDB) -> None:
        from code_search.indexer.relationships import Relationship

        rels = [
            Relationship("a.py::Foo", "imports", "b.py::Bar", "a.py"),
            Relationship("b.py::Bar", "calls", "c.py::Baz", "b.py"),
        ]
        cache.store_relationships(rels)
        cache.delete_relationships_by_file("a.py")
        result = cache.get_relationships("a.py::Foo", direction="outbound")
        assert len(result) == 0
        # b.py relationships should still exist
        result = cache.get_relationships("b.py::Bar", direction="outbound")
        assert len(result) == 1

    def test_store_relationships_upserts(self, cache: CacheDB) -> None:
        """Storing same relationship twice doesn't create duplicates."""
        from code_search.indexer.relationships import Relationship

        rel = Relationship("a.py::Foo", "imports", "b.py::Bar", "a.py")
        cache.store_relationships([rel])
        cache.store_relationships([rel])
        result = cache.get_relationships("a.py::Foo", direction="outbound")
        assert len(result) == 1
