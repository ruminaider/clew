"""Query intent classification using keyword heuristics."""

from __future__ import annotations

import re

from .models import QueryIntent

# Hard DEBUG keywords: always trigger DEBUG intent (includes common plurals)
HARD_DEBUG_KEYWORDS = frozenset(
    {
        "bug",
        "bugs",
        "error",
        "errors",
        "crash",
        "crashes",
        "exception",
        "exceptions",
        "traceback",
        "debug",
    }
)

# Soft DEBUG keywords: need question form or error context to trigger DEBUG
SOFT_DEBUG_KEYWORDS = frozenset(
    {
        "fix",
        "broken",
        "why",
        "failing",
        "fail",
        "issue",
        "problem",
        "investigate",
        "diagnose",
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


# Multi-word phrases that always indicate DEBUG intent
DEBUG_PHRASES = [
    "not working",
    "doesn't work",
    "does not work",
    "doesn't work",
]


def _has_error_context(query: str) -> bool:
    """Check for error signals that strengthen soft DEBUG keywords."""
    error_signals = {"error", "fail", "crash", "exception", "traceback", "500", "404", "timeout"}
    words = set(query.lower().split())
    return bool(words & error_signals)


def classify_intent(query: str) -> QueryIntent:
    """Classify query intent using keyword heuristics.

    Priority: DEBUG > LOCATION > DOCS > CODE (default).

    ENUMERATION auto-detection removed — keyword heuristics proved unreliable
    (0/45 agent queries matched in V4.1 evaluation). ENUMERATION intent is
    still available via explicit mode="keyword" override.

    Refinements over naive keyword matching:
    - Hard DEBUG keywords always trigger DEBUG
    - Soft DEBUG keywords need question form or error context
    - Questions starting with how/why → DOCS (not DEBUG) unless error context
    - Bare identifiers (PascalCase or snake_case) → LOCATION
    """
    query_lower = query.lower()
    words = set(query_lower.split())

    # Hard DEBUG: always trigger
    if words & HARD_DEBUG_KEYWORDS:
        return QueryIntent.DEBUG

    # DEBUG phrases: multi-word patterns that always indicate debugging
    for phrase in DEBUG_PHRASES:
        if phrase in query_lower:
            return QueryIntent.DEBUG

    # Soft DEBUG: single keyword needs question form or error context;
    # multiple soft keywords are a strong enough signal on their own
    soft_matches = words & SOFT_DEBUG_KEYWORDS
    if len(soft_matches) >= 2:
        return QueryIntent.DEBUG
    if soft_matches:
        if _has_error_context(query) or _is_question(query):
            return QueryIntent.DEBUG

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
