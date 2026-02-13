"""Python relationship extractor using tree-sitter AST.

Includes import-aware call resolution: builds a per-file symbol table
from import statements, then resolves call targets to fully qualified
names where possible.
"""

from __future__ import annotations

import logging
from typing import Any

from clew.indexer.extractors.base import RelationshipExtractor
from clew.indexer.relationships import Relationship

logger = logging.getLogger(__name__)


class PythonRelationshipExtractor(RelationshipExtractor):
    """Extract relationships from Python source via tree-sitter."""

    def extract(self, tree: Any, source: str, file_path: str) -> list[Relationship]:
        relationships: list[Relationship] = []
        self._import_table: dict[str, str] = {}
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
        """Extract from `import X` and `import X, Y` and `import X as Z` statements.

        Fixes two pre-existing bugs:
        - Bug 1: `import os, sys` only captured `os`
          (used child_by_field_name which returns first only)
        - Bug 2: `import os as o` stored "os as o" as target
          (raw text of aliased_import node)
        """
        for i, child in enumerate(node.children):
            field = node.field_name_for_child(i)
            if field != "name":
                continue

            if child.type == "dotted_name":
                module_name = child.text.decode()
                rels.append(
                    Relationship(
                        source_entity=file_path,
                        relationship="imports",
                        target_entity=module_name,
                        file_path=file_path,
                    )
                )
                # Populate import table: `import os.path` → local name "os" maps to "os.path"
                local_name = module_name.split(".")[0]
                self._import_table[local_name] = module_name

            elif child.type == "aliased_import":
                name_node = child.child_by_field_name("name")
                alias_node = child.child_by_field_name("alias")
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
                    local_name = (
                        alias_node.text.decode() if alias_node else module_name.split(".")[0]
                    )
                    self._import_table[local_name] = module_name

    def _extract_from_import(self, node: Any, file_path: str, rels: list[Relationship]) -> None:
        """Extract from `from X import Y, Z` and `from X import Y as Z` statements.

        Fixes pre-existing bug:
        - Bug 3: `from os.path import join as pjoin` was not extracted because
          aliased_import node type was not in the type check.
        """
        module_node = node.child_by_field_name("module_name")
        module_name = module_node.text.decode() if module_node else ""

        for i, child in enumerate(node.children):
            field = node.field_name_for_child(i)
            if field != "name":
                continue

            if child.type in ("dotted_name", "identifier"):
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
                # Populate import table: `from X import Y` → "Y" maps to "X::Y"
                self._import_table[imported_name] = target

            elif child.type == "aliased_import":
                name_node = child.child_by_field_name("name")
                alias_node = child.child_by_field_name("alias")
                if name_node:
                    imported_name = name_node.text.decode()
                    target = f"{module_name}::{imported_name}" if module_name else imported_name
                    rels.append(
                        Relationship(
                            source_entity=file_path,
                            relationship="imports",
                            target_entity=target,
                            file_path=file_path,
                        )
                    )
                    local_name = alias_node.text.decode() if alias_node else imported_name
                    self._import_table[local_name] = target

    def _extract_inheritance(
        self, node: Any, file_path: str, class_name: str | None, rels: list[Relationship]
    ) -> None:
        """Extract base classes from class definition, resolving via import table."""
        if not class_name:
            return
        superclasses = node.child_by_field_name("superclasses")
        if not superclasses:
            return
        for child in superclasses.named_children:
            if child.type in ("identifier", "attribute"):
                base_name = child.text.decode()
                resolved = self._resolve_name(child, base_name)
                rels.append(
                    Relationship(
                        source_entity=f"{file_path}::{class_name}",
                        relationship="inherits",
                        target_entity=resolved,
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
        """Extract decorator relationships, resolving via import table."""
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

        # Resolve decorator name via import table
        resolved = self._import_table.get(decorator_name, decorator_name)

        def_name = self._get_field_text(definition_node, "name")
        if not def_name:
            return

        qualified = f"{parent_class}.{def_name}" if parent_class else def_name
        rels.append(
            Relationship(
                source_entity=resolved,
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
        """Extract call relationships, resolving targets via import table."""
        func = node.child_by_field_name("function")
        if not func:
            return

        called_name = func.text.decode()
        source_entity = f"{file_path}::{current_function}" if current_function else file_path

        resolved_target = self._resolve_call_target(func, called_name)

        rels.append(
            Relationship(
                source_entity=source_entity,
                relationship="calls",
                target_entity=resolved_target,
                file_path=file_path,
                confidence="inferred",
            )
        )

        # Emit an additional class-level edge for attribute access chains.
        # e.g., care.models::PrescriptionFill.objects.create → care.models::PrescriptionFill
        if "::" in resolved_target:
            module, symbol_chain = resolved_target.split("::", 1)
            if "." in symbol_chain:
                class_name = symbol_chain.split(".")[0]
                class_target = f"{module}::{class_name}"
                rels.append(
                    Relationship(
                        source_entity=source_entity,
                        relationship="calls",
                        target_entity=class_target,
                        file_path=file_path,
                        confidence="inferred",
                    )
                )

    def _resolve_call_target(self, func_node: Any, called_name: str) -> str:
        """Resolve a call target using the import table.

        - Bare calls (identifier): direct dict lookup
        - Dotted calls (attribute): extract root, check import table, replace root segment
        - Fallback: return original called_name
        """
        if func_node.type == "identifier":
            # Direct lookup: `Prescription()` → import table["Prescription"]
            return self._import_table.get(called_name, called_name)

        if func_node.type == "attribute":
            root = self._get_attribute_root(func_node)
            if root is None:
                return called_name
            # Skip self/cls — no type info available
            if root in ("self", "cls"):
                return called_name
            # Check if root is in import table
            resolved_root = self._import_table.get(root)
            if resolved_root is not None:
                # Replace root with resolved path
                # e.g., `np.array()` with np→numpy becomes `numpy.array`
                suffix = called_name[len(root) :]  # ".array()" → ".array"
                return f"{resolved_root}{suffix}"

        return called_name

    def _resolve_name(self, node: Any, name: str) -> str:
        """Resolve a name (identifier or attribute) via import table."""
        if node.type == "identifier":
            return self._import_table.get(name, name)

        if node.type == "attribute":
            root = self._get_attribute_root(node)
            if root and root in self._import_table:
                resolved_root = self._import_table[root]
                suffix = name[len(root) :]
                return f"{resolved_root}{suffix}"

        return name

    @staticmethod
    def _get_attribute_root(node: Any) -> str | None:
        """Walk leftmost attribute.object chain to find root identifier.

        E.g., `os.path.join` → root "os"
        """
        current = node
        while current.type == "attribute":
            obj = current.child_by_field_name("object")
            if obj is None:
                return None
            current = obj
        if current.type == "identifier":
            result: str = current.text.decode()
            return result
        return None

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
