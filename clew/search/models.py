"""Search pipeline data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class QueryIntent(str, Enum):
    """Classified intent of a search query."""

    CODE = "code"
    DOCS = "docs"
    DEBUG = "debug"
    LOCATION = "location"
    ENUMERATION = "enumeration"


class SuggestionType(str, Enum):
    """Suggestion type for low-confidence or intent-specific follow-up."""

    NONE = "none"
    TRY_KEYWORD = "try_keyword"
    TRY_EXHAUSTIVE = "try_exhaustive"
    LOW_CONFIDENCE = "low_confidence"


@dataclass
class SearchResult:
    """A single search result returned to the user."""

    content: str
    file_path: str
    score: float
    chunk_type: str = ""
    line_start: int = 0
    line_end: int = 0
    language: str = ""
    class_name: str = ""
    function_name: str = ""
    signature: str = ""
    app_name: str = ""
    layer: str = ""
    chunk_id: str = ""
    docstring: str = ""
    is_test: bool = False
    importance_score: float = 0.0


@dataclass
class SearchRequest:
    """Parameters for a search query."""

    query: str
    collection: str = "code"
    limit: int = 10
    intent: QueryIntent | None = None
    filters: dict[str, str] = field(default_factory=dict)
    active_file: str | None = None
    mode: str | None = None


@dataclass
class SearchResponse:
    """Full search response with metadata."""

    results: list[SearchResult]
    query_enhanced: str
    total_candidates: int
    intent: QueryIntent
    confidence: float = 1.0
    confidence_label: str = "high"
    suggestion_type: SuggestionType = SuggestionType.NONE
    suggested_patterns: list[str] | None = None


@dataclass
class RelatedFile:
    """A file related to search results, surfaced from the trace graph."""

    file_path: str
    relationship: str  # "tests", "imported_by", "calls", etc.
    entity: str  # entity connecting this file to results
