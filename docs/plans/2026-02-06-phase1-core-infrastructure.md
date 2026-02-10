# Phase 1: Core Infrastructure Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the foundational infrastructure for the clew tool — project skeleton, chunking pipeline, caching, change detection, embedding abstraction, and safety limits.

**Architecture:** A Python CLI tool that uses tree-sitter for AST-based code chunking, Voyage AI for embeddings, Qdrant for vector storage, and SQLite for caching. Files are chunked via a three-tier fallback (AST → token-recursive → line split), then embedded and stored. Change detection uses git-diff primarily with file-hash as fallback. All configuration is Pydantic-validated from YAML.

**Tech Stack:** Python 3.10+, tree-sitter, Voyage AI, Qdrant, SQLite, typer/rich CLI, Pydantic v2, pathspec, pytest/ruff/mypy

---

## Source of Truth

All specs, schemas, models, and code samples come from `docs/IMPLEMENTATION.md`. When in doubt, re-read that file. `docs/DESIGN.md` provides architectural rationale. `CLAUDE.md` has project conventions.

## Conventions (from CLAUDE.md)

- `ruff` for formatting and linting
- `mypy --strict` for type checking
- Async where interacting with Voyage API or Qdrant
- All config through Pydantic models validated from YAML
- Error messages tell the user how to fix the problem

---

## Task 0: Project Skeleton

**Files:**
- Create: Full directory tree per IMPLEMENTATION.md Section 1
- Create: `pyproject.toml`
- Create: All `__init__.py` files
- Create: `clew/exceptions.py`
- Create: `clew/models.py`
- Create: `clew/config.py`
- Create: `clew/__main__.py`
- Create: `tests/conftest.py`
- Create: `tests/fixtures/python/sample_models.py`

### Step 1: Create directory structure

Create every directory in the tree:

```bash
mkdir -p clew/chunker
mkdir -p clew/search
mkdir -p clew/indexer
mkdir -p clew/clients
mkdir -p tests/unit
mkdir -p tests/integration
mkdir -p tests/fixtures/python
mkdir -p tests/fixtures/typescript
mkdir -p tests/fixtures/expected
mkdir -p .github/workflows
```

### Step 2: Create pyproject.toml

Copy exactly from IMPLEMENTATION.md Section 2:

```toml
[project]
name = "clew"
version = "0.1.0"
description = "Semantic code search with hybrid retrieval and MCP integration"
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.10"
authors = [
    {name = "Ruminaider", email = "hello@ruminaider.com"}
]
keywords = ["clew", "embeddings", "qdrant", "mcp", "claude"]

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
    "respx>=0.21.0",
]

[project.scripts]
clew = "clew.cli:app"

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

### Step 3: Create all `__init__.py` files

Create empty `__init__.py` in each package directory:

- `clew/__init__.py`
- `clew/chunker/__init__.py`
- `clew/search/__init__.py`
- `clew/indexer/__init__.py`
- `clew/clients/__init__.py`
- `tests/__init__.py`

### Step 4: Create `clew/__main__.py`

```python
"""Entry point: python -m clew."""

from clew.cli import app

app()
```

### Step 5: Create `clew/exceptions.py`

Copy the full exception hierarchy from IMPLEMENTATION.md Section 7:

```python
"""Custom exception hierarchy for clew."""


class ClewError(Exception):
    """Base exception for clew."""


# Configuration errors
class ConfigError(ClewError):
    """Configuration-related errors."""


class ConfigNotFoundError(ConfigError):
    """Config file not found."""


class ConfigValidationError(ConfigError):
    """Config validation failed."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(f"Config validation failed: {', '.join(errors)}")


# Infrastructure errors
class InfrastructureError(ClewError):
    """Infrastructure-related errors."""


class QdrantError(InfrastructureError):
    """Qdrant-related errors."""


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


class VoyageAuthError(VoyageError):
    """Voyage API authentication failed."""

    def __init__(self) -> None:
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
class IndexingError(ClewError):
    """Indexing-related errors."""


class ParseError(IndexingError):
    """Failed to parse source file."""

    def __init__(self, file_path: str, errors: list[str]):
        self.file_path = file_path
        self.errors = errors
        super().__init__(f"Failed to parse {file_path}: {errors}")


# Search errors
class SearchError(ClewError):
    """Search-related errors."""


class SearchUnavailableError(SearchError):
    """Search service is unavailable."""


class InvalidFilterError(SearchError):
    """Invalid search filter."""

    def __init__(self, filter_name: str, value: str, valid_values: list[str]):
        super().__init__(
            f"Invalid filter '{filter_name}': '{value}'. "
            f"Valid values: {valid_values}"
        )
```

### Step 6: Create `clew/models.py`

Copy the full Pydantic models from IMPLEMENTATION.md Section 5:

```python
"""Pydantic models for data structures."""

from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field, field_validator


class ChunkStrategy(str, Enum):
    CLASS_WITH_METHODS = "class_with_methods"
    FUNCTION = "function"
    FILE = "file"
    SECTION = "section"


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
    exclude_patterns: list[str] = Field(
        default_factory=lambda: [
            "**/.env*",
            "**/secrets/**",
            "**/*credential*",
            "**/*secret*",
            "**/*.pem",
            "**/*.key",
        ]
    )


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
    embedding_provider: str = Field(default="voyage")
    embedding_model: str = Field(default="voyage-code-3")


class ProjectConfig(BaseModel):
    """Root configuration model."""

    project: dict = Field(default_factory=lambda: {"name": "default", "root": "."})
    collections: dict[str, CollectionConfig] = Field(default_factory=dict)
    chunking: dict = Field(default_factory=lambda: {"default_max_tokens": 3000})
    django: DjangoConfig = Field(default_factory=DjangoConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)
    indexing: IndexingConfig = Field(default_factory=IndexingConfig)
    terminology_file: str | None = None

    @field_validator("collections", mode="before")
    @classmethod
    def validate_collections(cls, v: dict) -> dict:  # type: ignore[type-arg]
        if not v:
            return {
                "code": CollectionConfig(
                    include=["**/*.py", "**/*.ts", "**/*.tsx"],
                    exclude=["**/migrations/**", "**/node_modules/**"],
                ),
                "docs": CollectionConfig(include=["**/*.md"], exclude=[]),
            }
        return {
            k: CollectionConfig(**v_) if isinstance(v_, dict) else v_
            for k, v_ in v.items()
        }

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
    def from_yaml_with_errors(
        cls, path: Path
    ) -> tuple["ProjectConfig", list[str]]:
        """Load config and return any validation errors."""
        import yaml
        from pydantic import ValidationError

        errors: list[str] = []

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

### Step 7: Create `clew/config.py`

```python
"""Config loading and validation."""

import os
from pathlib import Path


class Environment:
    """Load environment variables with defaults."""

    VOYAGE_API_KEY: str = os.environ.get("VOYAGE_API_KEY", "")
    QDRANT_URL: str = os.environ.get("QDRANT_URL", "http://localhost:6333")
    QDRANT_API_KEY: str | None = os.environ.get("QDRANT_API_KEY") or None
    CACHE_DIR: Path = Path(os.environ.get("CLEW_CACHE_DIR", ".clew"))
    LOG_LEVEL: str = os.environ.get("CLEW_LOG_LEVEL", "INFO")

    @classmethod
    def validate(cls) -> list[str]:
        """Return list of missing required env vars."""
        errors: list[str] = []
        if not cls.VOYAGE_API_KEY:
            errors.append("VOYAGE_API_KEY is required")
        return errors
```

### Step 8: Create `tests/conftest.py`

```python
"""Shared pytest fixtures."""

import pytest
from pathlib import Path
from unittest.mock import Mock, AsyncMock

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_python_file() -> str:
    """Sample Python source for testing."""
    return (FIXTURES_DIR / "python" / "sample_models.py").read_text()


@pytest.fixture
def mock_voyage_client() -> Mock:
    """Mock Voyage API client."""
    client = Mock()
    client.embed = AsyncMock(
        return_value=Mock(embeddings=[[0.1] * 1024])
    )
    client.rerank = AsyncMock(
        return_value=Mock(results=[Mock(index=0, relevance_score=0.95)])
    )
    return client


@pytest.fixture
def mock_qdrant_client() -> Mock:
    """Mock Qdrant client."""
    client = Mock()
    client.get_collections = Mock(return_value=Mock(collections=[]))
    client.create_collection = Mock()
    client.upsert = Mock()
    client.query_points = Mock(return_value=[])
    return client


@pytest.fixture
def temp_cache_dir(tmp_path: Path) -> Path:
    """Temporary directory for SQLite caches."""
    cache_dir = tmp_path / ".clew"
    cache_dir.mkdir()
    return cache_dir
```

### Step 9: Create test fixture file

Create `tests/fixtures/python/sample_models.py` — copy from IMPLEMENTATION.md Section 8:

```python
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


def create_prescription(user, medication: str) -> "Prescription":
    """Factory function to create a prescription."""
    from django.utils import timezone
    from datetime import timedelta

    return Prescription.objects.create(
        user=user,
        medication=medication,
        expires_at=timezone.now() + timedelta(days=30)
    )
```

### Step 10: Create stub `clew/cli.py` (placeholder for Task 1.5)

```python
"""Typer CLI for clew."""

from pathlib import Path

import typer

app = typer.Typer(help="Semantic code search tool")


@app.command()
def index(
    config: Path = typer.Option("config.yaml", "--config", "-c"),
    full: bool = typer.Option(False, "--full"),
    files: list[str] = typer.Option(None, "--files", "-f"),
) -> None:
    """Index the codebase."""
    typer.echo("Indexing not yet implemented.")


@app.command()
def status() -> None:
    """Show system health and index statistics."""
    typer.echo("Status not yet implemented.")


@app.command()
def search(
    query: str = typer.Argument(...),
    raw: bool = typer.Option(False, "--raw"),
) -> None:
    """Search the codebase."""
    typer.echo("Search not yet implemented.")
```

### Step 11: Install and verify skeleton

```bash
pip install -e ".[dev]"
ruff check .
ruff format --check .
mypy clew/
pytest --co  # collect tests (should find conftest.py)
```

Expected: All commands pass with zero errors. `mypy` may have issues — fix any strict mode violations before proceeding.

### Step 12: Commit

```bash
git add -A
git commit -m "scaffold: project skeleton with models, exceptions, config, and test fixtures"
```

---

## Task 1.1: Qdrant Docker Setup

**Files:**
- Create: `docker-compose.yml`

### Step 1: Write the docker-compose.yml

Create `docker-compose.yml` in project root — copy from IMPLEMENTATION.md Section 3:

```yaml
services:
  qdrant:
    image: qdrant/qdrant:v1.9.2
    container_name: clew-qdrant
    ports:
      - "6333:6333"
      - "6334:6334"
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

### Step 2: Create `.env.example`

```bash
# Required
VOYAGE_API_KEY=pa-xxxxxxxxxxxxxxxxxxxx

# Optional (defaults shown)
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=
CLEW_CACHE_DIR=.clew
CLEW_LOG_LEVEL=INFO
```

### Step 3: Create `.gitignore`

```
# Python
__pycache__/
*.pyc
*.pyo
*.egg-info/
dist/
build/
.venv/
venv/

# IDE
.vscode/
.idea/

# Environment
.env

# Cache
.clew/
.mypy_cache/
.pytest_cache/
.ruff_cache/

# Qdrant local data
.qdrant/
```

### Step 4: Verify Qdrant starts

```bash
docker compose up -d qdrant
sleep 5
curl -s http://localhost:6333/ | python -m json.tool
```

Expected: JSON response with `"title": "qdrant - vector database"`.

### Step 5: Verify data persistence

```bash
docker compose down
docker compose up -d qdrant
sleep 5
curl -s http://localhost:6333/ | python -m json.tool
```

Expected: Same response — Qdrant data persists via named volume.

### Step 6: Commit

```bash
git add docker-compose.yml .env.example .gitignore
git commit -m "feat(infra): add Qdrant Docker setup with health check and persistence"
```

---

## Task 1.2: Voyage Tokenizer Integration

**Files:**
- Create: `clew/chunker/tokenizer.py`
- Create: `tests/unit/test_tokenizer.py`

### Step 1: Write the failing test

```python
# tests/unit/test_tokenizer.py
"""Tests for Voyage tokenizer wrapper."""

from clew.chunker.tokenizer import count_tokens, chunk_fits


class TestCountTokens:
    def test_empty_string(self) -> None:
        assert count_tokens("") == 0

    def test_simple_text(self) -> None:
        tokens = count_tokens("hello world")
        assert tokens > 0
        assert isinstance(tokens, int)

    def test_python_code(self) -> None:
        code = "def hello():\n    return 'world'"
        tokens = count_tokens(code)
        assert tokens > 0

    def test_longer_text_has_more_tokens(self) -> None:
        short = count_tokens("hello")
        long = count_tokens("hello world this is a longer sentence")
        assert long > short


class TestChunkFits:
    def test_small_chunk_fits(self) -> None:
        assert chunk_fits("hello world", max_tokens=100) is True

    def test_default_limit(self) -> None:
        # A small string should fit within 4000 tokens
        assert chunk_fits("x" * 10) is True

    def test_large_chunk_does_not_fit(self) -> None:
        # Generate text likely to exceed 10 tokens
        large = "word " * 5000
        assert chunk_fits(large, max_tokens=10) is False
```

### Step 2: Run test to verify it fails

```bash
pytest tests/unit/test_tokenizer.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'clew.chunker.tokenizer'` (module doesn't exist yet).

### Step 3: Write implementation

```python
# clew/chunker/tokenizer.py
"""Voyage tokenizer wrapper for accurate token counting."""

from functools import lru_cache

from transformers import AutoTokenizer, PreTrainedTokenizerBase


@lru_cache(maxsize=1)
def get_tokenizer() -> PreTrainedTokenizerBase:
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

### Step 4: Run test to verify it passes

```bash
pytest tests/unit/test_tokenizer.py -v
```

Expected: All tests PASS.

### Step 5: Run linters

```bash
ruff check clew/chunker/tokenizer.py
mypy clew/chunker/tokenizer.py
```

Expected: No errors.

### Step 6: Commit

```bash
git add clew/chunker/tokenizer.py tests/unit/test_tokenizer.py
git commit -m "feat(chunker): add Voyage tokenizer integration for token counting"
```

---

## Task 1.3: Basic AST Chunker

**Files:**
- Create: `clew/chunker/parser.py`
- Create: `clew/chunker/strategies.py`
- Create: `tests/unit/test_chunker.py`

### Step 1: Write the failing tests

```python
# tests/unit/test_chunker.py
"""Tests for AST parsing and entity extraction."""

from clew.chunker.parser import ASTParser
from clew.chunker.strategies import PythonChunker, CodeEntity


class TestASTParser:
    def setup_method(self) -> None:
        self.parser = ASTParser()

    def test_get_language_python(self) -> None:
        assert self.parser.get_language("models.py") == "python"

    def test_get_language_typescript(self) -> None:
        assert self.parser.get_language("app.ts") == "typescript"

    def test_get_language_tsx(self) -> None:
        assert self.parser.get_language("Component.tsx") == "tsx"

    def test_get_language_javascript(self) -> None:
        assert self.parser.get_language("index.js") == "javascript"

    def test_get_language_jsx(self) -> None:
        assert self.parser.get_language("App.jsx") == "javascript"

    def test_get_language_unsupported(self) -> None:
        assert self.parser.get_language("style.css") is None

    def test_parse_valid_python(self) -> None:
        code = "def hello():\n    return 'world'"
        tree = self.parser.parse(code, "python")
        assert tree is not None
        assert tree.root_node is not None

    def test_parse_file_auto_detect(self) -> None:
        code = "class Foo:\n    pass"
        tree = self.parser.parse_file("test.py", code)
        assert tree is not None

    def test_parse_file_unsupported_returns_none(self) -> None:
        assert self.parser.parse_file("style.css", "body {}") is None


class TestPythonChunker:
    def setup_method(self) -> None:
        self.parser = ASTParser()
        self.chunker = PythonChunker()

    def test_extract_function(self) -> None:
        code = "def greet(name: str) -> str:\n    return f'Hello {name}'"
        tree = self.parser.parse(code, "python")
        assert tree is not None
        entities = list(self.chunker.extract_entities(tree, code))
        assert len(entities) == 1
        assert entities[0].entity_type == "function"
        assert entities[0].name == "greet"
        assert entities[0].qualified_name == "greet"

    def test_extract_class_and_methods(self, sample_python_file: str) -> None:
        tree = self.parser.parse(sample_python_file, "python")
        assert tree is not None
        entities = list(self.chunker.extract_entities(tree, sample_python_file))

        # Should find: Prescription class, is_expired method, create_prescription function
        names = [e.name for e in entities]
        assert "Prescription" in names
        assert "is_expired" in names
        assert "create_prescription" in names

    def test_method_has_parent_class(self, sample_python_file: str) -> None:
        tree = self.parser.parse(sample_python_file, "python")
        assert tree is not None
        entities = list(self.chunker.extract_entities(tree, sample_python_file))

        method = next(e for e in entities if e.name == "is_expired")
        assert method.parent_class == "Prescription"
        assert method.qualified_name == "Prescription.is_expired"

    def test_entity_has_line_numbers(self, sample_python_file: str) -> None:
        tree = self.parser.parse(sample_python_file, "python")
        assert tree is not None
        entities = list(self.chunker.extract_entities(tree, sample_python_file))

        for entity in entities:
            assert entity.line_start > 0
            assert entity.line_end >= entity.line_start

    def test_entity_content_is_source_code(self) -> None:
        code = "def add(a, b):\n    return a + b"
        tree = self.parser.parse(code, "python")
        assert tree is not None
        entities = list(self.chunker.extract_entities(tree, code))
        assert len(entities) == 1
        assert "return a + b" in entities[0].content
```

### Step 2: Run test to verify it fails

```bash
pytest tests/unit/test_chunker.py -v
```

Expected: FAIL — modules don't exist yet.

### Step 3: Write `clew/chunker/parser.py`

Copy from IMPLEMENTATION.md Section 6 (ASTParser class):

```python
"""Tree-sitter AST parsing."""

from __future__ import annotations

from typing import Any

from tree_sitter import Language, Parser
import tree_sitter_javascript
import tree_sitter_python
import tree_sitter_typescript


class ASTParser:
    """Parse source files into AST using tree-sitter."""

    def __init__(self) -> None:
        self._parsers: dict[str, Parser] = {}
        self._init_parsers()

    def _init_parsers(self) -> None:
        """Initialize parsers for each supported language."""
        py_parser = Parser()
        py_parser.language = Language(tree_sitter_python.language())
        self._parsers["python"] = py_parser

        ts_parser = Parser()
        ts_parser.language = Language(tree_sitter_typescript.language_typescript())
        self._parsers["typescript"] = ts_parser

        tsx_parser = Parser()
        tsx_parser.language = Language(tree_sitter_typescript.language_tsx())
        self._parsers["tsx"] = tsx_parser

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

    def parse(self, content: str, language: str) -> Any:
        """Parse source content into AST."""
        parser = self._parsers.get(language)
        if not parser:
            return None
        try:
            return parser.parse(content.encode("utf-8"))
        except Exception:
            return None

    def parse_file(self, file_path: str, content: str) -> Any:
        """Parse file content, auto-detecting language."""
        language = self.get_language(file_path)
        if not language:
            return None
        return self.parse(content, language)
```

### Step 4: Write `clew/chunker/strategies.py`

Copy from IMPLEMENTATION.md Section 6 (CodeEntity + PythonChunker):

```python
"""File-type chunking strategies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator


@dataclass
class CodeEntity:
    """A parsed code entity (class, function, method)."""

    entity_type: str
    name: str
    qualified_name: str
    content: str
    line_start: int
    line_end: int
    parent_class: str | None


class PythonChunker:
    """Extract code entities from Python AST."""

    DEFINITION_TYPES = {"class_definition", "function_definition"}

    def extract_entities(self, tree: Any, source: str) -> Iterator[CodeEntity]:
        """Extract all code entities from AST."""
        source_bytes = source.encode("utf-8")
        for node in self._walk_definitions(tree.root_node):
            yield from self._node_to_entity(node, source_bytes)

    def _walk_definitions(self, node: Any) -> Iterator[Any]:
        """Walk tree finding definition nodes."""
        if node.type in self.DEFINITION_TYPES:
            yield node
        for child in node.children:
            yield from self._walk_definitions(child)

    def _node_to_entity(
        self, node: Any, source_bytes: bytes
    ) -> Iterator[CodeEntity]:
        """Convert AST node to CodeEntity."""
        name = self._get_name(node)
        content = source_bytes[node.start_byte : node.end_byte].decode("utf-8")

        if node.type == "class_definition":
            yield CodeEntity(
                entity_type="class",
                name=name,
                qualified_name=name,
                content=content,
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                parent_class=None,
            )
            for method in self._get_methods(node):
                method_name = self._get_name(method)
                method_content = source_bytes[
                    method.start_byte : method.end_byte
                ].decode("utf-8")
                yield CodeEntity(
                    entity_type="method",
                    name=method_name,
                    qualified_name=f"{name}.{method_name}",
                    content=method_content,
                    line_start=method.start_point[0] + 1,
                    line_end=method.end_point[0] + 1,
                    parent_class=name,
                )
        elif node.type == "function_definition":
            yield CodeEntity(
                entity_type="function",
                name=name,
                qualified_name=name,
                content=content,
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                parent_class=None,
            )

    def _get_name(self, node: Any) -> str:
        """Extract name from definition node."""
        for child in node.children:
            if child.type == "identifier":
                return child.text.decode("utf-8")  # type: ignore[no-any-return]
        return "unknown"

    def _get_methods(self, class_node: Any) -> Iterator[Any]:
        """Get method nodes from class body."""
        for child in class_node.children:
            if child.type == "block":
                for stmt in child.children:
                    if stmt.type == "function_definition":
                        yield stmt
```

### Step 5: Run tests to verify they pass

```bash
pytest tests/unit/test_chunker.py -v
```

Expected: All tests PASS.

### Step 6: Run linters

```bash
ruff check clew/chunker/parser.py clew/chunker/strategies.py
mypy clew/chunker/parser.py clew/chunker/strategies.py
```

Expected: No errors. The `Any` types for tree-sitter nodes are acceptable since tree-sitter's Python bindings don't have full type stubs.

### Step 7: Commit

```bash
git add clew/chunker/parser.py clew/chunker/strategies.py tests/unit/test_chunker.py
git commit -m "feat(chunker): add tree-sitter AST parser and Python entity extraction"
```

---

## Task 1.4: SQLite Caching

**Files:**
- Create: `clew/indexer/cache.py`
- Create: `tests/unit/test_cache.py`

### Step 1: Write the failing tests

```python
# tests/unit/test_cache.py
"""Tests for SQLite caching layer."""

import json
from pathlib import Path

import pytest

from clew.indexer.cache import CacheDB


class TestCacheDB:
    @pytest.fixture
    def cache(self, temp_cache_dir: Path) -> CacheDB:
        return CacheDB(temp_cache_dir)

    def test_init_creates_databases(self, cache: CacheDB) -> None:
        assert (cache.cache_dir / "cache.db").exists()
        assert (cache.cache_dir / "state.db").exists()

    def test_init_creates_directory(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "nested" / "cache"
        CacheDB(cache_dir)
        assert cache_dir.exists()


class TestEmbeddingCache:
    @pytest.fixture
    def cache(self, temp_cache_dir: Path) -> CacheDB:
        return CacheDB(temp_cache_dir)

    def test_get_missing_embedding_returns_none(self, cache: CacheDB) -> None:
        result = cache.get_embedding("hash123", "voyage-code-3")
        assert result is None

    def test_set_and_get_embedding(self, cache: CacheDB) -> None:
        embedding = b"\x00\x01\x02\x03"
        cache.set_embedding("hash123", "voyage-code-3", embedding, 42)
        result = cache.get_embedding("hash123", "voyage-code-3")
        assert result == embedding

    def test_different_models_are_separate(self, cache: CacheDB) -> None:
        cache.set_embedding("hash123", "model-a", b"embed-a", 10)
        cache.set_embedding("hash123", "model-b", b"embed-b", 10)
        assert cache.get_embedding("hash123", "model-a") == b"embed-a"
        assert cache.get_embedding("hash123", "model-b") == b"embed-b"

    def test_upsert_replaces_existing(self, cache: CacheDB) -> None:
        cache.set_embedding("hash123", "voyage-code-3", b"old", 10)
        cache.set_embedding("hash123", "voyage-code-3", b"new", 15)
        assert cache.get_embedding("hash123", "voyage-code-3") == b"new"


class TestChunkCache:
    @pytest.fixture
    def cache(self, temp_cache_dir: Path) -> CacheDB:
        return CacheDB(temp_cache_dir)

    def test_get_missing_file_hash_returns_none(self, cache: CacheDB) -> None:
        result = cache.get_file_hash("nonexistent.py")
        assert result is None

    def test_set_and_get_file_hash(self, cache: CacheDB) -> None:
        cache.set_file_chunks("models.py", "abc123", ["chunk1", "chunk2"])
        result = cache.get_file_hash("models.py")
        assert result == "abc123"

    def test_get_file_chunk_ids(self, cache: CacheDB) -> None:
        cache.set_file_chunks("models.py", "abc123", ["chunk1", "chunk2"])
        chunk_ids = cache.get_file_chunk_ids("models.py")
        assert chunk_ids == ["chunk1", "chunk2"]

    def test_update_file_replaces_old(self, cache: CacheDB) -> None:
        cache.set_file_chunks("models.py", "hash1", ["old_chunk"])
        cache.set_file_chunks("models.py", "hash2", ["new_chunk"])
        assert cache.get_file_hash("models.py") == "hash2"
        assert cache.get_file_chunk_ids("models.py") == ["new_chunk"]
```

### Step 2: Run test to verify it fails

```bash
pytest tests/unit/test_cache.py -v
```

Expected: FAIL — module doesn't exist yet.

### Step 3: Write implementation

```python
# clew/indexer/cache.py
"""SQLite caching for embeddings and chunk state."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

CACHE_SCHEMA = """
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

CREATE TABLE IF NOT EXISTS chunk_cache (
    file_path TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    chunk_count INTEGER NOT NULL,
    chunk_ids TEXT NOT NULL,
    updated_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (file_path)
);

CREATE INDEX IF NOT EXISTS idx_chunk_cache_hash
ON chunk_cache(file_hash);
"""

STATE_SCHEMA = """
CREATE TABLE IF NOT EXISTS index_state (
    collection_name TEXT PRIMARY KEY,
    last_commit TEXT,
    last_indexed_at TEXT,
    total_chunks INTEGER DEFAULT 0,
    total_files INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS failed_files (
    file_path TEXT PRIMARY KEY,
    error_type TEXT NOT NULL,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    last_attempt TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS checkpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    collection_name TEXT NOT NULL,
    batch_index INTEGER NOT NULL,
    files_processed TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS safety_state (
    collection_name TEXT PRIMARY KEY,
    chunk_count INTEGER DEFAULT 0,
    last_checked_at TEXT DEFAULT (datetime('now')),
    limit_breached BOOLEAN DEFAULT FALSE
);
"""


class CacheDB:
    """SQLite-based cache for embeddings and indexing state."""

    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._init_databases()

    def _init_databases(self) -> None:
        """Create tables if they don't exist."""
        with self._get_cache_conn() as conn:
            conn.executescript(CACHE_SCHEMA)
        with self._get_state_conn() as conn:
            conn.executescript(STATE_SCHEMA)

    @contextmanager
    def _get_cache_conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.cache_dir / "cache.db")
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    @contextmanager
    def _get_state_conn(self) -> Iterator[sqlite3.Connection]:
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
                "SELECT embedding FROM embedding_cache "
                "WHERE content_hash = ? AND embedding_model = ?",
                (content_hash, model),
            ).fetchone()
            return row["embedding"] if row else None

    def set_embedding(
        self,
        content_hash: str,
        model: str,
        embedding: bytes,
        token_count: int,
    ) -> None:
        """Cache an embedding."""
        with self._get_cache_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO embedding_cache "
                "(content_hash, embedding_model, embedding, token_count) "
                "VALUES (?, ?, ?, ?)",
                (content_hash, model, embedding, token_count),
            )

    def get_file_hash(self, file_path: str) -> str | None:
        """Get cached file hash for change detection."""
        with self._get_cache_conn() as conn:
            row = conn.execute(
                "SELECT file_hash FROM chunk_cache WHERE file_path = ?",
                (file_path,),
            ).fetchone()
            return row["file_hash"] if row else None

    def get_file_chunk_ids(self, file_path: str) -> list[str]:
        """Get cached chunk IDs for a file."""
        with self._get_cache_conn() as conn:
            row = conn.execute(
                "SELECT chunk_ids FROM chunk_cache WHERE file_path = ?",
                (file_path,),
            ).fetchone()
            if row:
                return json.loads(row["chunk_ids"])  # type: ignore[no-any-return]
            return []

    def set_file_chunks(
        self, file_path: str, file_hash: str, chunk_ids: list[str]
    ) -> None:
        """Cache file hash and chunk IDs."""
        with self._get_cache_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO chunk_cache "
                "(file_path, file_hash, chunk_count, chunk_ids) "
                "VALUES (?, ?, ?, ?)",
                (file_path, file_hash, len(chunk_ids), json.dumps(chunk_ids)),
            )
```

### Step 4: Run tests to verify they pass

```bash
pytest tests/unit/test_cache.py -v
```

Expected: All tests PASS.

### Step 5: Run linters

```bash
ruff check clew/indexer/cache.py
mypy clew/indexer/cache.py
```

### Step 6: Commit

```bash
git add clew/indexer/cache.py tests/unit/test_cache.py
git commit -m "feat(indexer): add SQLite caching for embeddings and chunk state"
```

---

## Task 1.5: Minimal CLI

**Files:**
- Modify: `clew/cli.py` (replace stub from Task 0)
- Create: `tests/unit/test_cli.py`

### Step 1: Write the failing tests

```python
# tests/unit/test_cli.py
"""Tests for CLI interface."""

from typer.testing import CliRunner

from clew.cli import app

runner = CliRunner()


class TestCLI:
    def test_help(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Semantic code search tool" in result.stdout

    def test_index_help(self) -> None:
        result = runner.invoke(app, ["index", "--help"])
        assert result.exit_code == 0
        assert "--config" in result.stdout
        assert "--full" in result.stdout

    def test_status_runs(self) -> None:
        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0

    def test_search_help(self) -> None:
        result = runner.invoke(app, ["search", "--help"])
        assert result.exit_code == 0
        assert "--raw" in result.stdout
```

### Step 2: Run test to verify behavior

```bash
pytest tests/unit/test_cli.py -v
```

Expected: Tests may pass if the stub from Task 0 is sufficient. If not, update in next step.

### Step 3: Update `clew/cli.py` with richer stubs

Replace the Task 0 stub with the version from IMPLEMENTATION.md Section 9, adding rich console output for status:

```python
"""Typer CLI for clew."""

from pathlib import Path

import typer
from rich.console import Console

app = typer.Typer(help="Semantic code search tool")
console = Console()


@app.command()
def index(
    config: Path = typer.Option("config.yaml", "--config", "-c"),
    full: bool = typer.Option(False, "--full"),
    files: list[str] = typer.Option(None, "--files", "-f"),
) -> None:
    """Index the codebase."""
    console.print("[yellow]Indexing not yet implemented.[/yellow]")


@app.command()
def status() -> None:
    """Show system health and index statistics."""
    console.print("[bold]clew status[/bold]")
    console.print("  Qdrant: [dim]not checked[/dim]")
    console.print("  Collections: [dim]none[/dim]")


@app.command()
def search(
    query: str = typer.Argument(...),
    raw: bool = typer.Option(False, "--raw"),
) -> None:
    """Search the codebase."""
    console.print("[yellow]Search not yet implemented.[/yellow]")
```

### Step 4: Run tests to verify they pass

```bash
pytest tests/unit/test_cli.py -v
```

Expected: All PASS.

### Step 5: Verify CLI works end-to-end

```bash
clew --help
clew status
```

Expected: Help text displays, status shows stub output.

### Step 6: Commit

```bash
git add clew/cli.py tests/unit/test_cli.py
git commit -m "feat(cli): add minimal typer CLI with index, status, and search commands"
```

---

## Task 1.6: Splitter Fallback Chain

**Files:**
- Create: `clew/chunker/fallback.py`
- Create: `tests/unit/test_fallback.py`

### Step 1: Write the failing tests

```python
# tests/unit/test_fallback.py
"""Tests for the three-tier splitter fallback chain."""

from clew.chunker.fallback import (
    line_split,
    split_file,
    token_recursive_split,
)
from clew.chunker.parser import ASTParser
from clew.chunker.tokenizer import count_tokens


class TestTokenRecursiveSplit:
    def test_small_text_returns_single_chunk(self) -> None:
        result = token_recursive_split("hello world", max_tokens=100)
        assert len(result) == 1
        assert result[0] == "hello world"

    def test_splits_on_paragraph_boundaries(self) -> None:
        text = "paragraph one\n\nparagraph two\n\nparagraph three"
        result = token_recursive_split(text, max_tokens=20, overlap_tokens=0)
        assert len(result) >= 2
        for chunk in result:
            assert count_tokens(chunk) <= 20

    def test_all_chunks_within_limit(self) -> None:
        text = "word " * 500
        result = token_recursive_split(text, max_tokens=50, overlap_tokens=0)
        for chunk in result:
            assert count_tokens(chunk) <= 50

    def test_overlap_applied(self) -> None:
        # Create text that will be split into multiple chunks
        text = "\n\n".join([f"Section {i}: " + "content " * 50 for i in range(5)])
        result = token_recursive_split(text, max_tokens=100, overlap_tokens=20)
        # With overlap, later chunks should contain some content from previous
        assert len(result) >= 2


class TestLineSplit:
    def test_small_text_returns_single_chunk(self) -> None:
        result = line_split("hello", max_tokens=100)
        assert len(result) == 1

    def test_splits_by_lines(self) -> None:
        text = "\n".join(["line " * 20] * 10)
        result = line_split(text, max_tokens=50, overlap_tokens=0)
        assert len(result) >= 2
        for chunk in result:
            assert count_tokens(chunk) <= 50


class TestSplitFile:
    def setup_method(self) -> None:
        self.parser = ASTParser()

    def test_valid_python_uses_ast(self, sample_python_file: str) -> None:
        chunks = split_file(
            "models.py", sample_python_file, max_tokens=3000, ast_parser=self.parser
        )
        assert len(chunks) > 0
        # AST chunks should have source="ast"
        assert all(c.source == "ast" for c in chunks)

    def test_plain_text_uses_fallback(self) -> None:
        plain = "This is just plain text.\n" * 100
        chunks = split_file(
            "readme.txt", plain, max_tokens=50, ast_parser=self.parser
        )
        assert len(chunks) > 0
        assert all(c.source == "fallback" for c in chunks)

    def test_all_chunks_within_token_limit(self) -> None:
        plain = "word " * 2000
        chunks = split_file(
            "big.txt", plain, max_tokens=100, ast_parser=self.parser
        )
        for chunk in chunks:
            assert count_tokens(chunk.content) <= 100
```

### Step 2: Run test to verify it fails

```bash
pytest tests/unit/test_fallback.py -v
```

Expected: FAIL — module doesn't exist.

### Step 3: Write implementation

Create `clew/chunker/fallback.py` — adapted from IMPLEMENTATION.md Section 12. This needs a `Chunk` dataclass for the return type:

```python
"""Splitter fallback chain: tree-sitter → token-recursive → line split."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .tokenizer import count_tokens

if TYPE_CHECKING:
    from .parser import ASTParser
    from .strategies import PythonChunker

SPLIT_SEPARATORS = [
    "\n\nclass ",
    "\n\ndef ",
    "\n\n",
    "\n",
    " ",
]


@dataclass
class Chunk:
    """A chunk of source code or text."""

    content: str
    source: str  # "ast" or "fallback"
    file_path: str


def token_recursive_split(
    text: str,
    max_tokens: int,
    overlap_tokens: int = 200,
    separators: list[str] | None = None,
) -> list[str]:
    """Split text recursively by token count using semantic separators."""
    if count_tokens(text) <= max_tokens:
        return [text]

    separators = separators or SPLIT_SEPARATORS

    for separator in separators:
        parts = text.split(separator)
        if len(parts) == 1:
            continue

        chunks: list[str] = []
        current = parts[0]

        for part in parts[1:]:
            candidate = current + separator + part
            if count_tokens(candidate) <= max_tokens:
                current = candidate
            else:
                if current.strip():
                    chunks.append(current.strip())
                current = (
                    _apply_overlap(chunks, part, overlap_tokens)
                    if chunks
                    else part
                )

        if current.strip():
            chunks.append(current.strip())

        if all(count_tokens(c) <= max_tokens for c in chunks):
            return chunks

    return line_split(text, max_tokens, overlap_tokens)


def line_split(
    text: str, max_tokens: int, overlap_tokens: int = 200
) -> list[str]:
    """Split text by lines, guaranteed to produce valid chunks."""
    lines = text.split("\n")
    chunks: list[str] = []
    current_lines: list[str] = []
    current_tokens = 0

    for line in lines:
        line_tokens = count_tokens(line)
        if current_tokens + line_tokens > max_tokens and current_lines:
            chunks.append("\n".join(current_lines))
            overlap_lines = _get_overlap_lines(current_lines, overlap_tokens)
            current_lines = overlap_lines
            current_tokens = sum(count_tokens(ln) for ln in current_lines)
        current_lines.append(line)
        current_tokens += line_tokens

    if current_lines:
        chunks.append("\n".join(current_lines))

    return chunks


def _apply_overlap(
    chunks: list[str], next_part: str, overlap_tokens: int
) -> str:
    """Prepend overlap from the end of the last chunk."""
    if not chunks or overlap_tokens == 0:
        return next_part
    last_chunk = chunks[-1]
    lines = last_chunk.split("\n")
    overlap_lines = _get_overlap_lines(lines, overlap_tokens)
    overlap_text = "\n".join(overlap_lines)
    return overlap_text + "\n" + next_part if overlap_text else next_part


def _get_overlap_lines(lines: list[str], overlap_tokens: int) -> list[str]:
    """Get lines from the end that fit within overlap_tokens."""
    result: list[str] = []
    total = 0
    for line in reversed(lines):
        line_tokens = count_tokens(line)
        if total + line_tokens > overlap_tokens:
            break
        result.insert(0, line)
        total += line_tokens
    return result


def split_file(
    file_path: str,
    content: str,
    max_tokens: int,
    ast_parser: ASTParser,
    overlap_tokens: int = 200,
) -> list[Chunk]:
    """Split a file using the three-tier fallback chain.

    Tier 1: tree-sitter AST parsing (no overlap)
    Tier 2: Token-recursive splitting (with overlap)
    Tier 3: Line splitting (with overlap, guaranteed)
    """
    tree = ast_parser.parse_file(file_path, content)
    if tree:
        chunks = _extract_ast_chunks(tree, file_path, content, max_tokens)
        if chunks:
            return chunks

    text_chunks = token_recursive_split(content, max_tokens, overlap_tokens)
    return [
        Chunk(content=c, source="fallback", file_path=file_path)
        for c in text_chunks
    ]


def _extract_ast_chunks(
    tree: Any, file_path: str, content: str, max_tokens: int
) -> list[Chunk]:
    """Extract chunks from AST, returning empty list if no entities found."""
    from .strategies import PythonChunker

    # Determine chunker based on file extension
    ext = file_path.rsplit(".", 1)[-1].lower()
    if ext != "py":
        return []  # Only Python chunker implemented for now

    chunker = PythonChunker()
    entities = list(chunker.extract_entities(tree, content))

    if not entities:
        return []

    chunks: list[Chunk] = []
    for entity in entities:
        if count_tokens(entity.content) <= max_tokens:
            chunks.append(
                Chunk(content=entity.content, source="ast", file_path=file_path)
            )
        else:
            # Entity too large — fallback to token-recursive for this entity
            sub_chunks = token_recursive_split(
                entity.content, max_tokens, overlap_tokens=200
            )
            chunks.extend(
                Chunk(content=c, source="fallback", file_path=file_path)
                for c in sub_chunks
            )

    return chunks
```

### Step 4: Run tests to verify they pass

```bash
pytest tests/unit/test_fallback.py -v
```

Expected: All tests PASS.

### Step 5: Run linters

```bash
ruff check clew/chunker/fallback.py
mypy clew/chunker/fallback.py
```

### Step 6: Commit

```bash
git add clew/chunker/fallback.py tests/unit/test_fallback.py
git commit -m "feat(chunker): add three-tier splitter fallback chain (AST → token → line)"
```

---

## Task 1.7: Embedding Provider ABC

**Files:**
- Create: `clew/clients/base.py`
- Create: `clew/clients/voyage.py`
- Modify: `clew/clients/__init__.py`
- Create: `tests/unit/test_embedding_provider.py`

### Step 1: Write the failing tests

```python
# tests/unit/test_embedding_provider.py
"""Tests for embedding provider abstraction."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from clew.clients.base import EmbeddingProvider
from clew.clients.voyage import VoyageEmbeddingProvider


class TestEmbeddingProviderABC:
    def test_cannot_instantiate_abc(self) -> None:
        with pytest.raises(TypeError):
            EmbeddingProvider()  # type: ignore[abstract]


class TestVoyageEmbeddingProvider:
    def test_dimensions(self) -> None:
        with patch("clew.clients.voyage.voyageai"):
            provider = VoyageEmbeddingProvider(api_key="test-key")
        assert provider.dimensions == 1024

    def test_model_name(self) -> None:
        with patch("clew.clients.voyage.voyageai"):
            provider = VoyageEmbeddingProvider(api_key="test-key")
        assert provider.model_name == "voyage-code-3"

    def test_custom_model(self) -> None:
        with patch("clew.clients.voyage.voyageai"):
            provider = VoyageEmbeddingProvider(
                api_key="test-key", model="voyage-3"
            )
        assert provider.model_name == "voyage-3"

    @pytest.mark.asyncio
    async def test_embed_returns_embeddings(self) -> None:
        mock_client = AsyncMock()
        mock_client.embed.return_value = Mock(
            embeddings=[[0.1] * 1024, [0.2] * 1024]
        )

        with patch("clew.clients.voyage.voyageai") as mock_voyage:
            mock_voyage.AsyncClient.return_value = mock_client
            provider = VoyageEmbeddingProvider(api_key="test-key")

        result = await provider.embed(["hello", "world"])
        assert len(result) == 2
        assert len(result[0]) == 1024

    @pytest.mark.asyncio
    async def test_embed_query_returns_single_vector(self) -> None:
        mock_client = AsyncMock()
        mock_client.embed.return_value = Mock(
            embeddings=[[0.1] * 1024]
        )

        with patch("clew.clients.voyage.voyageai") as mock_voyage:
            mock_voyage.AsyncClient.return_value = mock_client
            provider = VoyageEmbeddingProvider(api_key="test-key")

        result = await provider.embed_query("test query")
        assert len(result) == 1024
```

### Step 2: Run test to verify it fails

```bash
pytest tests/unit/test_embedding_provider.py -v
```

Expected: FAIL — modules don't exist.

### Step 3: Write `clew/clients/base.py`

```python
"""Abstract base class for embedding providers."""

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
    async def embed(
        self, texts: list[str], input_type: str = "document"
    ) -> list[list[float]]:
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
        """Embed a single query string."""
        ...
```

### Step 4: Write `clew/clients/voyage.py`

```python
"""Voyage AI embedding provider."""

from __future__ import annotations

import voyageai

from .base import EmbeddingProvider


class VoyageEmbeddingProvider(EmbeddingProvider):
    """Voyage AI embedding provider (default)."""

    def __init__(self, api_key: str, model: str = "voyage-code-3") -> None:
        self._client = voyageai.AsyncClient(api_key=api_key)
        self._model = model
        self._dimensions = 1024

    @property
    def dimensions(self) -> int:
        return self._dimensions

    @property
    def model_name(self) -> str:
        return self._model

    async def embed(
        self, texts: list[str], input_type: str = "document"
    ) -> list[list[float]]:
        result = await self._client.embed(
            texts,
            model=self._model,
            input_type=input_type,
            truncation=True,
        )
        return result.embeddings  # type: ignore[no-any-return]

    async def embed_query(self, query: str) -> list[float]:
        embeddings = await self.embed([query], input_type="query")
        return embeddings[0]
```

### Step 5: Write provider factory in `clew/clients/__init__.py`

```python
"""Client wrappers for external services."""

from __future__ import annotations

from typing import TYPE_CHECKING

from clew.exceptions import ConfigError

if TYPE_CHECKING:
    from clew.config import Environment
    from clew.models import IndexingConfig

    from .base import EmbeddingProvider


def create_embedding_provider(
    config: "IndexingConfig", env: "Environment"
) -> "EmbeddingProvider":
    """Create embedding provider from configuration."""
    if config.embedding_provider == "voyage":
        from .voyage import VoyageEmbeddingProvider

        return VoyageEmbeddingProvider(
            api_key=env.VOYAGE_API_KEY, model=config.embedding_model
        )
    raise ConfigError(f"Unknown embedding provider: {config.embedding_provider}")
```

### Step 6: Run tests to verify they pass

```bash
pytest tests/unit/test_embedding_provider.py -v
```

Expected: All tests PASS.

### Step 7: Run linters

```bash
ruff check clew/clients/
mypy clew/clients/
```

### Step 8: Commit

```bash
git add clew/clients/ tests/unit/test_embedding_provider.py
git commit -m "feat(clients): add EmbeddingProvider ABC with Voyage implementation"
```

---

## Task 1.8: File-Hash Change Detection

**Files:**
- Create: `clew/indexer/file_hash.py`
- Create: `tests/unit/test_file_hash.py`

### Step 1: Write the failing tests

```python
# tests/unit/test_file_hash.py
"""Tests for file-hash change detection."""

from pathlib import Path

import pytest

from clew.indexer.cache import CacheDB
from clew.indexer.file_hash import FileHashTracker


class TestFileHashTracker:
    @pytest.fixture
    def cache(self, temp_cache_dir: Path) -> CacheDB:
        return CacheDB(temp_cache_dir)

    @pytest.fixture
    def tracker(self, cache: CacheDB) -> FileHashTracker:
        return FileHashTracker(cache)

    def test_compute_hash_deterministic(self, tmp_path: Path, tracker: FileHashTracker) -> None:
        f = tmp_path / "test.py"
        f.write_text("hello world")
        h1 = tracker.compute_hash(str(f))
        h2 = tracker.compute_hash(str(f))
        assert h1 == h2

    def test_compute_hash_changes_with_content(self, tmp_path: Path, tracker: FileHashTracker) -> None:
        f = tmp_path / "test.py"
        f.write_text("version 1")
        h1 = tracker.compute_hash(str(f))
        f.write_text("version 2")
        h2 = tracker.compute_hash(str(f))
        assert h1 != h2

    def test_new_file_detected_as_added(self, tmp_path: Path, tracker: FileHashTracker) -> None:
        f = tmp_path / "new.py"
        f.write_text("new file")
        changes = tracker.detect_changes([str(f)])
        assert str(f) in changes["added"]
        assert changes["modified"] == []
        assert changes["unchanged"] == []

    def test_modified_file_detected(self, tmp_path: Path, tracker: FileHashTracker) -> None:
        f = tmp_path / "mod.py"
        f.write_text("original")
        # Register the original hash
        tracker.update_hash(str(f), tracker.compute_hash(str(f)), ["chunk1"])
        # Modify the file
        f.write_text("modified content")
        changes = tracker.detect_changes([str(f)])
        assert str(f) in changes["modified"]

    def test_unchanged_file_detected(self, tmp_path: Path, tracker: FileHashTracker) -> None:
        f = tmp_path / "same.py"
        f.write_text("unchanged")
        tracker.update_hash(str(f), tracker.compute_hash(str(f)), ["chunk1"])
        changes = tracker.detect_changes([str(f)])
        assert str(f) in changes["unchanged"]

    def test_mixed_changes(self, tmp_path: Path, tracker: FileHashTracker) -> None:
        new = tmp_path / "new.py"
        new.write_text("new")

        existing = tmp_path / "existing.py"
        existing.write_text("existing")
        tracker.update_hash(str(existing), tracker.compute_hash(str(existing)), ["c1"])

        modified = tmp_path / "modified.py"
        modified.write_text("original")
        tracker.update_hash(str(modified), tracker.compute_hash(str(modified)), ["c2"])
        modified.write_text("changed")

        changes = tracker.detect_changes([str(new), str(existing), str(modified)])
        assert str(new) in changes["added"]
        assert str(existing) in changes["unchanged"]
        assert str(modified) in changes["modified"]
```

### Step 2: Run test to verify it fails

```bash
pytest tests/unit/test_file_hash.py -v
```

Expected: FAIL — module doesn't exist.

### Step 3: Write implementation

```python
# clew/indexer/file_hash.py
"""File-hash based change detection (secondary to git-diff)."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .cache import CacheDB


class FileHashTracker:
    """File-hash based change detection (secondary to git-diff)."""

    def __init__(self, cache: "CacheDB") -> None:
        self.cache = cache

    def compute_hash(self, file_path: str) -> str:
        """Compute SHA256 hash of file contents."""
        content = Path(file_path).read_bytes()
        return hashlib.sha256(content).hexdigest()

    def detect_changes(self, file_paths: list[str]) -> dict[str, list[str]]:
        """Classify files as added, modified, or unchanged."""
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

    def update_hash(
        self, file_path: str, file_hash: str, chunk_ids: list[str]
    ) -> None:
        """Update cached hash after successful indexing."""
        self.cache.set_file_chunks(file_path, file_hash, chunk_ids)
```

### Step 4: Run tests to verify they pass

```bash
pytest tests/unit/test_file_hash.py -v
```

Expected: All tests PASS.

### Step 5: Run linters

```bash
ruff check clew/indexer/file_hash.py
mypy clew/indexer/file_hash.py
```

### Step 6: Commit

```bash
git add clew/indexer/file_hash.py tests/unit/test_file_hash.py
git commit -m "feat(indexer): add file-hash change detection as git-diff fallback"
```

---

## Task 1.9: Ignore Pattern Loading

**Files:**
- Create: `clew/indexer/ignore.py`
- Create: `tests/unit/test_ignore.py`

### Step 1: Write the failing tests

```python
# tests/unit/test_ignore.py
"""Tests for ignore pattern loading and matching."""

import os
from pathlib import Path

import pytest

from clew.indexer.ignore import DEFAULT_IGNORE_PATTERNS, IgnorePatternLoader


class TestDefaultPatterns:
    def test_defaults_include_pycache(self) -> None:
        assert "__pycache__/" in DEFAULT_IGNORE_PATTERNS

    def test_defaults_include_node_modules(self) -> None:
        assert "node_modules/" in DEFAULT_IGNORE_PATTERNS

    def test_defaults_include_git(self) -> None:
        assert ".git/" in DEFAULT_IGNORE_PATTERNS


class TestIgnorePatternLoader:
    @pytest.fixture
    def project_root(self, tmp_path: Path) -> Path:
        return tmp_path

    def test_default_patterns_applied(self, project_root: Path) -> None:
        loader = IgnorePatternLoader(project_root)
        loader.load()
        assert loader.should_ignore("__pycache__/module.pyc")
        assert loader.should_ignore("node_modules/pkg/index.js")

    def test_gitignore_loaded(self, project_root: Path) -> None:
        (project_root / ".gitignore").write_text("*.log\nbuild/\n")
        loader = IgnorePatternLoader(project_root)
        loader.load()
        assert loader.should_ignore("app.log")
        assert loader.should_ignore("build/output.js")

    def test_clewignore_loaded(self, project_root: Path) -> None:
        (project_root / ".clewignore").write_text("*.generated.py\n")
        loader = IgnorePatternLoader(project_root)
        loader.load()
        assert loader.should_ignore("output.generated.py")

    def test_config_excludes_applied(self, project_root: Path) -> None:
        loader = IgnorePatternLoader(
            project_root, config_excludes=["**/migrations/**"]
        )
        loader.load()
        assert loader.should_ignore("backend/app/migrations/0001.py")

    def test_env_var_override(self, project_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLEW_EXCLUDE", "*.tmp,*.bak")
        loader = IgnorePatternLoader(project_root)
        loader.load()
        assert loader.should_ignore("data.tmp")
        assert loader.should_ignore("backup.bak")

    def test_non_matching_file_not_ignored(self, project_root: Path) -> None:
        loader = IgnorePatternLoader(project_root)
        loader.load()
        assert not loader.should_ignore("src/models.py")

    def test_comments_and_blanks_skipped(self, project_root: Path) -> None:
        (project_root / ".gitignore").write_text(
            "# This is a comment\n\n*.log\n  \n"
        )
        loader = IgnorePatternLoader(project_root)
        loader.load()
        assert loader.should_ignore("app.log")

    def test_lazy_load_on_should_ignore(self, project_root: Path) -> None:
        loader = IgnorePatternLoader(project_root)
        # Don't call load() explicitly — should_ignore triggers it
        assert loader.should_ignore("__pycache__/foo.pyc")
```

### Step 2: Run test to verify it fails

```bash
pytest tests/unit/test_ignore.py -v
```

Expected: FAIL — module doesn't exist.

### Step 3: Write implementation

```python
# clew/indexer/ignore.py
"""Ignore pattern loading from 5-source hierarchy."""

from __future__ import annotations

import os
from pathlib import Path

from pathspec import PathSpec

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

    def __init__(
        self,
        project_root: Path,
        config_excludes: list[str] | None = None,
    ) -> None:
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

        # Source 3: .clewignore
        clewignore = self.project_root / ".clewignore"
        if clewignore.exists():
            all_patterns.extend(self._read_pattern_file(clewignore))

        # Source 4: config.yaml exclude patterns
        all_patterns.extend(self.config_excludes)

        # Source 5: Environment variable (highest priority)
        env_excludes = os.environ.get("CLEW_EXCLUDE", "")
        if env_excludes:
            all_patterns.extend(env_excludes.split(","))

        self._spec = PathSpec.from_lines("gitwildmatch", all_patterns)
        return self._spec

    def should_ignore(self, file_path: str) -> bool:
        """Check if a file should be ignored."""
        if self._spec is None:
            self.load()
        assert self._spec is not None
        return self._spec.match_file(file_path)

    @staticmethod
    def _read_pattern_file(path: Path) -> list[str]:
        """Read patterns from a file, skipping comments and blanks."""
        patterns: list[str] = []
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                patterns.append(line)
        return patterns
```

### Step 4: Run tests to verify they pass

```bash
pytest tests/unit/test_ignore.py -v
```

Expected: All tests PASS.

### Step 5: Run linters

```bash
ruff check clew/indexer/ignore.py
mypy clew/indexer/ignore.py
```

### Step 6: Commit

```bash
git add clew/indexer/ignore.py tests/unit/test_ignore.py
git commit -m "feat(indexer): add 5-source ignore pattern loading with pathspec"
```

---

## Task 1.10: Safety Limits

**Files:**
- Create: `clew/safety.py`
- Create: `tests/unit/test_safety.py`

The `SafetyConfig` model already exists in `clew/models.py` from Task 0. This task implements the `SafetyChecker` that enforces those limits.

### Step 1: Write the failing tests

```python
# tests/unit/test_safety.py
"""Tests for safety limit enforcement."""

import logging

import pytest

from clew.models import SafetyConfig
from clew.safety import SafetyChecker


class TestSafetyCheckerFileSize:
    def test_small_file_allowed(self) -> None:
        checker = SafetyChecker(SafetyConfig())
        assert checker.check_file("small.py", 1000) is True

    def test_file_at_limit_allowed(self) -> None:
        checker = SafetyChecker(SafetyConfig(max_file_size_bytes=1_048_576))
        assert checker.check_file("exact.py", 1_048_576) is True

    def test_large_file_rejected(self) -> None:
        checker = SafetyChecker(SafetyConfig(max_file_size_bytes=1_048_576))
        assert checker.check_file("huge.min.js", 5_000_000) is False

    def test_custom_limit(self) -> None:
        checker = SafetyChecker(SafetyConfig(max_file_size_bytes=5000))
        assert checker.check_file("small.py", 4999) is True
        assert checker.check_file("big.py", 5001) is False


class TestSafetyCheckerTotalChunks:
    def test_within_limit(self) -> None:
        checker = SafetyChecker(SafetyConfig(max_total_chunks=500_000))
        assert checker.check_total_chunks(499_990, 5) is True

    def test_at_limit(self) -> None:
        checker = SafetyChecker(SafetyConfig(max_total_chunks=500_000))
        assert checker.check_total_chunks(499_990, 10) is True

    def test_exceeds_limit(self) -> None:
        checker = SafetyChecker(SafetyConfig(max_total_chunks=500_000))
        assert checker.check_total_chunks(499_990, 20) is False

    def test_custom_limit(self) -> None:
        checker = SafetyChecker(SafetyConfig(max_total_chunks=1000))
        assert checker.check_total_chunks(999, 1) is True
        assert checker.check_total_chunks(999, 2) is False


class TestSafetyCheckerCollectionLimits:
    def test_no_collection_limit_allows_all(self) -> None:
        checker = SafetyChecker(SafetyConfig())
        assert checker.check_collection_chunks("code", 999_999, 1) is True

    def test_collection_limit_enforced(self) -> None:
        checker = SafetyChecker(
            SafetyConfig(collection_limits={"code": 10_000})
        )
        assert checker.check_collection_chunks("code", 9_999, 1) is True
        assert checker.check_collection_chunks("code", 9_999, 2) is False

    def test_unlisted_collection_unlimited(self) -> None:
        checker = SafetyChecker(
            SafetyConfig(collection_limits={"code": 10_000})
        )
        assert checker.check_collection_chunks("docs", 999_999, 1) is True


class TestSafetyCheckerLogging:
    def test_rejected_file_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        checker = SafetyChecker(SafetyConfig(max_file_size_bytes=100))
        with caplog.at_level(logging.WARNING):
            checker.check_file("big.py", 200)
        assert "big.py" in caplog.text

    def test_rejected_chunks_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        checker = SafetyChecker(SafetyConfig(max_total_chunks=1000))
        with caplog.at_level(logging.ERROR):
            checker.check_total_chunks(999, 10)
        assert "1009" in caplog.text or "1000" in caplog.text
```

### Step 2: Run test to verify it fails

```bash
pytest tests/unit/test_safety.py -v
```

Expected: FAIL — module doesn't exist.

### Step 3: Write implementation

```python
# clew/safety.py
"""Safety limit enforcement for indexing."""

from __future__ import annotations

import logging

from .models import SafetyConfig

logger = logging.getLogger(__name__)


class SafetyChecker:
    """Enforce safety limits to prevent runaway indexing."""

    def __init__(self, config: SafetyConfig) -> None:
        self.config = config

    def check_file(self, file_path: str, file_size: int) -> bool:
        """Return False if file should be skipped due to size."""
        if file_size > self.config.max_file_size_bytes:
            logger.warning(
                "Skipping %s: %d bytes > %d limit",
                file_path,
                file_size,
                self.config.max_file_size_bytes,
            )
            return False
        return True

    def check_total_chunks(self, current_count: int, new_chunks: int) -> bool:
        """Return False if adding chunks would exceed total limit."""
        if current_count + new_chunks > self.config.max_total_chunks:
            logger.error(
                "Safety limit: %d chunks would exceed %d limit",
                current_count + new_chunks,
                self.config.max_total_chunks,
            )
            return False
        return True

    def check_collection_chunks(
        self,
        collection_name: str,
        current_count: int,
        new_chunks: int,
    ) -> bool:
        """Return False if adding chunks would exceed collection limit."""
        limit = self.config.collection_limits.get(collection_name)
        if limit is None:
            return True
        if current_count + new_chunks > limit:
            logger.error(
                "Collection '%s' safety limit: %d chunks would exceed %d limit",
                collection_name,
                current_count + new_chunks,
                limit,
            )
            return False
        return True
```

### Step 4: Run tests to verify they pass

```bash
pytest tests/unit/test_safety.py -v
```

Expected: All tests PASS.

### Step 5: Run linters

```bash
ruff check clew/safety.py
mypy clew/safety.py
```

### Step 6: Commit

```bash
git add clew/safety.py tests/unit/test_safety.py
git commit -m "feat(safety): add SafetyChecker for file size and chunk count limits"
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

Expected: All tests pass, no linting errors, no type errors.

### Final tree check

Verify the directory structure matches IMPLEMENTATION.md Section 1 (Phase 1 files only):

```
clew/
├── clew/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py
│   ├── config.py
│   ├── exceptions.py
│   ├── models.py
│   ├── safety.py
│   ├── chunker/
│   │   ├── __init__.py
│   │   ├── parser.py
│   │   ├── strategies.py
│   │   ├── fallback.py
│   │   └── tokenizer.py
│   ├── search/
│   │   └── __init__.py
│   ├── indexer/
│   │   ├── __init__.py
│   │   ├── cache.py
│   │   ├── file_hash.py
│   │   └── ignore.py
│   └── clients/
│       ├── __init__.py
│       ├── base.py
│       └── voyage.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── fixtures/
│   │   └── python/
│   │       └── sample_models.py
│   └── unit/
│       ├── test_cache.py
│       ├── test_chunker.py
│       ├── test_cli.py
│       ├── test_embedding_provider.py
│       ├── test_fallback.py
│       ├── test_file_hash.py
│       ├── test_ignore.py
│       ├── test_safety.py
│       └── test_tokenizer.py
├── pyproject.toml
├── docker-compose.yml
├── .env.example
├── .gitignore
└── CLAUDE.md
```
