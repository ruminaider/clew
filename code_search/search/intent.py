"""Query intent classification using keyword heuristics."""

from __future__ import annotations

from .models import QueryIntent

DEBUG_KEYWORDS = frozenset(
    {"bug", "fix", "error", "fail", "broken", "why", "crash", "exception", "traceback", "debug"}
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


def classify_intent(query: str) -> QueryIntent:
    """Classify query intent using keyword heuristics.

    Priority: DEBUG > LOCATION > DOCS > CODE (default).
    """
    query_lower = query.lower()
    words = set(query_lower.split())

    if words & DEBUG_KEYWORDS:
        return QueryIntent.DEBUG

    for phrase in LOCATION_PHRASES:
        if phrase in query_lower:
            return QueryIntent.LOCATION

    for phrase in DOCS_PHRASES:
        if phrase in query_lower:
            return QueryIntent.DOCS

    return QueryIntent.CODE


def get_intent_collection_preference(intent: QueryIntent) -> str:
    """Return preferred collection for an intent.

    DOCS intent prefers the docs collection; all others prefer code.
    """
    if intent == QueryIntent.DOCS:
        return "docs"
    return "code"
