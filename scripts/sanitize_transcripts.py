#!/usr/bin/env python3
"""Sanitize raw exploration transcripts for blind A/B scoring.

Applies mechanical text transformations to remove tool-identifying information:
1. Replace tool invocations with generic labels
2. Remove metadata fields from JSON-like content
3. Normalize "context" → "related"
4. Add "related": "" to grep results (ensure both tools have the field)
5. Randomly assign Alpha/Beta labels
6. Write sanitized files + mapping.json

Usage:
    python3 scripts/sanitize_transcripts.py <raw_dir> <output_dir> [--tests A1,A2,...]
"""

import json
import os
import random
import re
import sys
from pathlib import Path


def strip_common_leaks(text: str) -> str:
    """Remove tool-identifying patterns common to both transcript types."""
    # Strip inline relevance scores: (score 0.917), (score: 0.5), (relevance 0.8)
    text = re.sub(r'\s*\(score:?\s*[\d.]+\)', '', text)
    text = re.sub(r'\s*\(relevance:?\s*[\d.]+\)', '', text)

    # Strip intent/mode annotations: (intent detected as DEBUG → exhaustive mode)
    text = re.sub(r'\s*\(intent detected as[^)]+\)', '', text)

    # Strip (semantic search), (exhaustive), (semantic) from search headings
    text = re.sub(r'\s*\(semantic search\)', '', text)
    text = re.sub(r'\s*\(exhaustive\)', '', text)
    text = re.sub(r'\s*\(semantic\)', '', text)

    # Strip "semantic search" from prose (but keep "search")
    text = re.sub(r'\bsemantic search\b', 'search', text, flags=re.IGNORECASE)

    # Strip confidence values from prose: "low confidence (0.05)"
    text = re.sub(r'low confidence \([\d.]+\)', 'low confidence', text)
    text = re.sub(r'high confidence \([\d.]+\)', 'high confidence', text)
    text = re.sub(r'confidence \([\d.]+\)', 'confidence', text)

    # Strip "exhaustive search" when it refers to search mode (not natural usage)
    # Keep natural usage like "After an exhaustive search across..."
    text = re.sub(r'\bexhaustive mode\b', 'search mode', text)

    # Remove metadata fields from JSON blocks
    metadata_fields = [
        "score", "importance_score", "confidence", "confidence_label",
        "suggestion_type", "mode_used", "auto_escalated", "intent",
        "query_enhanced", "total_candidates", "chunk_type", "enriched",
        "collection", "source",
    ]
    for field in metadata_fields:
        text = re.sub(rf'\s*"{field}":\s*[^\n,]+,?\n', '\n', text)
        text = re.sub(rf"\s*'{field}':\s*[^\n,]+,?\n", '\n', text)

    return text


def sanitize_clew_transcript(text: str) -> str:
    """Sanitize a clew-tool transcript."""
    # Replace clew search commands
    text = re.sub(
        r'\*\*Query:\*\*\s*`clew search "([^"]+)"[^`]*`',
        r'search("\1")',
        text,
    )
    text = re.sub(
        r'`clew search "([^"]+)"[^`]*`',
        r'`search("\1")`',
        text,
    )
    text = re.sub(
        r'clew search "([^"]+)"[^"]*',
        r'search("\1")',
        text,
    )

    # Replace clew trace commands (quoted and unquoted arguments)
    text = re.sub(
        r'\*\*Query:\*\*\s*`clew trace "([^"]+)"[^`]*`',
        r'search("code related to \1")',
        text,
    )
    text = re.sub(
        r'`clew trace "([^"]+)"[^`]*`',
        r'`search("code related to \1")`',
        text,
    )
    text = re.sub(
        r'`clew trace (\w+)`',
        r'`search("code related to \1")`',
        text,
    )
    text = re.sub(
        r'clew trace "([^"]+)"[^"]*',
        r'search("code related to \1")',
        text,
    )
    text = re.sub(
        r'clew trace (\w+)',
        r'search("code related to \1")',
        text,
    )

    # Replace clew status
    text = re.sub(r'clew status[^\n]*', 'check_status()', text)

    # Replace grep commands used by clew agent
    text = re.sub(
        r'`?grep -[a-zA-Z]+ "([^"]+)"[^`\n]*`?',
        r'search("\1")',
        text,
    )
    text = re.sub(
        r'`?rg "([^"]+)"[^`\n]*`?',
        r'search("\1")',
        text,
    )

    # Normalize context → related
    text = text.replace("`context`", "`related`")
    text = text.replace("context field", "related field")
    text = text.replace('"context":', '"related":')
    text = text.replace("'context':", "'related':")

    # Remove references to specific tool names in prose
    # First handle "clew search for" (a prose usage, not a command)
    text = re.sub(r'\bclew search for\b', 'search for', text, flags=re.IGNORECASE)
    # Then handle remaining "clew" references
    text = re.sub(r'\bclew\b(?!\s*search|\s*trace)', 'the search tool', text, flags=re.IGNORECASE)
    text = re.sub(r'\bthe search tool index\b', 'the index', text)
    text = re.sub(r'\bthe search tool\s+search\b', 'search', text)

    # Normalize Read tool references
    text = re.sub(
        r'\*\*File:\*\*\s*`?(/[^`\n]+)`?\s*lines?\s*(\d+)-(\d+)',
        r'read("\1") lines \2-\3',
        text,
    )

    # Apply common leak stripping
    text = strip_common_leaks(text)

    return text


def sanitize_grep_transcript(text: str) -> str:
    """Sanitize a grep-tool transcript."""
    # Replace Grep tool invocations
    text = re.sub(
        r'Grep\(pattern="([^"]+)"[^)]*\)',
        r'search("\1")',
        text,
    )
    text = re.sub(
        r'Searched for `([^`]+)` across[^\n]*',
        r'search("\1")',
        text,
    )
    text = re.sub(
        r'Searched for\s+"([^"]+)"[^\n]*',
        r'search("\1")',
        text,
    )
    text = re.sub(
        r'`?grep -[a-zA-Z]+ "([^"]+)"[^`\n]*`?',
        r'search("\1")',
        text,
    )
    text = re.sub(
        r'`?rg "([^"]+)"[^`\n]*`?',
        r'search("\1")',
        text,
    )
    text = re.sub(
        r'Searched (?:all|the)[^.]+for[^.]+\.',
        lambda m: 'search("pattern")' if 'pattern' not in m.group() else m.group(),
        text,
    )

    # Replace Glob tool invocations
    text = re.sub(
        r'Glob\(pattern="([^"]+)"[^)]*\)',
        r'find_files("\1")',
        text,
    )
    text = re.sub(
        r'Used file glob[^.]+\.',
        'find_files("pattern")',
        text,
    )

    # Replace Read tool invocations
    text = re.sub(
        r'Read\(file_path="([^"]+)"[^)]*\)',
        r'read("\1")',
        text,
    )

    # Add "related": "" to results that don't have it
    # This is harder to do mechanically — we'll add a note and handle in review

    # Remove metadata fields from JSON blocks (same as clew)
    metadata_fields = [
        "score", "importance_score", "confidence", "confidence_label",
        "suggestion_type", "mode_used", "auto_escalated", "intent",
        "query_enhanced", "total_candidates", "chunk_type", "enriched",
        "collection", "source",
    ]
    for field in metadata_fields:
        text = re.sub(rf'\s*"{field}":\s*[^\n,]+,?\n', '\n', text)
        text = re.sub(rf"\s*'{field}':\s*[^\n,]+,?\n", '\n', text)

    # Remove references to tool identity in prose
    text = re.sub(r'\b[Rr]ipgrep\b', 'search', text)
    text = re.sub(r'\bgrep tool\b', 'search tool', text, flags=re.IGNORECASE)
    text = re.sub(r'\bpattern[- ]matching tools?\b', 'search tool', text, flags=re.IGNORECASE)

    # Normalize Read references
    text = re.sub(
        r'\*\*File:\*\*\s*`?(/[^`\n]+)`?\s*lines?\s*(\d+)-(\d+)',
        r'read("\1") lines \2-\3',
        text,
    )

    # Apply common leak stripping
    text = strip_common_leaks(text)

    return text


def process_test(
    test_id: str,
    raw_dir: Path,
    output_dir: Path,
    seed: int | None = None,
) -> dict:
    """Process a single test: sanitize both transcripts and assign labels."""
    clew_path = raw_dir / f"{test_id}-clew.md"
    grep_path = raw_dir / f"{test_id}-grep.md"

    if not clew_path.exists() or not grep_path.exists():
        print(f"  SKIP {test_id}: missing raw transcript(s)")
        return {}

    clew_text = clew_path.read_text()
    grep_text = grep_path.read_text()

    # Sanitize
    sanitized_clew = sanitize_clew_transcript(clew_text)
    sanitized_grep = sanitize_grep_transcript(grep_text)

    # Random Alpha/Beta assignment
    rng = random.Random(seed)
    if rng.random() < 0.5:
        alpha_text, alpha_tool = sanitized_clew, "clew"
        beta_text, beta_tool = sanitized_grep, "grep"
    else:
        alpha_text, alpha_tool = sanitized_grep, "grep"
        beta_text, beta_tool = sanitized_clew, "clew"

    # Write files
    (output_dir / f"{test_id}-Alpha.md").write_text(alpha_text)
    (output_dir / f"{test_id}-Beta.md").write_text(beta_text)

    mapping = {"Alpha": alpha_tool, "Beta": beta_tool}
    (output_dir / f"{test_id}-mapping.json").write_text(
        json.dumps(mapping, indent=2) + "\n"
    )

    print(f"  OK {test_id}: Alpha={alpha_tool}, Beta={beta_tool}")
    return {test_id: {"alpha": alpha_tool, "beta": beta_tool}}


def main():
    raw_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".clew-eval/v4/raw-transcripts")
    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(".clew-eval/v4/sanitized-transcripts")

    # Optional: specify which tests to process
    if len(sys.argv) > 3 and sys.argv[3] == "--tests":
        tests = sys.argv[4].split(",")
    else:
        # Discover all tests from raw transcripts
        tests = sorted(set(
            p.stem.rsplit("-", 1)[0]
            for p in raw_dir.glob("*-clew.md")
        ))

    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Sanitizing {len(tests)} tests: {', '.join(tests)}")
    print(f"Raw dir: {raw_dir}")
    print(f"Output dir: {output_dir}")
    print()

    # Use fixed seed for reproducibility
    master_seed = 20260221
    all_mappings = {}

    for i, test_id in enumerate(tests):
        result = process_test(test_id, raw_dir, output_dir, seed=master_seed + i)
        all_mappings.update(result)

    # Write consolidated mapping
    consolidated_path = output_dir / "mapping.json"
    consolidated_path.write_text(json.dumps(all_mappings, indent=2) + "\n")
    print(f"\nConsolidated mapping written to {consolidated_path}")
    print(f"Total tests sanitized: {len(all_mappings)}")


if __name__ == "__main__":
    main()
