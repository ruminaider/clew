"""Test file relationship detection."""

from __future__ import annotations

import re
from typing import Any

from code_search.indexer.extractors.base import RelationshipExtractor
from code_search.indexer.relationships import Relationship

_TEST_FILE_PATTERNS = [
    re.compile(r"(?:^|/)test_"),
    re.compile(r"_test\.py$"),
    re.compile(r"\.test\.\w+$"),
    re.compile(r"\.spec\.\w+$"),
    re.compile(r"(?:^|/)tests/"),
    re.compile(r"(?:^|/)__tests__/"),
]


def _is_test_file(file_path: str) -> bool:
    """Check if a file path matches test file patterns."""
    return any(p.search(file_path) for p in _TEST_FILE_PATTERNS)


class TestRelationshipExtractor(RelationshipExtractor):
    """Detect test files and create 'tests' relationships from their imports."""

    def extract(self, tree: Any, source: str, file_path: str) -> list[Relationship]:
        if not _is_test_file(file_path):
            return []

        relationships: list[Relationship] = []
        self._walk(tree.root_node, file_path, relationships)
        return relationships

    def _walk(self, node: Any, file_path: str, rels: list[Relationship]) -> None:
        if node.type == "import_statement":
            self._extract_ts_import(node, file_path, rels)
            self._extract_python_import(node, file_path, rels)
        elif node.type == "import_from_statement":
            self._extract_python_from_import(node, file_path, rels)

        for child in node.children:
            self._walk(child, file_path, rels)

    def _extract_python_import(self, node: Any, file_path: str, rels: list[Relationship]) -> None:
        name_node = node.child_by_field_name("name")
        if name_node:
            rels.append(
                Relationship(
                    source_entity=file_path,
                    relationship="tests",
                    target_entity=name_node.text.decode(),
                    file_path=file_path,
                )
            )

    def _extract_python_from_import(
        self, node: Any, file_path: str, rels: list[Relationship]
    ) -> None:
        module_node = node.child_by_field_name("module_name")
        module_name = module_node.text.decode() if module_node else ""

        for i, child in enumerate(node.children):
            field = node.field_name_for_child(i)
            if field == "name" and child.type in ("dotted_name", "identifier"):
                imported_name = child.text.decode()
                target = f"{module_name}::{imported_name}" if module_name else imported_name
                rels.append(
                    Relationship(
                        source_entity=file_path,
                        relationship="tests",
                        target_entity=target,
                        file_path=file_path,
                    )
                )

    def _extract_ts_import(self, node: Any, file_path: str, rels: list[Relationship]) -> None:
        source_node = node.child_by_field_name("source")
        if not source_node:
            return
        module_path = source_node.text.decode().strip("'\"")

        for child in node.children:
            if child.type == "import_clause":
                for clause_child in child.children:
                    if clause_child.type == "identifier":
                        rels.append(
                            Relationship(
                                source_entity=file_path,
                                relationship="tests",
                                target_entity=f"{module_path}::{clause_child.text.decode()}",
                                file_path=file_path,
                            )
                        )
                    elif clause_child.type == "named_imports":
                        for spec in clause_child.named_children:
                            if spec.type == "import_specifier":
                                name_node = spec.child_by_field_name("name")
                                if name_node:
                                    rels.append(
                                        Relationship(
                                            source_entity=file_path,
                                            relationship="tests",
                                            target_entity=(
                                                f"{module_path}::{name_node.text.decode()}"
                                            ),
                                            file_path=file_path,
                                        )
                                    )
