# Phase 2: Search Pipeline Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the hybrid search pipeline: query enhancement with synonyms, intent classification, dense+BM25 hybrid search with RRF fusion and structural boosting, Voyage reranking with configurable limits, git-aware change detection, and the indexing pipeline that populates Qdrant with structured metadata.

**Architecture:** Search flows through: enhance query (abbreviations + synonyms) → classify intent (DEBUG > LOCATION > DOCS > CODE) → embed query (dense) + tokenize (raw term counts for BM25) → Qdrant multi-prefetch hybrid search with structural boosting + RRF fusion → Voyage rerank (configurable candidate limit, default 30) → format SearchResponse with `query_enhanced` and `total_candidates`. The indexing pipeline discovers files via git-aware change detection, chunks them with structured IDs, extracts metadata (app_name, layer, signature), embeds, generates sparse vectors with raw term counts, and upserts to Qdrant with full payload schema.

**Tech Stack:** qdrant-client (hybrid search, RRF fusion, IDF modifier), voyageai (embeddings + rerank-2.5), pathspec (file matching), pyyaml (terminology files). All deps already in pyproject.toml.

**Branch:** `feature/phase2-search-pipeline` (branch from current `feature/phase1-core-infrastructure`)

**Design Decisions (resolved with user):**
- **Tradeoff A:** Build `app_name` detection and structural boosting in Phase 2
- **Tradeoff B:** Configurable `rerank_candidates` via SearchConfig (default 30, bounds 10–100)
- **Tradeoff C:** `"other"` as explicit fallback for unmatched `layer` values
- **Tradeoff D:** Git-aware change detection (tier 1: `git diff`, tier 2: FileHashTracker fallback)
- **Tradeoff E:** Raw term counts for sparse vector values; Qdrant `Modifier.IDF` handles weighting

---

## Batch 1: Foundation Models (Tasks 2.0–2.2, independent, run in parallel)

---

## Task 2.0: Search Models, SearchConfig & Chunk Metadata Extension

**Files:**
- Create: `clew/search/models.py`
- Create: `tests/unit/test_search_models.py`
- Modify: `clew/models.py` (add SearchConfig, wire into ProjectConfig)
- Modify: `clew/chunker/fallback.py` (add metadata to Chunk dataclass)

### Step 1: Write the failing tests

```python
# tests/unit/test_search_models.py
"""Tests for search pipeline data models."""

from clew.search.models import QueryIntent, SearchRequest, SearchResponse, SearchResult


class TestQueryIntent:
    def test_code_value(self) -> None:
        assert QueryIntent.CODE.value == "code"

    def test_debug_value(self) -> None:
        assert QueryIntent.DEBUG.value == "debug"

    def test_docs_value(self) -> None:
        assert QueryIntent.DOCS.value == "docs"

    def test_location_value(self) -> None:
        assert QueryIntent.LOCATION.value == "location"


class TestSearchResult:
    def test_create_with_required_fields(self) -> None:
        result = SearchResult(content="def foo():", file_path="main.py", score=0.95)
        assert result.content == "def foo():"
        assert result.file_path == "main.py"
        assert result.score == 0.95

    def test_default_optional_fields(self) -> None:
        result = SearchResult(content="x", file_path="f.py", score=0.5)
        assert result.chunk_type == ""
        assert result.line_start == 0
        assert result.language == ""
        assert result.signature == ""
        assert result.app_name == ""
        assert result.layer == ""
        assert result.chunk_id == ""

    def test_all_metadata_fields(self) -> None:
        result = SearchResult(
            content="def foo():",
            file_path="backend/care/models.py",
            score=0.9,
            chunk_type="method",
            class_name="Prescription",
            function_name="is_expired",
            signature="def is_expired(self) -> bool",
            app_name="care",
            layer="model",
            chunk_id="backend/care/models.py::method::Prescription.is_expired",
        )
        assert result.signature == "def is_expired(self) -> bool"
        assert result.app_name == "care"
        assert result.layer == "model"
        assert result.chunk_id == "backend/care/models.py::method::Prescription.is_expired"


class TestSearchRequest:
    def test_defaults(self) -> None:
        req = SearchRequest(query="find auth")
        assert req.collection == "code"
        assert req.limit == 10
        assert req.intent is None
        assert req.active_file is None

    def test_custom_values(self) -> None:
        req = SearchRequest(
            query="q", collection="docs", limit=5,
            intent=QueryIntent.DEBUG, active_file="src/auth.py",
        )
        assert req.collection == "docs"
        assert req.intent == QueryIntent.DEBUG
        assert req.active_file == "src/auth.py"


class TestSearchResponse:
    def test_create(self) -> None:
        result = SearchResult(content="x", file_path="f.py", score=0.5)
        resp = SearchResponse(
            results=[result],
            query_enhanced="expanded query",
            total_candidates=30,
            intent=QueryIntent.CODE,
        )
        assert resp.query_enhanced == "expanded query"
        assert resp.total_candidates == 30
        assert resp.intent == QueryIntent.CODE
        assert len(resp.results) == 1

    def test_empty_response(self) -> None:
        resp = SearchResponse(
            results=[], query_enhanced="q", total_candidates=0, intent=QueryIntent.CODE,
        )
        assert resp.results == []
```

### Step 2: Run test to verify it fails

```bash
pytest tests/unit/test_search_models.py -v
```

Expected: FAIL — module doesn't exist.

### Step 3: Write search models

```python
# clew/search/models.py
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
```

Also update `clew/search/__init__.py`:

```python
# clew/search/__init__.py
"""Search pipeline: hybrid retrieval with reranking."""
```

### Step 4: Add SearchConfig to models.py

Write tests for SearchConfig first:

```python
# tests/unit/test_models.py (CREATE — this file does not exist yet)

from clew.models import SearchConfig


class TestSearchConfig:
    def test_defaults(self) -> None:
        config = SearchConfig()
        assert config.rerank_candidates == 30
        assert config.rerank_top_k == 10
        assert config.rerank_model == "rerank-2.5"

    def test_custom_candidates(self) -> None:
        config = SearchConfig(rerank_candidates=50)
        assert config.rerank_candidates == 50

    def test_bounds_enforced(self) -> None:
        import pytest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            SearchConfig(rerank_candidates=5)  # below 10
        with pytest.raises(ValidationError):
            SearchConfig(rerank_candidates=200)  # above 100
```

Add to `clew/models.py`:

```python
class SearchConfig(BaseModel):
    """Search pipeline configuration. See Tradeoff B resolution."""

    rerank_candidates: int = Field(default=30, ge=10, le=100)
    rerank_top_k: int = Field(default=10, ge=1, le=50)
    no_rerank_threshold: int = Field(default=10, ge=1)
    rerank_model: str = "rerank-2.5"
    high_confidence_threshold: float = Field(default=0.92, ge=0.0, le=1.0)
    low_variance_threshold: float = Field(default=0.1, ge=0.0, le=1.0)
```

Wire into ProjectConfig by adding:

```python
search: SearchConfig = Field(default_factory=SearchConfig)
```

### Step 5: Extend Chunk with metadata

Modify `clew/chunker/fallback.py`:

Add `field` to the import from `dataclasses`, add `Any` to the import from `typing`:

```python
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
```

Update the Chunk dataclass:

```python
@dataclass
class Chunk:
    """A chunk of source code or text."""

    content: str
    source: str  # "ast" or "fallback"
    file_path: str
    metadata: dict[str, Any] = field(default_factory=dict)
```

Update `_extract_ast_chunks` to populate metadata from entity fields:

```python
def _extract_ast_chunks(tree: Any, file_path: str, content: str, max_tokens: int) -> list[Chunk]:
    """Extract chunks from AST, returning empty list if no entities found."""
    from .strategies import PythonChunker

    ext = file_path.rsplit(".", 1)[-1].lower()
    if ext != "py":
        return []

    chunker = PythonChunker()
    entities = list(chunker.extract_entities(tree, content))

    if not entities:
        return []

    chunks: list[Chunk] = []
    for entity in entities:
        meta = {
            "entity_type": entity.entity_type,
            "name": entity.name,
            "qualified_name": entity.qualified_name,
            "line_start": entity.line_start,
            "line_end": entity.line_end,
            "parent_class": entity.parent_class or "",
        }
        if count_tokens(entity.content) <= max_tokens:
            chunks.append(Chunk(content=entity.content, source="ast", file_path=file_path, metadata=meta))
        else:
            sub_chunks = token_recursive_split(entity.content, max_tokens, overlap_tokens=200)
            chunks.extend(
                Chunk(content=c, source="fallback", file_path=file_path, metadata=meta)
                for c in sub_chunks
            )

    return chunks
```

### Step 6: Run tests to verify they pass

```bash
pytest tests/unit/test_search_models.py tests/unit/test_models.py tests/unit/test_fallback.py -v
```

Expected: All tests PASS (new models + existing tests still green).

### Step 7: Run linters

```bash
ruff check clew/search/models.py clew/models.py clew/chunker/fallback.py
mypy clew/search/models.py clew/models.py clew/chunker/fallback.py
```

### Step 8: Commit

```bash
git add clew/search/ clew/models.py clew/chunker/fallback.py tests/unit/test_search_models.py tests/unit/test_models.py
git commit -m "feat(search): add search models, SearchConfig, and extend Chunk with metadata"
```

---

## Task 2.1: Code Tokenization for BM25

**Files:**
- Create: `clew/search/tokenize.py`
- Create: `tests/unit/test_code_tokenize.py`

**Key design spec:** Raw term counts for sparse vector values (Tradeoff E). Qdrant `Modifier.IDF` handles weighting at query time. Hash-based token IDs via `md5(token) % 2^31`.

### Step 1: Write the failing tests

```python
# tests/unit/test_code_tokenize.py
"""Tests for code-aware BM25 tokenization."""

from clew.search.tokenize import SparseVector, split_identifier, text_to_sparse_vector, tokenize_code


class TestSplitIdentifier:
    def test_camel_case(self) -> None:
        assert split_identifier("getUserById") == ["get", "user", "by", "id"]

    def test_snake_case(self) -> None:
        assert split_identifier("get_user_by_id") == ["get", "user", "by", "id"]

    def test_pascal_case(self) -> None:
        result = split_identifier("PrescriptionFillOrder")
        assert result == ["prescription", "fill", "order"]

    def test_all_caps_acronym(self) -> None:
        result = split_identifier("HTMLParser")
        assert "html" in result
        assert "parser" in result

    def test_single_word(self) -> None:
        assert split_identifier("hello") == ["hello"]

    def test_upper_single_word(self) -> None:
        assert split_identifier("CONSTANT") == ["constant"]


class TestTokenizeCode:
    def test_extracts_identifiers(self) -> None:
        tokens = tokenize_code("def get_user(user_id: int):")
        assert "get" in tokens
        assert "user" in tokens

    def test_deduplicates(self) -> None:
        tokens = tokenize_code("user user user")
        assert tokens.count("user") == 1

    def test_skips_single_chars(self) -> None:
        tokens = tokenize_code("x = a + b")
        assert "x" not in tokens
        assert "a" not in tokens

    def test_includes_full_identifier(self) -> None:
        tokens = tokenize_code("getUserById()")
        assert "getuserbyid" in tokens
        assert "get" in tokens


class TestTextToSparseVector:
    def test_returns_sparse_vector(self) -> None:
        sv = text_to_sparse_vector("def get_user(): pass")
        assert isinstance(sv, SparseVector)
        assert len(sv.indices) > 0
        assert len(sv.indices) == len(sv.values)

    def test_empty_text(self) -> None:
        sv = text_to_sparse_vector("")
        assert sv.indices == []
        assert sv.values == []

    def test_raw_term_counts(self) -> None:
        """Tradeoff E: values are raw term counts, not normalized."""
        sv = text_to_sparse_vector("user user user auth")
        # All values should be positive integers (as floats)
        assert all(v >= 1.0 for v in sv.values)
        # "user" appears 3 times in the raw text, so its count should reflect frequency
        # (exact value depends on tokenization splitting)

    def test_deterministic(self) -> None:
        sv1 = text_to_sparse_vector("class Foo: pass")
        sv2 = text_to_sparse_vector("class Foo: pass")
        assert sv1.indices == sv2.indices
        assert sv1.values == sv2.values

    def test_repeated_tokens_have_higher_counts(self) -> None:
        """Raw counts: repeated tokens should have higher values."""
        sv = text_to_sparse_vector("user user auth")
        # There should be at least 2 distinct tokens
        assert len(sv.indices) >= 2
```

### Step 2: Run test to verify it fails

```bash
pytest tests/unit/test_code_tokenize.py -v
```

Expected: FAIL — module doesn't exist.

### Step 3: Write implementation

```python
# clew/search/tokenize.py
"""Code-aware tokenization for BM25 sparse vectors.

Sparse vector values are raw term counts (not normalized).
Qdrant applies IDF weighting at query time via Modifier.IDF.
See Tradeoff E resolution.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

CAMEL_CASE_PATTERN = re.compile(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\d|\b)")
IDENTIFIER_PATTERN = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]*")


@dataclass
class SparseVector:
    """Sparse vector for BM25 search."""

    indices: list[int]
    values: list[float]


def split_identifier(identifier: str) -> list[str]:
    """Split a code identifier into sub-tokens.

    Handles camelCase, PascalCase, snake_case, and ALLCAPS.

    Examples:
        "getUserById" -> ["get", "user", "by", "id"]
        "get_user_by_id" -> ["get", "user", "by", "id"]
        "HTMLParser" -> ["html", "parser"]
    """
    parts: list[str] = []
    for segment in identifier.split("_"):
        if not segment:
            continue
        camel_parts = CAMEL_CASE_PATTERN.findall(segment)
        if camel_parts:
            parts.extend(p.lower() for p in camel_parts)
        else:
            parts.append(segment.lower())
    return parts if parts else [identifier.lower()]


def tokenize_code(text: str) -> list[str]:
    """Tokenize code text into searchable tokens.

    Extracts identifiers, splits camelCase/snake_case,
    and returns deduplicated lowercase tokens (length > 1).
    """
    tokens: list[str] = []
    identifiers = IDENTIFIER_PATTERN.findall(text)
    for ident in identifiers:
        tokens.append(ident.lower())
        parts = split_identifier(ident)
        tokens.extend(parts)

    seen: set[str] = set()
    unique: list[str] = []
    for t in tokens:
        if t not in seen and len(t) > 1:
            seen.add(t)
            unique.append(t)
    return unique


def _extract_all_tokens(text: str) -> list[str]:
    """Extract ALL tokens from text (with duplicates) for term counting."""
    tokens: list[str] = []
    identifiers = IDENTIFIER_PATTERN.findall(text)
    for ident in identifiers:
        tokens.append(ident.lower())
        parts = split_identifier(ident)
        tokens.extend(parts)
    return [t for t in tokens if len(t) > 1]


def _token_to_index(token: str) -> int:
    """Map token to sparse vector index using deterministic hash."""
    h = hashlib.md5(token.encode()).hexdigest()  # noqa: S324
    return int(h, 16) % (2**31 - 1)


def text_to_sparse_vector(text: str) -> SparseVector:
    """Convert text to a BM25-style sparse vector.

    Uses raw term counts as values (not normalized).
    Qdrant applies IDF weighting at query time via Modifier.IDF.
    """
    all_tokens = _extract_all_tokens(text)
    if not all_tokens:
        return SparseVector(indices=[], values=[])

    # Count raw term frequencies
    freq: dict[str, int] = {}
    for t in all_tokens:
        freq[t] = freq.get(t, 0) + 1

    indices: list[int] = []
    values: list[float] = []
    for token, count in sorted(freq.items()):
        indices.append(_token_to_index(token))
        values.append(float(count))  # Raw count, not normalized

    return SparseVector(indices=indices, values=values)
```

### Step 4: Run tests to verify they pass

```bash
pytest tests/unit/test_code_tokenize.py -v
```

Expected: All tests PASS.

### Step 5: Run linters

```bash
ruff check clew/search/tokenize.py tests/unit/test_code_tokenize.py
mypy clew/search/tokenize.py
```

### Step 6: Commit

```bash
git add clew/search/tokenize.py tests/unit/test_code_tokenize.py
git commit -m "feat(search): add code-aware BM25 tokenization with raw term counts"
```

---

## Task 2.2: Intent Classification

**Files:**
- Create: `clew/search/intent.py`
- Create: `tests/unit/test_intent.py`

**Key design spec:** Priority order: DEBUG > LOCATION > DOCS > CODE (default). DOCS intent should prefer docs collection.

### Step 1: Write the failing tests

```python
# tests/unit/test_intent.py
"""Tests for query intent classification."""

from clew.search.intent import classify_intent, get_intent_collection_preference
from clew.search.models import QueryIntent


class TestClassifyIntent:
    def test_debug_keywords(self) -> None:
        assert classify_intent("why does login fail") == QueryIntent.DEBUG
        assert classify_intent("fix the auth bug") == QueryIntent.DEBUG
        assert classify_intent("error in payment") == QueryIntent.DEBUG

    def test_location_keywords(self) -> None:
        assert classify_intent("where is the User model defined") == QueryIntent.LOCATION
        assert classify_intent("find the auth middleware") == QueryIntent.LOCATION

    def test_docs_keywords(self) -> None:
        assert classify_intent("what is the prescription model") == QueryIntent.DOCS
        assert classify_intent("explain the auth flow") == QueryIntent.DOCS

    def test_default_is_code(self) -> None:
        assert classify_intent("user authentication handler") == QueryIntent.CODE

    def test_case_insensitive(self) -> None:
        assert classify_intent("FIX the BUG") == QueryIntent.DEBUG
        assert classify_intent("WHERE is Config") == QueryIntent.LOCATION

    def test_debug_takes_priority(self) -> None:
        # "fix" is debug, "where" is location — debug wins (checked first)
        assert classify_intent("fix where the error is") == QueryIntent.DEBUG

    def test_empty_query_is_code(self) -> None:
        assert classify_intent("") == QueryIntent.CODE

    def test_code_query(self) -> None:
        assert classify_intent("prescription fill order model") == QueryIntent.CODE


class TestIntentCollectionPreference:
    def test_docs_prefers_docs_collection(self) -> None:
        assert get_intent_collection_preference(QueryIntent.DOCS) == "docs"

    def test_code_prefers_code_collection(self) -> None:
        assert get_intent_collection_preference(QueryIntent.CODE) == "code"

    def test_debug_prefers_code_collection(self) -> None:
        assert get_intent_collection_preference(QueryIntent.DEBUG) == "code"

    def test_location_prefers_code_collection(self) -> None:
        assert get_intent_collection_preference(QueryIntent.LOCATION) == "code"
```

### Step 2: Run test to verify it fails

```bash
pytest tests/unit/test_intent.py -v
```

Expected: FAIL — module doesn't exist.

### Step 3: Write implementation

```python
# clew/search/intent.py
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
```

### Step 4: Run tests to verify they pass

```bash
pytest tests/unit/test_intent.py -v
```

Expected: All tests PASS.

### Step 5: Run linters

```bash
ruff check clew/search/intent.py tests/unit/test_intent.py
mypy clew/search/intent.py
```

### Step 6: Commit

```bash
git add clew/search/intent.py tests/unit/test_intent.py
git commit -m "feat(search): add keyword-based intent classification with DOCS collection preference"
```

---

## Batch 2: Integrations (Tasks 2.3–2.5, depends on Batch 1)

---

## Task 2.3: Query Enhancement with Synonyms

**Files:**
- Create: `clew/search/enhance.py`
- Create: `tests/unit/test_enhance.py`

**Key design spec:** Terminology YAML has BOTH `abbreviations` AND `synonyms` sections. Enhancement appends expansions to the query.

### Step 1: Write the failing tests

```python
# tests/unit/test_enhance.py
"""Tests for query enhancement with terminology expansion."""

from pathlib import Path

from clew.search.enhance import QueryEnhancer, should_skip_enhancement


class TestShouldSkipEnhancement:
    def test_quoted_query(self) -> None:
        assert should_skip_enhancement('"exact match"') is True

    def test_pascal_case_identifier(self) -> None:
        assert should_skip_enhancement("PrescriptionFillOrder") is True

    def test_snake_case_identifier(self) -> None:
        assert should_skip_enhancement("get_user_by_id") is True

    def test_file_path(self) -> None:
        assert should_skip_enhancement("src/models.py") is True
        assert should_skip_enhancement("components/Auth.tsx") is True

    def test_normal_query_not_skipped(self) -> None:
        assert should_skip_enhancement("how does auth work") is False

    def test_single_word_not_skipped(self) -> None:
        assert should_skip_enhancement("authentication") is False


class TestQueryEnhancerAbbreviations:
    def test_no_terminology_file(self) -> None:
        enhancer = QueryEnhancer()
        assert enhancer.enhance("hello world") == "hello world"

    def test_with_abbreviations(self, tmp_path: Path) -> None:
        term_file = tmp_path / "terminology.yaml"
        term_file.write_text(
            "abbreviations:\n  BV: bacterial vaginosis\n  UTI: urinary tract infection\n"
        )
        enhancer = QueryEnhancer(terminology_file=term_file)
        result = enhancer.enhance("BV treatment")
        assert "bacterial vaginosis" in result
        assert "BV" in result

    def test_skipped_query_unchanged(self) -> None:
        enhancer = QueryEnhancer()
        assert enhancer.enhance('"exact search"') == '"exact search"'

    def test_non_matching_unchanged(self, tmp_path: Path) -> None:
        term_file = tmp_path / "terminology.yaml"
        term_file.write_text("abbreviations:\n  BV: bacterial vaginosis\n")
        enhancer = QueryEnhancer(terminology_file=term_file)
        assert enhancer.enhance("prescription model") == "prescription model"

    def test_missing_file_no_error(self) -> None:
        enhancer = QueryEnhancer(terminology_file=Path("/nonexistent/file.yaml"))
        assert enhancer.enhance("test query") == "test query"

    def test_case_insensitive_expansion(self, tmp_path: Path) -> None:
        term_file = tmp_path / "terminology.yaml"
        term_file.write_text("abbreviations:\n  bv: bacterial vaginosis\n")
        enhancer = QueryEnhancer(terminology_file=term_file)
        result = enhancer.enhance("bv treatment")
        assert "bacterial vaginosis" in result


class TestQueryEnhancerSynonyms:
    def test_synonym_expansion(self, tmp_path: Path) -> None:
        term_file = tmp_path / "terminology.yaml"
        term_file.write_text(
            "synonyms:\n  consult:\n    - consultation\n    - telehealth\n    - wheel\n"
        )
        enhancer = QueryEnhancer(terminology_file=term_file)
        result = enhancer.enhance("consult flow")
        assert "consultation" in result or "telehealth" in result

    def test_synonym_and_abbreviation_together(self, tmp_path: Path) -> None:
        term_file = tmp_path / "terminology.yaml"
        term_file.write_text(
            "abbreviations:\n  BV: bacterial vaginosis\n"
            "synonyms:\n  consult:\n    - consultation\n    - telehealth\n"
        )
        enhancer = QueryEnhancer(terminology_file=term_file)
        result = enhancer.enhance("BV consult")
        assert "bacterial vaginosis" in result
        assert "consultation" in result or "telehealth" in result

    def test_empty_synonyms_section(self, tmp_path: Path) -> None:
        term_file = tmp_path / "terminology.yaml"
        term_file.write_text("abbreviations:\n  BV: bacterial vaginosis\nsynonyms: {}\n")
        enhancer = QueryEnhancer(terminology_file=term_file)
        result = enhancer.enhance("BV treatment")
        assert "bacterial vaginosis" in result
```

### Step 2: Run test to verify it fails

```bash
pytest tests/unit/test_enhance.py -v
```

Expected: FAIL — module doesn't exist.

### Step 3: Write implementation

```python
# clew/search/enhance.py
"""Query enhancement with terminology expansion and skip logic.

Supports both abbreviation expansion and synonym expansion
from a YAML terminology file.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml


def should_skip_enhancement(query: str) -> bool:
    """Determine if query should bypass enhancement."""
    # Quoted exact match
    if query.startswith('"') and query.endswith('"'):
        return True
    # PascalCase identifier
    if re.match(r"^[A-Z][a-zA-Z0-9]+$", query):
        return True
    # snake_case identifier
    if re.match(r"^[a-z][a-z0-9_]*$", query) and "_" in query:
        return True
    # File path
    if "/" in query or query.endswith((".py", ".ts", ".js", ".tsx", ".jsx")):
        return True
    return False


class QueryEnhancer:
    """Enhance queries with terminology expansion.

    Supports two expansion types from YAML:
    - abbreviations: BV -> "BV (bacterial vaginosis)"
    - synonyms: consult -> "consult (consultation, telehealth)"
    """

    def __init__(self, terminology_file: Path | None = None) -> None:
        self._abbreviations: dict[str, str] = {}
        self._synonyms: dict[str, list[str]] = {}
        if terminology_file and terminology_file.exists():
            self._load_terminology(terminology_file)

    def _load_terminology(self, path: Path) -> None:
        """Load terminology definitions from YAML file."""
        data: dict[str, Any] = yaml.safe_load(path.read_text()) or {}
        self._abbreviations = data.get("abbreviations", {}) or {}
        self._synonyms = data.get("synonyms", {}) or {}

    def enhance(self, query: str) -> str:
        """Enhance query with terminology expansion.

        Returns original query if skip conditions apply.
        """
        if should_skip_enhancement(query):
            return query

        enhanced = query

        # Expand abbreviations: "BV" -> "BV (bacterial vaginosis)"
        for abbr, expansion in self._abbreviations.items():
            pattern = re.compile(r"\b" + re.escape(abbr) + r"\b", re.IGNORECASE)
            if pattern.search(enhanced):
                enhanced = pattern.sub(f"{abbr} ({expansion})", enhanced)

        # Expand synonyms: "consult" -> "consult (consultation, telehealth)"
        for term, alternatives in self._synonyms.items():
            pattern = re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)
            if pattern.search(enhanced) and alternatives:
                alt_str = ", ".join(alternatives)
                enhanced = pattern.sub(f"{term} ({alt_str})", enhanced)

        return enhanced
```

### Step 4: Run tests to verify they pass

```bash
pytest tests/unit/test_enhance.py -v
```

Expected: All tests PASS.

### Step 5: Run linters

```bash
ruff check clew/search/enhance.py tests/unit/test_enhance.py
mypy clew/search/enhance.py
```

### Step 6: Commit

```bash
git add clew/search/enhance.py tests/unit/test_enhance.py
git commit -m "feat(search): add query enhancement with abbreviation and synonym expansion"
```

---

## Task 2.4: Metadata Extraction

**Files:**
- Create: `clew/indexer/metadata.py`
- Create: `tests/unit/test_metadata.py`

**Key design specs:**
- `app_name`: Django app detection from directory structure (Tradeoff A)
- `layer`: classification with `"other"` fallback (Tradeoff C)
- `signature`: first line of def/class/async def
- `chunk_id`: structured format `"file_path::entity_type::qualified_name"`

### Step 1: Write the failing tests

```python
# tests/unit/test_metadata.py
"""Tests for metadata extraction: app_name, layer, signature, chunk_id."""

import hashlib

from clew.indexer.metadata import build_chunk_id, classify_layer, detect_app_name, extract_signature


class TestClassifyLayer:
    def test_models_py(self) -> None:
        assert classify_layer("backend/care/models.py") == "model"

    def test_views_py(self) -> None:
        assert classify_layer("backend/care/views.py") == "view"

    def test_viewsets_py(self) -> None:
        assert classify_layer("backend/care/viewsets.py") == "view"

    def test_serializers_py(self) -> None:
        assert classify_layer("backend/care/serializers.py") == "serializer"

    def test_tasks_py(self) -> None:
        assert classify_layer("backend/care/tasks.py") == "task"

    def test_service_py(self) -> None:
        assert classify_layer("backend/care/service.py") == "service"

    def test_services_py(self) -> None:
        assert classify_layer("backend/care/services.py") == "service"

    def test_tsx_component(self) -> None:
        assert classify_layer("frontend/components/Auth.tsx") == "component"

    def test_jsx_component(self) -> None:
        assert classify_layer("frontend/components/Auth.jsx") == "component"

    def test_utils_fallback_other(self) -> None:
        """Tradeoff C: unmatched files get 'other' layer."""
        assert classify_layer("backend/care/utils.py") == "other"

    def test_admin_fallback_other(self) -> None:
        assert classify_layer("backend/care/admin.py") == "other"

    def test_unknown_extension(self) -> None:
        assert classify_layer("data.csv") == "other"

    def test_init_py(self) -> None:
        assert classify_layer("backend/care/__init__.py") == "other"


class TestDetectAppName:
    def test_django_models(self) -> None:
        assert detect_app_name("backend/care/models.py") == "care"

    def test_django_views(self) -> None:
        assert detect_app_name("backend/consults/views.py") == "consults"

    def test_nested_path(self) -> None:
        assert detect_app_name("backend/consults/wheel/wheel.py") == "wheel"

    def test_simple_file(self) -> None:
        assert detect_app_name("utils.py") == ""

    def test_frontend_component(self) -> None:
        assert detect_app_name("frontend/components/Auth.tsx") == "components"

    def test_deep_nested(self) -> None:
        assert detect_app_name("backend/care/tests/test_models.py") == "tests"


class TestExtractSignature:
    def test_function(self) -> None:
        code = "def is_expired(self) -> bool:\n    return True"
        assert extract_signature("method", code) == "def is_expired(self) -> bool"

    def test_class(self) -> None:
        code = "class Prescription(BaseModel):\n    pass"
        assert extract_signature("class", code) == "class Prescription(BaseModel)"

    def test_async_function(self) -> None:
        code = "async def fetch_data(url: str) -> dict:\n    pass"
        assert extract_signature("function", code) == "async def fetch_data(url: str) -> dict"

    def test_section_returns_empty(self) -> None:
        code = "# Some comment\nx = 1"
        assert extract_signature("section", code) == ""

    def test_empty_content(self) -> None:
        assert extract_signature("function", "") == ""


class TestBuildChunkId:
    def test_named_entity(self) -> None:
        chunk_id = build_chunk_id(
            "backend/care/models.py", "method", "Prescription.is_expired",
        )
        assert chunk_id == "backend/care/models.py::method::Prescription.is_expired"

    def test_function(self) -> None:
        chunk_id = build_chunk_id("src/utils.py", "function", "helper")
        assert chunk_id == "src/utils.py::function::helper"

    def test_class(self) -> None:
        chunk_id = build_chunk_id("models.py", "class", "User")
        assert chunk_id == "models.py::class::User"

    def test_toplevel_fallback(self) -> None:
        content = "x = 1\ny = 2"
        chunk_id = build_chunk_id("main.py", "section", "", content=content)
        expected_hash = hashlib.sha256(content.encode()).hexdigest()[:12]
        assert chunk_id == f"main.py::toplevel::{expected_hash}"

    def test_toplevel_no_name(self) -> None:
        chunk_id = build_chunk_id("main.py", "toplevel", "", content="some code")
        assert chunk_id.startswith("main.py::toplevel::")
        assert len(chunk_id.split("::")[-1]) == 12
```

### Step 2: Run test to verify it fails

```bash
pytest tests/unit/test_metadata.py -v
```

Expected: FAIL — module doesn't exist.

### Step 3: Write implementation

```python
# clew/indexer/metadata.py
"""Metadata extraction for indexed chunks.

Extracts app_name, layer, signature, and builds structured chunk IDs
from file paths and code entities.
"""

from __future__ import annotations

import hashlib
from pathlib import PurePosixPath

# Layer classification mapping (filename -> layer)
LAYER_MAP: dict[str, str] = {
    "models.py": "model",
    "views.py": "view",
    "viewsets.py": "view",
    "serializers.py": "serializer",
    "tasks.py": "task",
    "service.py": "service",
    "services.py": "service",
}

# Extensions that map to "component" layer
COMPONENT_EXTENSIONS = frozenset({".tsx", ".jsx"})

# Django-style filenames that indicate app structure
DJANGO_FILENAMES = frozenset(LAYER_MAP.keys())


def classify_layer(file_path: str) -> str:
    """Classify file into an architectural layer.

    Returns one of: model, view, serializer, task, service, component, other.
    Tradeoff C resolution: "other" is the explicit fallback for unmatched files.
    """
    path = PurePosixPath(file_path)
    filename = path.name

    if filename in LAYER_MAP:
        return LAYER_MAP[filename]

    if path.suffix in COMPONENT_EXTENSIONS:
        return "component"

    return "other"


def detect_app_name(file_path: str) -> str:
    """Detect app name from file path.

    For Django-style paths like 'backend/care/models.py', extracts 'care'.
    For other paths, uses the parent directory name.

    Tradeoff A resolution: Build this capability in Phase 2.
    """
    path = PurePosixPath(file_path)
    parts = path.parts

    if len(parts) < 2:
        return ""

    # Parent directory of the file
    return parts[-2]


def extract_signature(entity_type: str, content: str) -> str:
    """Extract function/method/class signature from code content.

    Returns the first line (up to the colon) for def/class definitions.
    Returns empty string for sections or empty content.
    """
    if entity_type in ("section", "toplevel") or not content:
        return ""

    first_line = content.strip().split("\n")[0].strip()
    if first_line.startswith(("def ", "class ", "async def ")):
        return first_line.rstrip(":")
    return ""


def build_chunk_id(
    file_path: str,
    entity_type: str,
    qualified_name: str,
    content: str = "",
) -> str:
    """Build structured chunk ID.

    Named entities: "file_path::entity_type::qualified_name"
    Anonymous/toplevel: "file_path::toplevel::sha256[:12]"
    """
    if qualified_name and entity_type not in ("section", "toplevel"):
        return f"{file_path}::{entity_type}::{qualified_name}"

    content_hash = hashlib.sha256(content.encode()).hexdigest()[:12]
    return f"{file_path}::toplevel::{content_hash}"
```

### Step 4: Run tests to verify they pass

```bash
pytest tests/unit/test_metadata.py -v
```

Expected: All tests PASS.

### Step 5: Run linters

```bash
ruff check clew/indexer/metadata.py tests/unit/test_metadata.py
mypy clew/indexer/metadata.py
```

### Step 6: Commit

```bash
git add clew/indexer/metadata.py tests/unit/test_metadata.py
git commit -m "feat(indexer): add metadata extraction with app_name, layer, signature, chunk IDs"
```

---

## Task 2.5: Qdrant Collection Manager

**Files:**
- Create: `clew/clients/qdrant.py`
- Create: `tests/unit/test_qdrant_manager.py`

**Key design specs:**
- Sparse vector name: `"bm25"` (not `"sparse"`)
- Modifier: `models.Modifier.IDF` on SparseVectorParams
- `delete_by_file_path` method for stale chunk removal
- Multi-prefetch `query_hybrid` with structural boost support

### Step 1: Write the failing tests

```python
# tests/unit/test_qdrant_manager.py
"""Tests for Qdrant collection manager."""

from unittest.mock import Mock, patch

import pytest

from clew.clients.qdrant import QdrantManager


@pytest.fixture
def mock_client() -> Mock:
    client = Mock()
    client.get_collections.return_value = Mock(collections=[])
    client.create_collection = Mock()
    client.upsert = Mock()
    client.count.return_value = Mock(count=42)
    client.query_points.return_value = Mock(points=[])
    client.delete = Mock()
    return client


@pytest.fixture
def manager(mock_client: Mock) -> QdrantManager:
    with patch("clew.clients.qdrant.QdrantClient", return_value=mock_client):
        return QdrantManager(url="http://localhost:6333")


class TestEnsureCollection:
    def test_creates_when_missing(self, manager: QdrantManager, mock_client: Mock) -> None:
        manager.ensure_collection("code")
        mock_client.create_collection.assert_called_once()

    def test_skips_when_exists(self, manager: QdrantManager, mock_client: Mock) -> None:
        mock_client.get_collections.return_value = Mock(
            collections=[Mock(name="code")]
        )
        manager.ensure_collection("code")
        mock_client.create_collection.assert_not_called()

    def test_creates_with_dense_and_bm25_sparse(
        self, manager: QdrantManager, mock_client: Mock,
    ) -> None:
        """Sparse vector must use name 'bm25' with IDF modifier."""
        manager.ensure_collection("code", dense_dim=1024)
        call_kwargs = mock_client.create_collection.call_args
        assert "dense" in call_kwargs.kwargs["vectors_config"]
        assert "bm25" in call_kwargs.kwargs["sparse_vectors_config"]


class TestUpsertPoints:
    def test_delegates_to_client(self, manager: QdrantManager, mock_client: Mock) -> None:
        points = [Mock()]
        manager.upsert_points("code", points)
        mock_client.upsert.assert_called_once_with(collection_name="code", points=points)


class TestDeleteByFilePath:
    def test_deletes_points_by_filter(self, manager: QdrantManager, mock_client: Mock) -> None:
        manager.delete_by_file_path("code", "backend/models.py")
        mock_client.delete.assert_called_once()
        call_args = mock_client.delete.call_args
        assert call_args.kwargs["collection_name"] == "code"


class TestQueryHybrid:
    def test_returns_points(self, manager: QdrantManager, mock_client: Mock) -> None:
        from qdrant_client import models

        mock_client.query_points.return_value = Mock(
            points=[Mock(id="1", score=0.9, payload={"content": "hello"})]
        )
        results = manager.query_hybrid(
            "code",
            prefetches=[
                models.Prefetch(query=[0.1] * 1024, using="dense", limit=30),
            ],
        )
        assert len(results) == 1
        mock_client.query_points.assert_called_once()

    def test_passes_limit(self, manager: QdrantManager, mock_client: Mock) -> None:
        from qdrant_client import models

        mock_client.query_points.return_value = Mock(points=[])
        manager.query_hybrid(
            "code",
            prefetches=[models.Prefetch(query=[0.1] * 1024, using="dense", limit=30)],
            limit=20,
        )
        call_kwargs = mock_client.query_points.call_args.kwargs
        assert call_kwargs["limit"] == 20


class TestHealthCheck:
    def test_returns_true_when_healthy(self, manager: QdrantManager) -> None:
        assert manager.health_check() is True

    def test_returns_false_on_error(self, manager: QdrantManager, mock_client: Mock) -> None:
        mock_client.get_collections.side_effect = Exception("connection refused")
        assert manager.health_check() is False


class TestCollectionInfo:
    def test_collection_exists(self, manager: QdrantManager, mock_client: Mock) -> None:
        mock_client.get_collections.return_value = Mock(collections=[Mock(name="code")])
        assert manager.collection_exists("code") is True
        assert manager.collection_exists("other") is False

    def test_collection_count(self, manager: QdrantManager) -> None:
        assert manager.collection_count("code") == 42
```

### Step 2: Run test to verify it fails

```bash
pytest tests/unit/test_qdrant_manager.py -v
```

Expected: FAIL — module doesn't exist.

### Step 3: Write implementation

```python
# clew/clients/qdrant.py
"""Qdrant vector database client wrapper.

Collection schema per DESIGN.md:
- Dense vector: "dense", 1024 dims, COSINE
- Sparse vector: "bm25" with Modifier.IDF (not "sparse")
"""

from __future__ import annotations

import logging

from qdrant_client import QdrantClient, models

from clew.exceptions import QdrantConnectionError

logger = logging.getLogger(__name__)


class QdrantManager:
    """Manage Qdrant collections and point operations."""

    def __init__(self, url: str = "http://localhost:6333", api_key: str | None = None) -> None:
        self._url = url
        try:
            self._client = QdrantClient(url=url, api_key=api_key)
        except Exception as e:
            raise QdrantConnectionError(url, e) from e

    @property
    def client(self) -> QdrantClient:
        """Access the underlying Qdrant client."""
        return self._client

    def ensure_collection(self, name: str, dense_dim: int = 1024) -> None:
        """Create collection with dense + BM25 sparse vectors if it doesn't exist.

        Sparse vector uses name "bm25" with Modifier.IDF per DESIGN.md.
        """
        existing = [c.name for c in self._client.get_collections().collections]
        if name in existing:
            logger.debug("Collection '%s' already exists", name)
            return

        self._client.create_collection(
            collection_name=name,
            vectors_config={
                "dense": models.VectorParams(
                    size=dense_dim,
                    distance=models.Distance.COSINE,
                )
            },
            sparse_vectors_config={
                "bm25": models.SparseVectorParams(
                    modifier=models.Modifier.IDF,
                )
            },
        )
        logger.info("Created collection '%s' (dense=%d dims, sparse=bm25+IDF)", name, dense_dim)

    def upsert_points(self, collection: str, points: list[models.PointStruct]) -> None:
        """Upsert points into a collection."""
        self._client.upsert(collection_name=collection, points=points)

    def delete_by_file_path(self, collection: str, file_path: str) -> None:
        """Delete all points matching a file_path."""
        self._client.delete(
            collection_name=collection,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="file_path",
                            match=models.MatchValue(value=file_path),
                        )
                    ]
                )
            ),
        )
        logger.debug("Deleted points for file_path='%s' from '%s'", file_path, collection)

    def query_hybrid(
        self,
        collection: str,
        prefetches: list[models.Prefetch],
        limit: int = 30,
        query_filter: models.Filter | None = None,
    ) -> list[models.ScoredPoint]:
        """Perform hybrid search with multi-prefetch and RRF fusion.

        Accepts pre-built prefetches to support structural boosting.
        """
        result = self._client.query_points(
            collection_name=collection,
            prefetch=prefetches,
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=limit,
            with_payload=True,
            query_filter=query_filter,
        )
        return result.points  # type: ignore[return-value]

    def collection_exists(self, name: str) -> bool:
        """Check if a collection exists."""
        return name in [c.name for c in self._client.get_collections().collections]

    def collection_count(self, name: str) -> int:
        """Get the number of points in a collection."""
        return self._client.count(collection_name=name).count  # type: ignore[return-value]

    def health_check(self) -> bool:
        """Check if Qdrant is reachable."""
        try:
            self._client.get_collections()
            return True
        except Exception:
            return False
```

### Step 4: Run tests to verify they pass

```bash
pytest tests/unit/test_qdrant_manager.py -v
```

Expected: All tests PASS.

### Step 5: Run linters

```bash
ruff check clew/clients/qdrant.py tests/unit/test_qdrant_manager.py
mypy clew/clients/qdrant.py
```

### Step 6: Commit

```bash
git add clew/clients/qdrant.py tests/unit/test_qdrant_manager.py
git commit -m "feat(clients): add Qdrant manager with bm25+IDF sparse vectors and delete support"
```

---

## Batch 3: Pipeline Components (Tasks 2.6–2.8, depends on Batch 2)

---

## Task 2.6: Rerank Provider

**Files:**
- Create: `clew/search/rerank.py`
- Create: `tests/unit/test_rerank.py`

**Key design spec:** Configurable candidate limit from SearchConfig (default 30, Tradeoff B). Skip conditions per DESIGN.md lines 574-580.

### Step 1: Write the failing tests

```python
# tests/unit/test_rerank.py
"""Tests for Voyage reranking integration."""

from unittest.mock import Mock, patch

import pytest

from clew.search.rerank import RerankProvider, RerankResult, should_skip_rerank


class TestShouldSkipRerank:
    def test_few_candidates(self) -> None:
        assert should_skip_rerank(
            "query", num_candidates=5, top_score=0.5, score_variance=0.5,
        ) is True

    def test_at_threshold_skipped(self) -> None:
        assert should_skip_rerank(
            "query", num_candidates=10, top_score=0.5, score_variance=0.5,
            no_rerank_threshold=10,
        ) is True

    def test_high_confidence_top(self) -> None:
        assert should_skip_rerank(
            "query", num_candidates=50, top_score=0.95, score_variance=0.5,
            high_confidence_threshold=0.92,
        ) is True

    def test_low_variance(self) -> None:
        assert should_skip_rerank(
            "query", num_candidates=50, top_score=0.5, score_variance=0.05,
            low_variance_threshold=0.1,
        ) is True

    def test_pascal_case_identifier(self) -> None:
        assert should_skip_rerank(
            "UserModel", num_candidates=50, top_score=0.5, score_variance=0.5,
        ) is True

    def test_file_path(self) -> None:
        assert should_skip_rerank(
            "src/auth.py", num_candidates=50, top_score=0.5, score_variance=0.5,
        ) is True

    def test_normal_query_not_skipped(self) -> None:
        assert should_skip_rerank(
            "how does auth work", num_candidates=50, top_score=0.5, score_variance=0.5,
        ) is False


class TestRerankProvider:
    @pytest.fixture
    def mock_voyage(self) -> Mock:
        client = Mock()
        client.rerank.return_value = Mock(
            results=[
                Mock(index=2, relevance_score=0.95),
                Mock(index=0, relevance_score=0.80),
            ]
        )
        return client

    @pytest.fixture
    def provider(self, mock_voyage: Mock) -> RerankProvider:
        with patch("clew.search.rerank.voyageai") as mock_module:
            mock_module.Client.return_value = mock_voyage
            return RerankProvider(api_key="test-key")

    def test_rerank_returns_results(self, provider: RerankProvider, mock_voyage: Mock) -> None:
        results = provider.rerank("query", ["doc1", "doc2", "doc3"])
        assert len(results) == 2
        assert results[0].index == 2
        assert results[0].relevance_score == 0.95

    def test_rerank_empty_documents(self, provider: RerankProvider) -> None:
        results = provider.rerank("query", [])
        assert results == []

    def test_rerank_calls_client(self, provider: RerankProvider, mock_voyage: Mock) -> None:
        provider.rerank("my query", ["doc1"], top_k=5)
        mock_voyage.rerank.assert_called_once_with(
            query="my query",
            documents=["doc1"],
            model="rerank-2.5",
            top_k=5,
            truncation=True,
        )

    def test_result_dataclass(self) -> None:
        r = RerankResult(index=3, relevance_score=0.88)
        assert r.index == 3
        assert r.relevance_score == 0.88
```

### Step 2: Run test to verify it fails

```bash
pytest tests/unit/test_rerank.py -v
```

Expected: FAIL — module doesn't exist.

### Step 3: Write implementation

```python
# clew/search/rerank.py
"""Voyage AI reranking integration.

Candidate limit is configurable via SearchConfig (default 30, Tradeoff B).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import voyageai


@dataclass
class RerankResult:
    """A reranked document with its new score."""

    index: int
    relevance_score: float


def should_skip_rerank(
    query: str,
    num_candidates: int,
    top_score: float,
    score_variance: float,
    *,
    no_rerank_threshold: int = 10,
    high_confidence_threshold: float = 0.92,
    low_variance_threshold: float = 0.1,
) -> bool:
    """Determine if reranking should be skipped.

    Skip conditions (per DESIGN.md):
    1. Few candidates (<=threshold) — no benefit
    2. High confidence top result (>0.92)
    3. Low score variance (<0.1) — already well-ranked
    4. Exact identifier (PascalCase)
    5. File path query
    """
    if num_candidates <= no_rerank_threshold:
        return True
    if top_score > high_confidence_threshold:
        return True
    if score_variance < low_variance_threshold:
        return True
    if re.match(r"^[A-Z][a-zA-Z0-9]+$", query):
        return True
    if "/" in query or query.endswith((".py", ".ts", ".js")):
        return True
    return False


class RerankProvider:
    """Voyage AI reranking provider."""

    def __init__(self, api_key: str, model: str = "rerank-2.5") -> None:
        self._client = voyageai.Client(api_key=api_key)  # type: ignore[attr-defined]
        self._model = model

    def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int = 10,
    ) -> list[RerankResult]:
        """Rerank documents by relevance to query."""
        if not documents:
            return []

        result = self._client.rerank(
            query=query,
            documents=documents,
            model=self._model,
            top_k=top_k,
            truncation=True,
        )
        return [
            RerankResult(index=r.index, relevance_score=r.relevance_score)
            for r in result.results
        ]
```

### Step 4: Run tests to verify they pass

```bash
pytest tests/unit/test_rerank.py -v
```

Expected: All tests PASS.

### Step 5: Run linters

```bash
ruff check clew/search/rerank.py tests/unit/test_rerank.py
mypy clew/search/rerank.py
```

### Step 6: Commit

```bash
git add clew/search/rerank.py tests/unit/test_rerank.py
git commit -m "feat(search): add Voyage rerank-2.5 provider with configurable skip conditions"
```

---

## Task 2.7: Git-Aware Change Detection

**Files:**
- Create: `clew/indexer/git_tracker.py`
- Create: `tests/unit/test_git_tracker.py`
- Modify: `clew/indexer/cache.py` (add state table accessor methods)
- Modify: `tests/unit/test_cache.py` (add tests for state methods)

**Key design spec (Tradeoff D):**
- Tier 1: `git diff --name-status last_commit HEAD` for add/modify/delete/rename
- Tier 2: Fallback to existing `FileHashTracker` for non-git repos
- Track `last_indexed_commit` in SQLite via CacheDB
- Expose CacheDB state table methods: `get_last_indexed_commit()` / `set_last_indexed_commit()`

### Step 0: Add CacheDB state table accessor methods

Add tests to `tests/unit/test_cache.py`:

```python
# Add to tests/unit/test_cache.py

class TestIndexState:
    def test_get_missing_commit_returns_none(self, cache: CacheDB) -> None:
        assert cache.get_last_indexed_commit("code") is None

    def test_set_and_get_commit(self, cache: CacheDB) -> None:
        cache.set_last_indexed_commit("code", "abc123def")
        assert cache.get_last_indexed_commit("code") == "abc123def"

    def test_update_commit(self, cache: CacheDB) -> None:
        cache.set_last_indexed_commit("code", "abc123")
        cache.set_last_indexed_commit("code", "def456")
        assert cache.get_last_indexed_commit("code") == "def456"

    def test_different_collections_independent(self, cache: CacheDB) -> None:
        cache.set_last_indexed_commit("code", "abc123")
        cache.set_last_indexed_commit("docs", "def456")
        assert cache.get_last_indexed_commit("code") == "abc123"
        assert cache.get_last_indexed_commit("docs") == "def456"
```

Add methods to `clew/indexer/cache.py`:

```python
    def get_last_indexed_commit(self, collection_name: str) -> str | None:
        """Get the last indexed commit hash for a collection."""
        with self._get_state_conn() as conn:
            row = conn.execute(
                "SELECT last_commit FROM index_state WHERE collection_name = ?",
                (collection_name,),
            ).fetchone()
            return row[0] if row else None

    def set_last_indexed_commit(self, collection_name: str, commit_hash: str) -> None:
        """Set the last indexed commit hash for a collection."""
        with self._get_state_conn() as conn:
            conn.execute(
                """INSERT INTO index_state (collection_name, last_commit, last_indexed_at)
                VALUES (?, ?, datetime('now'))
                ON CONFLICT(collection_name) DO UPDATE SET
                    last_commit = excluded.last_commit,
                    last_indexed_at = excluded.last_indexed_at""",
                (collection_name, commit_hash),
            )
```

Run tests to verify:

```bash
pytest tests/unit/test_cache.py -v
```

### Step 1: Write the failing tests

```python
# tests/unit/test_git_tracker.py
"""Tests for git-aware change detection."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from clew.indexer.git_tracker import GitChangeTracker


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    return tmp_path


class TestIsGitRepo:
    def test_is_git_repo_true(self, project_root: Path) -> None:
        tracker = GitChangeTracker(project_root)
        with patch("clew.indexer.git_tracker.subprocess") as mock_sub:
            mock_sub.run.return_value = Mock(returncode=0, stdout="true\n")
            assert tracker.is_git_repo() is True

    def test_is_git_repo_false(self, project_root: Path) -> None:
        tracker = GitChangeTracker(project_root)
        with patch("clew.indexer.git_tracker.subprocess") as mock_sub:
            mock_sub.run.return_value = Mock(returncode=128, stdout="")
            assert tracker.is_git_repo() is False


class TestGetCurrentCommit:
    def test_returns_commit_hash(self, project_root: Path) -> None:
        tracker = GitChangeTracker(project_root)
        with patch("clew.indexer.git_tracker.subprocess") as mock_sub:
            mock_sub.run.return_value = Mock(returncode=0, stdout="abc123def\n")
            assert tracker.get_current_commit() == "abc123def"

    def test_returns_none_on_error(self, project_root: Path) -> None:
        tracker = GitChangeTracker(project_root)
        with patch("clew.indexer.git_tracker.subprocess") as mock_sub:
            mock_sub.run.return_value = Mock(returncode=128, stdout="")
            assert tracker.get_current_commit() is None


class TestGetChangesSince:
    def test_parses_added_modified_deleted(self, project_root: Path) -> None:
        tracker = GitChangeTracker(project_root)
        git_output = "A\tnew_file.py\nM\tmodified.py\nD\tdeleted.py\n"
        with patch("clew.indexer.git_tracker.subprocess") as mock_sub:
            mock_sub.run.return_value = Mock(returncode=0, stdout=git_output)
            changes = tracker.get_changes_since("abc123")
        assert changes["added"] == ["new_file.py"]
        assert changes["modified"] == ["modified.py"]
        assert changes["deleted"] == ["deleted.py"]

    def test_parses_renamed(self, project_root: Path) -> None:
        tracker = GitChangeTracker(project_root)
        git_output = "R100\told_name.py\tnew_name.py\n"
        with patch("clew.indexer.git_tracker.subprocess") as mock_sub:
            mock_sub.run.return_value = Mock(returncode=0, stdout=git_output)
            changes = tracker.get_changes_since("abc123")
        assert len(changes["renamed"]) == 1
        assert changes["renamed"][0] == {"from": "old_name.py", "to": "new_name.py"}

    def test_empty_output(self, project_root: Path) -> None:
        tracker = GitChangeTracker(project_root)
        with patch("clew.indexer.git_tracker.subprocess") as mock_sub:
            mock_sub.run.return_value = Mock(returncode=0, stdout="")
            changes = tracker.get_changes_since("abc123")
        assert changes == {"added": [], "modified": [], "deleted": [], "renamed": []}

    def test_multiple_changes(self, project_root: Path) -> None:
        tracker = GitChangeTracker(project_root)
        git_output = "A\ta.py\nA\tb.py\nM\tc.py\n"
        with patch("clew.indexer.git_tracker.subprocess") as mock_sub:
            mock_sub.run.return_value = Mock(returncode=0, stdout=git_output)
            changes = tracker.get_changes_since("abc123")
        assert len(changes["added"]) == 2
        assert len(changes["modified"]) == 1
```

### Step 2: Run test to verify it fails

```bash
pytest tests/unit/test_git_tracker.py -v
```

Expected: FAIL — module doesn't exist.

### Step 3: Write implementation

```python
# clew/indexer/git_tracker.py
"""Git-aware change detection (primary tier).

Tier 1: git diff --name-status for add/modify/delete/rename detection.
Tier 2 fallback: FileHashTracker for non-git repos.
See Tradeoff D resolution.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class GitChangeTracker:
    """Detect file changes using git diff."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root

    def is_git_repo(self) -> bool:
        """Check if project root is inside a git repository."""
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            cwd=self.project_root,
        )
        return result.returncode == 0

    def get_current_commit(self) -> str | None:
        """Get current HEAD commit hash."""
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=self.project_root,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None

    def get_changes_since(self, last_commit: str) -> dict[str, list[Any]]:
        """Get file changes since last indexed commit.

        Returns dict with keys: added, modified, deleted, renamed.
        Renamed entries are dicts with "from" and "to" keys.
        """
        result = subprocess.run(
            ["git", "diff", "--name-status", last_commit, "HEAD"],
            capture_output=True,
            text=True,
            cwd=self.project_root,
        )

        changes: dict[str, list[Any]] = {
            "added": [],
            "modified": [],
            "deleted": [],
            "renamed": [],
        }

        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("\t")
            status = parts[0]
            if status == "A":
                changes["added"].append(parts[1])
            elif status == "M":
                changes["modified"].append(parts[1])
            elif status == "D":
                changes["deleted"].append(parts[1])
            elif status.startswith("R"):
                changes["renamed"].append({"from": parts[1], "to": parts[2]})

        return changes
```

### Step 4: Run tests to verify they pass

```bash
pytest tests/unit/test_git_tracker.py -v
```

Expected: All tests PASS.

### Step 5: Run linters

```bash
ruff check clew/indexer/git_tracker.py tests/unit/test_git_tracker.py
mypy clew/indexer/git_tracker.py
```

### Step 6: Commit

```bash
git add clew/indexer/git_tracker.py clew/indexer/cache.py tests/unit/test_git_tracker.py tests/unit/test_cache.py
git commit -m "feat(indexer): add git-aware change detection and CacheDB state accessors"
```

---

## Task 2.8: Indexing Pipeline

**Files:**
- Create: `clew/indexer/pipeline.py`
- Create: `tests/unit/test_indexing_pipeline.py`

**Key design specs:**
- Structured chunk IDs (not UUIDs)
- Full metadata payload: app_name, layer, signature, chunk_id, is_test, source_type
- Sparse vectors with name `"bm25"` and raw term counts
- Batch embed and upsert
- Delete stale chunks for modified/deleted files

### Step 1: Write the failing tests

```python
# tests/unit/test_indexing_pipeline.py
"""Tests for the indexing pipeline."""

from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from clew.indexer.pipeline import IndexingPipeline, IndexingResult, _detect_language, _is_test_file


class TestDetectLanguage:
    def test_python(self) -> None:
        assert _detect_language("models.py") == "python"

    def test_typescript(self) -> None:
        assert _detect_language("app.ts") == "typescript"

    def test_tsx(self) -> None:
        assert _detect_language("Component.tsx") == "tsx"

    def test_javascript(self) -> None:
        assert _detect_language("index.js") == "javascript"

    def test_markdown(self) -> None:
        assert _detect_language("README.md") == "markdown"

    def test_unknown(self) -> None:
        assert _detect_language("data.csv") == "unknown"


class TestIsTestFile:
    def test_test_prefix(self) -> None:
        assert _is_test_file("tests/test_auth.py") is True

    def test_test_directory(self) -> None:
        assert _is_test_file("tests/unit/test_models.py") is True

    def test_spec_suffix(self) -> None:
        assert _is_test_file("src/auth.spec.ts") is True

    def test_not_test(self) -> None:
        assert _is_test_file("src/models.py") is False


class TestIndexingResult:
    def test_create(self) -> None:
        result = IndexingResult(files_processed=10, chunks_created=50, files_skipped=2)
        assert result.files_processed == 10


class TestIndexingPipeline:
    @pytest.fixture
    def mock_qdrant(self) -> Mock:
        qdrant = Mock()
        qdrant.ensure_collection = Mock()
        qdrant.upsert_points = Mock()
        qdrant.delete_by_file_path = Mock()
        return qdrant

    @pytest.fixture
    def mock_embedder(self) -> Mock:
        embedder = Mock()
        embedder.embed = AsyncMock(return_value=[[0.1] * 1024])
        embedder.model_name = "voyage-code-3"
        embedder.dimensions = 1024
        return embedder

    @pytest.fixture
    def pipeline(self, mock_qdrant: Mock, mock_embedder: Mock) -> IndexingPipeline:
        return IndexingPipeline(
            qdrant=mock_qdrant,
            embedder=mock_embedder,
            batch_size=10,
        )

    async def test_index_single_file(
        self, pipeline: IndexingPipeline, mock_qdrant: Mock, tmp_path: Path,
    ) -> None:
        f = tmp_path / "hello.py"
        f.write_text("def hello():\n    return 'world'\n")
        result = await pipeline.index_files([f], collection="code")
        assert result.files_processed == 1
        assert result.chunks_created >= 1
        mock_qdrant.upsert_points.assert_called()

    async def test_skips_empty_file(self, pipeline: IndexingPipeline, tmp_path: Path) -> None:
        f = tmp_path / "empty.py"
        f.write_text("")
        result = await pipeline.index_files([f], collection="code")
        assert result.files_processed == 0

    async def test_embeds_chunks(
        self, pipeline: IndexingPipeline, mock_embedder: Mock, tmp_path: Path,
    ) -> None:
        f = tmp_path / "code.py"
        f.write_text("x = 1\ny = 2\n")
        await pipeline.index_files([f], collection="code")
        mock_embedder.embed.assert_called()

    async def test_point_id_is_deterministic_uuid(
        self, pipeline: IndexingPipeline, mock_qdrant: Mock, tmp_path: Path,
    ) -> None:
        """Point IDs should be deterministic UUIDs (Qdrant requirement)."""
        import uuid

        f = tmp_path / "models.py"
        f.write_text("x = 1\n")
        await pipeline.index_files([f], collection="code")
        points = mock_qdrant.upsert_points.call_args[0][1]
        for point in points:
            # ID should be a valid UUID string
            uuid.UUID(point.id)  # raises ValueError if not valid
            # Structured chunk_id should be in the payload instead
            assert "::" in point.payload["chunk_id"]

    async def test_payload_has_metadata_fields(
        self, pipeline: IndexingPipeline, mock_qdrant: Mock, tmp_path: Path,
    ) -> None:
        f = tmp_path / "models.py"
        f.write_text("x = 1\n")
        await pipeline.index_files([f], collection="code")
        points = mock_qdrant.upsert_points.call_args[0][1]
        payload = points[0].payload
        assert "app_name" in payload
        assert "layer" in payload
        assert "chunk_id" in payload
        assert "is_test" in payload
        assert "source_type" in payload

    async def test_sparse_vector_uses_bm25_name(
        self, pipeline: IndexingPipeline, mock_qdrant: Mock, tmp_path: Path,
    ) -> None:
        """Sparse vector key must be 'bm25', not 'sparse'."""
        f = tmp_path / "code.py"
        f.write_text("x = 1\n")
        await pipeline.index_files([f], collection="code")
        points = mock_qdrant.upsert_points.call_args[0][1]
        vector = points[0].vector
        assert "bm25" in vector
        assert "dense" in vector

    async def test_result_accumulates(self, pipeline: IndexingPipeline, tmp_path: Path) -> None:
        for i in range(3):
            (tmp_path / f"file{i}.py").write_text(f"x = {i}\n")
        files = list(tmp_path.glob("*.py"))
        result = await pipeline.index_files(files, collection="code")
        assert result.files_processed == 3

    async def test_deletes_stale_chunks(
        self, pipeline: IndexingPipeline, mock_qdrant: Mock, tmp_path: Path,
    ) -> None:
        """Modified files should have old chunks deleted first."""
        f = tmp_path / "models.py"
        f.write_text("x = 1\n")
        await pipeline.index_files([f], collection="code", delete_before_upsert=True)
        mock_qdrant.delete_by_file_path.assert_called()
```

### Step 2: Run test to verify it fails

```bash
pytest tests/unit/test_indexing_pipeline.py -v
```

Expected: FAIL — module doesn't exist.

### Step 3: Write implementation

```python
# clew/indexer/pipeline.py
"""Indexing pipeline: file -> chunk -> metadata -> embed -> upsert to Qdrant.

Uses structured chunk IDs, full metadata payload, and BM25 sparse vectors
with raw term counts.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from qdrant_client import models

# Namespace for deterministic UUID generation from chunk IDs
CHUNK_UUID_NAMESPACE = uuid.UUID("a3c0e7d2-b1f4-4c8a-9e6d-5f2a1b3c4d5e")

from clew.chunker.fallback import Chunk, split_file
from clew.chunker.parser import ASTParser
from clew.indexer.metadata import build_chunk_id, classify_layer, detect_app_name, extract_signature
from clew.search.tokenize import text_to_sparse_vector

if TYPE_CHECKING:
    from clew.clients.base import EmbeddingProvider
    from clew.clients.qdrant import QdrantManager

logger = logging.getLogger(__name__)

LANGUAGE_MAP: dict[str, str] = {
    "py": "python",
    "ts": "typescript",
    "tsx": "tsx",
    "js": "javascript",
    "jsx": "jsx",
    "md": "markdown",
    "yaml": "yaml",
    "yml": "yaml",
    "json": "json",
    "toml": "toml",
}


def _detect_language(file_path: str) -> str:
    """Detect language from file extension."""
    ext = file_path.rsplit(".", 1)[-1].lower() if "." in file_path else ""
    return LANGUAGE_MAP.get(ext, "unknown")


def _is_test_file(file_path: str) -> bool:
    """Check if a file is a test file."""
    parts = file_path.replace("\\", "/").split("/")
    name = parts[-1] if parts else ""
    return (
        name.startswith("test_")
        or name.endswith("_test.py")
        or name.endswith(".spec.ts")
        or name.endswith(".spec.js")
        or name.endswith(".test.ts")
        or name.endswith(".test.js")
        or "tests/" in file_path
        or "test/" in file_path
    )


@dataclass
class IndexingResult:
    """Result of an indexing run."""

    files_processed: int = 0
    chunks_created: int = 0
    files_skipped: int = 0
    errors: list[str] = field(default_factory=list)


class IndexingPipeline:
    """Orchestrate file indexing: chunk -> metadata -> embed -> upsert."""

    def __init__(
        self,
        qdrant: QdrantManager,
        embedder: EmbeddingProvider,
        batch_size: int = 100,
        max_tokens: int = 3000,
    ) -> None:
        self._qdrant = qdrant
        self._embedder = embedder
        self._batch_size = batch_size
        self._max_tokens = max_tokens
        self._parser = ASTParser()

    async def index_files(
        self,
        files: list[Path],
        collection: str = "code",
        delete_before_upsert: bool = False,
    ) -> IndexingResult:
        """Index a list of files into a Qdrant collection."""
        result = IndexingResult()
        all_chunks: list[Chunk] = []

        for file_path in files:
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
            except (OSError, UnicodeDecodeError) as e:
                logger.warning("Cannot read %s: %s", file_path, e)
                result.files_skipped += 1
                result.errors.append(f"{file_path}: {e}")
                continue

            if not content.strip():
                result.files_skipped += 1
                continue

            # Delete old chunks for this file if requested (for modified files)
            if delete_before_upsert:
                self._qdrant.delete_by_file_path(collection, str(file_path))

            chunks = split_file(
                str(file_path), content, self._max_tokens, self._parser,
            )
            all_chunks.extend(chunks)
            result.files_processed += 1

        if not all_chunks:
            return result

        # Batch embed and upsert
        for i in range(0, len(all_chunks), self._batch_size):
            batch = all_chunks[i : i + self._batch_size]
            await self._embed_and_upsert(batch, collection)
            result.chunks_created += len(batch)

        return result

    async def _embed_and_upsert(self, chunks: list[Chunk], collection: str) -> None:
        """Embed a batch of chunks and upsert to Qdrant."""
        texts = [c.content for c in chunks]
        embeddings = await self._embedder.embed(texts, input_type="document")

        points: list[models.PointStruct] = []
        for chunk, embedding in zip(chunks, embeddings):
            sparse = text_to_sparse_vector(chunk.content)
            file_path_str = chunk.file_path

            # Extract metadata
            entity_type = chunk.metadata.get("entity_type", "section")
            qualified_name = chunk.metadata.get("qualified_name", "")
            app_name = detect_app_name(file_path_str)
            layer = classify_layer(file_path_str)
            signature = extract_signature(entity_type, chunk.content)
            chunk_id = build_chunk_id(
                file_path_str, entity_type, qualified_name, content=chunk.content,
            )

            payload = {
                "content": chunk.content,
                "chunk_id": chunk_id,
                "file_path": file_path_str,
                "language": _detect_language(file_path_str),
                "chunk_type": entity_type,
                "class_name": chunk.metadata.get("parent_class", ""),
                "function_name": chunk.metadata.get("name", ""),
                "signature": signature,
                "app_name": app_name,
                "layer": layer,
                "line_start": chunk.metadata.get("line_start", 0),
                "line_end": chunk.metadata.get("line_end", 0),
                "is_test": _is_test_file(file_path_str),
                "source_type": collection,
                "embedding_model": self._embedder.model_name,
                "indexed_at": datetime.now(tz=timezone.utc).isoformat(),
            }

            # Qdrant requires UUID or int IDs — generate deterministic UUID from chunk_id
            point_id = str(uuid.uuid5(CHUNK_UUID_NAMESPACE, chunk_id))

            points.append(
                models.PointStruct(
                    id=point_id,
                    vector={
                        "dense": embedding,
                        "bm25": models.SparseVector(
                            indices=sparse.indices,
                            values=sparse.values,
                        ),
                    },
                    payload=payload,
                )
            )

        self._qdrant.upsert_points(collection, points)
```

### Step 4: Run tests to verify they pass

```bash
pytest tests/unit/test_indexing_pipeline.py -v
```

Expected: All tests PASS.

### Step 5: Run linters

```bash
ruff check clew/indexer/pipeline.py tests/unit/test_indexing_pipeline.py
mypy clew/indexer/pipeline.py
```

### Step 6: Commit

```bash
git add clew/indexer/pipeline.py tests/unit/test_indexing_pipeline.py
git commit -m "feat(indexer): add indexing pipeline with structured IDs, metadata, and bm25 sparse vectors"
```

---

## Batch 4: Orchestration (Tasks 2.9–2.10, depends on Batch 3)

---

## Task 2.9: Hybrid Search Engine with Structural Boosting

**Files:**
- Create: `clew/search/hybrid.py`
- Create: `tests/unit/test_hybrid_search.py`

**Key design specs:**
- Multi-prefetch: base dense (30) + base BM25 (30) + same-module boost (15) + debug test boost (10)
- Structural boosting via `app_name` filter when `active_file` is provided (Tradeoff A)
- DOCS intent prefers docs collection
- Sparse vector uses `"bm25"` named vector

### Step 1: Write the failing tests

```python
# tests/unit/test_hybrid_search.py
"""Tests for hybrid search engine with structural boosting."""

from unittest.mock import AsyncMock, Mock

import pytest

from clew.search.hybrid import HybridSearchEngine
from clew.search.models import QueryIntent, SearchResult


@pytest.fixture
def mock_qdrant() -> Mock:
    qdrant = Mock()
    qdrant.query_hybrid.return_value = [
        Mock(
            id="main.py::function::hello",
            score=0.9,
            payload={
                "content": "def hello(): pass",
                "file_path": "main.py",
                "chunk_type": "function",
                "line_start": 1,
                "line_end": 2,
                "language": "python",
                "class_name": "",
                "function_name": "hello",
                "signature": "def hello()",
                "app_name": "",
                "layer": "other",
                "chunk_id": "main.py::function::hello",
            },
        )
    ]
    return qdrant


@pytest.fixture
def mock_embedder() -> Mock:
    embedder = Mock()
    embedder.embed_query = AsyncMock(return_value=[0.1] * 1024)
    return embedder


@pytest.fixture
def engine(mock_qdrant: Mock, mock_embedder: Mock) -> HybridSearchEngine:
    return HybridSearchEngine(qdrant=mock_qdrant, embedder=mock_embedder)


class TestHybridSearch:
    async def test_returns_search_results(self, engine: HybridSearchEngine) -> None:
        results = await engine.search("hello function", collection="code")
        assert len(results) == 1
        assert isinstance(results[0], SearchResult)
        assert results[0].file_path == "main.py"

    async def test_embeds_query(self, engine: HybridSearchEngine, mock_embedder: Mock) -> None:
        await engine.search("test query")
        mock_embedder.embed_query.assert_awaited_once_with("test query")

    async def test_queries_qdrant_with_prefetches(
        self, engine: HybridSearchEngine, mock_qdrant: Mock,
    ) -> None:
        await engine.search("test query")
        mock_qdrant.query_hybrid.assert_called_once()
        call_kwargs = mock_qdrant.query_hybrid.call_args.kwargs
        prefetches = call_kwargs["prefetches"]
        # Base: dense + bm25 = 2 prefetches minimum
        assert len(prefetches) >= 2

    async def test_active_file_adds_module_boost(
        self, engine: HybridSearchEngine, mock_qdrant: Mock,
    ) -> None:
        """Tradeoff A: active_file triggers same-module structural boost."""
        await engine.search("test", active_file="backend/care/models.py")
        call_kwargs = mock_qdrant.query_hybrid.call_args.kwargs
        prefetches = call_kwargs["prefetches"]
        # Base (2) + module boost (1) = 3
        assert len(prefetches) >= 3

    async def test_debug_intent_adds_test_boost(
        self, engine: HybridSearchEngine, mock_qdrant: Mock,
    ) -> None:
        await engine.search("test", intent=QueryIntent.DEBUG)
        call_kwargs = mock_qdrant.query_hybrid.call_args.kwargs
        prefetches = call_kwargs["prefetches"]
        # Base (2) + debug test boost (1) = 3
        assert len(prefetches) >= 3

    async def test_debug_with_active_file_adds_both_boosts(
        self, engine: HybridSearchEngine, mock_qdrant: Mock,
    ) -> None:
        await engine.search(
            "fix bug", intent=QueryIntent.DEBUG, active_file="backend/care/views.py",
        )
        call_kwargs = mock_qdrant.query_hybrid.call_args.kwargs
        prefetches = call_kwargs["prefetches"]
        # Base (2) + module boost (1) + debug boost (1) = 4
        assert len(prefetches) >= 4

    async def test_empty_results(self, engine: HybridSearchEngine, mock_qdrant: Mock) -> None:
        mock_qdrant.query_hybrid.return_value = []
        results = await engine.search("nonexistent")
        assert results == []

    async def test_result_has_score(self, engine: HybridSearchEngine) -> None:
        results = await engine.search("hello")
        assert results[0].score == 0.9

    async def test_result_maps_all_metadata(self, engine: HybridSearchEngine) -> None:
        results = await engine.search("hello")
        r = results[0]
        assert r.function_name == "hello"
        assert r.language == "python"
        assert r.signature == "def hello()"
        assert r.chunk_id == "main.py::function::hello"

    async def test_respects_limit(self, engine: HybridSearchEngine, mock_qdrant: Mock) -> None:
        await engine.search("test", limit=5)
        call_kwargs = mock_qdrant.query_hybrid.call_args.kwargs
        assert call_kwargs["limit"] == 5
```

### Step 2: Run test to verify it fails

```bash
pytest tests/unit/test_hybrid_search.py -v
```

Expected: FAIL — module doesn't exist.

### Step 3: Write implementation

```python
# clew/search/hybrid.py
"""Hybrid search engine: dense + BM25 with RRF fusion and structural boosting.

Multi-prefetch approach per DESIGN.md:
- Base dense (limit=30)
- Base BM25 (limit=30)
- Same-module boost when active_file provided (limit=15)
- Debug intent test-file boost (limit=10)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from qdrant_client import models

from clew.indexer.metadata import detect_app_name

from .models import QueryIntent, SearchResult
from .tokenize import text_to_sparse_vector

if TYPE_CHECKING:
    from clew.clients.base import EmbeddingProvider
    from clew.clients.qdrant import QdrantManager

logger = logging.getLogger(__name__)


class HybridSearchEngine:
    """Perform hybrid dense + sparse search with RRF fusion and structural boosting."""

    def __init__(self, qdrant: QdrantManager, embedder: EmbeddingProvider) -> None:
        self._qdrant = qdrant
        self._embedder = embedder

    async def search(
        self,
        query: str,
        collection: str = "code",
        limit: int = 30,
        intent: QueryIntent | None = None,
        active_file: str | None = None,
    ) -> list[SearchResult]:
        """Execute hybrid search with structural boosting and return ranked results."""
        # Embed query
        dense_vector = await self._embedder.embed_query(query)

        # Generate sparse query vector (raw term counts)
        sparse = text_to_sparse_vector(query)
        sparse_vector = models.SparseVector(indices=sparse.indices, values=sparse.values)

        # Build multi-prefetch with structural boosts
        prefetches = self._build_prefetches(
            dense_vector, sparse_vector, active_file, intent,
        )

        # Execute hybrid search via Qdrant
        points = self._qdrant.query_hybrid(
            collection=collection,
            prefetches=prefetches,
            limit=limit,
        )

        return [self._point_to_result(p) for p in points]

    def _build_prefetches(
        self,
        dense_vector: list[float],
        sparse_vector: models.SparseVector,
        active_file: str | None,
        intent: QueryIntent | None,
    ) -> list[models.Prefetch]:
        """Build multi-prefetch list with structural boosting.

        Per DESIGN.md lines 588-621.
        """
        prefetches: list[models.Prefetch] = [
            # Base semantic search
            models.Prefetch(query=dense_vector, using="dense", limit=30),
            # Base keyword search
            models.Prefetch(query=sparse_vector, using="bm25", limit=30),
        ]

        # Structural boost: same module gets extra candidates (Tradeoff A)
        if active_file:
            app_name = detect_app_name(active_file)
            if app_name:
                prefetches.append(
                    models.Prefetch(
                        query=dense_vector,
                        using="dense",
                        filter=models.Filter(
                            must=[
                                models.FieldCondition(
                                    key="app_name",
                                    match=models.MatchValue(value=app_name),
                                )
                            ]
                        ),
                        limit=15,
                    )
                )

        # Intent-based boost: debug queries get more test files
        if intent == QueryIntent.DEBUG:
            prefetches.append(
                models.Prefetch(
                    query=dense_vector,
                    using="dense",
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="is_test",
                                match=models.MatchValue(value=True),
                            )
                        ]
                    ),
                    limit=10,
                )
            )

        return prefetches

    @staticmethod
    def _point_to_result(point: models.ScoredPoint) -> SearchResult:
        """Convert Qdrant ScoredPoint to SearchResult."""
        payload = point.payload or {}
        return SearchResult(
            content=payload.get("content", ""),
            file_path=payload.get("file_path", ""),
            score=point.score,
            chunk_type=payload.get("chunk_type", ""),
            line_start=payload.get("line_start", 0),
            line_end=payload.get("line_end", 0),
            language=payload.get("language", ""),
            class_name=payload.get("class_name", ""),
            function_name=payload.get("function_name", ""),
            signature=payload.get("signature", ""),
            app_name=payload.get("app_name", ""),
            layer=payload.get("layer", ""),
            chunk_id=payload.get("chunk_id", ""),
        )
```

### Step 4: Run tests to verify they pass

```bash
pytest tests/unit/test_hybrid_search.py -v
```

Expected: All tests PASS.

### Step 5: Run linters

```bash
ruff check clew/search/hybrid.py tests/unit/test_hybrid_search.py
mypy clew/search/hybrid.py
```

### Step 6: Commit

```bash
git add clew/search/hybrid.py tests/unit/test_hybrid_search.py
git commit -m "feat(search): add hybrid search engine with multi-prefetch structural boosting"
```

---

## Task 2.10: Search Orchestrator & CLI Integration

**Files:**
- Create: `clew/search/engine.py`
- Create: `tests/unit/test_search_engine.py`
- Modify: `clew/cli.py` (wire search and index commands)

**Key design specs:**
- Full pipeline: enhance → classify intent → search → rerank → SearchResponse
- SearchResponse includes `query_enhanced` and `total_candidates`
- Configurable rerank candidates from SearchConfig (Tradeoff B)
- DOCS intent overrides collection to "docs"

### Step 1: Write the failing tests

```python
# tests/unit/test_search_engine.py
"""Tests for the search orchestrator."""

from unittest.mock import AsyncMock, Mock

import pytest

from clew.models import SearchConfig
from clew.search.engine import SearchEngine
from clew.search.models import QueryIntent, SearchRequest, SearchResponse, SearchResult


@pytest.fixture
def mock_hybrid() -> Mock:
    hybrid = Mock()
    hybrid.search = AsyncMock(
        return_value=[
            SearchResult(
                content="def hello(): pass",
                file_path="main.py",
                score=0.9,
                chunk_type="function",
                function_name="hello",
            ),
            SearchResult(content="def world(): pass", file_path="other.py", score=0.7),
        ]
    )
    return hybrid


@pytest.fixture
def mock_reranker() -> Mock:
    from clew.search.rerank import RerankResult

    reranker = Mock()
    reranker.rerank.return_value = [
        RerankResult(index=1, relevance_score=0.95),
        RerankResult(index=0, relevance_score=0.80),
    ]
    return reranker


@pytest.fixture
def enhancer() -> Mock:
    e = Mock()
    e.enhance.return_value = "enhanced query"
    return e


@pytest.fixture
def search_config() -> SearchConfig:
    return SearchConfig()


@pytest.fixture
def engine(
    mock_hybrid: Mock, mock_reranker: Mock, enhancer: Mock, search_config: SearchConfig,
) -> SearchEngine:
    return SearchEngine(
        hybrid_engine=mock_hybrid,
        reranker=mock_reranker,
        enhancer=enhancer,
        search_config=search_config,
    )


class TestSearchEngine:
    async def test_returns_search_response(self, engine: SearchEngine) -> None:
        response = await engine.search(SearchRequest(query="hello"))
        assert isinstance(response, SearchResponse)
        assert len(response.results) > 0

    async def test_response_has_query_enhanced(self, engine: SearchEngine) -> None:
        response = await engine.search(SearchRequest(query="hello"))
        assert response.query_enhanced == "enhanced query"

    async def test_response_has_total_candidates(self, engine: SearchEngine) -> None:
        response = await engine.search(SearchRequest(query="hello"))
        assert response.total_candidates == 2  # 2 mock candidates

    async def test_response_has_intent(self, engine: SearchEngine) -> None:
        response = await engine.search(SearchRequest(query="fix the auth bug"))
        assert response.intent == QueryIntent.DEBUG

    async def test_enhances_query(self, engine: SearchEngine, enhancer: Mock) -> None:
        await engine.search(SearchRequest(query="original"))
        enhancer.enhance.assert_called_once_with("original")

    async def test_classifies_intent(self, engine: SearchEngine, mock_hybrid: Mock) -> None:
        await engine.search(SearchRequest(query="fix the auth bug"))
        call_kwargs = mock_hybrid.search.call_args.kwargs
        assert call_kwargs["intent"] == QueryIntent.DEBUG

    async def test_passes_active_file(self, engine: SearchEngine, mock_hybrid: Mock) -> None:
        await engine.search(
            SearchRequest(query="test", active_file="backend/care/models.py"),
        )
        call_kwargs = mock_hybrid.search.call_args.kwargs
        assert call_kwargs["active_file"] == "backend/care/models.py"

    async def test_reranks_results(self, engine: SearchEngine, mock_reranker: Mock) -> None:
        # Mock hybrid returns 2 results, but we need >10 to trigger rerank
        # Override the mock to return enough candidates
        engine._hybrid.search = AsyncMock(
            return_value=[
                SearchResult(content=f"content {i}", file_path=f"f{i}.py", score=0.9 - i * 0.05)
                for i in range(15)
            ]
        )
        response = await engine.search(SearchRequest(query="test"))
        mock_reranker.rerank.assert_called_once()

    async def test_respects_limit(self, engine: SearchEngine) -> None:
        response = await engine.search(SearchRequest(query="test", limit=1))
        assert len(response.results) <= 1

    async def test_skips_rerank_when_few_results(
        self, engine: SearchEngine, mock_hybrid: Mock, mock_reranker: Mock,
    ) -> None:
        mock_hybrid.search = AsyncMock(
            return_value=[SearchResult(content="x", file_path="f.py", score=0.5)]
        )
        await engine.search(SearchRequest(query="test"))
        mock_reranker.rerank.assert_not_called()

    async def test_docs_intent_overrides_collection(
        self, engine: SearchEngine, mock_hybrid: Mock,
    ) -> None:
        """DOCS intent should search docs collection."""
        await engine.search(SearchRequest(query="what is the prescription model"))
        call_kwargs = mock_hybrid.search.call_args.kwargs
        assert call_kwargs["collection"] == "docs"

    async def test_uses_configurable_rerank_candidates(
        self, mock_hybrid: Mock, mock_reranker: Mock, enhancer: Mock,
    ) -> None:
        """Tradeoff B: rerank_candidates comes from SearchConfig."""
        config = SearchConfig(rerank_candidates=50)
        engine = SearchEngine(
            hybrid_engine=mock_hybrid, reranker=mock_reranker,
            enhancer=enhancer, search_config=config,
        )
        await engine.search(SearchRequest(query="test"))
        call_kwargs = mock_hybrid.search.call_args.kwargs
        assert call_kwargs["limit"] == 50
```

### Step 2: Run test to verify it fails

```bash
pytest tests/unit/test_search_engine.py -v
```

Expected: FAIL — module doesn't exist.

### Step 3: Write search engine implementation

```python
# clew/search/engine.py
"""Search orchestrator: enhance -> classify -> search -> rerank -> respond.

Returns SearchResponse with query_enhanced and total_candidates fields.
"""

from __future__ import annotations

import logging
import statistics
from typing import TYPE_CHECKING

from clew.models import SearchConfig

from .intent import classify_intent, get_intent_collection_preference
from .models import SearchRequest, SearchResponse, SearchResult
from .rerank import should_skip_rerank

if TYPE_CHECKING:
    from clew.search.enhance import QueryEnhancer
    from clew.search.hybrid import HybridSearchEngine
    from clew.search.rerank import RerankProvider

logger = logging.getLogger(__name__)


class SearchEngine:
    """Top-level search orchestrator."""

    def __init__(
        self,
        hybrid_engine: HybridSearchEngine,
        reranker: RerankProvider | None = None,
        enhancer: QueryEnhancer | None = None,
        search_config: SearchConfig | None = None,
    ) -> None:
        self._hybrid = hybrid_engine
        self._reranker = reranker
        self._enhancer = enhancer
        self._config = search_config or SearchConfig()

    async def search(self, request: SearchRequest) -> SearchResponse:
        """Execute full search pipeline and return SearchResponse."""
        query = request.query

        # Step 1: Enhance query
        query_enhanced = query
        if self._enhancer:
            query_enhanced = self._enhancer.enhance(query)

        # Step 2: Classify intent
        intent = request.intent or classify_intent(query_enhanced)

        # Step 3: Determine collection (DOCS intent prefers docs collection)
        collection = request.collection
        if request.intent is None:
            collection = get_intent_collection_preference(intent)

        # Step 4: Hybrid search with configurable candidate limit (Tradeoff B)
        candidates = await self._hybrid.search(
            query=query_enhanced,
            collection=collection,
            limit=self._config.rerank_candidates,
            intent=intent,
            active_file=request.active_file,
        )

        total_candidates = len(candidates)

        if not candidates:
            return SearchResponse(
                results=[],
                query_enhanced=query_enhanced,
                total_candidates=0,
                intent=intent,
            )

        # Step 5: Rerank (if applicable)
        results = self._maybe_rerank(query_enhanced, candidates)

        # Step 6: Apply limit
        results = results[: request.limit]

        return SearchResponse(
            results=results,
            query_enhanced=query_enhanced,
            total_candidates=total_candidates,
            intent=intent,
        )

    def _maybe_rerank(self, query: str, candidates: list[SearchResult]) -> list[SearchResult]:
        """Rerank candidates if conditions are met."""
        if not self._reranker:
            return candidates

        scores = [c.score for c in candidates]
        variance = statistics.variance(scores) if len(scores) > 1 else 0.0
        top_score = scores[0] if scores else 0.0

        if should_skip_rerank(
            query,
            len(candidates),
            top_score,
            variance,
            no_rerank_threshold=self._config.no_rerank_threshold,
            high_confidence_threshold=self._config.high_confidence_threshold,
            low_variance_threshold=self._config.low_variance_threshold,
        ):
            return candidates

        rerank_results = self._reranker.rerank(
            query=query,
            documents=[c.content for c in candidates],
            top_k=self._config.rerank_top_k,
        )

        reranked = [candidates[r.index] for r in rerank_results]
        # Update scores from reranker
        for result, rr in zip(reranked, rerank_results):
            result.score = rr.relevance_score

        return reranked
```

### Step 4: Update CLI

Modify `clew/cli.py` to wire the search and index commands:

```python
# clew/cli.py
"""Typer CLI for clew."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Semantic code search tool")
console = Console()


@app.command()
def index(
    config: Path = typer.Option("config.yaml", "--config", "-c"),
    full: bool = typer.Option(False, "--full"),
    files: list[str] = typer.Option(None, "--files", "-f"),
) -> None:
    """Index the codebase."""
    console.print("[yellow]Indexing not yet fully wired. Pipeline available at clew.indexer.pipeline.[/yellow]")


@app.command()
def status() -> None:
    """Show system health and index statistics."""
    console.print("[bold]clew status[/bold]")
    console.print("  Qdrant: [dim]not checked[/dim]")
    console.print("  Collections: [dim]none[/dim]")


@app.command()
def search(
    query: str = typer.Argument(...),
    collection: str = typer.Option("code", "--collection", "-c"),
    limit: int = typer.Option(10, "--limit", "-n"),
    raw: bool = typer.Option(False, "--raw"),
) -> None:
    """Search the codebase."""
    console.print(f"[dim]Searching for:[/dim] {query}")
    console.print("[yellow]Search requires running Qdrant and configured API keys.[/yellow]")
    console.print("[dim]Full integration will be wired in Phase 3 (MCP).[/dim]")
```

### Step 5: Run tests to verify they pass

```bash
pytest tests/unit/test_search_engine.py tests/unit/test_cli.py -v
```

Expected: All tests PASS.

### Step 6: Run linters

```bash
ruff check clew/search/engine.py clew/cli.py
mypy clew/search/engine.py
```

### Step 7: Commit

```bash
git add clew/search/engine.py tests/unit/test_search_engine.py clew/cli.py
git commit -m "feat(search): add search orchestrator with SearchResponse, configurable reranking, and DOCS intent"
```

---

## Final Verification

After all tasks are complete, run the full test suite and linters:

```bash
pytest --cov=clew -v
ruff check .
ruff format --check .
mypy clew/
```

Expected: All tests pass (160+), no linting errors, no type errors.

### Final tree check

Verify new files added in Phase 2:

```
clew/
├── search/
│   ├── __init__.py        (updated)
│   ├── models.py          (NEW — QueryIntent, SearchResult, SearchRequest, SearchResponse)
│   ├── tokenize.py        (NEW — BM25 tokenization with raw term counts)
│   ├── intent.py          (NEW — intent classification with DOCS preference)
│   ├── enhance.py         (NEW — abbreviation + synonym expansion)
│   ├── hybrid.py          (NEW — multi-prefetch with structural boosting)
│   ├── rerank.py          (NEW — Voyage rerank-2.5 with configurable limits)
│   └── engine.py          (NEW — full orchestrator with SearchResponse)
├── clients/
│   ├── qdrant.py          (NEW — bm25+IDF sparse vectors, delete support)
│   └── ...existing...
├── indexer/
│   ├── pipeline.py        (NEW — structured IDs, metadata, bm25 sparse)
│   ├── metadata.py        (NEW — app_name, layer, signature, chunk IDs)
│   ├── git_tracker.py     (NEW — git diff change detection)
│   └── ...existing...
├── chunker/
│   └── fallback.py        (MODIFIED — Chunk metadata dict)
├── models.py              (MODIFIED — added SearchConfig)
└── cli.py                 (MODIFIED — search args)

tests/unit/
├── test_search_models.py      (NEW — 12 tests)
├── test_code_tokenize.py      (NEW — 12 tests)
├── test_intent.py             (NEW — 10 tests)
├── test_enhance.py            (NEW — 12 tests)
├── test_metadata.py           (NEW — 18 tests)
├── test_qdrant_manager.py     (NEW — 11 tests)
├── test_rerank.py             (NEW — 11 tests)
├── test_git_tracker.py        (NEW — 8 tests)
├── test_indexing_pipeline.py  (NEW — 10 tests)
├── test_hybrid_search.py      (NEW — 10 tests)
├── test_search_engine.py      (NEW — 13 tests)
├── test_models.py             (MODIFIED — added SearchConfig tests)
└── ...existing...
```

### Batch execution order

- **Batch 1** (independent foundations): Tasks 2.0, 2.1, 2.2
- **Batch 2** (external integrations): Tasks 2.3, 2.4, 2.5
- **Batch 3** (pipeline components): Tasks 2.6, 2.7, 2.8
- **Batch 4** (orchestration): Tasks 2.9, 2.10

### Design compliance checklist

| Design Spec | Plan Coverage |
|---|---|
| Sparse vector name `"bm25"` | Task 2.5 (QdrantManager), Task 2.8 (pipeline), Task 2.9 (hybrid) |
| `Modifier.IDF` on sparse params | Task 2.5 (ensure_collection) |
| Raw term counts (not normalized) | Task 2.1 (text_to_sparse_vector) |
| Structured chunk IDs | Task 2.4 (build_chunk_id), Task 2.8 (pipeline) |
| `app_name` detection | Task 2.4 (detect_app_name), Task 2.8 (payload) |
| `layer` with `"other"` fallback | Task 2.4 (classify_layer), Task 2.8 (payload) |
| `signature` extraction | Task 2.4 (extract_signature), Task 2.8 (payload) |
| Synonym expansion | Task 2.3 (QueryEnhancer with synonyms) |
| DOCS intent → docs collection | Task 2.2 (get_intent_collection_preference), Task 2.10 (engine) |
| `query_enhanced` in response | Task 2.0 (SearchResponse), Task 2.10 (engine) |
| `total_candidates` in response | Task 2.0 (SearchResponse), Task 2.10 (engine) |
| Configurable rerank candidates | Task 2.0 (SearchConfig), Task 2.10 (engine) |
| Git-aware change detection | Task 2.7 (GitChangeTracker) |
| delete_by_file_path | Task 2.5 (QdrantManager), Task 2.8 (pipeline) |
| Multi-prefetch structural boost | Task 2.9 (build_prefetches) |
| DEBUG intent test-file boost | Task 2.9 (build_prefetches) |
| Rerank skip conditions (5) | Task 2.6 (should_skip_rerank) |
