#!/usr/bin/env python3
"""Counterfactual analysis: compute grep's marginal contribution.

For each escalated query, measures how many results came exclusively from
grep (not from semantic search). This answers: "Is grep augmentation finding
genuinely new files, or just duplicating semantic results?"

Usage:
    python3 scripts/counterfactual_analysis.py behavioral_data.json

Input format (behavioral_data.json):
    {
        "version": "V4.1",
        "queries": [
            {
                "test_id": "A1",
                "query": "subscription renewal processing",
                "intent": "code",
                "auto_escalated": true,
                "results": [
                    {"file_path": "ecomm/utils.py", "source": "semantic"},
                    {"file_path": "ecomm/tasks.py", "source": "grep"},
                    {"file_path": "ecomm/models.py", "source": "semantic"}
                ]
            },
            ...
        ]
    }

Output: Markdown report with per-query and aggregate marginal contribution stats.

The `source` field on each result indicates whether it came from "semantic"
search or "grep" augmentation. Results present in both are tagged "semantic"
(semantic is the primary source).
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class QueryAnalysis:
    test_id: str
    query: str
    intent: str
    total_results: int
    semantic_count: int
    grep_count: int
    grep_unique_files: set[str]
    semantic_files: set[str]
    marginal_contribution: float  # |grep_unique| / |total_results|


def analyze_query(entry: dict) -> QueryAnalysis:
    """Compute marginal contribution for a single escalated query."""
    results = entry.get("results", [])
    total = len(results)

    semantic_files: set[str] = set()
    grep_files: set[str] = set()
    semantic_count = 0
    grep_count = 0

    for r in results:
        fp = r["file_path"]
        source = r.get("source", "semantic")
        if source == "grep":
            grep_files.add(fp)
            grep_count += 1
        else:
            semantic_files.add(fp)
            semantic_count += 1

    grep_unique = grep_files - semantic_files
    marginal = len(grep_unique) / total if total > 0 else 0.0

    return QueryAnalysis(
        test_id=entry.get("test_id", "?"),
        query=entry.get("query", ""),
        intent=entry.get("intent", "unknown"),
        total_results=total,
        semantic_count=semantic_count,
        grep_count=grep_count,
        grep_unique_files=grep_unique,
        semantic_files=semantic_files,
        marginal_contribution=marginal,
    )


def compute_aggregate(analyses: list[QueryAnalysis]) -> dict:
    """Compute aggregate stats across all escalated queries."""
    if not analyses:
        return {
            "total_escalated": 0,
            "avg_marginal": 0.0,
            "pct_with_novel_files": 0.0,
            "advisory": "no escalated queries to analyze",
        }

    n = len(analyses)
    avg_marginal = sum(a.marginal_contribution for a in analyses) / n
    with_novel = sum(1 for a in analyses if len(a.grep_unique_files) > 0)
    pct_with_novel = with_novel / n * 100

    if avg_marginal < 0.10:
        advisory = "mostly noise — grep adds <10% novel files on average"
    elif avg_marginal > 0.50:
        advisory = "semantic genuinely incomplete — grep adds >50% novel files"
    else:
        advisory = "healthy range — grep provides meaningful augmentation"

    return {
        "total_escalated": n,
        "avg_marginal": avg_marginal,
        "pct_with_novel_files": pct_with_novel,
        "advisory": advisory,
    }


def format_report(
    version: str,
    analyses: list[QueryAnalysis],
    aggregate: dict,
    total_queries: int,
    escalation_rate: float,
) -> str:
    """Format the counterfactual analysis as a markdown report."""
    lines: list[str] = []
    lines.append(f"# {version} Counterfactual Analysis")
    lines.append("")
    lines.append(f"**Escalated queries:** {aggregate['total_escalated']}/{total_queries} "
                 f"({escalation_rate:.0%})")
    lines.append(f"**Avg marginal contribution:** {aggregate['avg_marginal']:.1%}")
    pct = aggregate["pct_with_novel_files"]
    lines.append(f"**Queries where grep found novel files:** {pct:.0f}%")
    lines.append(f"**Advisory:** {aggregate['advisory']}")
    lines.append("")

    if analyses:
        lines.append("## Per-Query Breakdown")
        lines.append("")
        lines.append("| Test | Intent | Total | Semantic | Grep | Grep-Unique | Marginal |")
        lines.append("|------|--------|-------|----------|------|-------------|----------|")
        for a in analyses:
            lines.append(
                f"| {a.test_id} | {a.intent} | {a.total_results} | "
                f"{a.semantic_count} | {a.grep_count} | "
                f"{len(a.grep_unique_files)} | {a.marginal_contribution:.1%} |"
            )
        lines.append("")

        # Queries where grep found nothing new
        zero_marginal = [a for a in analyses if len(a.grep_unique_files) == 0]
        if zero_marginal:
            lines.append("## Zero-Contribution Queries (grep added no novel files)")
            lines.append("")
            for a in zero_marginal:
                q_preview = a.query[:80] + "..." if len(a.query) > 80 else a.query
                lines.append(f"- **{a.test_id}:** `{q_preview}`")
            lines.append("")

    return "\n".join(lines)


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python3 scripts/counterfactual_analysis.py behavioral_data.json")
        print()
        print("See script docstring for input format.")
        sys.exit(1)

    data_path = Path(sys.argv[1])
    if not data_path.exists():
        print(f"Error: {data_path} not found")
        sys.exit(1)

    data = json.loads(data_path.read_text())
    version = data.get("version", "Unknown")
    queries = data.get("queries", [])

    total_queries = len(queries)
    escalated = [q for q in queries if q.get("auto_escalated", False)]
    escalation_rate = len(escalated) / total_queries if total_queries > 0 else 0.0

    analyses = [analyze_query(q) for q in escalated]
    aggregate = compute_aggregate(analyses)

    report = format_report(version, analyses, aggregate, total_queries, escalation_rate)
    print(report)

    # Write JSON output alongside input
    output_path = data_path.parent / "counterfactual_results.json"
    output = {
        "version": version,
        "total_queries": total_queries,
        "escalated_queries": len(escalated),
        "escalation_rate": round(escalation_rate, 4),
        "avg_marginal_contribution": round(aggregate["avg_marginal"], 4),
        "pct_queries_with_novel_files": round(aggregate["pct_with_novel_files"], 1),
        "advisory": aggregate["advisory"],
        "per_query": [
            {
                "test_id": a.test_id,
                "query": a.query,
                "intent": a.intent,
                "total_results": a.total_results,
                "semantic_count": a.semantic_count,
                "grep_count": a.grep_count,
                "grep_unique_count": len(a.grep_unique_files),
                "marginal_contribution": round(a.marginal_contribution, 4),
            }
            for a in analyses
        ],
    }
    output_path.write_text(json.dumps(output, indent=2) + "\n")
    print(f"\nJSON results written to {output_path}")


if __name__ == "__main__":
    main()
