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


@dataclass
class SearchRequest:
    """Parameters for a search query."""

    query: str
    collection: str = "code"
    limit: int = 10
    intent: QueryIntent | None = None
    filters: dict[str, str] = field(default_factory=dict)
    active_file: str | None = None


@dataclass
class SearchResponse:
    """Full search response with metadata."""

    results: list[SearchResult]
    query_enhanced: str
    total_candidates: int
    intent: QueryIntent
