"""Tree-sitter AST parsing."""

from __future__ import annotations

from typing import Any

import tree_sitter_javascript
import tree_sitter_python
import tree_sitter_typescript
from tree_sitter import Language, Parser


class ASTParser:
    """Parse source files into AST using tree-sitter."""

    def __init__(self) -> None:
        self._parsers: dict[str, Parser] = {}
        self._init_parsers()

    def _init_parsers(self) -> None:
        """Initialize parsers for each supported language."""
        py_parser = Parser()
        py_parser.language = Language(tree_sitter_python.language())
        self._parsers["python"] = py_parser

        ts_parser = Parser()
        ts_parser.language = Language(tree_sitter_typescript.language_typescript())
        self._parsers["typescript"] = ts_parser

        tsx_parser = Parser()
        tsx_parser.language = Language(tree_sitter_typescript.language_tsx())
        self._parsers["tsx"] = tsx_parser

        js_parser = Parser()
        js_parser.language = Language(tree_sitter_javascript.language())
        self._parsers["javascript"] = js_parser

    def get_language(self, file_path: str) -> str | None:
        """Determine language from file extension."""
        ext = file_path.rsplit(".", 1)[-1].lower()
        return {
            "py": "python",
            "ts": "typescript",
            "tsx": "tsx",
            "js": "javascript",
            "jsx": "javascript",
        }.get(ext)

    def parse(self, content: str, language: str) -> Any:
        """Parse source content into AST."""
        parser = self._parsers.get(language)
        if not parser:
            return None
        try:
            return parser.parse(content.encode("utf-8"))
        except Exception:
            return None

    def parse_file(self, file_path: str, content: str) -> Any:
        """Parse file content, auto-detecting language."""
        language = self.get_language(file_path)
        if not language:
            return None
        return self.parse(content, language)
