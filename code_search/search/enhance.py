"""Query enhancement with terminology expansion and skip logic.

Supports both abbreviation expansion and synonym expansion
from a YAML terminology file.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml


def should_skip_enhancement(query: str) -> bool:
    """Determine if query should bypass enhancement."""
    # Quoted exact match
    if query.startswith('"') and query.endswith('"'):
        return True
    # PascalCase identifier
    if re.match(r"^[A-Z][a-zA-Z0-9]+$", query):
        return True
    # snake_case identifier
    if re.match(r"^[a-z][a-z0-9_]*$", query) and "_" in query:
        return True
    # File path
    if "/" in query or query.endswith((".py", ".ts", ".js", ".tsx", ".jsx")):
        return True
    return False


class QueryEnhancer:
    """Enhance queries with terminology expansion.

    Supports two expansion types from YAML:
    - abbreviations: BV -> "BV (bacterial vaginosis)"
    - synonyms: consult -> "consult (consultation, telehealth)"
    """

    def __init__(self, terminology_file: Path | None = None) -> None:
        self._abbreviations: dict[str, str] = {}
        self._synonyms: dict[str, list[str]] = {}
        if terminology_file and terminology_file.exists():
            self._load_terminology(terminology_file)

    def _load_terminology(self, path: Path) -> None:
        """Load terminology definitions from YAML file."""
        data: dict[str, Any] = yaml.safe_load(path.read_text()) or {}
        self._abbreviations = data.get("abbreviations", {}) or {}
        self._synonyms = data.get("synonyms", {}) or {}

    def enhance(self, query: str) -> str:
        """Enhance query with terminology expansion.

        Returns original query if skip conditions apply.
        """
        if should_skip_enhancement(query):
            return query

        enhanced = query

        # Expand abbreviations: "BV" -> "BV (bacterial vaginosis)"
        for abbr, expansion in self._abbreviations.items():
            pattern = re.compile(r"\b" + re.escape(abbr) + r"\b", re.IGNORECASE)
            if pattern.search(enhanced):
                enhanced = pattern.sub(f"{abbr} ({expansion})", enhanced)

        # Expand synonyms: "consult" -> "consult (consultation, telehealth)"
        for term, alternatives in self._synonyms.items():
            pattern = re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)
            if pattern.search(enhanced) and alternatives:
                alt_str = ", ".join(alternatives)
                enhanced = pattern.sub(f"{term} ({alt_str})", enhanced)

        return enhanced
