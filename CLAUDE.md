# code-search

Semantic code search tool with hybrid retrieval and MCP integration for Claude Code.

## Project State

**Phase 1 (Core Infrastructure) is complete** on branch `feature/phase1-core-infrastructure`. 20 source modules, 10 test files, 80 tests passing at 86% coverage.

Phase 2 (Search Pipeline) is next — see `docs/plans/2026-02-06-phase2-search-pipeline.md`.

## Module Inventory

```
code_search/
├── chunker/          # AST parsing (tree-sitter), language strategies, token-aware fallback splitting
│   ├── parser.py     # ASTParser — tree-sitter wrapper, language detection by extension
│   ├── strategies.py # PythonChunker — extracts functions/classes as CodeEntity dataclasses
│   ├── fallback.py   # Token-recursive + line-based splitting for non-parseable files
│   └── tokenizer.py  # tiktoken cl100k_base token counting
├── clients/          # External service abstractions
│   ├── base.py       # EmbeddingProvider ABC (embed, embed_query, dimensions, model_name)
│   └── voyage.py     # VoyageEmbeddingProvider — httpx async client for Voyage AI
├── indexer/          # File discovery, caching, change detection
│   ├── cache.py      # CacheDB — SQLite via contextmanager, embedding + chunk caches
│   ├── file_hash.py  # FileHashTracker — SHA256-based change detection (added/modified/unchanged)
│   └── ignore.py     # IgnorePatternLoader — .gitignore + .codesearchignore + defaults
├── search/           # (Phase 2 — empty __init__.py)
├── cli.py            # Typer app — index, search, status commands
├── config.py         # Environment class — env var loading with defaults
├── exceptions.py     # Exception hierarchy with user-facing fix suggestions
├── models.py         # Pydantic v2 models — CodeSearchConfig, CollectionConfig, Chunk, etc.
└── safety.py         # SafetyChecker — file size, chunk count, collection limits
```

## Established Patterns

- **Data models:** Pydantic v2 `BaseModel` for config/validation, `@dataclass` for internal data (CodeEntity, FileChange)
- **Provider abstraction:** ABC base classes (e.g., `EmbeddingProvider`) with concrete implementations
- **SQLite access:** `contextmanager` pattern in `CacheDB._connect()` — no ORM
- **Config:** `Environment` class reads env vars with sensible defaults; `CodeSearchConfig` loaded from YAML
- **Exceptions:** Hierarchy rooted in `CodeSearchError`, each with `fix_hint` for user-facing messages
- **Async:** Used for external API calls (Voyage AI, future Qdrant); sync for file I/O and SQLite

## Commands

```bash
pytest --cov=code_search -v    # Run tests with coverage
ruff check .                   # Lint
ruff format --check .          # Check formatting
mypy code_search/              # Type check
```

## Key Files

- `docs/DESIGN.md` — Architecture, chunking strategy, search pipeline, MCP tools, metadata schema
- `docs/IMPLEMENTATION.md` — Concrete specs: dependencies, SQLite schemas, Pydantic models, tree-sitter setup, phase tasks
- `docs/adr/` — Architecture Decision Records (Qdrant over Milvus, build vs adopt)
- `docs/plans/2026-02-06-phase1-core-infrastructure.md` — Phase 1 plan (complete)
- `docs/plans/2026-02-06-phase2-search-pipeline.md` — Phase 2 plan (next)
- `docs/plans/2026-02-06-three-layer-knowledge-design.md` — Future roadmap (V1.2+)

## Tech Stack

- Python >=3.10, Qdrant (Docker), Voyage AI voyage-code-3, tree-sitter, typer + rich CLI, Pydantic v2, SQLite for caching
- Testing: pytest + pytest-asyncio, respx for HTTP mocking
- Linting: ruff, mypy (strict)

## Conventions

- Use `ruff` for formatting and linting
- Use `mypy --strict` for type checking
- Async where interacting with Voyage API or Qdrant
- All config through Pydantic models validated from YAML
- Error messages should tell the user how to fix the problem (e.g., "Qdrant not running. Start with: docker compose up -d qdrant")
