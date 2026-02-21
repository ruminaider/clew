"""Query intent classification using keyword heuristics."""

from __future__ import annotations

import re

from .models import QueryIntent

# Hard DEBUG keywords: always trigger DEBUG intent
HARD_DEBUG_KEYWORDS = frozenset({"bug", "error", "crash", "exception", "traceback", "debug"})

# Soft DEBUG keywords: need question form or error context to trigger DEBUG
SOFT_DEBUG_KEYWORDS = frozenset({"fix", "broken", "why", "failing"})

ENUMERATION_PHRASES = [
    "find all",
    "list all",
    "every instance",
    "all instances",
    "all uses",
    "all callers",
    "all references",
    "enumerate",
    "how many",
    "count all",
    # V4.1: broader patterns for agent-style queries
    "all places",
    "show all",
    "get all",
    "all of the",
    "what are all",
]

# Matches "all <noun>" at a word boundary, but only when "all" appears
# at the start of the query or after an enumeration-compatible prefix.
# Catches: "all Celery tasks", "all API endpoints that use auth"
# Avoids: "handles all requests", "for all users" (mid-sentence "all")
_ALL_NOUN_RE = re.compile(
    r"^(?:.*?\b(?:show|get|see|find|list|what are)\s+)?all\s+\w+",
    re.IGNORECASE,
)

# Words that when preceding "all" indicate non-enumerative usage
_NON_ENUM_ALL_PREFIXES = frozenset(
    {
        "handles",
        "processes",
        "for",
        "with",
        "across",
        "supports",
        "covers",
        "serves",
        "takes",
        "accepts",
        "manages",
    }
)

LOCATION_PHRASES = [
    "where is",
    "where are",
    "find ",
    "locate ",
    "defined",
    "declaration",
]

DOCS_PHRASES = [
    "what is",
    "explain",
    "how does",
    "how do",
    "documentation",
    "readme",
    "guide",
]

QUESTION_PREFIXES = ("how", "why", "what", "when", "who", "which")

# Matches PascalCase or snake_case single identifiers (no spaces)
_BARE_IDENTIFIER_RE = re.compile(
    r"^(?:[A-Z][a-zA-Z0-9]*(?:[A-Z][a-z0-9]*)*|_?[a-z][a-z0-9]*(?:_[a-z0-9]+)*)$"
)


def _is_question(query: str) -> bool:
    """Check if query is a question (has ? or starts with question word)."""
    if query.rstrip().endswith("?"):
        return True
    first_word = query.split()[0].lower() if query.split() else ""
    return first_word in QUESTION_PREFIXES


def _has_error_context(query: str) -> bool:
    """Check for error signals that strengthen soft DEBUG keywords."""
    error_signals = {"error", "fail", "crash", "exception", "traceback", "500", "404", "timeout"}
    words = set(query.lower().split())
    return bool(words & error_signals)


def _is_enumeration(query_lower: str) -> bool:
    """Check if query has enumeration intent via phrase or pattern matching.

    Uses two strategies:
    1. Exact phrase match against ENUMERATION_PHRASES
    2. Regex match for "all [noun]" patterns (V4.1 broadening)
    """
    # Strategy 1: exact phrase match
    for phrase in ENUMERATION_PHRASES:
        if phrase in query_lower:
            return True

    # Strategy 2: "all [noun]" regex with false-positive guard
    if " all " in query_lower or query_lower.startswith("all "):
        # Check that "all" isn't preceded by a non-enumerative verb
        words = query_lower.split()
        try:
            all_idx = words.index("all")
        except ValueError:
            return False
        if all_idx > 0 and words[all_idx - 1] in _NON_ENUM_ALL_PREFIXES:
            return False
        # Must have a noun after "all"
        if all_idx + 1 < len(words):
            return True

    return False


def classify_intent(query: str) -> QueryIntent:
    """Classify query intent using keyword heuristics.

    Priority: DEBUG > ENUMERATION > LOCATION > DOCS > CODE (default).

    Refinements over naive keyword matching:
    - Hard DEBUG keywords always trigger DEBUG
    - Soft DEBUG keywords need question form or error context
    - Enumeration phrases ("find all", "list all", etc.) → ENUMERATION
    - Questions starting with how/why → DOCS (not DEBUG) unless error context
    - Bare identifiers (PascalCase or snake_case) → LOCATION
    """
    query_lower = query.lower()
    words = set(query_lower.split())

    # Hard DEBUG: always trigger (DEBUG > ENUMERATION)
    if words & HARD_DEBUG_KEYWORDS:
        return QueryIntent.DEBUG

    # Soft DEBUG: only if question form or error context
    if words & SOFT_DEBUG_KEYWORDS:
        if _has_error_context(query) or _is_question(query):
            return QueryIntent.DEBUG

    # ENUMERATION: check before LOCATION so "find all" doesn't match "find "
    if _is_enumeration(query_lower):
        # Check for DEBUG keyword stems as standalone words
        # (e.g. "bugs" matches "bug", but "ValidationError" does not)
        if any(re.search(rf"\b{kw}", query_lower) for kw in HARD_DEBUG_KEYWORDS):
            return QueryIntent.DEBUG
        # "explain all X" should be DOCS, not ENUMERATION
        for docs_phrase in DOCS_PHRASES:
            if docs_phrase in query_lower:
                return QueryIntent.DOCS
        return QueryIntent.ENUMERATION

    for phrase in LOCATION_PHRASES:
        if phrase in query_lower:
            return QueryIntent.LOCATION

    # Questions starting with how/why → DOCS
    if _is_question(query):
        for phrase in DOCS_PHRASES:
            if phrase in query_lower:
                return QueryIntent.DOCS
        # "how does X work?" or "why does X fail?" with question mark → DOCS
        first_word = query.split()[0].lower() if query.split() else ""
        if first_word in ("how", "what") and query.rstrip().endswith("?"):
            return QueryIntent.DOCS

    for phrase in DOCS_PHRASES:
        if phrase in query_lower:
            return QueryIntent.DOCS

    # Bare identifiers → LOCATION
    query_stripped = query.strip()
    if _BARE_IDENTIFIER_RE.match(query_stripped):
        return QueryIntent.LOCATION

    return QueryIntent.CODE


def get_intent_collection_preference(intent: QueryIntent) -> str:
    """Return preferred collection for an intent.

    DOCS intent prefers the docs collection; all others prefer code.
    """
    if intent == QueryIntent.DOCS:
        return "docs"
    return "code"
