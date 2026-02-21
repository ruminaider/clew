"""Peripheral surfacing: surface related files from the trace graph."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


def extract_entity_ids(
    results: list[Any],
    max_results: int = 3,
    relativize: Callable[[str], str] | None = None,
) -> tuple[list[str], set[str]]:
    """Extract entity identifiers and result file paths from search results.

    If relativize is provided, it converts absolute file paths to relative
    paths matching the relationship database format.
    """
    _rel = relativize or (lambda x: x)
    entities: list[str] = []
    result_files: set[str] = {r.file_path for r in results}

    for r in results[:max_results]:
        chunk_id = getattr(r, "chunk_id", "")
        if chunk_id:
            entities.append(chunk_id)
        # Also try file_path::class_name.function_name format
        rel_path = _rel(r.file_path)
        class_name = getattr(r, "class_name", "")
        func_name = getattr(r, "function_name", "")
        if class_name and func_name:
            entities.append(f"{rel_path}::{class_name}.{func_name}")
        elif func_name:
            entities.append(f"{rel_path}::{func_name}")
        elif class_name:
            entities.append(f"{rel_path}::{class_name}")

    return entities, result_files


def surface_peripherals(
    results: list[Any],
    cache: Any,
    max_files: int = 5,
) -> list[dict[str, str]]:
    """Surface related files from the trace graph for top search results.

    Extracts entity identifiers from top-3 results, batch traverses
    relationships, filters out files already in results, and categorizes.
    """
    if not results:
        return []

    entities, result_files = extract_entity_ids(results, max_results=3)

    if not entities:
        return []

    # Batch traverse relationships (single SQL query)
    try:
        relations = cache.traverse_relationships_batch(entities, max_depth=1)
    except Exception:
        logger.debug("Peripheral surfacing failed", exc_info=True)
        return []

    # Collect unique related files, excluding files already in results
    seen: dict[str, dict[str, str]] = {}  # file_path -> {relationship, entity}
    for rel in relations:
        # Determine the "other" file
        source = str(rel["source_entity"])
        target = str(rel["target_entity"])
        relationship = str(rel["relationship"])

        # Extract file paths from entities
        source_file = source.split("::")[0] if "::" in source else source
        target_file = target.split("::")[0] if "::" in target else target

        # Pick the file that's NOT in our results
        for candidate_file, entity in [(target_file, target), (source_file, source)]:
            if candidate_file not in result_files and candidate_file not in seen:
                # Categorize the relationship
                category = categorize_relationship(relationship, candidate_file)
                seen[candidate_file] = {
                    "file_path": candidate_file,
                    "relationship": category,
                    "entity": entity,
                }

    return list(seen.values())[:max_files]


def categorize_relationship(relationship: str, file_path: str) -> str:
    """Categorize a relationship for display."""
    # Check file path patterns first
    file_lower = file_path.lower()
    if "test" in file_lower:
        return "tests"
    if "admin" in file_lower:
        return "admin"
    if "constants" in file_lower or "config" in file_lower:
        return "config"
    if "script" in file_lower:
        return "scripts"

    # Fall back to relationship type
    return relationship
