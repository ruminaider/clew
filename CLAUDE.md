# clew

Semantic code search tool with hybrid retrieval and MCP integration for Claude Code.

## Project State

**Phase 1 (Core Infrastructure) is complete.** 20 source modules, 10 test files, 80 tests passing at 86% coverage.

**Phase 2 (Search Pipeline) is complete.** 27 source modules, 16 test files, 240 tests passing at 91% coverage.

**Phase 3 (MCP Integration & CLI) is complete.** 31 source modules, 27 test files, 349 tests passing at 92% coverage.

**V1.1 (NL Descriptions) is complete.** 32 source modules, 30 test files, 394 tests passing. LLM-generated descriptions for undocumented code chunks, prepended before embedding to improve semantic search quality.

**V1.2 (Structural Layer) is complete.** 39 source modules, 36 test files, 472 tests passing. Code relationship extraction (imports, inherits, calls, decorates, renders, tests, calls_api) with BFS graph traversal via `trace` MCP tool and CLI command.

**V1.3 (Compact Responses & Cache Fix) is complete.** 39 source modules, 36 test files, 491 tests passing. Compact MCP responses by default (~20x token reduction), opt-in full content via `detail="full"`. CACHE_DIR now resolves from git root so MCP server and indexer share the same state.db.

**V5 (Ship the Core Engine) is complete.** Remove autonomous escalation (ADR-008), grep available only via explicit `--mode exhaustive`, confidence scoring is informational only (Z-score in result metadata), agent skills for composed workflows, telemetry hooks for future calibration.

## Module Inventory

```
clew/
├── chunker/            # AST parsing (tree-sitter), language strategies, token-aware fallback splitting
│   ├── parser.py       # ASTParser — tree-sitter wrapper, language detection by extension
│   ├── strategies.py   # PythonChunker — extracts functions/classes as CodeEntity dataclasses
│   ├── fallback.py     # Token-recursive + line-based splitting; Chunk dataclass with metadata dict
│   └── tokenizer.py    # tiktoken cl100k_base token counting
├── clients/            # External service abstractions
│   ├── base.py         # EmbeddingProvider ABC (embed, embed_query, dimensions, model_name)
│   ├── description.py  # DescriptionProvider ABC + AnthropicDescriptionProvider — NL descriptions for code
│   ├── qdrant.py       # QdrantManager — collection CRUD, hybrid query with RRF fusion, delete by file_path
│   └── voyage.py       # VoyageEmbeddingProvider — httpx async client for Voyage AI
├── indexer/            # File discovery, caching, change detection, indexing pipeline, relationship extraction
│   ├── cache.py        # CacheDB — SQLite via contextmanager, embedding + chunk caches, state tracking, relationship store
│   ├── change_detector.py # ChangeDetector — unified interface: git-first, file-hash fallback
│   ├── extractors/     # Pluggable relationship extractors (V1.2)
│   │   ├── base.py     # RelationshipExtractor ABC
│   │   ├── python.py   # Python: imports, inherits, decorates, calls
│   │   ├── typescript.py # TypeScript/JS: imports, inherits, renders (JSX), calls, calls_api (fetch/axios)
│   │   ├── tests.py    # Test file detection: maps test files to tested modules
│   │   ├── django_urls.py # Django URL pattern extraction from urls.py
│   │   └── api_boundary.py # Cross-language API boundary matching (frontend→backend)
│   ├── file_hash.py    # FileHashTracker — SHA256-based change detection (added/modified/unchanged)
│   ├── git_tracker.py  # GitChangeTracker — git diff --name-status change detection (A/M/D/R parsing)
│   ├── ignore.py       # IgnorePatternLoader — .gitignore + .clewignore + defaults
│   ├── metadata.py     # detect_app_name, classify_layer, extract_signature, build_chunk_id
│   ├── pipeline.py     # IndexingPipeline — file -> chunk -> metadata -> embed -> upsert + relationship extraction
│   └── relationships.py # Relationship dataclass — entity-relationship-entity with confidence
├── search/             # Search pipeline: enhance -> classify -> hybrid search -> rerank -> confidence (informational)
│   ├── engine.py       # SearchEngine — top-level orchestrator, explicit exhaustive mode only (no auto-escalation)
│   ├── enhance.py      # QueryEnhancer — terminology expansion from YAML (abbreviations + synonyms)
│   ├── hybrid.py       # HybridSearchEngine — dense + BM25 multi-prefetch with structural boosting
│   ├── intent.py       # classify_intent — keyword heuristic intent routing (DEBUG > LOCATION > DOCS > CODE)
│   ├── models.py       # QueryIntent, SearchResult, SearchRequest, SearchResponse dataclasses
│   ├── filters.py      # build_qdrant_filter() — converts SearchRequest.filters to Qdrant Filter objects
│   ├── rerank.py       # RerankProvider — Voyage rerank-2.5 integration with configurable skip conditions
│   └── tokenize.py     # BM25 tokenization — camelCase/snake_case splitting, raw term count sparse vectors
├── cli.py              # Typer app — index, search, status, trace, serve commands (fully wired)
├── config.py           # Environment class — env var loading with defaults
├── discovery.py        # discover_files() — centralized file discovery using IgnorePatternLoader + SafetyChecker
├── exceptions.py       # Exception hierarchy with user-facing fix suggestions
├── factory.py          # Component factory — centralized wiring, create_components() returns Components dataclass
├── mcp_server.py       # FastMCP server — 5 tools: search, get_context, explain, index_status, trace
├── models.py           # Pydantic v2 models — ProjectConfig, SearchConfig, CollectionConfig, SafetyConfig, etc.
└── safety.py           # SafetyChecker — file size, chunk count, collection limits
```

## Established Patterns

- **Data models:** Pydantic v2 `BaseModel` for config/validation, `@dataclass` for internal data (CodeEntity, FileChange, SearchResult)
- **Provider abstraction:** ABC base classes (e.g., `EmbeddingProvider`) with concrete implementations
- **SQLite access:** `contextmanager` pattern in `CacheDB._connect()` — no ORM
- **Config:** `Environment` class reads env vars with sensible defaults; `ProjectConfig` loaded from YAML
- **Exceptions:** Hierarchy rooted in `ClewError`, each with `fix_hint` for user-facing messages
- **Async:** Used for external API calls (Voyage AI, Qdrant hybrid search, embedding); sync for file I/O and SQLite
- **Deterministic IDs:** Qdrant point IDs are UUID5 derived from structured chunk IDs (format: `file_path::entity_type::qualified_name`)

## Commands

```bash
# Dev commands
pytest --cov=clew -v    # Run tests with coverage
pytest -m integration          # Run integration tests only
ruff check .                   # Lint
ruff format --check .          # Check formatting
mypy clew/              # Type check

# CLI commands
clew index [PROJECT_ROOT] --full    # Full reindex
clew index [PROJECT_ROOT]           # Incremental (change detection)
clew index [PROJECT_ROOT] --nl-descriptions  # Generate NL descriptions (requires ANTHROPIC_API_KEY)
clew search "query" --raw           # Search with JSON output
clew trace "entity::name"           # Trace code relationships (BFS graph traversal)
clew trace "entity" --direction outbound --depth 3  # Directed trace with depth limit
clew status                          # Show Qdrant health + index stats
clew serve                           # Start MCP server (stdio transport)
```

## Key Files

- `docs/DESIGN.md` — Architecture, chunking strategy, search pipeline, MCP tools, metadata schema
- `docs/IMPLEMENTATION.md` — Concrete specs: dependencies, SQLite schemas, Pydantic models, tree-sitter setup, phase tasks
- `docs/adr/` — Architecture Decision Records (Qdrant over Milvus, build vs adopt, code retrieval landscape)
- `docs/plans/2026-02-06-phase1-core-infrastructure.md` — Phase 1 plan (complete)
- `docs/plans/2026-02-06-phase2-search-pipeline.md` — Phase 2 plan (complete)
- `docs/plans/2026-02-09-v1.1-nl-descriptions.md` — V1.1 NL Descriptions plan (complete)
- `docs/plans/2026-02-09-v1.2-structural-layer.md` — V1.2 Structural Layer plan (complete)
- `docs/plans/2026-02-10-compact-responses-and-cache-fix.md` — V1.3 Compact Responses & Cache Fix plan (complete)
- `docs/plans/2026-02-06-three-layer-knowledge-design.md` — Future roadmap (V1.4+)
- `docs/VIABILITY-EVALUATION-STANDARDS.md` — Blind A/B evaluation methodology for viability testing (reusable across versions)
- `docs/PRODUCT-VISION.md` — V1→V5 trajectory analysis, product identity, and path to beta
- `docs/adr/008-remove-autonomous-escalation.md` — ADR-008: Why autonomous escalation was removed (V4.0-V4.3 evidence)

## Tech Stack

- Python >=3.10, Qdrant (Docker), Voyage AI voyage-code-3, tree-sitter, typer + rich CLI, Pydantic v2, SQLite for caching
- Testing: pytest + pytest-asyncio, respx for HTTP mocking
- Linting: ruff, mypy (strict)

## MCP Server Configuration

Add to Claude Code's `.mcp.json`:
```json
{
  "mcpServers": {
    "clew": {
      "command": "clew",
      "args": ["serve"],
      "env": {
        "VOYAGE_API_KEY": "your-key-here",
        "QDRANT_URL": "http://localhost:6333",
        "ANTHROPIC_API_KEY": "your-key-here (optional, for NL descriptions)",
        "CLEW_CACHE_DIR": "/absolute/path/to/project/.clew (optional, auto-detected from git root)"
      }
    }
  }
}
```

## MCP Tool Response Modes

MCP tools default to **compact** responses to minimize context window usage:

- **`search`** — Returns `snippet` (signature + docstring preview) instead of full source. Default `limit=5`. Pass `detail="full"` for complete content. Pass `mode="exhaustive"` to run grep alongside semantic search.
- **`explain`** — Same compact/full behavior. Default `limit=5`.
- **`get_context`** — Returns file content only. Pass `include_related=True` to also get related code chunks (compact format).
- **`trace`** and **`index_status`** — Already compact, no changes needed.

The agent can always use the `Read` tool to fetch specific lines from results that look promising.

## Conventions

- Use `ruff` for formatting and linting
- Use `mypy --strict` for type checking
- Async where interacting with Voyage API or Qdrant
- All config through Pydantic models validated from YAML
- Error messages should tell the user how to fix the problem (e.g., "Qdrant not running. Start with: docker compose up -d qdrant")
- Component wiring through `factory.py` — no global state, one factory call per invocation
- MCP tools return structured dicts with `error` + `fix` keys on failure
