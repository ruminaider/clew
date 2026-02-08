"""Base class for language-specific relationship extractors."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from code_search.indexer.relationships import Relationship


class RelationshipExtractor(ABC):
    """Abstract base for extracting code relationships from AST."""

    @abstractmethod
    def extract(self, tree: Any, source: str, file_path: str) -> list[Relationship]:
        """Extract relationships from a parsed AST tree.

        Args:
            tree: tree-sitter parse tree
            source: original source code
            file_path: path of the source file (for entity naming)

        Returns:
            List of Relationship instances found in the file.
        """
        ...
