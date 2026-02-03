# code-search

Semantic code search tool with hybrid retrieval and MCP integration for Claude Code.

## Project State

**Phase 1 (Core Infrastructure) is complete** on branch `feature/phase1-core-infrastructure`. 20 source modules, 10 test files, 80 tests passing at 86% coverage.

**Phase 2 (Search Pipeline) is complete** on branch `feature/phase2-search-pipeline`. 27 source modules, 16 test files, 240 tests passing at 91% coverage.

## Module Inventory

```
code_search/
├── chunker/            # AST parsing (tree-sitter), language strategies, token-aware fallback splitting
│   ├── parser.py       # ASTParser — tree-sitter wrapper, language detection by extension
│   ├── strategies.py   # PythonChunker — extracts functions/classes as CodeEntity dataclasses
│   ├── fallback.py     # Token-recursive + line-based splitting; Chunk dataclass with metadata dict
│   └── tokenizer.py    # tiktoken cl100k_base token counting
├── clients/            # External service abstractions
│   ├── base.py         # EmbeddingProvider ABC (embed, embed_query, dimensions, model_name)
│   ├── qdrant.py       # QdrantManager — collection CRUD, hybrid query with RRF fusion, delete by file_path
│   └── voyage.py       # VoyageEmbeddingProvider — httpx async client for Voyage AI
├── indexer/            # File discovery, caching, change detection, indexing pipeline
│   ├── cache.py        # CacheDB — SQLite via contextmanager, embedding + chunk caches, state tracking
│   ├── file_hash.py    # FileHashTracker — SHA256-based change detection (added/modified/unchanged)
│   ├── git_tracker.py  # GitChangeTracker — git diff --name-status change detection (A/M/D/R parsing)
│   ├── ignore.py       # IgnorePatternLoader — .gitignore + .codesearchignore + defaults
│   ├── metadata.py     # detect_app_name, classify_layer, extract_signature, build_chunk_id
│   └── pipeline.py     # IndexingPipeline — file -> chunk -> metadata -> embed -> upsert to Qdrant
├── search/             # Search pipeline: enhance -> classify -> hybrid search -> rerank
│   ├── engine.py       # SearchEngine — top-level orchestrator, full pipeline coordination
│   ├── enhance.py      # QueryEnhancer — terminology expansion from YAML (abbreviations + synonyms)
│   ├── hybrid.py       # HybridSearchEngine — dense + BM25 multi-prefetch with structural boosting
│   ├── intent.py       # classify_intent — keyword heuristic intent routing (DEBUG > LOCATION > DOCS > CODE)
│   ├── models.py       # QueryIntent, SearchResult, SearchRequest, SearchResponse dataclasses
│   ├── rerank.py       # RerankProvider — Voyage rerank-2.5 integration with configurable skip conditions
│   └── tokenize.py     # BM25 tokenization — camelCase/snake_case splitting, raw term count sparse vectors
├── cli.py              # Typer app — index, search, status commands
├── config.py           # Environment class — env var loading with defaults
├── exceptions.py       # Exception hierarchy with user-facing fix suggestions
├── models.py           # Pydantic v2 models — ProjectConfig, SearchConfig, CollectionConfig, SafetyConfig, etc.
└── safety.py           # SafetyChecker — file size, chunk count, collection limits
```

## Established Patterns

- **Data models:** Pydantic v2 `BaseModel` for config/validation, `@dataclass` for internal data (CodeEntity, FileChange, SearchResult)
- **Provider abstraction:** ABC base classes (e.g., `EmbeddingProvider`) with concrete implementations
- **SQLite access:** `contextmanager` pattern in `CacheDB._connect()` — no ORM
- **Config:** `Environment` class reads env vars with sensible defaults; `ProjectConfig` loaded from YAML
- **Exceptions:** Hierarchy rooted in `CodeSearchError`, each with `fix_hint` for user-facing messages
- **Async:** Used for external API calls (Voyage AI, Qdrant hybrid search, embedding); sync for file I/O and SQLite
- **Deterministic IDs:** Qdrant point IDs are UUID5 derived from structured chunk IDs (format: `file_path::entity_type::qualified_name`)

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
- `docs/plans/2026-02-06-phase2-search-pipeline.md` — Phase 2 plan (complete)
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
