"""Importance scoring based on inbound relationship edge counts.

Computes per-file importance scores at index time. Scores are stored
in Qdrant payload for search-time boosting. The search pipeline reads
importance_score from payload — it never imports this module.
"""

from __future__ import annotations


def compute_importance_scores(
    relationship_pairs: list[tuple[str, str]],
) -> dict[str, float]:
    """Compute file importance from inbound edge count.

    Args:
        relationship_pairs: List of (source_entity, target_entity) pairs
            from the code_relationships table.

    Returns:
        Dict mapping file_path -> importance_score (0.0-1.0).
        The file with the most inbound edges gets score 1.0.
    """
    inbound_counts: dict[str, int] = {}
    for _source, target in relationship_pairs:
        file_path = target.split("::")[0] if "::" in target else target
        inbound_counts[file_path] = inbound_counts.get(file_path, 0) + 1

    if not inbound_counts:
        return {}

    max_count = max(inbound_counts.values())
    return {path: count / max_count for path, count in inbound_counts.items()}
