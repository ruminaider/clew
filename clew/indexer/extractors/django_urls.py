"""Django URL pattern extraction."""

from __future__ import annotations

import os
from typing import Any


class DjangoURLExtractor:
    """Extract URL patterns from Django urls.py files."""

    def extract_url_patterns(self, tree: Any, source: str, file_path: str) -> list[dict[str, str]]:
        """Extract URL patterns from a parsed AST.

        Only processes files named urls.py. Returns empty list for other files.
        """
        if os.path.basename(file_path) != "urls.py":
            return []

        patterns: list[dict[str, str]] = []
        self._walk(tree.root_node, file_path, patterns)
        return patterns

    def _walk(self, node: Any, file_path: str, patterns: list[dict[str, str]]) -> None:
        if node.type == "call":
            self._extract_url_call(node, file_path, patterns)

        for child in node.children:
            self._walk(child, file_path, patterns)

    def _extract_url_call(self, node: Any, file_path: str, patterns: list[dict[str, str]]) -> None:
        func = node.child_by_field_name("function")
        if not func:
            return

        func_name = func.text.decode()
        if func_name not in ("path", "re_path"):
            return

        args = node.child_by_field_name("arguments")
        if not args:
            return

        positional_args = [
            child for child in args.named_children if child.type != "keyword_argument"
        ]

        if not positional_args:
            return

        pattern_node = positional_args[0]
        if pattern_node.type != "string":
            return
        url_pattern = pattern_node.text.decode().strip("'\"")
        if not url_pattern.startswith("/"):
            url_pattern = "/" + url_pattern

        result: dict[str, str] = {"pattern": url_pattern, "file_path": file_path}

        if len(positional_args) > 1:
            view_node = positional_args[1]
            if view_node.type == "call":
                include_func = view_node.child_by_field_name("function")
                if include_func and include_func.text.decode() == "include":
                    include_args = view_node.child_by_field_name("arguments")
                    if include_args and include_args.named_children:
                        first_arg = include_args.named_children[0]
                        if first_arg.type == "string":
                            result["include"] = first_arg.text.decode().strip("'\"")
            else:
                result["view"] = view_node.text.decode()

        for child in args.named_children:
            if child.type == "keyword_argument":
                key_node = child.child_by_field_name("name")
                value_node = child.child_by_field_name("value")
                if key_node and value_node and key_node.text.decode() == "name":
                    result["name"] = value_node.text.decode().strip("'\"")

        patterns.append(result)
