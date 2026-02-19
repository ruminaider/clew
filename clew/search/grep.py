"""Grep integration for exhaustive search mode.

Provides pattern generation from search queries and results,
ripgrep execution with timeout and error handling, and
a search_with_grep() orchestration function used by both MCP and CLI.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from clew.search.engine import SearchEngine
    from clew.search.models import QueryIntent, SearchRequest, SearchResponse, SearchResult

logger = logging.getLogger(__name__)


@dataclass
class GrepResult:
    """A single grep match from ripgrep."""

    file_path: str
    line_number: int
    line_content: str
    pattern_matched: str


# Framework-specific pattern mappings for common search terms
FRAMEWORK_PATTERNS: dict[str, list[str]] = {
    "url": [r"urlpatterns", r"path\(", r"re_path\(", r"@app\.route"],
    "api": [r"@api_view", r"@action", r"fetch\(", r"axios\.", r"@router\."],
    "model": [r"class\s+\w+\(.*Model\)", r"models\.\w+Field"],
    "view": [r"class\s+\w+\(.*View\)", r"def\s+\w+\(request"],
    "test": [r"def test_", r"class Test", r"@pytest\."],
    "middleware": [r"class\s+\w+Middleware", r"process_request", r"process_response"],
    "serializer": [r"class\s+\w+Serializer", r"serializers\.\w+Field"],
}

# Words too short or common to be useful as grep patterns
_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "in",
        "of",
        "to",
        "for",
        "is",
        "it",
        "on",
        "at",
        "by",
        "and",
        "or",
        "not",
        "with",
        "from",
        "as",
        "are",
        "was",
        "be",
        "has",
        "had",
        "do",
        "does",
        "did",
        "all",
        "how",
        "what",
        "where",
        "when",
        "why",
        "who",
        "which",
        "find",
        "show",
        "get",
        "set",
        "use",
        "that",
        "this",
        "can",
        "will",
        "code",
        "file",
        "function",
        "class",
        "method",
        "def",
        "import",
    }
)

_CAMEL_CASE_RE = re.compile(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
_IDENTIFIER_RE = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]*")

_MAX_PATTERNS = 10


def _split_identifier(term: str) -> list[str]:
    """Split camelCase and snake_case into component words."""
    # Split snake_case
    parts = term.split("_")
    # Split camelCase within each part
    result: list[str] = []
    for part in parts:
        if part:
            result.extend(_CAMEL_CASE_RE.sub("_", part).split("_"))
    return [p.lower() for p in result if p]


def generate_grep_patterns(
    query: str,
    results: list[SearchResult],
    intent: QueryIntent | None = None,
) -> list[str]:
    """Generate ripgrep-compatible regex patterns from query and results.

    Two sources:
    1. Query-derived: identifiers and framework keywords from the query
    2. Result-derived: function/class names from top search results
    """
    patterns: list[str] = []

    # 1. Query-derived patterns
    query_lower = query.lower()

    # Check framework pattern mappings
    for keyword, fw_patterns in FRAMEWORK_PATTERNS.items():
        if keyword in query_lower:
            patterns.extend(fw_patterns)

    # Extract identifiers from query
    identifiers = _IDENTIFIER_RE.findall(query)
    for ident in identifiers:
        # Skip stop words and very short terms
        if ident.lower() in _STOP_WORDS or len(ident) < 3:
            continue
        # If it looks like a specific identifier (has caps or underscores), use as-is
        if "_" in ident or any(c.isupper() for c in ident[1:]):
            patterns.append(re.escape(ident))
        else:
            # Generic word: only add if it's long enough to be meaningful
            if len(ident) >= 4:
                patterns.append(ident)

    # 2. Result-derived patterns
    for result in results[:5]:
        if result.function_name and result.function_name not in _STOP_WORDS:
            patterns.append(re.escape(result.function_name))
        if result.class_name and result.class_name not in _STOP_WORDS:
            patterns.append(re.escape(result.class_name))

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for p in patterns:
        if p not in seen:
            seen.add(p)
            unique.append(p)

    return unique[:_MAX_PATTERNS]


async def run_grep(
    patterns: list[str],
    project_root: Path,
    file_globs: list[str] | None = None,
    timeout: float = 10.0,
    max_count: int = 500,
) -> list[GrepResult]:
    """Execute ripgrep with JSON output. Returns empty list on any failure."""
    if not patterns:
        return []

    combined_pattern = "|".join(f"({p})" for p in patterns)
    cmd = [
        "rg",
        "--json",
        "--max-count",
        str(max_count),
        "--no-heading",
        "-e",
        combined_pattern,
        str(project_root),
    ]

    if file_globs:
        for glob in file_globs:
            cmd.extend(["--glob", glob])

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except FileNotFoundError:
        logger.warning("ripgrep (rg) not installed — skipping grep search")
        return []
    except asyncio.TimeoutError:
        logger.warning("ripgrep timed out after %.1fs", timeout)
        try:
            process.kill()
        except ProcessLookupError:
            pass
        return []

    # Exit code 1 = no matches (not an error)
    if process.returncode not in (0, 1):
        logger.warning("ripgrep exited with code %d: %s", process.returncode, stderr.decode()[:200])
        return []

    results: list[GrepResult] = []
    for line in stdout.decode(errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue

        if obj.get("type") != "match":
            continue

        data = obj.get("data", {})
        path_info = data.get("path", {})
        file_path = path_info.get("text", "")
        line_number = data.get("line_number", 0)
        lines_info = data.get("lines", {})
        line_content = lines_info.get("text", "").rstrip("\n")

        # Extract which pattern matched from submatches
        submatches = data.get("submatches", [])
        matched_text = submatches[0].get("match", {}).get("text", "") if submatches else ""

        results.append(
            GrepResult(
                file_path=file_path,
                line_number=line_number,
                line_content=line_content,
                pattern_matched=matched_text,
            )
        )

    return results


def _deduplicate_grep(
    grep_results: list[GrepResult],
    semantic_results: list[SearchResult],
) -> list[GrepResult]:
    """Remove grep results that overlap with semantic results by file+line range."""
    semantic_ranges: set[tuple[str, int]] = set()
    for r in semantic_results:
        for line in range(r.line_start, r.line_end + 1):
            semantic_ranges.add((r.file_path, line))

    return [g for g in grep_results if (g.file_path, g.line_number) not in semantic_ranges]


async def search_with_grep(
    engine: SearchEngine,
    request: SearchRequest,
    project_root: Path,
    grep_timeout: float = 10.0,
    grep_max_count: int = 500,
    grep_response_cap: int = 100,
) -> tuple[SearchResponse, list[GrepResult]]:
    """Run semantic search then grep, deduplicate results.

    Both MCP and CLI call this function.

    Returns:
        Tuple of (SearchResponse, list[GrepResult])
    """
    # 1. Run semantic search
    response = await engine.search(request)

    # 2. Generate patterns from query and results
    patterns = generate_grep_patterns(request.query, response.results, response.intent)

    if not patterns:
        return response, []

    # 3. Run grep
    grep_results = await run_grep(
        patterns,
        project_root,
        timeout=grep_timeout,
        max_count=grep_max_count,
    )

    # 4. Deduplicate: remove grep hits that overlap with semantic results
    unique_grep = _deduplicate_grep(grep_results, response.results)

    # 5. Cap at response limit
    unique_grep = unique_grep[:grep_response_cap]

    return response, unique_grep
