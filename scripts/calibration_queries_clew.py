#!/usr/bin/env python3
"""V4 confidence threshold calibration script — clew codebase.

Parallel to calibration_queries.py (Evvy-domain), this runs 30 queries
specific to the clew codebase to validate threshold portability.

Categories:
  A: Semantic/Discovery (10) — grep should NOT trigger
  B: Location/Identifier (8) — grep should NOT trigger
  C: Enumeration (7) — grep SHOULD trigger via intent
  D: Ambiguous/Borderline (5) — grep MIGHT help (calibration signal)

Usage:
    python3 scripts/calibration_queries_clew.py /path/to/clew [--output path]

Outputs: .clew-eval/v4.3-beta/calibration_clew.json
"""

from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

# Clew-domain calibration queries organized by category
QUERIES: dict[str, list[dict[str, str]]] = {
    "A_semantic_discovery": [
        {"id": "A01", "query": "how does the search pipeline handle query enhancement"},
        {"id": "A02", "query": "explain the reranking skip conditions"},
        {"id": "A03", "query": "what happens when confidence is low during search"},
        {"id": "A04", "query": "how are code relationships extracted during indexing"},
        {"id": "A05", "query": "describe the hybrid search fusion strategy"},
        {"id": "A06", "query": "how does the MCP server format search results"},
        {"id": "A07", "query": "explain the change detection logic for incremental indexing"},
        {"id": "A08", "query": "how are test files demoted in search results"},
        {"id": "A09", "query": "what is the query intent classification logic"},
        {"id": "A10", "query": "how does the chunker handle different programming languages"},
    ],
    "B_location_identifier": [
        {"id": "B01", "query": "SearchEngine"},
        {"id": "B02", "query": "_should_post_hoc_grep"},
        {"id": "B03", "query": "where is the QdrantManager defined"},
        {"id": "B04", "query": "find the SearchConfig model"},
        {"id": "B05", "query": "locate the tree-sitter parser setup"},
        {"id": "B06", "query": "where is build_qdrant_filter"},
        {"id": "B07", "query": "CacheDB"},
        {"id": "B08", "query": "find the MCP search tool handler"},
    ],
    "C_enumeration": [
        {"id": "C01", "query": "find all ABC base classes in the codebase"},
        {"id": "C02", "query": "list all Pydantic models with Field validators"},
        {"id": "C03", "query": "find all async functions"},
        {"id": "C04", "query": "list all files that import from clew.models"},
        {"id": "C05", "query": "find all pytest fixtures"},
        {"id": "C06", "query": "enumerate all dataclass definitions"},
        {"id": "C07", "query": "find all exception classes"},
    ],
    "D_ambiguous_borderline": [
        {"id": "D01", "query": "code that handles embedding failures"},
        {"id": "D02", "query": "all places where scores are modified or boosted"},
        {"id": "D03", "query": "configuration for search pipeline thresholds"},
        {"id": "D04", "query": "how are file paths resolved across the codebase"},
        {"id": "D05", "query": "code that validates user input"},
    ],
}


@dataclass
class QueryResult:
    """Captured metrics for a single calibration query."""

    query_id: str
    category: str
    query: str
    intent: str
    confidence: float
    confidence_label: str
    suggestion_type: str
    mode_used: str
    auto_escalated: bool
    total_candidates: int
    num_results: int
    was_reranked: bool
    top_scores: list[float]
    score_gap_1_2: float | None
    grep_result_count: int
    grep_should_trigger: bool  # expected behavior


async def run_calibration(project_root: Path, output_path: Path) -> list[QueryResult]:
    """Run all 30 calibration queries and capture metrics."""
    from clew.factory import create_components
    from clew.search.models import SearchRequest

    # Wire up the full search pipeline
    components = create_components(project_root=project_root)
    engine = components.search_engine

    results: list[QueryResult] = []

    for category, queries in QUERIES.items():
        for q in queries:
            request = SearchRequest(
                query=q["query"],
                collection="code",
                limit=10,
            )

            response = await engine.search(request)

            # Determine if reranking occurred by checking if scores look reranked
            # (reranked scores are 0-1 calibrated; RRF scores are small ~0.01-0.1)
            was_reranked = bool(
                response.results
                and response.results[0].score > 0.2
            )

            top_scores = [r.score for r in response.results[:5]]
            score_gap = None
            if len(response.results) >= 2:
                score_gap = response.results[0].score - response.results[1].score

            grep_count = sum(1 for r in response.results if r.source == "grep")

            # Expected behavior
            grep_should = category in ("C_enumeration",)
            # D category: ambiguous -- grep might help
            if category == "D_ambiguous_borderline":
                grep_should = True  # mark as "should consider"

            result = QueryResult(
                query_id=q["id"],
                category=category,
                query=q["query"],
                intent=response.intent.value,
                confidence=response.confidence,
                confidence_label=response.confidence_label,
                suggestion_type=response.suggestion_type.value,
                mode_used=response.mode_used,
                auto_escalated=response.auto_escalated,
                total_candidates=response.total_candidates,
                num_results=len(response.results),
                was_reranked=was_reranked,
                top_scores=top_scores,
                score_gap_1_2=score_gap,
                grep_result_count=grep_count,
                grep_should_trigger=grep_should,
            )
            results.append(result)

            # Progress
            label = result.confidence_label.upper()
            esc = "ESCALATED" if result.auto_escalated else ""
            print(
                f"  {q['id']:4s} [{label:6s}] conf={result.confidence:.4f} "
                f"intent={result.intent:12s} mode={result.mode_used:10s} "
                f"cands={result.total_candidates:3d} {esc}"
            )

    # Write raw results
    output_path.parent.mkdir(parents=True, exist_ok=True)
    serializable = [asdict(r) for r in results]
    output_path.write_text(json.dumps(serializable, indent=2) + "\n")
    print(f"\nResults written to {output_path}")

    # Summary
    print("\n--- Summary ---")
    for cat in QUERIES:
        cat_results = [r for r in results if r.category == cat]
        cat_confs = [r.confidence for r in cat_results]
        escalated = sum(1 for r in cat_results if r.auto_escalated)
        low = sum(1 for r in cat_results if r.confidence_label == "low")
        med = sum(1 for r in cat_results if r.confidence_label == "medium")
        high = sum(1 for r in cat_results if r.confidence_label == "high")
        enum_intent = sum(1 for r in cat_results if r.intent == "enumeration")
        avg_conf = sum(cat_confs) / len(cat_confs) if cat_confs else 0
        print(
            f"  {cat:30s}: avg_conf={avg_conf:.4f} "
            f"H/M/L={high}/{med}/{low} "
            f"escalated={escalated}/{len(cat_results)} "
            f"ENUM={enum_intent}"
        )

    # Overall escalation rate
    non_enum = [r for r in results if r.intent != "enumeration"]
    non_enum_escalated = sum(1 for r in non_enum if r.auto_escalated)
    print(
        f"\n  Non-ENUMERATION escalation: {non_enum_escalated}/{len(non_enum)} "
        f"({non_enum_escalated/len(non_enum)*100:.1f}%)" if non_enum else ""
    )

    all_escalated = sum(1 for r in results if r.auto_escalated)
    print(f"  Total escalation: {all_escalated}/{len(results)}")

    return results


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/calibration_queries_clew.py /path/to/clew [--output path]")
        sys.exit(1)

    project_root = Path(sys.argv[1])
    if not project_root.exists():
        print(f"Error: {project_root} not found")
        sys.exit(1)

    # Default output path
    output_path = Path(".clew-eval/v4.3-beta/calibration_clew.json")
    if "--output" in sys.argv:
        idx = sys.argv.index("--output")
        if idx + 1 < len(sys.argv):
            output_path = Path(sys.argv[idx + 1])

    print(f"Running clew-domain calibration against {project_root}")
    print(f"Output: {output_path}\n")

    asyncio.run(run_calibration(project_root, output_path))


if __name__ == "__main__":
    main()
