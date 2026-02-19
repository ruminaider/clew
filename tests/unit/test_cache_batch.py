"""Tests for CacheDB.traverse_relationships_batch()."""

from __future__ import annotations

import pytest

from clew.indexer.cache import CacheDB
from clew.indexer.relationships import Relationship


@pytest.fixture
def cache_db(tmp_path):
    """Create a CacheDB with test relationships."""
    db = CacheDB(tmp_path / ".clew")
    db.store_relationships(
        [
            Relationship(
                source_entity="app/views.py::OrderView",
                relationship="calls",
                target_entity="app/services.py::process_order",
                file_path="app/views.py",
            ),
            Relationship(
                source_entity="tests/test_views.py::TestOrderView",
                relationship="tests",
                target_entity="app/views.py::OrderView",
                file_path="tests/test_views.py",
            ),
            Relationship(
                source_entity="app/views.py::OrderView",
                relationship="imports",
                target_entity="app/models.py::Order",
                file_path="app/views.py",
            ),
        ]
    )
    return db


class TestTraverseRelationshipsBatch:
    def test_outbound_batch(self, cache_db):
        results = cache_db.traverse_relationships_batch(
            ["app/views.py::OrderView"], direction="outbound"
        )
        targets = [r["target_entity"] for r in results]
        assert "app/services.py::process_order" in targets
        assert "app/models.py::Order" in targets

    def test_inbound_batch(self, cache_db):
        results = cache_db.traverse_relationships_batch(
            ["app/views.py::OrderView"], direction="inbound"
        )
        sources = [r["source_entity"] for r in results]
        assert "tests/test_views.py::TestOrderView" in sources

    def test_both_directions(self, cache_db):
        results = cache_db.traverse_relationships_batch(
            ["app/views.py::OrderView"], direction="both"
        )
        assert len(results) == 3  # 2 outbound + 1 inbound

    def test_multiple_entities(self, cache_db):
        results = cache_db.traverse_relationships_batch(
            ["app/views.py::OrderView", "app/services.py::process_order"],
            direction="both",
        )
        assert len(results) >= 3

    def test_empty_entities(self, cache_db):
        results = cache_db.traverse_relationships_batch([])
        assert results == []

    def test_nonexistent_entity(self, cache_db):
        results = cache_db.traverse_relationships_batch(["nonexistent::Entity"], direction="both")
        assert results == []

    def test_depth_is_always_one(self, cache_db):
        results = cache_db.traverse_relationships_batch(
            ["app/views.py::OrderView"], direction="both"
        )
        for r in results:
            assert r["depth"] == 1
