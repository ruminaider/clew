"""TypeScript/JavaScript relationship extractor using tree-sitter AST."""

from __future__ import annotations

from typing import Any

from code_search.indexer.extractors.base import RelationshipExtractor
from code_search.indexer.relationships import Relationship

_FETCH_METHODS = {"fetch"}
_AXIOS_METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}


class TypeScriptRelationshipExtractor(RelationshipExtractor):
    """Extract relationships from TypeScript/JavaScript source via tree-sitter."""

    def extract(self, tree: Any, source: str, file_path: str) -> list[Relationship]:
        relationships: list[Relationship] = []
        self._walk(tree.root_node, source, file_path, relationships, current_function=None)
        return relationships

    def _walk(
        self,
        node: Any,
        source: str,
        file_path: str,
        rels: list[Relationship],
        *,
        current_function: str | None,
    ) -> None:
        if node.type == "import_statement":
            self._extract_import(node, file_path, rels)
        elif node.type in ("class_declaration", "class"):
            self._extract_class(node, file_path, rels)
        elif node.type in ("function_declaration", "method_definition"):
            func_name = self._get_function_name(node)
            if func_name:
                for child in node.children:
                    self._walk(child, source, file_path, rels, current_function=func_name)
                return
        elif node.type == "variable_declarator":
            name_node = node.child_by_field_name("name")
            value_node = node.child_by_field_name("value")
            if name_node and value_node:
                if value_node.type in ("arrow_function", "function"):
                    func_name = name_node.text.decode()
                    for child in value_node.children:
                        self._walk(
                            child, source, file_path, rels, current_function=func_name
                        )
                    return
                if value_node.type == "call_expression":
                    self._extract_require(value_node, file_path, rels)
        elif node.type == "jsx_self_closing_element":
            self._extract_jsx_render(node, file_path, rels, current_function)
        elif node.type == "jsx_opening_element":
            self._extract_jsx_render(node, file_path, rels, current_function)
        elif node.type == "call_expression":
            self._extract_call(node, file_path, rels, current_function)

        for child in node.children:
            self._walk(child, source, file_path, rels, current_function=current_function)

    def _extract_import(self, node: Any, file_path: str, rels: list[Relationship]) -> None:
        """Extract ES6 imports."""
        source_node = node.child_by_field_name("source")
        if not source_node:
            return
        module_path = source_node.text.decode().strip("'\"")

        for child in node.children:
            if child.type == "import_clause":
                self._extract_import_clause(child, module_path, file_path, rels)

    def _extract_import_clause(
        self, clause: Any, module_path: str, file_path: str, rels: list[Relationship]
    ) -> None:
        """Extract names from import clause."""
        for child in clause.children:
            if child.type == "identifier":
                rels.append(
                    Relationship(
                        source_entity=file_path,
                        relationship="imports",
                        target_entity=f"{module_path}::{child.text.decode()}",
                        file_path=file_path,
                    )
                )
            elif child.type == "named_imports":
                for spec in child.named_children:
                    if spec.type == "import_specifier":
                        name_node = spec.child_by_field_name("name")
                        if name_node:
                            rels.append(
                                Relationship(
                                    source_entity=file_path,
                                    relationship="imports",
                                    target_entity=f"{module_path}::{name_node.text.decode()}",
                                    file_path=file_path,
                                )
                            )
            elif child.type == "namespace_import":
                rels.append(
                    Relationship(
                        source_entity=file_path,
                        relationship="imports",
                        target_entity=module_path,
                        file_path=file_path,
                    )
                )

    def _extract_require(
        self, call_node: Any, file_path: str, rels: list[Relationship]
    ) -> None:
        """Extract CommonJS require() calls."""
        func = call_node.child_by_field_name("function")
        if not func or func.text.decode() != "require":
            return
        args = call_node.child_by_field_name("arguments")
        if not args:
            return
        for child in args.named_children:
            if child.type == "string":
                module = child.text.decode().strip("'\"")
                rels.append(
                    Relationship(
                        source_entity=file_path,
                        relationship="imports",
                        target_entity=module,
                        file_path=file_path,
                    )
                )
                break

    def _extract_class(self, node: Any, file_path: str, rels: list[Relationship]) -> None:
        """Extract class inheritance."""
        name_node = node.child_by_field_name("name")
        if not name_node:
            return
        class_name = name_node.text.decode()

        for child in node.children:
            if child.type == "class_heritage":
                for heritage_child in child.children:
                    if heritage_child.type == "extends_clause":
                        for ext_child in heritage_child.named_children:
                            if ext_child.type in (
                                "identifier",
                                "type_identifier",
                                "member_expression",
                            ):
                                rels.append(
                                    Relationship(
                                        source_entity=f"{file_path}::{class_name}",
                                        relationship="inherits",
                                        target_entity=ext_child.text.decode(),
                                        file_path=file_path,
                                    )
                                )

    def _extract_jsx_render(
        self,
        node: Any,
        file_path: str,
        rels: list[Relationship],
        current_function: str | None,
    ) -> None:
        """Extract JSX component renders."""
        tag_name = None
        name_node = node.child_by_field_name("name")
        if name_node:
            tag_name = name_node.text.decode()
        else:
            for child in node.named_children:
                if child.type in ("identifier", "member_expression"):
                    tag_name = child.text.decode()
                    break

        if not tag_name or tag_name[0].islower():
            return

        source_entity = f"{file_path}::{current_function}" if current_function else file_path
        rels.append(
            Relationship(
                source_entity=source_entity,
                relationship="renders",
                target_entity=tag_name,
                file_path=file_path,
            )
        )

    def _extract_call(
        self,
        node: Any,
        file_path: str,
        rels: list[Relationship],
        current_function: str | None,
    ) -> None:
        """Extract function calls and API calls (fetch/axios)."""
        func = node.child_by_field_name("function")
        if not func:
            return

        called_name = func.text.decode()
        source_entity = f"{file_path}::{current_function}" if current_function else file_path

        # Check for API calls: fetch('/api/...') or axios.get('/api/...')
        if self._is_api_call(called_name):
            url = self._extract_first_string_arg(node)
            if url:
                rels.append(
                    Relationship(
                        source_entity=source_entity,
                        relationship="calls_api",
                        target_entity=url,
                        file_path=file_path,
                        confidence="inferred",
                    )
                )
                return

        # Regular call
        rels.append(
            Relationship(
                source_entity=source_entity,
                relationship="calls",
                target_entity=called_name,
                file_path=file_path,
                confidence="inferred",
            )
        )

    def _is_api_call(self, called_name: str) -> bool:
        """Check if a call is an API call (fetch or axios.method)."""
        if called_name in _FETCH_METHODS:
            return True
        parts = called_name.split(".")
        return len(parts) == 2 and parts[0] == "axios" and parts[1] in _AXIOS_METHODS

    def _extract_first_string_arg(self, call_node: Any) -> str | None:
        """Extract the first string literal argument from a call. Skip template literals."""
        args = call_node.child_by_field_name("arguments")
        if not args:
            return None
        for child in args.named_children:
            if child.type == "string":
                return child.text.decode().strip("'\"")
            if child.type == "template_string":
                return None  # Can't resolve template literals
            break  # Only check first arg
        return None

    def _get_function_name(self, node: Any) -> str | None:
        """Get function name from declaration node."""
        name_node = node.child_by_field_name("name")
        if name_node:
            return name_node.text.decode()
        return None
