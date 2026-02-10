"""Code relationship data model for structural analysis."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Relationship:
    """A directional relationship between two code entities."""

    source_entity: str  # "file_path::qualified_name"
    relationship: str  # imports|inherits|calls|decorates|renders|tests|calls_api
    target_entity: str  # "file_path::qualified_name" or "module::name" for external
    file_path: str  # source file where relationship was found
    confidence: str = "static"  # "static" (AST-provable) or "inferred" (heuristic)
