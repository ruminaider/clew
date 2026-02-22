"""Result enrichment: add relationship context to search results.

Sync design — SQLite is local and traverse_relationships_batch() completes
in <10ms. Future async direction if external data sources are added.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

from .surfacing import extract_entity_ids

if TYPE_CHECKING:
    from clew.indexer.cache import CacheDB
    from clew.search.models import SearchResult

logger = logging.getLogger(__name__)


class ResultEnricher(ABC):
    """Abstract base class for result enrichment."""

    @abstractmethod
    def enrich(self, results: list[SearchResult]) -> list[SearchResult]:
        """Enrich search results with additional context."""


class CacheResultEnricher(ResultEnricher):
    """Enrich results with relationship context from the cache database."""

    def __init__(self, cache: CacheDB, project_root: Path | None = None) -> None:
        self._cache = cache
        self._project_root = project_root

    def _relativize(self, abs_path: str) -> str:
        """Convert absolute file path to relative (matching relationship DB format)."""
        if self._project_root is None:
            return abs_path
        try:
            return str(Path(abs_path).relative_to(self._project_root))
        except ValueError:
            return abs_path

    def enrich(self, results: list[SearchResult]) -> list[SearchResult]:
        """Add relationship context to top-5 results.

        Extracts entity IDs using relative paths (matching the relationship
        DB format), batch traverses relationships, groups by source entity,
        and builds a context string for each result.
        """
        if not results:
            return results

        entities, _ = extract_entity_ids(results, max_results=5, relativize=self._relativize)
        if not entities:
            return results

        try:
            relations = self._cache.traverse_relationships_batch(entities, max_depth=1)
        except Exception:
            logger.debug("Result enrichment failed", exc_info=True)
            return results

        if not relations:
            return results

        # Group relationships by source entity
        entity_rels: dict[str, list[dict[str, object]]] = {}
        for rel in relations:
            source = str(rel["source_entity"])
            target = str(rel["target_entity"])
            # Index by both source and target so we can match either direction
            entity_rels.setdefault(source, []).append(rel)
            entity_rels.setdefault(target, []).append(rel)

        # Build context for each result
        for result in results:
            rel_path = self._relativize(result.file_path)
            context_parts = _build_context_for_result(result, rel_path, entities, entity_rels)
            if context_parts:
                result.context = " | ".join(context_parts)

        return results


def _build_context_for_result(
    result: SearchResult,
    rel_path: str,
    entities: list[str],
    entity_rels: dict[str, list[dict[str, object]]],
) -> list[str]:
    """Build context string parts for a single result."""
    # Find which entities belong to this result (using relative path)
    result_entities: list[str] = []
    for eid in entities:
        if eid.startswith(rel_path + "::") or eid == result.chunk_id:
            result_entities.append(eid)

    if not result_entities:
        return []

    callers: list[str] = []
    tests: list[str] = []

    for eid in result_entities:
        for rel in entity_rels.get(eid, []):
            relationship = str(rel["relationship"])
            source = str(rel["source_entity"])
            target = str(rel["target_entity"])

            # Determine the "other" entity
            other = target if source == eid else source

            # Extract short name from entity ID
            short_name = other.split("::")[-1] if "::" in other else other

            if relationship == "tests" or "test" in other.lower():
                if short_name not in tests:
                    tests.append(short_name)
            elif relationship in ("calls", "imports", "inherits", "renders"):
                if short_name not in callers:
                    callers.append(short_name)

    parts: list[str] = []
    if callers:
        parts.append(f"Called by: {', '.join(callers[:3])}")
    if tests:
        parts.append(f"Tests: {', '.join(tests[:1])}")

    return parts
