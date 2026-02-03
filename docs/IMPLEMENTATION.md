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
11. [Embedding Provider Abstraction](#11-embedding-provider-abstraction)
12. [Splitter Fallback Chain](#12-splitter-fallback-chain)
13. [File-Hash Change Detection](#13-file-hash-change-detection)
14. [Ignore Pattern Loading](#14-ignore-pattern-loading)
15. [Batch Embedding with Progress](#15-batch-embedding-with-progress)

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
│   │   ├── fallback.py               # Splitter fallback chain
│   │   ├── tokenizer.py              # Voyage tokenizer wrapper
│   │   └── identity.py               # Chunk identity generation
│   ├── search/
│   │   ├── __init__.py
│   │   ├── engine.py                 # Top-level search orchestrator
│   │   ├── models.py                 # QueryIntent, SearchResult, SearchRequest, SearchResponse
│   │   ├── tokenize.py               # BM25 tokenization and sparse vectors
│   │   ├── hybrid.py                 # Dense + BM25 fusion
│   │   ├── rerank.py                 # Voyage reranker
│   │   ├── enhance.py                # Query enhancement
│   │   └── intent.py                 # Intent classification
│   ├── indexer/
│   │   ├── __init__.py
│   │   ├── pipeline.py               # Main indexing pipeline
│   │   ├── cache.py                  # SQLite caching
│   │   ├── git_tracker.py            # Git change detection (primary)
│   │   ├── file_hash.py              # File-hash change detection (secondary)
│   │   ├── ignore.py                 # Ignore pattern hierarchy
│   │   └── metadata.py               # Chunk metadata extraction
│   ├── clients/
│   │   ├── __init__.py
│   │   ├── base.py                   # EmbeddingProvider ABC
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

    # Ignore patterns
    "pathspec>=0.12.0",

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
| `pathspec` | >=0.12.0 | `.gitignore`-compatible pattern matching for ignore hierarchy |
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

-- Safety state: track chunk counts for limit enforcement
CREATE TABLE IF NOT EXISTS safety_state (
    collection_name TEXT PRIMARY KEY,
    chunk_count INTEGER DEFAULT 0,
    last_checked_at TEXT DEFAULT (datetime('now')),
    limit_breached BOOLEAN DEFAULT FALSE
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

    def get_file_chunk_ids(self, file_path: str) -> list[str]:
        """Get cached chunk IDs for a file."""
        with self._get_cache_conn() as conn:
            row = conn.execute(
                "SELECT chunk_ids FROM chunk_cache WHERE file_path = ?",
                (file_path,),
            ).fetchone()
            if row:
                return json.loads(row["chunk_ids"])
            return []

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

class SafetyConfig(BaseModel):
    """Safety limits to prevent runaway indexing. See ADR-003."""
    max_total_chunks: int = Field(default=500_000, ge=1000)
    max_file_size_bytes: int = Field(default=1_048_576, ge=1024)  # 1 MB
    batch_size: int = Field(default=100, ge=1, le=1000)
    collection_limits: dict[str, int] = Field(default_factory=dict)

class IndexingConfig(BaseModel):
    """Indexing pipeline configuration."""
    overlap_tokens: int = Field(default=200, ge=0, le=1000)
    fallback_max_tokens: int = Field(default=3000, ge=500, le=8000)
    embedding_provider: str = Field(default="voyage")  # voyage | openai | ollama
    embedding_model: str = Field(default="voyage-code-3")

class SearchConfig(BaseModel):
    """Search pipeline configuration. See Tradeoff B resolution."""

    rerank_candidates: int = Field(default=30, ge=10, le=100)
    rerank_top_k: int = Field(default=10, ge=1, le=50)
    no_rerank_threshold: int = Field(default=10, ge=1)
    rerank_model: str = "rerank-2.5"
    high_confidence_threshold: float = Field(default=0.92, ge=0.0, le=1.0)
    low_variance_threshold: float = Field(default=0.1, ge=0.0, le=1.0)

class ProjectConfig(BaseModel):
    """Root configuration model."""

    project: dict[str, str] = Field(default_factory=lambda: {"name": "default", "root": "."})
    collections: dict[str, CollectionConfig] = Field(default_factory=dict)
    chunking: dict[str, int] = Field(default_factory=lambda: {"default_max_tokens": 3000})
    django: DjangoConfig = Field(default_factory=DjangoConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)
    indexing: IndexingConfig = Field(default_factory=IndexingConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)
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

#### Task 1.6: Splitter Fallback Chain

**Implementation:** See Section 12 for full specification.

**Acceptance Test:**
```python
# Tier 1: Valid Python file → AST chunks
chunks = split_file("models.py", valid_python, max_tokens=3000, ast_parser=parser)
assert all(c.source == "ast" for c in chunks)

# Tier 2: Invalid syntax → token-recursive chunks
chunks = split_file("config.txt", plain_text, max_tokens=3000, ast_parser=parser)
assert all(count_tokens(c.content) <= 3000 for c in chunks)

# Tier 3: Verify overlap in fallback chunks
assert chunks[1].content.startswith(chunks[0].content[-200:])  # approximate
```

#### Task 1.7: Embedding Provider ABC

**Implementation:** See Section 11 for full specification.

**Acceptance Test:**
```python
# Provider interface works
provider = VoyageEmbeddingProvider(api_key=key)
assert provider.dimensions == 1024
assert provider.model_name == "voyage-code-3"

# Embed returns correct shape
embeddings = await provider.embed(["hello world"])
assert len(embeddings) == 1
assert len(embeddings[0]) == 1024

# Provider is swappable
provider = create_embedding_provider(config, env)
assert isinstance(provider, EmbeddingProvider)
```

#### Task 1.8: File-Hash Change Detection

**Implementation:** See Section 13 for full specification.

**Acceptance Test:**
```python
# New file detected as added
changes = tracker.detect_changes(["new_file.py"])
assert "new_file.py" in changes["added"]

# Modified file detected
tracker.update_hash("file.py", "old_hash", ["chunk1"])
# ... modify file ...
changes = tracker.detect_changes(["file.py"])
assert "file.py" in changes["modified"]

# Unchanged file detected
changes = tracker.detect_changes(["file.py"])
assert "file.py" in changes["unchanged"]
```

#### Task 1.9: Ignore Pattern Loading

**Implementation:** See Section 14 for full specification.

**Acceptance Test:**
```python
# Built-in defaults work
loader = IgnorePatternLoader(project_root)
assert loader.should_ignore("__pycache__/module.pyc")
assert loader.should_ignore("node_modules/pkg/index.js")

# .gitignore patterns loaded
assert loader.should_ignore("*.log")  # if in .gitignore

# Config excludes work
loader = IgnorePatternLoader(project_root, config_excludes=["**/migrations/**"])
assert loader.should_ignore("backend/app/migrations/0001.py")

# Env var override
os.environ["CODE_SEARCH_EXCLUDE"] = "*.generated.py"
loader = IgnorePatternLoader(project_root)
loader.load()
assert loader.should_ignore("output.generated.py")
```

#### Task 1.10: Safety Limits

**Implementation:** See Section 19 of DESIGN.md and `SafetyConfig` model in Section 5.

**Acceptance Test:**
```python
# File size limit enforced
checker = SafetyChecker(SafetyConfig(max_file_size_bytes=1_048_576))
assert checker.check_file("small.py", 1000) is True
assert checker.check_file("huge.min.js", 5_000_000) is False

# Total chunk limit enforced
assert checker.check_total_chunks(499_990, 5) is True
assert checker.check_total_chunks(499_990, 20) is False
```

### Phase 2: Search Pipeline

Phase 2 delivers the search pipeline and completes the indexing flow. All modules listed below are implemented and tested.

#### Delivered Modules

| Module | Description |
|--------|-------------|
| `code_search/models.py` | `SearchConfig` added to `ProjectConfig` (rerank thresholds, candidate counts) |
| `code_search/search/models.py` | `QueryIntent`, `SearchResult`, `SearchRequest`, `SearchResponse` dataclasses |
| `code_search/search/tokenize.py` | BM25 tokenization: camelCase/snake_case splitting, raw term-count sparse vectors |
| `code_search/search/engine.py` | `SearchEngine` — top-level orchestrator: enhance -> classify -> hybrid search -> rerank |
| `code_search/search/hybrid.py` | `HybridSearchEngine` — dense + BM25 multi-prefetch with structural boosting |
| `code_search/search/rerank.py` | `RerankProvider` — Voyage rerank-2.5 with configurable skip conditions |
| `code_search/search/enhance.py` | `QueryEnhancer` — terminology expansion from YAML |
| `code_search/search/intent.py` | `classify_intent` — keyword heuristic intent routing |
| `code_search/indexer/metadata.py` | `detect_app_name`, `classify_layer`, `extract_signature`, `build_chunk_id` |
| `code_search/indexer/pipeline.py` | `IndexingPipeline` — file -> chunk -> metadata -> embed -> upsert (batch embedding inline) |
| `code_search/indexer/git_tracker.py` | `GitChangeTracker` — `git diff --name-status` parsing (A/M/D/R) |
| `code_search/clients/qdrant.py` | `QdrantManager` — collection CRUD, hybrid query with RRF fusion, delete by file_path |

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

---

## 11. Embedding Provider Abstraction

The embedding provider is abstracted behind a Python ABC, allowing the system to use different embedding backends. Adapted from claude-context's multi-provider interface — see [ADR-003](./adr/003-ported-features-from-claude-context.md#4-embedding-provider-abstraction).

### EmbeddingProvider ABC

```python
# code_search/clients/base.py
from abc import ABC, abstractmethod

class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Return the embedding dimensions."""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model identifier."""
        ...

    @abstractmethod
    async def embed(self, texts: list[str], input_type: str = "document") -> list[list[float]]:
        """Embed a batch of texts.

        Args:
            texts: List of text strings to embed.
            input_type: "document" for indexing, "query" for search.

        Returns:
            List of embedding vectors.
        """
        ...

    @abstractmethod
    async def embed_query(self, query: str) -> list[float]:
        """Embed a single query string.

        Convenience method that calls embed() with input_type="query".
        """
        ...
```

### VoyageEmbeddingProvider

```python
# code_search/clients/voyage.py (updated)
import voyageai

class VoyageEmbeddingProvider(EmbeddingProvider):
    """Voyage AI embedding provider (default)."""

    def __init__(self, api_key: str, model: str = "voyage-code-3"):
        self._client = voyageai.AsyncClient(api_key=api_key)
        self._model = model
        self._dimensions = 1024

    @property
    def dimensions(self) -> int:
        return self._dimensions

    @property
    def model_name(self) -> str:
        return self._model

    async def embed(self, texts: list[str], input_type: str = "document") -> list[list[float]]:
        result = await self._client.embed(
            texts,
            model=self._model,
            input_type=input_type,
            truncation=True,
        )
        return result.embeddings

    async def embed_query(self, query: str) -> list[float]:
        embeddings = await self.embed([query], input_type="query")
        return embeddings[0]
```

### Provider Factory

```python
# code_search/clients/__init__.py
def create_embedding_provider(config: IndexingConfig, env: Environment) -> EmbeddingProvider:
    """Create embedding provider from configuration."""
    if config.embedding_provider == "voyage":
        from .voyage import VoyageEmbeddingProvider
        return VoyageEmbeddingProvider(api_key=env.VOYAGE_API_KEY, model=config.embedding_model)
    elif config.embedding_provider == "openai":
        from .openai import OpenAIEmbeddingProvider
        return OpenAIEmbeddingProvider(api_key=env.OPENAI_API_KEY, model=config.embedding_model)
    elif config.embedding_provider == "ollama":
        from .ollama import OllamaEmbeddingProvider
        return OllamaEmbeddingProvider(model=config.embedding_model)
    else:
        raise ConfigError(f"Unknown embedding provider: {config.embedding_provider}")
```

---

## 12. Splitter Fallback Chain

Three-tier fallback for chunking files when AST parsing fails. No LangChain dependency — the token-recursive splitter is ~100 lines of Python. See [ADR-003](./adr/003-ported-features-from-claude-context.md#1-ast-fallback-chain).

### Token-Recursive Splitter

```python
# code_search/chunker/fallback.py
from dataclasses import dataclass, field
from typing import Any
from .tokenizer import count_tokens

@dataclass
class Chunk:
    """A chunk of source code or text."""

    content: str
    source: str  # "ast" or "fallback"
    file_path: str
    metadata: dict[str, Any] = field(default_factory=dict)

# Split points ordered by preference (most semantic to least)
SPLIT_SEPARATORS = [
    "\n\nclass ",      # Class boundaries
    "\n\ndef ",        # Function boundaries
    "\n\n",            # Paragraph/block boundaries
    "\n",              # Line boundaries
    " ",               # Word boundaries
]

def token_recursive_split(
    text: str,
    max_tokens: int,
    overlap_tokens: int = 200,
    separators: list[str] | None = None,
) -> list[str]:
    """Split text recursively by token count using semantic separators.

    Args:
        text: Text to split.
        max_tokens: Maximum tokens per chunk.
        overlap_tokens: Tokens of overlap between chunks (non-AST only).
        separators: Ordered list of split points to try.

    Returns:
        List of text chunks, each within max_tokens.
    """
    if count_tokens(text) <= max_tokens:
        return [text]

    separators = separators or SPLIT_SEPARATORS

    for separator in separators:
        parts = text.split(separator)
        if len(parts) == 1:
            continue

        chunks = []
        current = parts[0]

        for part in parts[1:]:
            candidate = current + separator + part
            if count_tokens(candidate) <= max_tokens:
                current = candidate
            else:
                if current.strip():
                    chunks.append(current.strip())
                current = _apply_overlap(chunks, part, overlap_tokens) if chunks else part

        if current.strip():
            chunks.append(current.strip())

        # Verify all chunks fit; if not, recurse with next separator
        if all(count_tokens(c) <= max_tokens for c in chunks):
            return chunks

    # Last resort: line split
    return line_split(text, max_tokens, overlap_tokens)


def line_split(text: str, max_tokens: int, overlap_tokens: int = 200) -> list[str]:
    """Split text by lines, guaranteed to produce valid chunks."""
    lines = text.split("\n")
    chunks = []
    current_lines = []
    current_tokens = 0

    for line in lines:
        line_tokens = count_tokens(line)
        if current_tokens + line_tokens > max_tokens and current_lines:
            chunks.append("\n".join(current_lines))
            # Apply overlap: keep last N tokens worth of lines
            overlap_lines = _get_overlap_lines(current_lines, overlap_tokens)
            current_lines = overlap_lines
            current_tokens = sum(count_tokens(l) for l in current_lines)
        current_lines.append(line)
        current_tokens += line_tokens

    if current_lines:
        chunks.append("\n".join(current_lines))

    return chunks


def _apply_overlap(chunks: list[str], next_part: str, overlap_tokens: int) -> str:
    """Prepend overlap from the end of the last chunk."""
    if not chunks or overlap_tokens == 0:
        return next_part
    last_chunk = chunks[-1]
    # Take last N tokens worth of text from previous chunk
    lines = last_chunk.split("\n")
    overlap_lines = _get_overlap_lines(lines, overlap_tokens)
    overlap_text = "\n".join(overlap_lines)
    return overlap_text + "\n" + next_part if overlap_text else next_part


def _get_overlap_lines(lines: list[str], overlap_tokens: int) -> list[str]:
    """Get lines from the end that fit within overlap_tokens."""
    result = []
    total = 0
    for line in reversed(lines):
        line_tokens = count_tokens(line)
        if total + line_tokens > overlap_tokens:
            break
        result.insert(0, line)
        total += line_tokens
    return result
```

### Fallback Chain Entry Point

```python
# code_search/chunker/fallback.py (continued)

def split_file(
    file_path: str,
    content: str,
    max_tokens: int,
    ast_parser: "ASTParser",
    overlap_tokens: int = 200,
) -> list["Chunk"]:
    """Split a file using the three-tier fallback chain.

    Tier 1: tree-sitter AST parsing (no overlap)
    Tier 2: Token-recursive splitting (with overlap)
    Tier 3: Line splitting (with overlap, guaranteed)
    """
    # Tier 1: AST
    tree = ast_parser.parse_file(file_path, content)
    if tree:
        chunks = extract_ast_chunks(tree, content, max_tokens)
        if chunks:
            return chunks

    # Tier 2 + 3: Token-recursive with line-split fallback
    text_chunks = token_recursive_split(content, max_tokens, overlap_tokens)
    return [
        Chunk(content=c, source="fallback", file_path=file_path, metadata={})
        for c in text_chunks
    ]
```

---

## 13. File-Hash Change Detection

Secondary change detection when git-diff is unavailable. Uses the existing `chunk_cache` table in SQLite. See [ADR-003](./adr/003-ported-features-from-claude-context.md#2-change-detection-hybrid-strategy).

```python
# code_search/indexer/file_hash.py
import hashlib
from pathlib import Path
from .cache import CacheDB

class FileHashTracker:
    """File-hash based change detection (secondary to git-diff)."""

    def __init__(self, cache: CacheDB):
        self.cache = cache

    def compute_hash(self, file_path: str) -> str:
        """Compute SHA256 hash of file contents."""
        content = Path(file_path).read_bytes()
        return hashlib.sha256(content).hexdigest()

    def detect_changes(self, file_paths: list[str]) -> dict[str, list[str]]:
        """Classify files as added, modified, or unchanged.

        Args:
            file_paths: List of file paths to check.

        Returns:
            Dict with keys "added", "modified", "unchanged".
        """
        changes: dict[str, list[str]] = {
            "added": [],
            "modified": [],
            "unchanged": [],
        }

        for path in file_paths:
            current_hash = self.compute_hash(path)
            cached_hash = self.cache.get_file_hash(path)

            if cached_hash is None:
                changes["added"].append(path)
            elif cached_hash != current_hash:
                changes["modified"].append(path)
            else:
                changes["unchanged"].append(path)

        return changes

    def update_hash(self, file_path: str, file_hash: str, chunk_ids: list[str]):
        """Update cached hash after successful indexing."""
        self.cache.set_file_chunks(file_path, file_hash, chunk_ids)
```

### Integration with Pipeline

```python
# In code_search/indexer/pipeline.py
def detect_changes(self, file_paths: list[str]) -> dict:
    """Detect changes using git-diff (primary) or file-hash (secondary)."""
    try:
        return self.git_tracker.get_changes_since(self.last_commit)
    except (GitError, subprocess.CalledProcessError):
        logger.warning("Git change detection failed; falling back to file-hash")
        return self.file_hash_tracker.detect_changes(file_paths)
```

---

## 14. Ignore Pattern Loading

Five-source hierarchy for file exclusion patterns, using `pathspec` for `.gitignore`-compatible matching. See [ADR-003](./adr/003-ported-features-from-claude-context.md#6-ignore-pattern-hierarchy).

```python
# code_search/indexer/ignore.py
import os
from pathlib import Path
from pathspec import PathSpec

# Built-in defaults (always excluded)
DEFAULT_IGNORE_PATTERNS = [
    "__pycache__/",
    "*.pyc",
    ".git/",
    "node_modules/",
    ".venv/",
    "venv/",
    ".tox/",
    "*.egg-info/",
    "dist/",
    "build/",
    ".mypy_cache/",
    ".pytest_cache/",
    ".ruff_cache/",
]

class IgnorePatternLoader:
    """Load and merge ignore patterns from 5 sources."""

    def __init__(self, project_root: Path, config_excludes: list[str] | None = None):
        self.project_root = project_root
        self.config_excludes = config_excludes or []
        self._spec: PathSpec | None = None

    def load(self) -> PathSpec:
        """Load and merge patterns from all sources."""
        all_patterns: list[str] = []

        # Source 1: Built-in defaults (lowest priority)
        all_patterns.extend(DEFAULT_IGNORE_PATTERNS)

        # Source 2: .gitignore
        gitignore = self.project_root / ".gitignore"
        if gitignore.exists():
            all_patterns.extend(self._read_pattern_file(gitignore))

        # Source 3: .codesearchignore
        codesearchignore = self.project_root / ".codesearchignore"
        if codesearchignore.exists():
            all_patterns.extend(self._read_pattern_file(codesearchignore))

        # Source 4: config.yaml exclude patterns
        all_patterns.extend(self.config_excludes)

        # Source 5: Environment variable (highest priority)
        env_excludes = os.environ.get("CODE_SEARCH_EXCLUDE", "")
        if env_excludes:
            all_patterns.extend(env_excludes.split(","))

        self._spec = PathSpec.from_lines("gitwildmatch", all_patterns)
        return self._spec

    def should_ignore(self, file_path: str) -> bool:
        """Check if a file should be ignored."""
        if self._spec is None:
            self.load()
        return self._spec.match_file(file_path)

    @staticmethod
    def _read_pattern_file(path: Path) -> list[str]:
        """Read patterns from a file, skipping comments and blanks."""
        patterns = []
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                patterns.append(line)
        return patterns
```

---

## 15. Batch Embedding with Progress

Batch embedding with configurable batch size and `rich` progress bars. Adapted from claude-context's 100-chunk batching with callbacks. See [ADR-003](./adr/003-ported-features-from-claude-context.md#3-batch-embedding-with-progress).

```python
# code_search/indexer/batch.py (updated)
from dataclasses import dataclass, field
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn
from ..clients.base import EmbeddingProvider
from ..chunker.tokenizer import count_tokens

@dataclass
class BatchProgress:
    """Track batch embedding progress."""
    total_chunks: int = 0
    embedded_chunks: int = 0
    total_tokens: int = 0
    embedded_tokens: int = 0
    failed_chunks: int = 0
    current_batch: int = 0
    total_batches: int = 0

    @property
    def progress_pct(self) -> float:
        if self.total_chunks == 0:
            return 0.0
        return self.embedded_chunks / self.total_chunks * 100


async def embed_in_batches(
    chunks: list[str],
    provider: EmbeddingProvider,
    batch_size: int = 100,
    show_progress: bool = True,
) -> tuple[list[list[float]], BatchProgress]:
    """Embed chunks in batches with progress tracking.

    Args:
        chunks: List of text chunks to embed.
        provider: Embedding provider instance.
        batch_size: Chunks per API call (default 100).
        show_progress: Whether to show rich progress bar.

    Returns:
        Tuple of (embeddings list, progress stats).
    """
    progress_stats = BatchProgress(
        total_chunks=len(chunks),
        total_tokens=sum(count_tokens(c) for c in chunks),
        total_batches=(len(chunks) + batch_size - 1) // batch_size,
    )

    all_embeddings: list[list[float]] = []
    batches = [chunks[i:i + batch_size] for i in range(0, len(chunks), batch_size)]

    with Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("({task.completed}/{task.total} chunks)"),
        TimeRemainingColumn(),
        disable=not show_progress,
    ) as progress_bar:
        task = progress_bar.add_task("Embedding", total=len(chunks))

        for i, batch in enumerate(batches):
            progress_stats.current_batch = i + 1
            try:
                embeddings = await provider.embed(batch, input_type="document")
                all_embeddings.extend(embeddings)
                progress_stats.embedded_chunks += len(batch)
                progress_stats.embedded_tokens += sum(count_tokens(c) for c in batch)
            except Exception as e:
                logger.error(f"Batch {i+1} failed: {e}")
                progress_stats.failed_chunks += len(batch)
                all_embeddings.extend([[] for _ in batch])  # Placeholder

            progress_bar.update(task, advance=len(batch))

    return all_embeddings, progress_stats
```
