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
