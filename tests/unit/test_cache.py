"""Tests for SQLite caching layer."""

from pathlib import Path

import pytest

from clew.indexer.cache import CacheDB


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


class TestClearAllState:
    @pytest.fixture
    def cache(self, temp_cache_dir: Path) -> CacheDB:
        return CacheDB(temp_cache_dir)

    def test_clears_state_tables(self, cache: CacheDB) -> None:
        """clear_all_state wipes relationships, failed_files, checkpoints, state, chunks."""
        from clew.indexer.relationships import Relationship

        # Populate state tables
        cache.store_relationships([Relationship("a.py::Foo", "calls", "b.py::Bar", "a.py")])
        cache.record_failed_file("bad.py", "SyntaxError", "invalid syntax")
        cache.save_checkpoint("code", 0, ["a.py"])
        cache.set_last_indexed_commit("code", "abc123")
        cache.set_file_chunks("a.py", "hash1", ["chunk1"])

        # Clear
        cache.clear_all_state("code")

        # Verify state tables are empty
        assert cache.get_relationships("a.py::Foo", direction="outbound") == []
        assert cache.get_failed_files() == []
        assert cache.get_last_checkpoint("code") == -1
        assert cache.get_last_indexed_commit("code") is None
        assert cache.get_file_hash("a.py") is None

    def test_preserves_embedding_cache(self, cache: CacheDB) -> None:
        """clear_all_state must NOT wipe embedding_cache."""
        cache.set_embedding("hash1", "voyage-code-3", b"\x00\x01", 10)
        cache.clear_all_state("code")
        assert cache.get_embedding("hash1", "voyage-code-3") == b"\x00\x01"

    def test_preserves_description_cache(self, cache: CacheDB) -> None:
        """clear_all_state must NOT wipe description_cache."""
        cache.set_description("hash1", "model-a", "A function that does X.")
        cache.clear_all_state("code")
        assert cache.get_description("hash1", "model-a") == "A function that does X."

    def test_scoped_to_collection(self, cache: CacheDB) -> None:
        """Clearing 'code' collection doesn't affect 'docs' collection state."""
        cache.set_last_indexed_commit("code", "abc123")
        cache.set_last_indexed_commit("docs", "def456")
        cache.save_checkpoint("code", 0, ["a.py"])
        cache.save_checkpoint("docs", 0, ["readme.md"])

        cache.clear_all_state("code")

        assert cache.get_last_indexed_commit("code") is None
        assert cache.get_last_indexed_commit("docs") == "def456"
        assert cache.get_last_checkpoint("code") == -1
        assert cache.get_last_checkpoint("docs") == 0


class TestRelationshipStore:
    @pytest.fixture
    def cache(self, temp_cache_dir: Path) -> CacheDB:
        return CacheDB(temp_cache_dir)

    def test_store_and_get_relationships(self, cache: CacheDB) -> None:
        from clew.indexer.relationships import Relationship

        rels = [
            Relationship("a.py::Foo", "imports", "b.py::Bar", "a.py"),
            Relationship("a.py::Foo", "inherits", "c.py::Base", "a.py"),
        ]
        cache.store_relationships(rels)
        result = cache.get_relationships("a.py::Foo", direction="outbound")
        assert len(result) == 2

    def test_get_relationships_inbound(self, cache: CacheDB) -> None:
        from clew.indexer.relationships import Relationship

        rels = [
            Relationship("a.py::main", "calls", "b.py::helper", "a.py"),
        ]
        cache.store_relationships(rels)
        result = cache.get_relationships("b.py::helper", direction="inbound")
        assert len(result) == 1
        assert result[0].source_entity == "a.py::main"

    def test_get_relationships_both_directions(self, cache: CacheDB) -> None:
        from clew.indexer.relationships import Relationship

        rels = [
            Relationship("a.py::Foo", "imports", "b.py::Bar", "a.py"),
            Relationship("c.py::Baz", "calls", "a.py::Foo", "c.py"),
        ]
        cache.store_relationships(rels)
        result = cache.get_relationships("a.py::Foo", direction="both")
        assert len(result) == 2

    def test_delete_relationships_by_file(self, cache: CacheDB) -> None:
        from clew.indexer.relationships import Relationship

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
        from clew.indexer.relationships import Relationship

        rel = Relationship("a.py::Foo", "imports", "b.py::Bar", "a.py")
        cache.store_relationships([rel])
        cache.store_relationships([rel])
        result = cache.get_relationships("a.py::Foo", direction="outbound")
        assert len(result) == 1


class TestBFSTraversal:
    @pytest.fixture
    def cache(self, temp_cache_dir: Path) -> CacheDB:
        return CacheDB(temp_cache_dir)

    def test_single_hop(self, cache: CacheDB) -> None:
        from clew.indexer.relationships import Relationship

        rels = [Relationship("a.py::Foo", "calls", "b.py::Bar", "a.py")]
        cache.store_relationships(rels)
        result = cache.traverse_relationships("a.py::Foo", direction="outbound", max_depth=1)
        assert len(result) == 1
        assert result[0]["depth"] == 1

    def test_multi_hop(self, cache: CacheDB) -> None:
        from clew.indexer.relationships import Relationship

        rels = [
            Relationship("a.py::Foo", "calls", "b.py::Bar", "a.py"),
            Relationship("b.py::Bar", "calls", "c.py::Baz", "b.py"),
        ]
        cache.store_relationships(rels)
        result = cache.traverse_relationships("a.py::Foo", direction="outbound", max_depth=2)
        assert len(result) == 2
        depths = {r["target_entity"]: r["depth"] for r in result}
        assert depths["b.py::Bar"] == 1
        assert depths["c.py::Baz"] == 2

    def test_max_depth_limits_traversal(self, cache: CacheDB) -> None:
        from clew.indexer.relationships import Relationship

        rels = [
            Relationship("a.py::A", "calls", "b.py::B", "a.py"),
            Relationship("b.py::B", "calls", "c.py::C", "b.py"),
            Relationship("c.py::C", "calls", "d.py::D", "c.py"),
        ]
        cache.store_relationships(rels)
        result = cache.traverse_relationships("a.py::A", direction="outbound", max_depth=1)
        assert len(result) == 1

    def test_filter_by_relationship_type(self, cache: CacheDB) -> None:
        from clew.indexer.relationships import Relationship

        rels = [
            Relationship("a.py::Foo", "imports", "b.py::Bar", "a.py"),
            Relationship("a.py::Foo", "calls", "c.py::Baz", "a.py"),
        ]
        cache.store_relationships(rels)
        result = cache.traverse_relationships(
            "a.py::Foo", direction="outbound", max_depth=1, relationship_types=["imports"]
        )
        assert len(result) == 1
        assert result[0]["relationship"] == "imports"

    def test_cycle_detection(self, cache: CacheDB) -> None:
        """BFS doesn't loop on circular references."""
        from clew.indexer.relationships import Relationship

        rels = [
            Relationship("a.py::A", "calls", "b.py::B", "a.py"),
            Relationship("b.py::B", "calls", "a.py::A", "b.py"),
        ]
        cache.store_relationships(rels)
        result = cache.traverse_relationships("a.py::A", direction="outbound", max_depth=5)
        assert len(result) == 2

    def test_inbound_traversal(self, cache: CacheDB) -> None:
        from clew.indexer.relationships import Relationship

        rels = [
            Relationship("a.py::A", "calls", "c.py::C", "a.py"),
            Relationship("b.py::B", "calls", "c.py::C", "b.py"),
        ]
        cache.store_relationships(rels)
        result = cache.traverse_relationships("c.py::C", direction="inbound", max_depth=1)
        assert len(result) == 2

    def test_bfs_uses_resolution_cache(self, cache: CacheDB) -> None:
        """BFS uses resolve_entity with caching as defense-in-depth.

        When a target entity is a non-canonical form, resolve_entity is called
        to attempt resolution. Results are cached so repeated lookups for the
        same entity don't incur additional LIKE queries.
        """
        from unittest.mock import patch

        from clew.indexer.relationships import Relationship

        cache.store_relationships(
            [
                Relationship("a.py::Foo", "calls", "b.py::Bar", "a.py"),
                Relationship("b.py::Bar", "calls", "c.py::Baz", "b.py"),
            ]
        )

        with patch.object(cache, "resolve_entity", wraps=cache.resolve_entity) as mock_resolve:
            result = cache.traverse_relationships("a.py::Foo", direction="outbound", max_depth=2)
            assert len(result) == 2

            # resolve_entity should be called for each unique next_entity
            # (b.py::Bar at depth 1, c.py::Baz at depth 2)
            assert mock_resolve.call_count == 2
            mock_resolve.assert_any_call("b.py::Bar")
            mock_resolve.assert_any_call("c.py::Baz")

    def test_bfs_resolution_cache_deduplicates(self, cache: CacheDB) -> None:
        """Resolution cache avoids calling resolve_entity multiple times for same entity."""
        from unittest.mock import patch

        from clew.indexer.relationships import Relationship

        # Create a diamond: A -> B, A -> C, B -> D, C -> D
        # D appears as target_entity twice but resolve_entity should only be called once for it
        cache.store_relationships(
            [
                Relationship("a.py::A", "calls", "b.py::B", "a.py"),
                Relationship("a.py::A", "calls", "c.py::C", "a.py"),
                Relationship("b.py::B", "calls", "d.py::D", "b.py"),
                Relationship("c.py::C", "calls", "d.py::D", "c.py"),
            ]
        )

        with patch.object(cache, "resolve_entity", wraps=cache.resolve_entity) as mock_resolve:
            result = cache.traverse_relationships("a.py::A", direction="outbound", max_depth=2)
            # Should find B, C at depth 1, and D at depth 2
            assert len(result) >= 3

            # D should only be resolved once (cached on second encounter)
            d_calls = [c for c in mock_resolve.call_args_list if c[0][0] == "d.py::D"]
            assert len(d_calls) == 1


class TestResolveEntity:
    @pytest.fixture
    def cache(self, temp_cache_dir: Path) -> CacheDB:
        return CacheDB(temp_cache_dir)

    def test_exact_match(self, cache: CacheDB) -> None:
        """Returns the entity as-is when it's an exact match."""
        from clew.indexer.relationships import Relationship

        rels = [
            Relationship(
                "/abs/path/backend/care/models.py::Prescription",
                "imports",
                "/abs/path/backend/utils/mixins.py::TimestampMixin",
                "/abs/path/backend/care/models.py",
            ),
        ]
        cache.store_relationships(rels)
        result = cache.resolve_entity("/abs/path/backend/care/models.py::Prescription")
        assert result == "/abs/path/backend/care/models.py::Prescription"

    def test_suffix_match_relative_path(self, cache: CacheDB) -> None:
        """Resolves a relative path to the full absolute entity."""
        from clew.indexer.relationships import Relationship

        rels = [
            Relationship(
                "/abs/path/backend/care/models.py::Foo",
                "calls",
                "/abs/path/backend/utils/helpers.py::bar",
                "/abs/path/backend/care/models.py",
            ),
        ]
        cache.store_relationships(rels)
        result = cache.resolve_entity("backend/care/models.py::Foo")
        assert result == "/abs/path/backend/care/models.py::Foo"

    def test_symbol_only_match(self, cache: CacheDB) -> None:
        """Resolves a bare symbol name to the full entity."""
        from clew.indexer.relationships import Relationship

        rels = [
            Relationship(
                "/abs/path/backend/care/models.py::Prescription",
                "inherits",
                "/abs/path/backend/utils/mixins.py::Base",
                "/abs/path/backend/care/models.py",
            ),
        ]
        cache.store_relationships(rels)
        result = cache.resolve_entity("Prescription")
        assert result == "/abs/path/backend/care/models.py::Prescription"

    def test_no_match_returns_original(self, cache: CacheDB) -> None:
        """Returns the original string when nothing matches."""
        from clew.indexer.relationships import Relationship

        rels = [
            Relationship("a.py::Foo", "calls", "b.py::Bar", "a.py"),
        ]
        cache.store_relationships(rels)
        result = cache.resolve_entity("nonexistent.py::DoesNotExist")
        assert result == "nonexistent.py::DoesNotExist"

    def test_prefers_source_entity(self, cache: CacheDB) -> None:
        """When entity suffix appears in both source and target, prefers source."""
        from clew.indexer.relationships import Relationship

        rels = [
            Relationship(
                "/other/path/models.py::Widget",
                "calls",
                "/some/path/models.py::Gadget",
                "/other/path/models.py",
            ),
            Relationship(
                "/some/path/models.py::Gadget",
                "imports",
                "/lib/utils.py::helper",
                "/some/path/models.py",
            ),
        ]
        cache.store_relationships(rels)
        # "Gadget" appears as target in 1st rel, source in 2nd rel.
        # resolve_entity should prefer the source_entity match.
        result = cache.resolve_entity("Gadget")
        assert result == "/some/path/models.py::Gadget"


class TestEnrichmentCache:
    """Test enrichment cache CRUD operations."""

    @pytest.fixture
    def cache(self, temp_cache_dir: Path) -> CacheDB:
        return CacheDB(temp_cache_dir)

    def test_get_enrichment_missing(self, cache: CacheDB) -> None:
        result = cache.get_enrichment("nonexistent_chunk")
        assert result is None

    def test_set_and_get_enrichment(self, cache: CacheDB) -> None:
        cache.set_enrichment("file.py::Foo", "A Foo class.", "foo bar baz")
        result = cache.get_enrichment("file.py::Foo")
        assert result is not None
        assert result[0] == "A Foo class."
        assert result[1] == "foo bar baz"

    def test_enrichment_upsert(self, cache: CacheDB) -> None:
        cache.set_enrichment("file.py::Foo", "Old desc.", "old keywords")
        cache.set_enrichment("file.py::Foo", "New desc.", "new keywords")
        result = cache.get_enrichment("file.py::Foo")
        assert result is not None
        assert result[0] == "New desc."
        assert result[1] == "new keywords"

    def test_enrichment_stores_timestamp(self, cache: CacheDB) -> None:
        import time

        before = time.time()
        cache.set_enrichment("file.py::Foo", "Desc.", "kw")
        after = time.time()

        with cache._get_cache_conn() as conn:
            row = conn.execute(
                "SELECT enriched_at FROM enrichment_cache WHERE chunk_id = ?",
                ("file.py::Foo",),
            ).fetchone()
            assert row is not None
            assert before <= row["enriched_at"] <= after


class TestGetAllRelationshipPairs:
    """Test get_all_relationship_pairs method."""

    @pytest.fixture
    def cache(self, temp_cache_dir: Path) -> CacheDB:
        return CacheDB(temp_cache_dir)

    def test_empty_returns_empty(self, cache: CacheDB) -> None:
        result = cache.get_all_relationship_pairs()
        assert result == []

    def test_returns_all_pairs(self, cache: CacheDB) -> None:
        from clew.indexer.relationships import Relationship

        rels = [
            Relationship("a.py::Foo", "calls", "b.py::Bar", "a.py"),
            Relationship("c.py::Baz", "imports", "d.py::Qux", "c.py"),
        ]
        cache.store_relationships(rels)
        pairs = cache.get_all_relationship_pairs()
        assert len(pairs) == 2
        assert ("a.py::Foo", "b.py::Bar") in pairs
        assert ("c.py::Baz", "d.py::Qux") in pairs


class TestSchemaMigration:
    """Test schema migration from v2 to v3."""

    def test_new_database_has_enrichment_table(self, temp_cache_dir: Path) -> None:
        """A fresh CacheDB creates the enrichment_cache table."""
        cache = CacheDB(temp_cache_dir)
        # Should be able to use enrichment methods without error
        cache.set_enrichment("test::chunk", "desc", "keywords")
        result = cache.get_enrichment("test::chunk")
        assert result == ("desc", "keywords")

    def test_clear_all_state_clears_enrichment(self, temp_cache_dir: Path) -> None:
        """clear_all_state should also clear enrichment_cache."""
        cache = CacheDB(temp_cache_dir)
        cache.set_enrichment("test::chunk", "desc", "keywords")
        cache.clear_all_state("code")
        result = cache.get_enrichment("test::chunk")
        assert result is None
