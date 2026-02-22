#!/usr/bin/env python3
"""Viability evaluation computation script.

Pre-registered mechanical aggregation for viability evaluation.
Reads scorer ratings, computes weighted averages, determines winners,
applies verdict thresholds. No agent judgment — pure arithmetic.

Usage:
    python3 scripts/viability_compute.py scores.json mapping.json \\
        [--behavioral behavioral.json] [--rubric R2] [--flip-rate 0.30]

Input format (scores.json):
    {
        "tests": {
            "A1": {
                "scorer_1": {
                    "alpha": {"discovery": 4, "precision": 3,
                              "completeness": 5, "relational": 4,
                              "confidence": 4},
                    "beta":  {"discovery": 3, "precision": 4,
                              "completeness": 4, "relational": 2,
                              "confidence": 3}
                },
                "scorer_2": { ... },
                "scorer_3": { ... }  // optional tiebreaker
            },
            ...
        }
    }

Mapping format (mapping.json):
    {"A1": {"alpha": "clew", "beta": "grep"}, ...}

Behavioral metrics format (optional, behavioral.json):
    {
        "total_queries": 45,
        "escalated_queries": 22,
        "feature_activations": {
            "auto_escalation": {"activated": 22, "total": 45},
            "enumeration_detection": {"activated": 0, "total": 45}
        },
        "feature_health_cards": [
            {"feature": "Auto-escalation", "metric": "escalation rate",
             "target": "15-40%", "actual": "49%", "status": "ABOVE_CEILING"}
        ]
    }
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass, field
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
TRACK_B_TESTS = {"E1", "E2", "E3", "E4"}

# Behavioral metrics advisory thresholds
ESCALATION_TARGET_LOW = 0.15
ESCALATION_TARGET_HIGH = 0.40
ESCALATION_CEILING = 0.50
ESCALATION_FLOOR = 0.05

# Stability analysis
NOISE_PROBABILITY_THRESHOLD = 0.30


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


@dataclass
class BehavioralMetrics:
    total_queries: int = 0
    escalated_queries: int = 0
    escalation_rate: float = 0.0
    escalation_advisory: str = ""
    feature_activations: dict[str, dict[str, int]] = field(default_factory=dict)
    feature_health_cards: list[dict] = field(default_factory=list)


@dataclass
class StabilityAnalysis:
    flip_rate: float = 0.0
    num_tests: int = 0
    win_margin: int = 0
    p_noise: float = 0.0
    confidence_flag: str = "CONFIDENT"


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


def parse_behavioral_metrics(data: dict) -> BehavioralMetrics:
    """Parse behavioral metrics from JSON input."""
    total = data.get("total_queries", 0)
    escalated = data.get("escalated_queries", 0)
    rate = escalated / total if total > 0 else 0.0

    if rate > ESCALATION_CEILING:
        advisory = f"ABOVE CEILING ({rate:.0%} > {ESCALATION_CEILING:.0%}) — effectively always-on"
    elif rate > ESCALATION_TARGET_HIGH:
        advisory = f"ABOVE TARGET ({rate:.0%} > {ESCALATION_TARGET_HIGH:.0%})"
    elif rate < ESCALATION_FLOOR:
        advisory = (f"BELOW FLOOR ({rate:.0%} < {ESCALATION_FLOOR:.0%})"
                    " — effectively never activates")
    elif rate < ESCALATION_TARGET_LOW:
        advisory = f"BELOW TARGET ({rate:.0%} < {ESCALATION_TARGET_LOW:.0%})"
    else:
        advisory = f"IN TARGET RANGE ({rate:.0%})"

    return BehavioralMetrics(
        total_queries=total,
        escalated_queries=escalated,
        escalation_rate=rate,
        escalation_advisory=advisory,
        feature_activations=data.get("feature_activations", {}),
        feature_health_cards=data.get("feature_health_cards", []),
    )


def compute_stability(
    results: list[TestResult],
    flip_rate: float,
) -> StabilityAnalysis:
    """Compute stability analysis using binomial noise model.

    Given a historical flip rate and observed win margin, estimate the
    probability that the margin arose from noise (random test flips).
    """
    n = len(results)
    clew_wins = sum(1 for r in results if r.winner == "clew")
    win_margin = abs(clew_wins - (n - clew_wins))

    if flip_rate <= 0 or n == 0:
        return StabilityAnalysis(
            flip_rate=flip_rate,
            num_tests=n,
            win_margin=win_margin,
            p_noise=0.0,
            confidence_flag="CONFIDENT",
        )

    # Model: each test has probability flip_rate of changing its winner.
    # Under noise, the number of flips X ~ Binomial(n, flip_rate).
    # Each flip randomly reassigns the winner with P(clew)=0.5.
    # P(noise) = P(|wins - n/2| >= observed_margin/2) under this model.
    #
    # Simplified: treat each test as a fair coin flip with probability
    # flip_rate of being "random". P(noise) is the probability that
    # fair coin flips produce the observed margin.
    # Using binomial CDF: P(X >= threshold) where X ~ Binom(n, 0.5)
    threshold = (n + win_margin) // 2  # minimum clew wins needed for this margin

    # Compute P(X >= threshold) using binomial PMF
    p_noise = 0.0
    for k in range(threshold, n + 1):
        # Binomial coefficient * p^k * (1-p)^(n-k), p=0.5
        binom_coeff = math.comb(n, k)
        p_noise += binom_coeff * (0.5 ** n)
    # Two-tailed (margin in either direction)
    p_noise *= 2
    p_noise = min(p_noise, 1.0)

    # Weight by flip rate: if flip_rate is low, less noise
    p_noise *= flip_rate / 0.5 if flip_rate < 0.5 else 1.0

    confidence_flag = "LOW CONFIDENCE" if p_noise > NOISE_PROBABILITY_THRESHOLD else "CONFIDENT"

    return StabilityAnalysis(
        flip_rate=flip_rate,
        num_tests=n,
        win_margin=win_margin,
        p_noise=round(p_noise, 4),
        confidence_flag=confidence_flag,
    )


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
    total_wins = track_a_wins + track_b_wins
    if (overall_avg >= TRACK_A_SHIP_AVG and total_wins >= 7
            and track_a_avg >= TRACK_A_SHIP_AVG):
        verdict = "Ship"
    elif overall_avg >= 3.30 and total_wins >= 6:
        verdict = "Iterate"
    else:
        verdict = "Kill"

    # Disagreement summary
    tests_with_disagreements = [r.test_id for r in results if r.disagreements]

    return {
        "verdict": verdict,
        "track_a": {
            "clew_avg": round(track_a_avg, 2),
            "grep_avg": (
                round(sum(r.grep_weighted for r in track_a) / len(track_a), 2)
                if track_a else 0
            ),
            "clew_wins": track_a_wins,
            "grep_wins": sum(1 for r in track_a if r.winner == "grep"),
            "ties": sum(1 for r in track_a if r.winner == "tie"),
            "ship_threshold": round(TRACK_A_SHIP_AVG, 2),
        },
        "track_b": {
            "clew_avg": round(track_b_avg, 2),
            "grep_avg": (
                round(sum(r.grep_weighted for r in track_b) / len(track_b), 2)
                if track_b else 0
            ),
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


def format_behavioral_metrics(metrics: BehavioralMetrics) -> str:
    """Format behavioral metrics as markdown."""
    lines: list[str] = []
    lines.append("## Behavioral Metrics (Advisory)")
    lines.append("")

    # Escalation rate
    lines.append("### Escalation Rate")
    lines.append(f"- Escalated queries: {metrics.escalated_queries}/{metrics.total_queries} "
                 f"({metrics.escalation_rate:.0%})")
    lines.append(f"- Target range: {ESCALATION_TARGET_LOW:.0%}-{ESCALATION_TARGET_HIGH:.0%}")
    lines.append(f"- **Advisory: {metrics.escalation_advisory}**")
    lines.append("")

    # Feature activations
    if metrics.feature_activations:
        lines.append("### Feature Activation Rates")
        lines.append("")
        lines.append("| Feature | Activated | Total | Rate |")
        lines.append("|---------|-----------|-------|------|")
        for name, data in metrics.feature_activations.items():
            activated = data.get("activated", 0)
            total = data.get("total", 0)
            rate = activated / total if total > 0 else 0.0
            flag = " (dead code)" if activated == 0 and total > 0 else ""
            lines.append(f"| {name} | {activated} | {total} | {rate:.0%}{flag} |")
        lines.append("")

    # Feature health cards
    if metrics.feature_health_cards:
        lines.append("### Feature Health Cards")
        lines.append("")
        lines.append("| Feature | Metric | Target | Actual | Status |")
        lines.append("|---------|--------|--------|--------|--------|")
        for card in metrics.feature_health_cards:
            lines.append(
                f"| {card['feature']} | {card['metric']} | {card['target']} | "
                f"{card['actual']} | {card['status']} |"
            )
        lines.append("")

    return "\n".join(lines)


def format_stability_analysis(stability: StabilityAnalysis) -> str:
    """Format stability analysis as markdown."""
    lines: list[str] = []
    lines.append("## Stability Analysis")
    lines.append("")
    lines.append(f"- Historical flip rate: {stability.flip_rate:.0%}")
    lines.append(f"- Number of tests: {stability.num_tests}")
    lines.append(f"- Observed win margin: {stability.win_margin}")
    lines.append(f"- P(noise): {stability.p_noise:.1%}")
    lines.append(f"- **Confidence: {stability.confidence_flag}**")
    if stability.confidence_flag == "LOW CONFIDENCE":
        lines.append(f"  - Win margin is within the noise floor (P(noise) > "
                     f"{NOISE_PROBABILITY_THRESHOLD:.0%})")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Viability evaluation computation — pre-registered mechanical aggregation."
    )
    parser.add_argument("scores", type=Path, help="Path to scores.json")
    parser.add_argument("mapping", type=Path, help="Path to mapping.json")
    parser.add_argument("--behavioral", type=Path, default=None,
                        help="Path to behavioral metrics JSON (optional)")
    parser.add_argument("--rubric", type=str, default="R1",
                        help="Rubric version identifier (default: R1)")
    parser.add_argument("--flip-rate", type=float, default=0.0,
                        help="Historical flip rate for stability analysis (0.0-1.0)")
    args = parser.parse_args()

    if not args.scores.exists():
        print(f"Error: {args.scores} not found")
        sys.exit(1)
    if not args.mapping.exists():
        print(f"Error: {args.mapping} not found")
        sys.exit(1)

    scores_data = json.loads(args.scores.read_text())
    mapping_data = json.loads(args.mapping.read_text())

    # Compute
    results = compute_all(scores_data, mapping_data)
    verdict_info = apply_verdicts(results)

    # Parse behavioral metrics if provided
    behavioral: BehavioralMetrics | None = None
    if args.behavioral and args.behavioral.exists():
        behavioral = parse_behavioral_metrics(json.loads(args.behavioral.read_text()))

    # Compute stability if flip rate provided
    stability: StabilityAnalysis | None = None
    if args.flip_rate > 0:
        stability = compute_stability(results, args.flip_rate)

    # Output header
    print("# Viability Computation Results")
    print()
    print(f"**Rubric Version:** {args.rubric}")
    verdict_line = f"**Verdict: {verdict_info['verdict']}**"
    if stability and stability.confidence_flag == "LOW CONFIDENCE":
        verdict_line += f" (LOW CONFIDENCE — P(noise) = {stability.p_noise:.1%})"
    print(verdict_line)
    print()

    # Track A summary
    ta = verdict_info["track_a"]
    print("## Track A (Regression)")
    print(f"- Clew avg: {ta['clew_avg']}/5.0 (Ship threshold: {ta['ship_threshold']})")
    print(f"- Grep avg: {ta['grep_avg']}/5.0")
    print(f"- Win/Loss: {ta['clew_wins']} clew / {ta['grep_wins']} grep / {ta['ties']} tie")
    print()

    # Track B summary
    tb = verdict_info["track_b"]
    print("## Track B (Feature)")
    print(f"- Clew avg: {tb['clew_avg']}/5.0")
    print(f"- Grep avg: {tb['grep_avg']}/5.0")
    print(f"- Win/Loss: {tb['clew_wins']} clew / {tb['grep_wins']} grep / {tb['ties']} tie")
    print()

    # Overall
    ov = verdict_info["overall"]
    print("## Overall")
    print(f"- Clew avg: {ov['clew_avg']}/5.0 (Ship threshold: {TRACK_A_SHIP_AVG:.2f})")
    print(f"- Grep avg: {ov['grep_avg']}/5.0")
    total_wins = ta["clew_wins"] + tb["clew_wins"]
    total_grep = ta["grep_wins"] + tb["grep_wins"]
    total_ties = ta["ties"] + tb["ties"]
    print(f"- Win/Loss: {total_wins} clew / {total_grep} grep / "
          f"{total_ties} tie (Ship threshold: 7/12)")
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

    # Behavioral metrics
    if behavioral:
        print(format_behavioral_metrics(behavioral))

    # Stability analysis
    if stability:
        print(format_stability_analysis(stability))

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
    json_output: dict = {
        "rubric_version": args.rubric,
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

    if behavioral:
        json_output["behavioral_metrics"] = {
            "escalation_rate": round(behavioral.escalation_rate, 4),
            "escalation_advisory": behavioral.escalation_advisory,
            "feature_activations": behavioral.feature_activations,
            "feature_health_cards": behavioral.feature_health_cards,
        }

    if stability:
        json_output["stability_analysis"] = {
            "flip_rate": stability.flip_rate,
            "win_margin": stability.win_margin,
            "p_noise": stability.p_noise,
            "confidence_flag": stability.confidence_flag,
        }

    json_path = args.scores.parent / "viability_results.json"
    json_path.write_text(json.dumps(json_output, indent=2) + "\n")
    print(f"JSON results written to {json_path}")


if __name__ == "__main__":
    main()
