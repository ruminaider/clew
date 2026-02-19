#!/usr/bin/env python3
"""Viability evaluation computation script.

Pre-registered mechanical aggregation for V3.0 viability evaluation.
Reads scorer ratings, computes weighted averages, determines winners,
applies verdict thresholds. No agent judgment — pure arithmetic.

Usage:
    python3 scripts/viability_compute.py scores.json mapping.json

Input format (scores.json):
    {
        "tests": {
            "A1": {
                "scorer_1": {
                    "alpha": {"discovery": 4, "precision": 3, "completeness": 5, "relational": 4, "confidence": 4},
                    "beta":  {"discovery": 3, "precision": 4, "completeness": 4, "relational": 2, "confidence": 3}
                },
                "scorer_2": { ... },
                "scorer_3": { ... }  // optional tiebreaker
            },
            ...
        }
    }

Mapping format (mapping.json):
    {"A1": {"alpha": "clew", "beta": "grep"}, ...}
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

# Pre-registered weights (frozen — do not change after evaluation starts)
WEIGHTS = {
    "discovery": 0.30,
    "precision": 0.25,
    "completeness": 0.20,
    "relational": 0.15,
    "confidence": 0.10,
}

DIMENSIONS = list(WEIGHTS.keys())

# Pre-registered thresholds
V23_SCORE = 3.96
REGRESSION_BUFFER = 0.30
TRACK_A_SHIP_AVG = max(3.50, V23_SCORE - REGRESSION_BUFFER)  # 3.66

# Track assignments
TRACK_A_TESTS = {"A1", "A2", "A3", "A4", "B1", "B2", "C1", "C2"}
TRACK_B_TESTS = {"D1", "D2", "D3", "D4"}


@dataclass
class TestResult:
    test_id: str
    track: str
    clew_scores: dict[str, float]  # dimension → averaged score
    grep_scores: dict[str, float]
    clew_weighted: float
    grep_weighted: float
    winner: str
    disagreements: list[str]  # dimensions with >1 point scorer disagreement


def compute_weighted(scores: dict[str, float]) -> float:
    """Compute weighted average from dimension scores."""
    return sum(scores[dim] * WEIGHTS[dim] for dim in DIMENSIONS)


def average_scorer_ratings(
    scorers: dict[str, dict[str, dict[str, int]]],
    agent_label: str,
) -> tuple[dict[str, float], list[str]]:
    """Average ratings across scorers for one agent, detect disagreements.

    Returns (averaged_scores, list_of_disagreement_dimensions).
    """
    all_ratings: dict[str, list[int]] = {dim: [] for dim in DIMENSIONS}

    for scorer_data in scorers.values():
        agent_data = scorer_data[agent_label]
        for dim in DIMENSIONS:
            all_ratings[dim].append(agent_data[dim])

    # Use median if 3 scorers (tiebreaker), mean if 2
    averaged: dict[str, float] = {}
    disagreements: list[str] = []

    for dim in DIMENSIONS:
        ratings = all_ratings[dim]
        if len(ratings) == 3:
            # Median of 3
            averaged[dim] = float(sorted(ratings)[1])
        elif len(ratings) == 2:
            averaged[dim] = sum(ratings) / len(ratings)
        else:
            averaged[dim] = float(ratings[0])

        # Check for >1 point disagreement (between first 2 scorers)
        if len(ratings) >= 2 and abs(ratings[0] - ratings[1]) > 1:
            disagreements.append(dim)

    return averaged, disagreements


def determine_winner(clew_weighted: float, grep_weighted: float,
                     clew_completeness: float, grep_completeness: float) -> str:
    """Determine winner per pre-registered formula."""
    if clew_weighted > grep_weighted:
        return "clew"
    elif grep_weighted > clew_weighted:
        return "grep"
    else:
        # Tiebreaker: higher completeness
        if clew_completeness > grep_completeness:
            return "clew"
        elif grep_completeness > clew_completeness:
            return "grep"
        else:
            return "tie"


def compute_all(scores_data: dict, mapping_data: dict) -> list[TestResult]:
    """Compute results for all tests."""
    results: list[TestResult] = []

    for test_id, scorers in scores_data["tests"].items():
        test_mapping = mapping_data[test_id]

        # Determine which label is clew and which is grep
        if test_mapping["alpha"] == "clew":
            clew_label, grep_label = "alpha", "beta"
        else:
            clew_label, grep_label = "beta", "alpha"

        # Average scores across scorers
        clew_scores, clew_disagree = average_scorer_ratings(scorers, clew_label)
        grep_scores, grep_disagree = average_scorer_ratings(scorers, grep_label)

        # Compute weighted averages
        clew_weighted = compute_weighted(clew_scores)
        grep_weighted = compute_weighted(grep_scores)

        # Determine winner
        winner = determine_winner(
            clew_weighted, grep_weighted,
            clew_scores["completeness"], grep_scores["completeness"],
        )

        # Track assignment
        track = "A" if test_id in TRACK_A_TESTS else "B"

        # Merge disagreements
        all_disagreements = []
        for dim in clew_disagree:
            all_disagreements.append(f"clew/{dim}")
        for dim in grep_disagree:
            all_disagreements.append(f"grep/{dim}")

        results.append(TestResult(
            test_id=test_id,
            track=track,
            clew_scores=clew_scores,
            grep_scores=grep_scores,
            clew_weighted=clew_weighted,
            grep_weighted=grep_weighted,
            winner=winner,
            disagreements=all_disagreements,
        ))

    return results


def apply_verdicts(results: list[TestResult]) -> dict:
    """Apply pre-registered verdict thresholds."""
    track_a = [r for r in results if r.track == "A"]
    track_b = [r for r in results if r.track == "B"]

    track_a_avg = sum(r.clew_weighted for r in track_a) / len(track_a) if track_a else 0
    track_a_wins = sum(1 for r in track_a if r.winner == "clew")

    track_b_avg = sum(r.clew_weighted for r in track_b) / len(track_b) if track_b else 0
    track_b_wins = sum(1 for r in track_b if r.winner == "clew")

    overall_avg = sum(r.clew_weighted for r in results) / len(results) if results else 0
    grep_avg = sum(r.grep_weighted for r in results) / len(results) if results else 0

    # Verdict logic (pre-registered, frozen)
    if (track_a_avg >= TRACK_A_SHIP_AVG and track_a_wins >= 5
            and track_b_avg >= 3.50 and track_b_wins >= 3):
        verdict = "Ship (Improved)"
    elif (track_a_avg >= TRACK_A_SHIP_AVG and track_a_wins >= 5
            and track_b_avg >= 3.00 and track_b_wins >= 2):
        verdict = "Ship (Maintained)"
    elif track_a_avg >= 3.00 and track_a_wins >= 4:
        verdict = "Iterate"
    else:
        verdict = "Kill"

    # Disagreement summary
    tests_with_disagreements = [r.test_id for r in results if r.disagreements]

    return {
        "verdict": verdict,
        "track_a": {
            "clew_avg": round(track_a_avg, 2),
            "grep_avg": round(sum(r.grep_weighted for r in track_a) / len(track_a), 2) if track_a else 0,
            "clew_wins": track_a_wins,
            "grep_wins": sum(1 for r in track_a if r.winner == "grep"),
            "ties": sum(1 for r in track_a if r.winner == "tie"),
            "ship_threshold": round(TRACK_A_SHIP_AVG, 2),
        },
        "track_b": {
            "clew_avg": round(track_b_avg, 2),
            "grep_avg": round(sum(r.grep_weighted for r in track_b) / len(track_b), 2) if track_b else 0,
            "clew_wins": track_b_wins,
            "grep_wins": sum(1 for r in track_b if r.winner == "grep"),
            "ties": sum(1 for r in track_b if r.winner == "tie"),
        },
        "overall": {
            "clew_avg": round(overall_avg, 2),
            "grep_avg": round(grep_avg, 2),
            "total_tests": len(results),
        },
        "disagreements": {
            "tests_with_disagreements": tests_with_disagreements,
            "needs_tiebreaker": len(tests_with_disagreements) > 0,
        },
    }


def format_results_table(results: list[TestResult]) -> str:
    """Format results as a markdown table."""
    lines = [
        "| Test | Track | Clew | Grep | Winner | Disagreements |",
        "|------|-------|------|------|--------|---------------|",
    ]
    for r in sorted(results, key=lambda x: x.test_id):
        disagree = ", ".join(r.disagreements) if r.disagreements else "—"
        lines.append(
            f"| {r.test_id} | {r.track} | {r.clew_weighted:.2f} | "
            f"{r.grep_weighted:.2f} | {r.winner.upper()} | {disagree} |"
        )
    return "\n".join(lines)


def format_dimension_table(results: list[TestResult], tool: str) -> str:
    """Format per-test dimension scores for one tool."""
    lines = [
        f"**{tool.title()}:**",
        "",
        "| Test | Discovery | Precision | Completeness | Relational | Confidence | Weighted |",
        "|------|-----------|-----------|--------------|------------|------------|----------|",
    ]
    for r in sorted(results, key=lambda x: x.test_id):
        scores = r.clew_scores if tool == "clew" else r.grep_scores
        weighted = r.clew_weighted if tool == "clew" else r.grep_weighted
        lines.append(
            f"| {r.test_id} | {scores['discovery']:.1f} | {scores['precision']:.1f} | "
            f"{scores['completeness']:.1f} | {scores['relational']:.1f} | "
            f"{scores['confidence']:.1f} | {weighted:.2f} |"
        )

    # Averages
    all_scores = [r.clew_scores if tool == "clew" else r.grep_scores for r in results]
    all_weighted = [r.clew_weighted if tool == "clew" else r.grep_weighted for r in results]
    n = len(results)
    if n > 0:
        avg_line = "| **Avg** |"
        for dim in DIMENSIONS:
            avg = sum(s[dim] for s in all_scores) / n
            avg_line += f" **{avg:.2f}** |"
        avg_line += f" **{sum(all_weighted) / n:.2f}** |"
        lines.append(avg_line)

    return "\n".join(lines)


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: python3 scripts/viability_compute.py scores.json mapping.json")
        print()
        print("See script docstring for input format.")
        sys.exit(1)

    scores_path = Path(sys.argv[1])
    mapping_path = Path(sys.argv[2])

    if not scores_path.exists():
        print(f"Error: {scores_path} not found")
        sys.exit(1)
    if not mapping_path.exists():
        print(f"Error: {mapping_path} not found")
        sys.exit(1)

    scores_data = json.loads(scores_path.read_text())
    mapping_data = json.loads(mapping_path.read_text())

    # Compute
    results = compute_all(scores_data, mapping_data)
    verdict_info = apply_verdicts(results)

    # Output
    print(f"# V3.0 Viability Computation Results")
    print()
    print(f"**Verdict: {verdict_info['verdict']}**")
    print()

    # Track A summary
    ta = verdict_info["track_a"]
    print(f"## Track A (Regression)")
    print(f"- Clew avg: {ta['clew_avg']}/5.0 (Ship threshold: {ta['ship_threshold']})")
    print(f"- Grep avg: {ta['grep_avg']}/5.0")
    print(f"- Win/Loss: {ta['clew_wins']} clew / {ta['grep_wins']} grep / {ta['ties']} tie")
    print()

    # Track B summary
    tb = verdict_info["track_b"]
    print(f"## Track B (Modes)")
    print(f"- Clew avg: {tb['clew_avg']}/5.0")
    print(f"- Grep avg: {tb['grep_avg']}/5.0")
    print(f"- Win/Loss: {tb['clew_wins']} clew / {tb['grep_wins']} grep / {tb['ties']} tie")
    print()

    # Overall
    ov = verdict_info["overall"]
    print(f"## Overall")
    print(f"- Clew avg: {ov['clew_avg']}/5.0")
    print(f"- Grep avg: {ov['grep_avg']}/5.0")
    print()

    # Results table
    print("## Per-Test Results")
    print()
    print(format_results_table(results))
    print()

    # Dimension tables
    print("## Per-Test Dimension Scores")
    print()
    print(format_dimension_table(results, "clew"))
    print()
    print(format_dimension_table(results, "grep"))
    print()

    # Disagreements
    dis = verdict_info["disagreements"]
    if dis["needs_tiebreaker"]:
        print("## Scorer Disagreements (need tiebreaker)")
        print()
        for r in results:
            if r.disagreements:
                print(f"- **{r.test_id}:** {', '.join(r.disagreements)}")
        print()
    else:
        print("## Scorer Disagreements")
        print()
        print("No disagreements >1 point detected. No tiebreakers needed.")
        print()

    # JSON output for downstream processing
    json_output = {
        "verdict": verdict_info,
        "per_test": [
            {
                "test_id": r.test_id,
                "track": r.track,
                "clew_weighted": round(r.clew_weighted, 2),
                "grep_weighted": round(r.grep_weighted, 2),
                "winner": r.winner,
                "clew_scores": {k: round(v, 2) for k, v in r.clew_scores.items()},
                "grep_scores": {k: round(v, 2) for k, v in r.grep_scores.items()},
                "disagreements": r.disagreements,
            }
            for r in sorted(results, key=lambda x: x.test_id)
        ],
    }

    json_path = scores_path.parent / "viability_results.json"
    json_path.write_text(json.dumps(json_output, indent=2) + "\n")
    print(f"JSON results written to {json_path}")


if __name__ == "__main__":
    main()
