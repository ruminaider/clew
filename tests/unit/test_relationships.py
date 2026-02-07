"""Tests for code relationship data model."""

from __future__ import annotations

from code_search.indexer.relationships import Relationship


class TestRelationship:
    def test_create_import_relationship(self) -> None:
        rel = Relationship(
            source_entity="app/main.py::main",
            relationship="imports",
            target_entity="app/utils.py::helper",
            file_path="app/main.py",
            confidence="static",
        )
        assert rel.source_entity == "app/main.py::main"
        assert rel.relationship == "imports"
        assert rel.target_entity == "app/utils.py::helper"
        assert rel.file_path == "app/main.py"
        assert rel.confidence == "static"

    def test_default_confidence_is_static(self) -> None:
        rel = Relationship(
            source_entity="a.py::Foo",
            relationship="inherits",
            target_entity="b.py::Bar",
            file_path="a.py",
        )
        assert rel.confidence == "static"
