"""Django model field relationship extractor.

Extracts ForeignKey, OneToOneField, and ManyToManyField relationships
from Django model definitions via tree-sitter AST.
"""

from __future__ import annotations

import logging
from typing import Any

from clew.indexer.extractors.base import RelationshipExtractor
from clew.indexer.relationships import Relationship

logger = logging.getLogger(__name__)

RELATIONSHIP_FIELDS: dict[str, str] = {
    "ForeignKey": "has_fk",
    "OneToOneField": "has_o2o",
    "ManyToManyField": "has_m2m",
}

# Base classes that indicate a Django model
_MODEL_BASES = {"Model", "models.Model"}


class DjangoModelFieldExtractor(RelationshipExtractor):
    """Extract ForeignKey/M2M/O2O relationships from Django model definitions."""

    def extract(self, tree: Any, source: str, file_path: str) -> list[Relationship]:
        relationships: list[Relationship] = []
        self._walk(tree.root_node, source, file_path, relationships, enclosing_class=None)
        return relationships

    def _walk(
        self,
        node: Any,
        source: str,
        file_path: str,
        rels: list[Relationship],
        *,
        enclosing_class: str | None,
    ) -> None:
        if node.type == "class_definition":
            class_name = self._get_field_text(node, "name")
            if class_name and self._is_model_class(node):
                body = node.child_by_field_name("body")
                if body:
                    for child in body.children:
                        self._walk(child, source, file_path, rels, enclosing_class=class_name)
            return

        if node.type == "expression_statement" and enclosing_class:
            # Look for: field_name = models.ForeignKey(...)
            for child in node.children:
                if child.type == "assignment":
                    self._extract_field_assignment(child, source, file_path, rels, enclosing_class)

        for child in node.children:
            self._walk(child, source, file_path, rels, enclosing_class=enclosing_class)

    def _extract_field_assignment(
        self,
        node: Any,
        source: str,
        file_path: str,
        rels: list[Relationship],
        enclosing_class: str,
    ) -> None:
        """Extract relationship field from an assignment node."""
        right = node.child_by_field_name("right")
        if not right or right.type != "call":
            return

        func = right.child_by_field_name("function")
        if not func:
            return

        func_text = func.text.decode()
        # Match both "ForeignKey" and "models.ForeignKey"
        field_name = func_text.split(".")[-1] if "." in func_text else func_text

        if field_name not in RELATIONSHIP_FIELDS:
            return

        rel_type = RELATIONSHIP_FIELDS[field_name]

        # Get the first positional argument (target model)
        args = right.child_by_field_name("arguments")
        if not args:
            return

        positional_args = [
            child for child in args.named_children if child.type != "keyword_argument"
        ]
        if not positional_args:
            return

        target_node = positional_args[0]
        target_text = target_node.text.decode().strip("'\"")

        # Handle self-referential ForeignKey
        if target_text == "self":
            target_text = enclosing_class

        source_entity = f"{file_path}::{enclosing_class}"
        rels.append(
            Relationship(
                source_entity=source_entity,
                relationship=rel_type,
                target_entity=target_text,
                file_path=file_path,
            )
        )

    def _is_model_class(self, node: Any) -> bool:
        """Check if a class definition inherits from models.Model."""
        superclasses = node.child_by_field_name("superclasses")
        if not superclasses:
            return False
        for child in superclasses.named_children:
            text = child.text.decode()
            if text in _MODEL_BASES:
                return True
            # Also match classes ending in Model (e.g., TimeStampedModel, AbstractModel)
            if text.endswith("Model"):
                return True
        return False

    @staticmethod
    def _get_field_text(node: Any, field_name: str) -> str | None:
        child = node.child_by_field_name(field_name)
        return child.text.decode() if child else None
