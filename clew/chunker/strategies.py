"""File-type chunking strategies."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any


@dataclass
class CodeEntity:
    """A parsed code entity (class, function, method)."""

    entity_type: str
    name: str
    qualified_name: str
    content: str
    line_start: int
    line_end: int
    parent_class: str | None
    docstring: str | None = None


class PythonChunker:
    """Extract code entities from Python AST."""

    DEFINITION_TYPES = {"class_definition", "function_definition"}

    def extract_entities(self, tree: Any, source: str) -> Iterator[CodeEntity]:
        """Extract all code entities from AST."""
        source_bytes = source.encode("utf-8")
        for node in self._walk_definitions(tree.root_node):
            yield from self._node_to_entity(node, source_bytes)

    def _walk_definitions(self, node: Any) -> Iterator[Any]:
        """Walk tree finding definition nodes."""
        if node.type in self.DEFINITION_TYPES:
            yield node
        for child in node.children:
            yield from self._walk_definitions(child)

    def _node_to_entity(self, node: Any, source_bytes: bytes) -> Iterator[CodeEntity]:
        """Convert AST node to CodeEntity."""
        name = self._get_name(node)
        content = source_bytes[node.start_byte : node.end_byte].decode("utf-8")

        if node.type == "class_definition":
            yield CodeEntity(
                entity_type="class",
                name=name,
                qualified_name=name,
                content=content,
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                parent_class=None,
                docstring=self._extract_docstring(node, source_bytes),
            )
            for method in self._get_methods(node):
                method_name = self._get_name(method)
                method_content = source_bytes[method.start_byte : method.end_byte].decode("utf-8")
                yield CodeEntity(
                    entity_type="method",
                    name=method_name,
                    qualified_name=f"{name}.{method_name}",
                    content=method_content,
                    line_start=method.start_point[0] + 1,
                    line_end=method.end_point[0] + 1,
                    parent_class=name,
                    docstring=self._extract_docstring(method, source_bytes),
                )
        elif node.type == "function_definition":
            yield CodeEntity(
                entity_type="function",
                name=name,
                qualified_name=name,
                content=content,
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                parent_class=None,
                docstring=self._extract_docstring(node, source_bytes),
            )

    def _extract_docstring(self, node: Any, source_bytes: bytes) -> str | None:
        """Extract docstring from a function/class definition node.

        Docstrings are the first expression_statement containing a string
        in the body block.  f-strings and byte literals are rejected since
        they cannot be valid Python docstrings.
        """
        for child in node.children:
            if child.type == "block":
                for stmt in child.children:
                    if stmt.type == "expression_statement":
                        for expr in stmt.children:
                            if expr.type == "string":
                                raw = source_bytes[expr.start_byte : expr.end_byte].decode("utf-8")
                                # Reject f-strings and byte literals (not valid Python docstrings)
                                lower_raw = raw.lstrip().lower()
                                if lower_raw.startswith(('f"', "f'", 'b"', "b'")):
                                    return None
                                # Strip string prefix (r, u) and quote delimiters
                                stripped_prefix = raw.lstrip("rRuU")
                                if stripped_prefix.startswith('"""') or stripped_prefix.startswith(
                                    "'''"
                                ):
                                    content = stripped_prefix[3:-3]
                                elif stripped_prefix.startswith('"') or stripped_prefix.startswith(
                                    "'"
                                ):
                                    content = stripped_prefix[1:-1]
                                else:
                                    return None
                                return content.strip() if content.strip() else None
                    # Only the first statement can be a docstring
                    if stmt.type not in ("comment", "newline", "expression_statement"):
                        break
        return None

    def _get_name(self, node: Any) -> str:
        """Extract name from definition node."""
        for child in node.children:
            if child.type == "identifier":
                return child.text.decode("utf-8")  # type: ignore[no-any-return]
        return "unknown"

    def _get_methods(self, class_node: Any) -> Iterator[Any]:
        """Get method nodes from class body."""
        for child in class_node.children:
            if child.type == "block":
                for stmt in child.children:
                    if stmt.type == "function_definition":
                        yield stmt
