# Codebase Embedding System: Implementation Guide

**Status:** Draft
**Companion Document:** [DESIGN.md](./DESIGN.md)

This guide provides the concrete specifications needed to implement the code-search tool. The DESIGN doc covers *why* we're building it; this doc covers *how*.

---

## Table of Contents

1. [Project Setup](#1-project-setup)
2. [Dependencies](#2-dependencies)
3. [Infrastructure](#3-infrastructure)
4. [SQLite Schemas](#4-sqlite-schemas)
5. [Configuration System](#5-configuration-system)
6. [Tree-sitter Setup](#6-tree-sitter-setup)
7. [Error Handling](#7-error-handling)
8. [Testing Strategy](#8-testing-strategy)
9. [Phase Implementation Details](#9-phase-implementation-details)
10. [Developer Workflow](#10-developer-workflow)

---

## 1. Project Setup

### Repository Structure

```
code-search/                          # https://github.com/ruminaider/code-search
├── code_search/
│   ├── __init__.py
│   ├── __main__.py                   # Entry point: python -m code_search
│   ├── cli.py                        # typer CLI
│   ├── mcp_server.py                 # MCP server
│   ├── config.py                     # Config loading and validation
│   ├── models.py                     # Pydantic models for data structures
│   ├── chunker/
│   │   ├── __init__.py
│   │   ├── parser.py                 # tree-sitter AST parsing
│   │   ├── strategies.py             # File-type chunking strategies
│   │   ├── tokenizer.py              # Voyage tokenizer wrapper
│   │   └── identity.py               # Chunk identity generation
│   ├── search/
│   │   ├── __init__.py
│   │   ├── hybrid.py                 # Dense + BM25 fusion
│   │   ├── rerank.py                 # Voyage reranker
│   │   ├── enhance.py                # Query enhancement
│   │   └── intent.py                 # Intent classification
│   ├── indexer/
│   │   ├── __init__.py
│   │   ├── pipeline.py               # Main indexing pipeline
│   │   ├── cache.py                  # SQLite caching
│   │   ├── git.py                    # Git change detection
│   │   └── batch.py                  # Batch embedding with retry
│   ├── clients/
│   │   ├── __init__.py
│   │   ├── voyage.py                 # Voyage API wrapper
│   │   └── qdrant.py                 # Qdrant client wrapper
│   └── exceptions.py                 # Custom exception hierarchy
├── tests/
│   ├── __init__.py
│   ├── conftest.py                   # pytest fixtures
│   ├── fixtures/                     # Test data
│   │   ├── python/                   # Sample Python files
│   │   ├── typescript/               # Sample TS/TSX files
│   │   └── expected/                 # Expected chunk outputs
│   ├── unit/
│   │   ├── test_chunker.py
│   │   ├── test_tokenizer.py
│   │   ├── test_identity.py
│   │   ├── test_enhance.py
│   │   └── test_intent.py
│   └── integration/
│       ├── test_pipeline.py
│       └── test_search.py
├── pyproject.toml
├── README.md
├── LICENSE                           # MIT
└── .github/
    └── workflows/
        └── ci.yml
```

### Python Version

```
Python >= 3.10
```

---

## 2. Dependencies

### pyproject.toml

```toml
[project]
name = "code-search"
version = "0.1.0"
description = "Semantic code search with hybrid retrieval and MCP integration"
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.10"
authors = [
    {name = "Ruminaider", email = "hello@ruminaider.com"}
]
keywords = ["code-search", "embeddings", "qdrant", "mcp", "claude"]

dependencies = [
    # Core
    "qdrant-client>=1.9.0,<2.0",
    "voyageai>=0.3.0",

    # CLI
    "typer>=0.12.0",
    "rich>=13.7.0",

    # Tokenization
    "transformers>=4.40.0",
    "tokenizers>=0.19.0",

    # AST Parsing
    "tree-sitter>=0.22.0",
    "tree-sitter-python>=0.21.0",
    "tree-sitter-typescript>=0.21.0",
    "tree-sitter-javascript>=0.21.0",

    # Config & Validation
    "pydantic>=2.7.0",
    "pyyaml>=6.0.1",

    # Async & Retry
    "tenacity>=8.2.0",
    "httpx>=0.27.0",

    # MCP
    "mcp>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=5.0.0",
    "ruff>=0.4.0",
    "mypy>=1.10.0",
    "respx>=0.21.0",  # HTTP mocking for httpx
]

[project.scripts]
code-search = "code_search.cli:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
line-length = 100
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.mypy]
python_version = "3.10"
strict = true
```

### Dependency Rationale

| Package | Version | Why |
|---------|---------|-----|
| `qdrant-client` | >=1.9.0 | Hybrid search with RRF requires 1.9+ |
| `voyageai` | >=0.3.0 | Rerank API requires 0.3+ |
| `transformers` | >=4.40.0 | Voyage tokenizer support |
| `tree-sitter` | >=0.22.0 | Latest stable with Python 3.10+ wheels |
| `pydantic` | >=2.7.0 | V2 for config validation |
| `mcp` | >=1.0.0 | Claude Code MCP protocol |
| `respx` | >=0.21.0 | Mock httpx calls in tests |

---

## 3. Infrastructure

### docker-compose.yml (Qdrant Service)

Add to your project's `docker-compose.yml`:

```yaml
services:
  # ... existing services ...

  qdrant:
    image: qdrant/qdrant:v1.9.2
    container_name: code-search-qdrant
    ports:
      - "6333:6333"   # REST API
      - "6334:6334"   # gRPC
    volumes:
      - qdrant_data:/qdrant/storage
    environment:
      - QDRANT__SERVICE__GRPC_PORT=6334
      - QDRANT__LOG_LEVEL=INFO
    healthcheck:
      test: ["CMD", "wget", "--no-verbose", "--tries=1", "--spider", "http://localhost:6333/"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
    restart: unless-stopped

volumes:
  qdrant_data:
    driver: local
```

### Environment Variables

Create `.env` file (gitignored):

```bash
# Required
VOYAGE_API_KEY=pa-xxxxxxxxxxxxxxxxxxxx

# Optional (defaults shown)
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=                          # Empty for local, set for cloud
CODE_SEARCH_CACHE_DIR=.code-search       # SQLite cache location
CODE_SEARCH_LOG_LEVEL=INFO
```

### Environment Variable Loading

```python
# code_search/config.py
import os
from pathlib import Path

class Environment:
    """Load environment variables with defaults."""

    VOYAGE_API_KEY: str = os.environ.get("VOYAGE_API_KEY", "")
    QDRANT_URL: str = os.environ.get("QDRANT_URL", "http://localhost:6333")
    QDRANT_API_KEY: str | None = os.environ.get("QDRANT_API_KEY") or None
    CACHE_DIR: Path = Path(os.environ.get("CODE_SEARCH_CACHE_DIR", ".code-search"))
    LOG_LEVEL: str = os.environ.get("CODE_SEARCH_LOG_LEVEL", "INFO")

    @classmethod
    def validate(cls) -> list[str]:
        """Return list of missing required env vars."""
        errors = []
        if not cls.VOYAGE_API_KEY:
            errors.append("VOYAGE_API_KEY is required")
        return errors
```

---

## 4. SQLite Schemas

### Database Location

```
{project_root}/.code-search/
├── cache.db          # Embedding and chunk cache
├── state.db          # Indexing state and checkpoints
└── logs/             # Debug logs (optional)
```

### cache.db Schema

```sql
-- Embedding cache: avoid re-embedding unchanged content
CREATE TABLE IF NOT EXISTS embedding_cache (
    content_hash TEXT NOT NULL,
    embedding_model TEXT NOT NULL,
    embedding BLOB NOT NULL,
    token_count INTEGER NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (content_hash, embedding_model)
);

CREATE INDEX IF NOT EXISTS idx_embedding_cache_model
ON embedding_cache(embedding_model);

-- Chunk cache: track which chunks exist for each file
CREATE TABLE IF NOT EXISTS chunk_cache (
    file_path TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    chunk_count INTEGER NOT NULL,
    chunk_ids TEXT NOT NULL,          -- JSON array of chunk IDs
    updated_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (file_path)
);

CREATE INDEX IF NOT EXISTS idx_chunk_cache_hash
ON chunk_cache(file_hash);
```

### state.db Schema

```sql
-- Indexing state: track progress for incremental updates
CREATE TABLE IF NOT EXISTS index_state (
    collection_name TEXT PRIMARY KEY,
    last_commit TEXT,                  -- Git commit SHA
    last_indexed_at TEXT,
    total_chunks INTEGER DEFAULT 0,
    total_files INTEGER DEFAULT 0
);

-- Failed files: retry on next run
CREATE TABLE IF NOT EXISTS failed_files (
    file_path TEXT PRIMARY KEY,
    error_type TEXT NOT NULL,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    last_attempt TEXT DEFAULT (datetime('now'))
);

-- Checkpoints: resume interrupted indexing
CREATE TABLE IF NOT EXISTS checkpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    collection_name TEXT NOT NULL,
    batch_index INTEGER NOT NULL,
    files_processed TEXT NOT NULL,     -- JSON array
    created_at TEXT DEFAULT (datetime('now'))
);
```

### Cache Implementation

```python
# code_search/indexer/cache.py
import sqlite3
import json
from pathlib import Path
from contextlib import contextmanager

class CacheDB:
    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._init_databases()

    def _init_databases(self):
        """Create tables if they don't exist."""
        with self._get_cache_conn() as conn:
            conn.executescript(CACHE_SCHEMA)
        with self._get_state_conn() as conn:
            conn.executescript(STATE_SCHEMA)

    @contextmanager
    def _get_cache_conn(self):
        conn = sqlite3.connect(self.cache_dir / "cache.db")
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    @contextmanager
    def _get_state_conn(self):
        conn = sqlite3.connect(self.cache_dir / "state.db")
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def get_embedding(self, content_hash: str, model: str) -> bytes | None:
        """Get cached embedding or None if not found."""
        with self._get_cache_conn() as conn:
            row = conn.execute(
                "SELECT embedding FROM embedding_cache WHERE content_hash = ? AND embedding_model = ?",
                (content_hash, model)
            ).fetchone()
            return row["embedding"] if row else None

    def set_embedding(self, content_hash: str, model: str, embedding: bytes, token_count: int):
        """Cache an embedding."""
        with self._get_cache_conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO embedding_cache
                   (content_hash, embedding_model, embedding, token_count)
                   VALUES (?, ?, ?, ?)""",
                (content_hash, model, embedding, token_count)
            )

    def get_file_hash(self, file_path: str) -> str | None:
        """Get cached file hash for change detection."""
        with self._get_cache_conn() as conn:
            row = conn.execute(
                "SELECT file_hash FROM chunk_cache WHERE file_path = ?",
                (file_path,)
            ).fetchone()
            return row["file_hash"] if row else None

    def set_file_chunks(self, file_path: str, file_hash: str, chunk_ids: list[str]):
        """Cache file hash and chunk IDs."""
        with self._get_cache_conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO chunk_cache
                   (file_path, file_hash, chunk_count, chunk_ids)
                   VALUES (?, ?, ?, ?)""",
                (file_path, file_hash, len(chunk_ids), json.dumps(chunk_ids))
            )
```

---

## 5. Configuration System

### Pydantic Models

```python
# code_search/models.py
from enum import Enum
from pathlib import Path
from pydantic import BaseModel, Field, field_validator

class ChunkStrategy(str, Enum):
    CLASS_WITH_METHODS = "class_with_methods"
    FUNCTION = "function"
    FILE = "file"
    SECTION = "section"  # For markdown

class CollectionConfig(BaseModel):
    include: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)

class ChunkOverride(BaseModel):
    strategy: ChunkStrategy = ChunkStrategy.CLASS_WITH_METHODS
    max_tokens: int = Field(default=3000, ge=100, le=8000)

class DjangoConfig(BaseModel):
    app_detection: bool = True
    related_files: dict[str, list[str]] = Field(default_factory=dict)

class SecurityConfig(BaseModel):
    exclude_patterns: list[str] = Field(default_factory=lambda: [
        "**/.env*",
        "**/secrets/**",
        "**/*credential*",
        "**/*secret*",
        "**/*.pem",
        "**/*.key",
    ])

class ProjectConfig(BaseModel):
    """Root configuration model."""

    project: dict = Field(default_factory=lambda: {"name": "default", "root": "."})
    collections: dict[str, CollectionConfig] = Field(default_factory=dict)
    chunking: dict = Field(default_factory=lambda: {"default_max_tokens": 3000})
    django: DjangoConfig = Field(default_factory=DjangoConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    terminology_file: str | None = None

    @field_validator("collections", mode="before")
    @classmethod
    def validate_collections(cls, v):
        if not v:
            return {
                "code": CollectionConfig(
                    include=["**/*.py", "**/*.ts", "**/*.tsx"],
                    exclude=["**/migrations/**", "**/node_modules/**"]
                ),
                "docs": CollectionConfig(
                    include=["**/*.md"],
                    exclude=[]
                )
            }
        return {k: CollectionConfig(**v_) if isinstance(v_, dict) else v_
                for k, v_ in v.items()}

    @classmethod
    def from_yaml(cls, path: Path) -> "ProjectConfig":
        """Load config from YAML file."""
        import yaml

        if not path.exists():
            return cls()

        with open(path) as f:
            data = yaml.safe_load(f) or {}

        return cls(**data)

    @classmethod
    def from_yaml_with_errors(cls, path: Path) -> tuple["ProjectConfig", list[str]]:
        """Load config and return any validation errors."""
        import yaml
        from pydantic import ValidationError

        errors = []

        if not path.exists():
            return cls(), [f"Config file not found: {path}"]

        try:
            with open(path) as f:
                data = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            return cls(), [f"Invalid YAML: {e}"]

        try:
            config = cls(**data)
            return config, []
        except ValidationError as e:
            for error in e.errors():
                loc = ".".join(str(x) for x in error["loc"])
                errors.append(f"{loc}: {error['msg']}")
            return cls(), errors
```

---

## 6. Tree-sitter Setup

### Grammar Installation

Tree-sitter requires language grammars to be compiled. The Python bindings handle this automatically:

```python
# code_search/chunker/parser.py
from tree_sitter import Language, Parser
import tree_sitter_python
import tree_sitter_typescript
import tree_sitter_javascript

class ASTParser:
    """Parse source files into AST using tree-sitter."""

    def __init__(self):
        self._parsers: dict[str, Parser] = {}
        self._init_parsers()

    def _init_parsers(self):
        """Initialize parsers for each supported language."""
        # Python
        py_parser = Parser()
        py_parser.language = Language(tree_sitter_python.language())
        self._parsers["python"] = py_parser

        # TypeScript
        ts_parser = Parser()
        ts_parser.language = Language(tree_sitter_typescript.language_typescript())
        self._parsers["typescript"] = ts_parser

        # TSX
        tsx_parser = Parser()
        tsx_parser.language = Language(tree_sitter_typescript.language_tsx())
        self._parsers["tsx"] = tsx_parser

        # JavaScript/JSX
        js_parser = Parser()
        js_parser.language = Language(tree_sitter_javascript.language())
        self._parsers["javascript"] = js_parser

    def get_language(self, file_path: str) -> str | None:
        """Determine language from file extension."""
        ext = file_path.rsplit(".", 1)[-1].lower()
        return {
            "py": "python",
            "ts": "typescript",
            "tsx": "tsx",
            "js": "javascript",
            "jsx": "javascript",
        }.get(ext)

    def parse(self, content: str, language: str) -> "Tree | None":
        """Parse source content into AST."""
        parser = self._parsers.get(language)
        if not parser:
            return None

        try:
            return parser.parse(content.encode("utf-8"))
        except Exception:
            return None

    def parse_file(self, file_path: str, content: str) -> "Tree | None":
        """Parse file content, auto-detecting language."""
        language = self.get_language(file_path)
        if not language:
            return None
        return self.parse(content, language)
```

### Extracting Code Entities

```python
# code_search/chunker/strategies.py
from dataclasses import dataclass
from typing import Iterator

@dataclass
class CodeEntity:
    """A parsed code entity (class, function, method)."""
    entity_type: str          # "class", "function", "method"
    name: str                 # Entity name
    qualified_name: str       # Full qualified name
    content: str              # Full source code
    line_start: int
    line_end: int
    parent_class: str | None  # For methods

class PythonChunker:
    """Extract code entities from Python AST."""

    DEFINITION_TYPES = {"class_definition", "function_definition"}

    def extract_entities(self, tree, source: str) -> Iterator[CodeEntity]:
        """Extract all code entities from AST."""
        source_bytes = source.encode("utf-8")

        for node in self._walk_definitions(tree.root_node):
            yield from self._node_to_entity(node, source_bytes)

    def _walk_definitions(self, node) -> Iterator:
        """Walk tree finding definition nodes."""
        if node.type in self.DEFINITION_TYPES:
            yield node
        for child in node.children:
            yield from self._walk_definitions(child)

    def _node_to_entity(self, node, source_bytes: bytes) -> Iterator[CodeEntity]:
        """Convert AST node to CodeEntity."""
        name = self._get_name(node)
        content = source_bytes[node.start_byte:node.end_byte].decode("utf-8")

        if node.type == "class_definition":
            yield CodeEntity(
                entity_type="class",
                name=name,
                qualified_name=name,
                content=content,
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                parent_class=None
            )

            for method in self._get_methods(node):
                method_name = self._get_name(method)
                method_content = source_bytes[method.start_byte:method.end_byte].decode("utf-8")
                yield CodeEntity(
                    entity_type="method",
                    name=method_name,
                    qualified_name=f"{name}.{method_name}",
                    content=method_content,
                    line_start=method.start_point[0] + 1,
                    line_end=method.end_point[0] + 1,
                    parent_class=name
                )

        elif node.type == "function_definition":
            yield CodeEntity(
                entity_type="function",
                name=name,
                qualified_name=name,
                content=content,
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                parent_class=None
            )

    def _get_name(self, node) -> str:
        """Extract name from definition node."""
        for child in node.children:
            if child.type == "identifier":
                return child.text.decode("utf-8")
        return "unknown"

    def _get_methods(self, class_node) -> Iterator:
        """Get method nodes from class body."""
        for child in class_node.children:
            if child.type == "block":
                for stmt in child.children:
                    if stmt.type == "function_definition":
                        yield stmt
```

---

## 7. Error Handling

### Exception Hierarchy

```python
# code_search/exceptions.py

class CodeSearchError(Exception):
    """Base exception for code-search."""
    pass

# Configuration errors
class ConfigError(CodeSearchError):
    """Configuration-related errors."""
    pass

class ConfigNotFoundError(ConfigError):
    """Config file not found."""
    pass

class ConfigValidationError(ConfigError):
    """Config validation failed."""
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(f"Config validation failed: {', '.join(errors)}")

# Infrastructure errors
class InfrastructureError(CodeSearchError):
    """Infrastructure-related errors."""
    pass

class QdrantError(InfrastructureError):
    """Qdrant-related errors."""
    pass

class QdrantConnectionError(QdrantError):
    """Cannot connect to Qdrant."""
    def __init__(self, url: str, original: Exception | None = None):
        self.url = url
        self.original = original
        super().__init__(
            f"Cannot connect to Qdrant at {url}. "
            "Ensure Qdrant is running: docker compose up -d qdrant"
        )

class VoyageError(InfrastructureError):
    """Voyage API errors."""
    pass

class VoyageAuthError(VoyageError):
    """Voyage API authentication failed."""
    def __init__(self):
        super().__init__(
            "Voyage API authentication failed. "
            "Check VOYAGE_API_KEY environment variable."
        )

class VoyageRateLimitError(VoyageError):
    """Voyage API rate limit exceeded."""
    def __init__(self, retry_after: int | None = None):
        self.retry_after = retry_after
        msg = "Voyage API rate limit exceeded."
        if retry_after:
            msg += f" Retry after {retry_after} seconds."
        super().__init__(msg)

# Indexing errors
class IndexingError(CodeSearchError):
    """Indexing-related errors."""
    pass

class ParseError(IndexingError):
    """Failed to parse source file."""
    def __init__(self, file_path: str, errors: list[str]):
        self.file_path = file_path
        self.errors = errors
        super().__init__(f"Failed to parse {file_path}: {errors}")

# Search errors
class SearchError(CodeSearchError):
    """Search-related errors."""
    pass

class SearchUnavailableError(SearchError):
    """Search service is unavailable."""
    pass

class InvalidFilterError(SearchError):
    """Invalid search filter."""
    def __init__(self, filter_name: str, value: str, valid_values: list[str]):
        super().__init__(
            f"Invalid filter '{filter_name}': '{value}'. "
            f"Valid values: {valid_values}"
        )
```

---

## 8. Testing Strategy

### Test Categories

| Category | Purpose | Mocking | Speed |
|----------|---------|---------|-------|
| Unit | Test individual functions | Full mocking | Fast (<1s each) |
| Integration | Test component interactions | Partial mocking | Medium (<5s each) |
| E2E | Test full pipeline | Real Qdrant (Docker) | Slow (<30s each) |

### Fixtures

```python
# tests/conftest.py
import pytest
from pathlib import Path
from unittest.mock import Mock, AsyncMock

FIXTURES_DIR = Path(__file__).parent / "fixtures"

@pytest.fixture
def sample_python_file():
    """Sample Python source for testing."""
    return (FIXTURES_DIR / "python" / "sample_models.py").read_text()

@pytest.fixture
def mock_voyage_client():
    """Mock Voyage API client."""
    client = Mock()
    client.embed = AsyncMock(return_value=Mock(
        embeddings=[[0.1] * 1024]
    ))
    client.rerank = AsyncMock(return_value=Mock(
        results=[Mock(index=0, relevance_score=0.95)]
    ))
    return client

@pytest.fixture
def mock_qdrant_client():
    """Mock Qdrant client."""
    client = Mock()
    client.get_collections = Mock(return_value=Mock(collections=[]))
    client.create_collection = Mock()
    client.upsert = Mock()
    client.query_points = Mock(return_value=[])
    return client

@pytest.fixture
def temp_cache_dir(tmp_path):
    """Temporary directory for SQLite caches."""
    cache_dir = tmp_path / ".code-search"
    cache_dir.mkdir()
    return cache_dir
```

### Sample Test File

```python
# tests/fixtures/python/sample_models.py
"""Sample Django models for testing chunker."""

from django.db import models


class Prescription(models.Model):
    """A prescription for medication."""

    user = models.ForeignKey("User", on_delete=models.CASCADE)
    medication = models.CharField(max_length=255)
    expires_at = models.DateTimeField()

    def is_expired(self) -> bool:
        """Check if prescription has passed expiration date."""
        from django.utils import timezone
        return timezone.now() > self.expires_at


def create_prescription(user, medication: str) -> Prescription:
    """Factory function to create a prescription."""
    from django.utils import timezone
    from datetime import timedelta

    return Prescription.objects.create(
        user=user,
        medication=medication,
        expires_at=timezone.now() + timedelta(days=30)
    )
```

### CI Configuration

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      qdrant:
        image: qdrant/qdrant:v1.9.2
        ports:
          - 6333:6333

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.10"

      - name: Install dependencies
        run: pip install -e ".[dev]"

      - name: Run linting
        run: |
          ruff check .
          ruff format --check .

      - name: Run tests
        env:
          VOYAGE_API_KEY: ${{ secrets.VOYAGE_API_KEY }}
          QDRANT_URL: http://localhost:6333
        run: pytest --cov=code_search
```

---

## 9. Phase Implementation Details

### Phase 1: Core Infrastructure

#### Task 1.1: Qdrant Docker Setup

**Steps:**
1. Add Qdrant service to `docker-compose.yml` (see Section 3)
2. Add volume for data persistence
3. Test with: `docker compose up -d qdrant && curl http://localhost:6333/`

**Acceptance Test:**
```bash
docker compose up -d qdrant
curl -s http://localhost:6333/ | jq .title
# Expected: "qdrant - vector database"
```

#### Task 1.2: Voyage Tokenizer Integration

**Implementation:**
```python
# code_search/chunker/tokenizer.py
from functools import lru_cache
from transformers import AutoTokenizer

@lru_cache(maxsize=1)
def get_tokenizer():
    """Load and cache the Voyage tokenizer."""
    return AutoTokenizer.from_pretrained("voyageai/voyage-code-3")

def count_tokens(text: str) -> int:
    """Count tokens using Voyage tokenizer."""
    tokenizer = get_tokenizer()
    return len(tokenizer.encode(text))

def chunk_fits(chunk: str, max_tokens: int = 4000) -> bool:
    """Check if chunk is within token limit."""
    return count_tokens(chunk) <= max_tokens
```

#### Task 1.3: Basic AST Chunker

See Section 6 for full implementation.

#### Task 1.4: SQLite Caching

See Section 4 for full implementation.

#### Task 1.5: Minimal CLI

```python
# code_search/cli.py
import typer
from rich.console import Console

app = typer.Typer(help="Semantic code search tool")
console = Console()

@app.command()
def index(
    config: Path = typer.Option("config.yaml", "--config", "-c"),
    full: bool = typer.Option(False, "--full"),
    files: list[str] = typer.Option(None, "--files", "-f"),
):
    """Index the codebase."""
    # Implementation
    pass

@app.command()
def status():
    """Show system health and index statistics."""
    # Implementation
    pass

@app.command()
def search(query: str, raw: bool = typer.Option(False, "--raw")):
    """Search the codebase."""
    # Implementation
    pass

if __name__ == "__main__":
    app()
```

---

## 10. Developer Workflow

### Getting Started

```bash
# 1. Clone repository
git clone https://github.com/ruminaider/code-search.git
cd code-search

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate

# 3. Install in development mode
pip install -e ".[dev]"

# 4. Set up environment variables
cp .env.example .env
# Edit .env and add your VOYAGE_API_KEY

# 5. Start Qdrant
docker compose up -d qdrant

# 6. Verify setup
code-search status

# 7. Run tests
pytest
```

### Using with a Project

```bash
# 1. Install code-search
pip install code-search

# 2. Create project config
cat > indexer/config.yaml << 'EOF'
project:
  name: myproject
  root: .

collections:
  code:
    include:
      - "src/**/*.py"
    exclude:
      - "**/tests/**"
EOF

# 3. Start Qdrant
docker compose up -d qdrant

# 4. Full index
code-search index --config indexer/config.yaml --full

# 5. Add MCP configuration to .mcp.json
```

### Troubleshooting

| Error | Cause | Solution |
|-------|-------|----------|
| `QdrantConnectionError` | Qdrant not running | `docker compose up -d qdrant` |
| `VoyageAuthError` | Invalid API key | Check `VOYAGE_API_KEY` in `.env` |
| `ConfigValidationError` | Invalid config.yaml | Check error message for invalid field |
| `ParseError` | Syntax error in source | File will be skipped; check logs |

### Common Commands

```bash
# Full reindex
code-search index --full

# Index specific files
code-search index --files src/models.py src/views.py

# Debug search
code-search search "prescription expiry" --raw

# Inspect chunks for a file
code-search inspect --file src/models.py

# Start MCP server
code-search serve --config config.yaml
```
