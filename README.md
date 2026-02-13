# clew

Semantic code search with hybrid retrieval and MCP integration for Claude Code.

Ask natural language questions about your codebase — clewdex indexes your code with AST-aware chunking, embeds it with [Voyage AI](https://www.voyageai.com/), stores it in [Qdrant](https://qdrant.tech/), and serves results through both a CLI and an [MCP](https://modelcontextprotocol.io/) server that Claude Code can call directly.

## Quick start

### 1. Install clewdex

```bash
pip install clewdex
```

Or with [pipx](https://pipx.pypa.io/), [Homebrew](https://brew.sh/), or [npx](https://docs.npmjs.com/cli/commands/npx):

```bash
pipx install clewdex                          # isolated install
brew install ruminaider/tap/clewdex           # macOS
npx clewdex                                   # run without installing
```

### 2. Start Qdrant

```bash
docker run -d -p 6333:6333 qdrant/qdrant:v1.16.1
```

### 3. Set your API key

```bash
export VOYAGE_API_KEY=pa-xxxxxxxxxxxxxxxxxxxx
```

Get a key at [dash.voyageai.com](https://dash.voyageai.com/).

### 4. Index and search

```bash
clew index /path/to/your/project --full
clew search "how do we handle authentication"
```

## Features

- **Hybrid search** — Dense embeddings (Voyage voyage-code-3) + BM25 keyword matching fused with Reciprocal Rank Fusion, optionally re-ranked with Voyage rerank-2.5
- **AST-aware chunking** — tree-sitter parses Python, TypeScript, and JavaScript into semantic units (functions, classes, components) with token-aware fallback splitting
- **Code relationship tracing** — Extracts imports, calls, inheritance, decorators, JSX renders, test mappings, and API boundaries; traversable via BFS graph queries
- **Incremental indexing** — Git-aware change detection (with file-hash fallback) so re-indexing only touches what changed
- **NL descriptions** — LLM-generated descriptions for undocumented code, prepended before embedding to improve search quality
- **Compact MCP responses** — ~20x token reduction by default; returns signatures + docstring previews instead of full source
- **Multi-collection** — Separate `code` and `docs` collections with intent-driven routing

## CLI usage

### `clew index`

Index a codebase for search.

```bash
# Incremental — only re-index changed files
clew index /path/to/project

# Full reindex
clew index /path/to/project --full

# Generate NL descriptions for undocumented code (requires ANTHROPIC_API_KEY)
clew index /path/to/project --nl-descriptions

# Index specific files
clew index --files src/auth.py --files src/models.py
```

### `clew search`

Search the indexed codebase.

```bash
# Natural language query
clew search "where is the rate limiter configured"

# Filter by language
clew search "database models" --language python

# Filter by chunk type
clew search "API endpoints" --chunk-type function

# Set intent explicitly (code, docs, debug, location)
clew search "why does login fail" --intent debug

# JSON output
clew search "user authentication" --raw
```

### `clew trace`

Trace code relationships via BFS graph traversal.

```bash
# Show all relationships for an entity
clew trace "src/auth/models.py::User"

# Only inbound (what depends on this)
clew trace "src/auth/models.py::User" --direction inbound

# Limit depth and filter types
clew trace "src/api/views.py::handle_request" --depth 3 --type calls --type imports

# JSON output
clew trace "src/auth/models.py::User" --raw
```

Relationship types: `imports`, `calls`, `inherits`, `decorates`, `renders`, `tests`, `calls_api`

### `clew status`

Show system health and index statistics.

```bash
clew status
```

### `clew serve`

Start the MCP server (stdio transport) for Claude Code integration.

```bash
clew serve
```

## MCP integration

Add clewdex to Claude Code's `.mcp.json`:

```json
{
  "mcpServers": {
    "clew": {
      "command": "clew",
      "args": ["serve"],
      "env": {
        "VOYAGE_API_KEY": "pa-xxxxxxxxxxxxxxxxxxxx",
        "QDRANT_URL": "http://localhost:6333"
      }
    }
  }
}
```

### MCP tools

#### `search`

Semantic search over the indexed codebase.

```
search(query, limit=5, collection="code", active_file=None,
       intent=None, filters=None, detail="compact")
```

- `detail="compact"` (default) — returns signature + docstring snippet
- `detail="full"` — returns complete source content
- `filters` — metadata filters: `language`, `chunk_type`, `app_name`, `layer`, `is_test`

#### `get_context`

Read file content with optional related code chunks.

```
get_context(file_path, line_start=None, line_end=None, include_related=False)
```

#### `explain`

Search for context about a symbol or question in a file.

```
explain(file_path, symbol=None, question=None, detail="compact")
```

#### `trace`

Traverse code relationships (imports, calls, inheritance, etc.).

```
trace(entity, direction="both", max_depth=2, relationship_types=None)
```

#### `index_status`

Check health or trigger re-indexing.

```
index_status(action="status", project_root=None)
```

## Configuration

### Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `VOYAGE_API_KEY` | Yes | — | Voyage AI API key for embeddings and re-ranking |
| `QDRANT_URL` | No | `http://localhost:6333` | Qdrant server endpoint |
| `QDRANT_API_KEY` | No | — | Qdrant API key (if auth is enabled) |
| `CLEW_CACHE_DIR` | No | Auto-detected from git root | SQLite cache directory (`.clew/`) |
| `CLEW_LOG_LEVEL` | No | `INFO` | Logging verbosity |
| `ANTHROPIC_API_KEY` | No | — | Required for NL description generation |

The cache directory resolves in order: `CLEW_CACHE_DIR` env var, then `{git_root}/.clew/`, then `.clew/` relative to the working directory. This ensures the MCP server and CLI share the same cache.

### Project configuration (optional)

Create a `config.yaml` in your project root for fine-grained control:

```yaml
project:
  name: "my-project"
  root: "."

collections:
  code:
    include:
      - "src/**/*.py"
      - "frontend/**/*.tsx"
    exclude:
      - "**/migrations/*.py"
      - "**/__pycache__/**"
  docs:
    include:
      - "**/*.md"

chunking:
  default_max_tokens: 3000
  overlap_tokens: 200

terminology_file: indexer/terminology.yaml
```

## Architecture

```
                    ┌──────────────┐
                    │ Claude Code  │
                    │ (MCP client) │
                    └──────┬───────┘
                           │ stdio
                    ┌──────▼───────┐
                    │  MCP Server  │  search, get_context, explain, trace, index_status
                    └──────┬───────┘
                           │
              ┌────────────▼────────────┐
              │     Search Pipeline     │
              │  enhance → classify →   │
              │  hybrid search → rerank │
              └────────────┬────────────┘
                           │
              ┌────────────▼────────────┐
              │    Qdrant Collections   │
              │  code: py/ts/tsx/js/jsx │
              │  docs: markdown         │
              └────────────┬────────────┘
                           │
              ┌────────────▼────────────┐
              │   Indexing Pipeline     │
              │  discover → chunk →     │
              │  enrich → embed →       │
              │  upsert + relationships │
              └────────────┬────────────┘
                           │
        ┌──────────┬───────┼───────┬──────────┐
        ▼          ▼       ▼       ▼          ▼
   tree-sitter  Voyage   SQLite   git     Anthropic
   (AST parse)  (embed)  (cache)  (diff)  (NL desc)
```

### Search pipeline

1. **Query enhancement** — Terminology expansion via YAML (abbreviations, synonyms)
2. **Intent classification** — Heuristic routing: `CODE`, `DOCS`, `DEBUG`, `LOCATION`
3. **Hybrid search** — Dense + BM25 multi-prefetch with structural boosting (same-module, test files for debug intent)
4. **Re-ranking** — Voyage rerank-2.5 for final ordering

### Chunking strategy

| File pattern | Strategy | Token range |
|---|---|---|
| `models.py` | Class + fields as unit | 1,500 - 3,000 |
| `views.py` | Class as unit; split large actions | 2,000 - 4,000 |
| `tasks.py` | Function with decorators | 1,000 - 2,000 |
| `*.tsx`, `*.jsx` | Component boundaries | 1,500 - 3,000 |
| `*.md` | Section-level by headers | 1,000 - 2,000 |
| Migrations | Skipped | — |

Fallback chain: tree-sitter AST → token-recursive splitting → line-based splitting.

## Development

### Setup

```bash
git clone https://github.com/ruminaider/clew.git
cd clew
pip install -e ".[dev]"
```

### Tests

```bash
# All tests with coverage
pytest --cov=clew -v

# Integration tests (requires running Qdrant)
pytest -m integration

# Single test file
pytest tests/search/test_hybrid.py -v
```

### Linting and type checking

```bash
ruff format .           # Format
ruff check .            # Lint
mypy clew/              # Type check (strict mode)
```

### Project structure

```
clew/
├── chunker/             # AST parsing, language strategies, token counting
├── clients/             # External service wrappers (Voyage, Qdrant, Anthropic)
├── indexer/             # Pipeline, caching, change detection, relationship extraction
│   └── extractors/      # Pluggable per-language relationship extractors
├── search/              # Engine, hybrid retrieval, intent classification, re-ranking
├── cli.py               # Typer CLI
├── mcp_server.py        # FastMCP server (5 tools)
├── config.py            # Environment variable loading
├── factory.py           # Component wiring (no global state)
├── models.py            # Pydantic v2 config models
├── exceptions.py        # Error hierarchy with fix hints
├── discovery.py         # File discovery with ignore patterns and safety checks
└── safety.py            # File size, chunk count, collection limits
```

## Troubleshooting

| Problem | Fix |
|---|---|
| Qdrant not running | `docker compose up -d qdrant` or `docker run -d -p 6333:6333 qdrant/qdrant:v1.16.1` |
| `VOYAGE_API_KEY not set` | `export VOYAGE_API_KEY=pa-...` |
| No search results | Run `clew index --full` to reindex |
| MCP server can't find cache | Set `CLEW_CACHE_DIR` to an absolute path, or run from within the git repo |
| Stale results after code changes | Run `clew index` (incremental) to pick up changes |

## License

MIT
