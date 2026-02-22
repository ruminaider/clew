#!/usr/bin/env python3
"""Assemble individual scorer JSON files into consolidated scores.json.

Reads from .clew-eval/v4/scores/{TEST}-scorer{N}.json and produces
.clew-eval/v4/scores/scores.json in the format expected by viability_compute.py.

Usage:
    python3 scripts/assemble_scores.py
"""

import json
from pathlib import Path

SCORES_DIR = Path(".clew-eval/v4/scores")
TESTS = ["A1", "A2", "A3", "A4", "B1", "B2", "C1", "C2", "E1", "E2", "E3", "E4"]


def main() -> None:
    consolidated: dict = {"tests": {}}
    missing: list[str] = []

    for test_id in TESTS:
        test_scores: dict = {}

        for scorer_num in [1, 2, 3]:  # 3 = optional tiebreaker
            score_file = SCORES_DIR / f"{test_id}-scorer{scorer_num}.json"
            if not score_file.exists():
                if scorer_num <= 2:
                    missing.append(str(score_file))
                continue

            data = json.loads(score_file.read_text())
            scorer_key = f"scorer_{scorer_num}"
            test_scores[scorer_key] = {
                "alpha": data["alpha"],
                "beta": data["beta"],
            }

        if test_scores:
            consolidated["tests"][test_id] = test_scores

    # Report
    print(f"Assembled {len(consolidated['tests'])}/12 tests")
    for test_id in TESTS:
        if test_id in consolidated["tests"]:
            scorers = list(consolidated["tests"][test_id].keys())
            print(f"  {test_id}: {', '.join(scorers)}")
        else:
            print(f"  {test_id}: MISSING")

    if missing:
        print(f"\nMissing files ({len(missing)}):")
        for f in missing:
            print(f"  {f}")

    # Write consolidated
    output_path = SCORES_DIR / "scores.json"
    output_path.write_text(json.dumps(consolidated, indent=2) + "\n")
    print(f"\nWritten to {output_path}")


if __name__ == "__main__":
    main()
