#!/usr/bin/env python3
"""Analyze query telemetry from JSONL log.

Reads .clew/query_telemetry.jsonl and produces summary statistics:
- Total queries
- Intent distribution
- Confidence distribution
- Average results per query
- Mode distribution (semantic vs exhaustive)
- Escalation candidates (low confidence queries)

Usage:
    python3 scripts/analyze_telemetry.py [path/to/query_telemetry.jsonl]

If no path is provided, looks for .clew/query_telemetry.jsonl in the current
directory or git root.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path


def _find_telemetry_file() -> Path:
    """Locate the telemetry JSONL file."""
    # Try git root first
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            candidate = Path(result.stdout.strip()) / ".clew" / "query_telemetry.jsonl"
            if candidate.exists():
                return candidate
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Try CWD
    candidate = Path(".clew") / "query_telemetry.jsonl"
    if candidate.exists():
        return candidate

    print("Error: No telemetry file found.")
    print("Expected at: .clew/query_telemetry.jsonl")
    print("Run some searches first to generate telemetry data.")
    sys.exit(1)


def _load_events(path: Path) -> list[dict[str, object]]:
    """Load JSONL events from file."""
    events: list[dict[str, object]] = []
    with open(path) as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                print(f"Warning: Skipping malformed line {line_num}")
    return events


def _format_distribution(counter: Counter[str], total: int) -> str:
    """Format a counter as a text bar chart."""
    lines: list[str] = []
    max_label = max(len(k) for k in counter) if counter else 0
    for label, count in counter.most_common():
        pct = (count / total) * 100 if total > 0 else 0
        bar = "#" * int(pct / 2)
        lines.append(f"  {label:<{max_label}}  {count:>4}  ({pct:5.1f}%)  {bar}")
    return "\n".join(lines)


def analyze(path: Path) -> None:
    """Run analysis and print report."""
    events = _load_events(path)
    total = len(events)

    if total == 0:
        print("No telemetry events found.")
        return

    print(f"Query Telemetry Analysis: {path}")
    print("=" * 60)
    print(f"\nTotal queries: {total}")

    # Intent distribution
    intents: Counter[str] = Counter()
    for e in events:
        intents[str(e.get("intent", "unknown"))] += 1
    print(f"\nIntent distribution:")
    print(_format_distribution(intents, total))

    # Confidence distribution
    confidences: Counter[str] = Counter()
    for e in events:
        confidences[str(e.get("confidence_label", "unknown"))] += 1
    print(f"\nConfidence distribution:")
    print(_format_distribution(confidences, total))

    # Mode distribution
    modes: Counter[str] = Counter()
    for e in events:
        modes[str(e.get("mode_used", "unknown"))] += 1
    print(f"\nMode distribution:")
    print(_format_distribution(modes, total))

    # Rerank distribution
    reranked_count = sum(1 for e in events if e.get("reranked") is True)
    not_reranked = total - reranked_count
    print(f"\nRerank usage:")
    print(f"  reranked      {reranked_count:>4}  ({reranked_count / total * 100:5.1f}%)")
    print(f"  not reranked  {not_reranked:>4}  ({not_reranked / total * 100:5.1f}%)")

    # Average results per query
    result_counts = [int(e.get("result_count", 0)) for e in events]
    avg_results = sum(result_counts) / total
    print(f"\nAverage results per query: {avg_results:.1f}")

    # Average top score
    top_scores = [float(e.get("top_score", 0)) for e in events]
    avg_top = sum(top_scores) / total
    print(f"Average top score: {avg_top:.4f}")

    # Average Z-score
    z_scores = [float(e.get("z_score", 0)) for e in events]
    avg_z = sum(z_scores) / total
    print(f"Average Z-score: {avg_z:.4f}")

    # Escalation candidates (low confidence)
    low_conf = [e for e in events if e.get("confidence_label") == "low"]
    if low_conf:
        print(f"\nEscalation candidates (low confidence): {len(low_conf)}/{total}")
        print(f"  ({len(low_conf) / total * 100:.1f}% of queries)")
        low_z = [float(e.get("z_score", 0)) for e in low_conf]
        print(f"  Average Z-score: {sum(low_z) / len(low_z):.4f}")
        low_results = [int(e.get("result_count", 0)) for e in low_conf]
        print(f"  Average result count: {sum(low_results) / len(low_conf):.1f}")
    else:
        print("\nNo low-confidence queries found (0 escalation candidates).")


def main() -> None:
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
        if not path.exists():
            print(f"Error: File not found: {path}")
            sys.exit(1)
    else:
        path = _find_telemetry_file()

    analyze(path)


if __name__ == "__main__":
    main()
