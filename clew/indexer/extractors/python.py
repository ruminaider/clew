"""Python relationship extractor using tree-sitter AST."""

from __future__ import annotations

from typing import Any

from clew.indexer.extractors.base import RelationshipExtractor
from clew.indexer.relationships import Relationship


class PythonRelationshipExtractor(RelationshipExtractor):
    """Extract relationships from Python source via tree-sitter."""

    def extract(self, tree: Any, source: str, file_path: str) -> list[Relationship]:
        relationships: list[Relationship] = []
        self._walk(
            tree.root_node,
            source,
            file_path,
            relationships,
            parent_class=None,
            current_function=None,
        )
        return relationships

    def _walk(
        self,
        node: Any,
        source: str,
        file_path: str,
        rels: list[Relationship],
        *,
        parent_class: str | None,
        current_function: str | None,
    ) -> None:
        if node.type == "import_statement":
            self._extract_import(node, file_path, rels)
        elif node.type == "import_from_statement":
            self._extract_from_import(node, file_path, rels)
        elif node.type == "class_definition":
            class_name = self._get_field_text(node, "name")
            self._extract_inheritance(node, file_path, class_name, rels)
            body = node.child_by_field_name("body")
            if body:
                for child in body.children:
                    self._walk(
                        child,
                        source,
                        file_path,
                        rels,
                        parent_class=class_name,
                        current_function=None,
                    )
            return
        elif node.type == "decorated_definition":
            self._extract_decorator(node, file_path, rels, parent_class=parent_class)
        elif node.type == "function_definition":
            func_name = self._get_field_text(node, "name")
            if func_name:
                qualified = f"{parent_class}.{func_name}" if parent_class else func_name
                body = node.child_by_field_name("body")
                if body:
                    for child in body.children:
                        self._walk(
                            child,
                            source,
                            file_path,
                            rels,
                            parent_class=parent_class,
                            current_function=qualified,
                        )
                return
        elif node.type == "call":
            self._extract_call(node, file_path, rels, current_function=current_function)

        for child in node.children:
            self._walk(
                child,
                source,
                file_path,
                rels,
                parent_class=parent_class,
                current_function=current_function,
            )

    def _extract_import(self, node: Any, file_path: str, rels: list[Relationship]) -> None:
        """Extract from `import X` statements."""
        name_node = node.child_by_field_name("name")
        if name_node:
            module_name = name_node.text.decode()
            rels.append(
                Relationship(
                    source_entity=file_path,
                    relationship="imports",
                    target_entity=module_name,
                    file_path=file_path,
                )
            )

    def _extract_from_import(self, node: Any, file_path: str, rels: list[Relationship]) -> None:
        """Extract from `from X import Y, Z` statements."""
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
                        relationship="imports",
                        target_entity=target,
                        file_path=file_path,
                    )
                )

    def _extract_inheritance(
        self, node: Any, file_path: str, class_name: str | None, rels: list[Relationship]
    ) -> None:
        """Extract base classes from class definition."""
        if not class_name:
            return
        superclasses = node.child_by_field_name("superclasses")
        if not superclasses:
            return
        for child in superclasses.named_children:
            if child.type in ("identifier", "attribute"):
                base_name = child.text.decode()
                rels.append(
                    Relationship(
                        source_entity=f"{file_path}::{class_name}",
                        relationship="inherits",
                        target_entity=base_name,
                        file_path=file_path,
                    )
                )

    def _extract_decorator(
        self,
        node: Any,
        file_path: str,
        rels: list[Relationship],
        *,
        parent_class: str | None,
    ) -> None:
        """Extract decorator relationships from decorated_definition."""
        decorator_node = None
        definition_node = None
        for child in node.children:
            if child.type == "decorator":
                decorator_node = child
            elif child.type in ("function_definition", "class_definition"):
                definition_node = child

        if not decorator_node or not definition_node:
            return

        decorator_name = self._get_decorator_name(decorator_node)
        if not decorator_name:
            return

        def_name = self._get_field_text(definition_node, "name")
        if not def_name:
            return

        qualified = f"{parent_class}.{def_name}" if parent_class else def_name
        rels.append(
            Relationship(
                source_entity=decorator_name,
                relationship="decorates",
                target_entity=f"{file_path}::{qualified}",
                file_path=file_path,
            )
        )

    def _extract_call(
        self,
        node: Any,
        file_path: str,
        rels: list[Relationship],
        *,
        current_function: str | None,
    ) -> None:
        """Extract call relationships."""
        func = node.child_by_field_name("function")
        if not func:
            return

        called_name = func.text.decode()
        source_entity = f"{file_path}::{current_function}" if current_function else file_path

        rels.append(
            Relationship(
                source_entity=source_entity,
                relationship="calls",
                target_entity=called_name,
                file_path=file_path,
                confidence="inferred",
            )
        )

    def _get_decorator_name(self, decorator_node: Any) -> str | None:
        """Extract decorator name from decorator node."""
        for child in decorator_node.children:
            if child.type == "identifier":
                result: str = child.text.decode()
                return result
            if child.type == "call":
                func = child.child_by_field_name("function")
                if func:
                    result = func.text.decode()
                    return result
            if child.type == "attribute":
                result = child.text.decode()
                return result
        return None

    @staticmethod
    def _get_field_text(node: Any, field_name: str) -> str | None:
        child = node.child_by_field_name(field_name)
        return child.text.decode() if child else None
