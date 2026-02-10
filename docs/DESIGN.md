# Codebase Embedding System Design

**Status:** Final
**Companion Document:** [IMPLEMENTATION.md](./IMPLEMENTATION.md)

---

## 1. Overview

### Goal

Build a semantic code search system for developer productivity:
- Natural language code search ("how do we handle expired prescriptions")
- AI agent context feeding (provide relevant code to Claude Code)
- Onboarding acceleration (understand codebase through queries)

### Architecture: Generic Tool + Project Config

The system consists of two parts:

1. **`clew`** — Generic, reusable tool (separate repository)
2. **Project configuration** — Evvy-specific settings (in evvy repo)

This separation allows the tool to be used across any codebase.

### Tech Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Vector Database | Qdrant (self-hosted, Docker) | Open source, hybrid search, no vendor lock-in |
| Embedding Model | Voyage AI voyage-code-3 (1024 dims) | Best-in-class for code, 14.6% better than OpenAI |
| Re-ranking | Voyage AI rerank-2.5 | Pairs with voyage-code-3 |
| Embedding Provider | Voyage AI (default) with provider ABC | Pluggable: OpenAI, Ollama optional |
| AST Parsing | tree-sitter | Industry standard, multi-language |
| CLI Framework | typer + rich | Modern Python CLI |
| MCP Integration | Custom server | Claude Code integration |

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Query Layer                               │
│  Claude Code ←── MCP Server ←── Context Assembler ←── CLI       │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│                       Search Layer                               │
│  Query Enhancement → Hybrid Search (RRF) → Re-ranking → Format  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│                    Qdrant Collections                            │
│  ┌─────────────────────────┬─────────────────────────────────┐  │
│  │ code                    │ docs                             │  │
│  │ (Python, TypeScript)    │ (Markdown, ADRs, README)         │  │
│  └─────────────────────────┴─────────────────────────────────┘  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│                   Indexing Pipeline                              │
│                                                                  │
│  ┌──────────────┐   ┌───────────────────────────┐               │
│  │ Change        │   │ Splitter Fallback Chain    │               │
│  │ Detection     │   │                           │               │
│  │               │   │ tree-sitter (AST)         │               │
│  │ PRIMARY:      │   │   ↓ (parse failure)       │               │
│  │  git diff     │──▶│ Token-recursive splitter  │               │
│  │               │   │   ↓ (oversized chunks)    │               │
│  │ SECONDARY:    │   │ Line split                │               │
│  │  file hash    │   └─────────────┬─────────────┘               │
│  └──────────────┘                 │                              │
│                                   ▼                              │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Embedding Provider (ABC)                                 │    │
│  │ ┌──────────┐  ┌──────────┐  ┌──────────┐               │    │
│  │ │ Voyage   │  │ OpenAI   │  │ Ollama   │               │    │
│  │ │ (default)│  │ (optional)│  │ (optional)│               │    │
│  │ └──────────┘  └──────────┘  └──────────┘               │    │
│  └───────────────────────────┬─────────────────────────────┘    │
│                              ▼                                   │
│              ┌──────────────────────────────┐                    │
│              │ Caches (SQLite)              │                    │
│              │ Chunk Cache │ Embedding Cache│                    │
│              └──────────────────────────────┘                    │
└─────────────────────────────────────────────────────────────────┘
```

### Two Collections (V1)

| Collection | Contents | Rationale |
|------------|----------|-----------|
| `code` | Python, TypeScript, JSX/TSX | Primary search target |
| `docs` | Markdown files (README, ADRs, CLAUDE.md) | Context and documentation |

**Deferred to V2:** `schema` (DB tables), `git` (commits, PRs)

---

## 3. Chunking Strategy

### Research-Backed Parameters

Based on Voyage AI documentation and industry best practices:

| Parameter | Value | Source |
|-----------|-------|--------|
| Token counting | Voyage HuggingFace tokenizer | Voyage docs |
| Target chunk size | 1,000-4,000 tokens | Sourcegraph, Pinecone research |
| Embedding dimensions | 1024 (Matryoshka truncation) | Voyage docs |
| Input type | "document" for indexing, "query" for search | Voyage docs |

### Token Counting Implementation

```python
from transformers import AutoTokenizer

tokenizer = AutoTokenizer.from_pretrained("voyageai/voyage-code-3")

def count_tokens(text: str) -> int:
    return len(tokenizer.encode(text))

def chunk_fits(chunk: str, max_tokens: int = 4000) -> bool:
    return count_tokens(chunk) <= max_tokens
```

### AST-Based Chunking by File Type

| File Pattern | Strategy | Target Tokens |
|--------------|----------|---------------|
| `models.py` | Class + fields as unit; large methods split | 1,500-3,000 |
| `views.py`, `viewsets.py` | Class as unit; actions split if large | 2,000-4,000 |
| `serializers.py` | Class-level | 1,000-2,000 |
| `tasks.py` | Function with decorators | 1,000-2,000 |
| `service.py` | Function-level | 1,500-3,000 |
| `enums.py`, `constants.py` | Entire file | 500-1,500 |
| `migrations/*.py` | **Skip entirely** | — |
| `tests/*.py` | Test class as unit | 2,000-4,000 |
| `*.tsx`, `*.jsx` | Component boundaries | 1,500-3,000 |
| `*.md` | Section-level by headers | 1,000-2,000 |

### Splitter Fallback Chain

When tree-sitter parsing fails (unsupported language, malformed syntax), chunks are produced via a three-tier fallback. See [ADR-003](./adr/003-ported-features-from-claude-context.md) for provenance.

| Tier | Splitter | When Used | Overlap |
|------|----------|-----------|---------|
| 1 | tree-sitter AST | Supported languages, valid syntax | None (semantic units) |
| 2 | Token-recursive splitter | AST parse failure | 200 tokens |
| 3 | Line split | Oversized chunks from Tier 2 | 200 tokens |

```python
def split_file(file_path: str, content: str, max_tokens: int) -> list[Chunk]:
    # Tier 1: AST parsing
    tree = ast_parser.parse_file(file_path, content)
    if tree:
        chunks = extract_ast_chunks(tree, content, max_tokens)
        if chunks:
            return chunks

    # Tier 2: Token-recursive splitting
    chunks = token_recursive_split(content, max_tokens, overlap_tokens=200)
    if all(chunk_fits(c, max_tokens) for c in chunks):
        return chunks

    # Tier 3: Line splitting (guaranteed to terminate)
    return line_split(content, max_tokens, overlap_tokens=200)
```

**Implementation:** `clew/chunker/fallback.py` — See [IMPLEMENTATION.md](./IMPLEMENTATION.md)

### Chunk Overlap (Non-AST Only)

Overlap is applied **only** to fallback-split chunks (Tiers 2 and 3). AST-parsed chunks are self-contained semantic units that should not bleed into adjacent chunks.

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Overlap size | 200 tokens | Balances context continuity with chunk independence |
| Applied to | Non-AST fallback chunks only | AST entities are complete semantic units |
| Configurable | Yes, via `IndexingConfig.overlap_tokens` | Projects may need more/less |

Adapted from claude-context's 300-character overlap, converted to token-based measurement for accuracy with Voyage's tokenizer. See [ADR-003](./adr/003-ported-features-from-claude-context.md#5-chunk-overlap-non-ast-only).

### Chunk Identity (Dual Strategy)

**Level 1: File-level change detection**
```python
def file_hash(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()
```
If file hash matches cache, skip entirely.

**Level 2: AST-based chunk identity**
```python
# Named entities (functions, classes, methods)
chunk_id = f"{file_path}::{entity_type}::{qualified_name}"
# Example: "backend/care/models.py::method::Prescription.is_expired"

# Anonymous/top-level code
chunk_id = f"{file_path}::toplevel::{content_hash[:12]}"
```

This ensures:
- Renaming creates new chunk (correct—semantically different)
- Adding functions doesn't invalidate existing chunks
- Moving code within file doesn't trigger re-embedding
- Content changes trigger re-embedding

**Content-Hash IDs for Anonymous Chunks**

For code without named entities (top-level statements, configuration blocks, module-level assignments), content-hash IDs provide stability:

```python
# Anonymous/top-level code (enhanced)
chunk_id = f"{file_path}::toplevel::{hashlib.sha256(content.encode()).hexdigest()[:12]}"
```

This dual strategy improves on claude-context's approach of `SHA256(path:start_offset:end_offset:content)`, which invalidates chunk IDs when unrelated code shifts byte offsets. Our entity-based IDs are offset-independent. See [ADR-003](./adr/003-ported-features-from-claude-context.md#7-dual-chunk-id-strategy).

---

## 4. Metadata Schema

### V1 Schema

```python
{
    # === IDENTITY ===
    # Qdrant point id is a UUID5: uuid.uuid5(CHUNK_UUID_NAMESPACE, chunk_id)
    # The structured chunk ID is stored in payload["chunk_id"]
    "chunk_id": "backend/care/models.py::method::Prescription.is_expired",
    "file_path": "backend/care/models.py",
    "line_start": 45,
    "line_end": 52,
    "language": "python",

    # === CODE STRUCTURE ===
    "chunk_type": "method",        # class | method | function | section
    "class_name": "Prescription",
    "function_name": "is_expired",
    "signature": "def is_expired(self) -> bool",

    # === PROJECT CONTEXT (from config) ===
    "app_name": "care",            # Django app or directory
    "layer": "model",              # model | view | serializer | task | service | component

    # === FILTERING FLAGS ===
    "is_test": false,
    "source_type": "code",         # code | docs

    # === VERSIONING ===
    "embedding_model": "voyage-code-3",
    "indexed_at": "2026-02-05T10:30:00Z",
}
```

### V1.1 Addition: NL Descriptions (Deferred)

```python
{
    "nl_description": "Check if prescription has passed expiration date",
    "docstring": "Returns True if...",
}
```

### V2 Additions (Deferred)

```python
{
    # Cross-file analysis
    "imports": ["django.utils.timezone"],
    "references": ["PrescriptionFill"],
    "referenced_by": ["PrescriptionView"],

    # Git integration
    "last_modified": "2026-01-15",
    "last_author": "developer@evvy.com",
}
```

---

## 5. Incremental Update Pipeline

### Git-Aware Change Detection

```python
# In clew/indexer/git_tracker.py
class GitChangeTracker:
    def get_changes_since(self, last_commit: str) -> dict[str, list[Any]]:
        result = subprocess.run(
            ["git", "diff", "--name-status", last_commit, "HEAD"],
            capture_output=True, text=True
        )

        changes = {"added": [], "modified": [], "deleted": [], "renamed": []}
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            status, *paths = line.split("\t")
            if status == "A":
                changes["added"].append(paths[0])
            elif status == "M":
                changes["modified"].append(paths[0])
            elif status == "D":
                changes["deleted"].append(paths[0])
            elif status.startswith("R"):
                changes["renamed"].append({"from": paths[0], "to": paths[1]})

        return changes
```

### Processing Strategy

| Change Type | Action |
|-------------|--------|
| Added | Parse → Chunk → Embed → Insert |
| Modified | File hash check → Chunk-level diff → Re-embed changed only |
| Deleted | Delete all chunks with that file_path |
| Renamed | Update file_path in chunk IDs (no re-embed if content unchanged) |

### Caching

- **Embedding Cache:** SQLite, keyed by `content_hash` + `embedding_model`
- **Chunk Cache:** File path → file hash + chunk identities
- **Checkpoint:** Save `last_indexed_commit` for incremental updates

### File-Hash Change Detection (Secondary)

When git-diff is unavailable or unreliable (shallow clones, squashed merges, force pushes), file-hash change detection serves as a fallback. Adapted from claude-context's Merkle DAG approach — see [ADR-003](./adr/003-ported-features-from-claude-context.md#2-change-detection-hybrid-strategy).

```python
class FileHashTracker:
    """Secondary change detection using file content hashes."""

    def __init__(self, cache: CacheDB):
        self.cache = cache

    def detect_changes(self, file_paths: list[str]) -> dict:
        changes = {"added": [], "modified": [], "unchanged": []}
        for path in file_paths:
            current_hash = hashlib.sha256(Path(path).read_bytes()).hexdigest()
            cached_hash = self.cache.get_file_hash(path)
            if cached_hash is None:
                changes["added"].append(path)
            elif cached_hash != current_hash:
                changes["modified"].append(path)
            else:
                changes["unchanged"].append(path)
        return changes
```

**When to use:** The indexing pipeline tries git-diff first. If git is unavailable or returns errors, it falls back to `FileHashTracker`. This hybrid approach is configured in the pipeline, not chosen by the user.

### Ignore Pattern Hierarchy

File exclusion follows a 5-source merge hierarchy, adapted from claude-context's 5-level pattern system. See [ADR-003](./adr/003-ported-features-from-claude-context.md#6-ignore-pattern-hierarchy).

| Priority | Source | Example |
|----------|--------|---------|
| 1 (lowest) | Built-in defaults | `__pycache__/`, `node_modules/`, `.git/` |
| 2 | `.gitignore` | Project-maintained patterns |
| 3 | `.clewignore` | Code-search-specific overrides |
| 4 | `config.yaml` exclude patterns | Per-collection exclusions |
| 5 (highest) | `CLEW_EXCLUDE` env var | Runtime overrides |

Higher-priority sources override lower-priority ones. All patterns use `.gitignore` syntax via the `pathspec` library.

**Implementation:** `clew/indexer/ignore.py` — See [IMPLEMENTATION.md](./IMPLEMENTATION.md)

---

## 6. Error Handling

### Indexing Errors (Retry with Backoff)

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type((RateLimitError, TimeoutError, ConnectionError))
)
async def embed_batch(chunks: list[str]) -> list[list[float]]:
    return await voyage_client.embed(chunks, model="voyage-code-3")
```

**Failure handling:**
- Log failed files to `indexer/failed_files.log`
- Continue with remaining files
- Checkpoint progress after each batch
- Retry failed files on next run

### Search Errors (Fail-Fast)

```python
async def search(query: str) -> SearchResult:
    try:
        results = await hybrid_search(query)
        return results
    except QdrantConnectionError:
        raise SearchUnavailableError("Qdrant is not running. Start with: docker compose up -d qdrant")
    except VoyageAPIError as e:
        raise SearchUnavailableError(f"Voyage API error: {e.message}")
```

**Rationale:** Search is interactive—better to fail immediately with a clear message than hang waiting for retries.

---

## 7. Hybrid Search

### Dense + Sparse Architecture

```python
client.create_collection(
    collection_name="code",
    vectors_config={
        "dense": models.VectorParams(size=1024, distance=models.Distance.COSINE)
    },
    sparse_vectors_config={
        "bm25": models.SparseVectorParams(modifier=models.Modifier.IDF)
    }
)
```

### Code-Specific BM25 Tokenization

```python
def tokenize_code(text: str) -> list[str]:
    """Split camelCase, snake_case, and dotted.paths for BM25.
    Filters out single-char tokens (len(t) > 1).
    Returns a SparseVector dataclass for Qdrant ingestion."""
    tokens = []
    identifiers = re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*', text)

    for ident in identifiers:
        tokens.append(ident.lower())
        # camelCase: "getUserById" -> ["get", "user", "by", "id"]
        camel = re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)', ident)
        tokens.extend([p.lower() for p in camel])
        # snake_case
        tokens.extend([p.lower() for p in ident.split('_') if p])

    # Filter single-char tokens and deduplicate
    tokens = [t for t in set(tokens) if len(t) > 1]
    # Build raw term-count sparse vector as SparseVector dataclass
    return tokens  # converted to SparseVector(indices, values) for Qdrant
```

### Reciprocal Rank Fusion (RRF)

```python
results = client.query_points(
    collection_name="code",
    prefetch=[
        models.Prefetch(query=dense_vector, using="dense", limit=30),
        models.Prefetch(
            query=models.SparseVector(indices=indices, values=values),
            using="bm25",
            limit=30
        ),
    ],
    query=models.FusionQuery(fusion=models.Fusion.RRF),
    limit=30,  # Configurable via SearchConfig.rerank_candidates
    with_payload=True
)
```

---

## 8. Query Enhancement

### Enhancement Bypass Logic

Skip enhancement when:
1. Query is quoted (exact match requested)
2. Contains specific code identifiers (PascalCase, snake_case)
3. Is a file path query
4. Very short with uppercase (likely class name)

```python
def should_skip_enhancement(query: str) -> bool:
    if query.startswith('"') and query.endswith('"'):
        return True
    if re.match(r'^[A-Z][a-zA-Z0-9]+$', query):  # PascalCase
        return True
    if re.match(r'^[a-z][a-z0-9_]*$', query) and '_' in query:  # snake_case
        return True
    if '/' in query or query.endswith((".py", ".ts", ".js", ".tsx", ".jsx")):  # File path
        return True
    return False
```

### Query Intent Classification (Simple Heuristics)

```python
class QueryIntent(Enum):
    CODE = "code"
    DOCS = "docs"
    DEBUG = "debug"
    LOCATION = "location"

def classify_intent(query: str) -> QueryIntent:
    query_lower = query.lower()

    DEBUG_KEYWORDS = {"bug", "fix", "error", "fail", "broken", "why", "crash", "exception", "traceback", "debug"}
    words = set(query_lower.split())
    if words & DEBUG_KEYWORDS:
        return QueryIntent.DEBUG
    if any(phrase in query_lower for phrase in ["where is", "where are", "find ", "locate ", "defined", "declaration"]):
        return QueryIntent.LOCATION
    if any(phrase in query_lower for phrase in ["what is", "explain", "how does", "how do", "documentation", "readme", "guide"]):
        return QueryIntent.DOCS
    return QueryIntent.CODE
```

**Future enhancement (V1.2+):** Optional Claude Max-based classification for higher accuracy.

---

## 9. Terminology Expansion

### Static Terminology (V1)

```yaml
# indexer/terminology.yaml (Evvy-specific)
abbreviations:
  BV: "bacterial vaginosis"
  STI: "sexually transmitted infection"
  UTI: "urinary tract infection"
  PCR: "polymerase chain reaction lab test"
  OTC: "over the counter treatment"
  Rx: "prescription"
  vNGS: "vaginal next generation sequencing"

synonyms:
  consult: ["consultation", "telehealth", "wheel"]
  sub: ["subscription", "recurring"]
  fill: ["prescription fill", "medication order"]
```

### Terminology Discovery (Weekly Cron)

```bash
# Scheduled: weekly
clew extract-terms --output indexer/terminology_candidates.yaml
```

**Process:**
1. Scan docstrings/comments for patterns: `TERM (expansion)`, `TERM - expansion`
2. Output candidates to `terminology_candidates.yaml`
3. Human reviews and moves approved terms to `terminology.yaml`
4. Indexer loads `terminology.yaml` at startup

---

## 10. Re-ranking

### Two-Stage Retrieval

```python
async def search_with_rerank(query: str, limit: int = 10) -> list[Chunk]:
    # Stage 1: Hybrid search (default 30 candidates, configurable via SearchConfig.rerank_candidates)
    candidates = await hybrid_search(query, limit=30)

    # Check skip conditions (threshold configurable via SearchConfig.no_rerank_threshold, default 10)
    if should_skip_rerank(query, candidates):
        return candidates[:limit]

    # Stage 2: Re-rank with Voyage (sync via RerankProvider.rerank(), orchestrated by async SearchEngine.search())
    reranked = rerank_provider.rerank(
        query=query,
        documents=[c.content for c in candidates],
        model="rerank-2.5",
        top_k=limit
    )

    return [candidates[r.index] for r in reranked.results]
```

### Skip Conditions

1. Few candidates (configurable via `SearchConfig.no_rerank_threshold`, default 10)
2. High-confidence top result (>0.92)
3. Exact identifier query
4. File path query
5. Low score variance (<0.1)

---

## 11. Structural Boosting (Prefetch Weighting)

Instead of post-hoc score manipulation, use Qdrant prefetch to gather more candidates from relevant sources:

```python
def build_prefetch(query: str, active_file: str | None, intent: QueryIntent) -> list[Prefetch]:
    prefetches = [
        # Base semantic search
        Prefetch(query=dense_vector, using="dense", limit=30),
        # Base keyword search
        Prefetch(query=sparse_vector, using="bm25", limit=30),
    ]

    # Structural boost: same module gets extra candidates
    if active_file:
        module = detect_app_name(active_file)  # from clew.indexer.metadata
        prefetches.append(
            Prefetch(
                query=dense_vector,
                using="dense",
                filter=Filter(must=[FieldCondition(key="app_name", match=MatchValue(value=module))]),
                limit=15
            )
        )

    # Intent-based boost: debug queries get more test files
    if intent == QueryIntent.DEBUG:
        prefetches.append(
            Prefetch(
                query=dense_vector,
                using="dense",
                filter=Filter(must=[FieldCondition(key="is_test", match=MatchValue(value=True))]),
                limit=10
            )
        )

    return prefetches
```

**Deferred to V2+:** Recency boosting (old code isn't necessarily less relevant)

---

## 12. MCP Tool Specifications

### Tool 1: `search`

```typescript
// Input
{
  query: string,              // Natural language or code query
  limit?: number,             // Default 10, max 50
  filters?: {
    app_name?: string,        // Django app / directory filter
    layer?: "model" | "view" | "serializer" | "task" | "service" | "component",
    is_test?: boolean,
    language?: "python" | "typescript" | "markdown"
  },
  intent?: "code" | "docs" | "debug" | "location"  // Optional override
}

// Output
{
  results: Array<{
    file_path: string,
    line_start: number,
    line_end: number,
    content: string,
    score: number,            // 0-1 relevance score
    chunk_type: string,
    app_name: string
  }>,
  query_enhanced: string,     // Show expansions applied
  total_candidates: number
}

// Errors
{ error: "search_unavailable", message: string }
{ error: "invalid_filter", message: string }
```

### Tool 2: `get_context`

```typescript
// Input
{
  file_path: string,
  line_start?: number,
  line_end?: number,
  include_related?: boolean   // Default true
}

// Output
{
  primary: {
    file_path: string,
    content: string,
    language: string
  },
  related: Array<{            // Django-related files
    file_path: string,
    relationship: "serializer" | "view" | "model" | "test" | "url",
    content: string
  }>,
  imports: Array<{
    module: string,
    file_path: string | null  // null if external package
  }>
}
```

### Tool 3: `explain`

```typescript
// Input
{
  file_path: string,
  symbol?: string,            // Specific function/class name
  question?: string           // Specific question about the code
}

// Output
{
  explanation: string,
  related_chunks: Array<{
    file_path: string,
    chunk_type: string,
    relevance: string
  }>
}
```

### Tool 4: `index_status`

```typescript
// Input
{
  action?: "status" | "trigger"  // Default "status"
}

// Output (status)
{
  healthy: boolean,
  collections: {
    code: { chunk_count: number, last_indexed: string },
    docs: { chunk_count: number, last_indexed: string }
  },
  last_commit_indexed: string,
  pending_files: number,
  embedding_model: string
}

// Output (trigger)
{
  triggered: boolean,
  message: string
}
```

---

## 13. Project Structure

### Generic Tool: `ruminaider/clew`

Open source repository: `https://github.com/ruminaider/clew`

```
clew/
├── clew/
│   ├── __init__.py
│   ├── cli.py              # typer CLI (index, search, status, inspect)
│   ├── mcp_server.py       # MCP server implementation
│   ├── config.py           # Load project-specific config
│   ├── chunker/
│   │   ├── __init__.py
│   │   ├── parser.py       # tree-sitter AST parsing
│   │   ├── strategies.py   # File-type-specific chunking
│   │   ├── fallback.py     # Splitter fallback chain (tree-sitter → token → line)
│   │   └── tokenizer.py    # Voyage tokenizer wrapper
│   ├── search/
│   │   ├── __init__.py
│   │   ├── engine.py       # SearchEngine — top-level orchestrator
│   │   ├── hybrid.py       # Dense + BM25 fusion
│   │   ├── intent.py       # Query intent classification heuristics
│   │   ├── models.py       # QueryIntent, SearchResult, SearchRequest, SearchResponse
│   │   ├── rerank.py       # Voyage reranker
│   │   ├── enhance.py      # Query enhancement
│   │   └── tokenize.py     # BM25 tokenization (camelCase/snake_case splitting)
│   ├── indexer/
│   │   ├── __init__.py
│   │   ├── pipeline.py     # Main indexing pipeline
│   │   ├── cache.py        # SQLite caching
│   │   ├── git_tracker.py  # Git change detection (primary)
│   │   ├── file_hash.py    # File-hash change detection (secondary)
│   │   ├── metadata.py     # detect_app_name, classify_layer, build_chunk_id
│   │   └── ignore.py       # Ignore pattern hierarchy loading
│   ├── clients/
│   │   ├── __init__.py
│   │   ├── base.py         # EmbeddingProvider ABC
│   │   ├── qdrant.py       # QdrantManager — collection CRUD, hybrid query
│   │   └── voyage.py       # Voyage API wrapper with retry
├── pyproject.toml
├── README.md
└── tests/
```

### Evvy Configuration: `evvy/indexer/`

```
evvy/
├── backend/
├── frontend/
├── indexer/                  # Evvy-specific configuration
│   ├── config.yaml           # Chunking rules, collections, patterns
│   ├── terminology.yaml      # BV, UTI, STI expansions
│   ├── terminology_candidates.yaml  # Auto-extracted, pending review
│   └── .qdrant/              # Local Qdrant data (gitignored)
├── docker-compose.yml        # Add Qdrant service
└── .mcp.json                 # Add clew server
```

### Evvy Config Example

```yaml
# indexer/config.yaml
project:
  name: "evvy"
  root: "."

collections:
  code:
    include:
      - "backend/**/*.py"
      - "frontend/**/*.tsx"
      - "frontend/**/*.ts"
    exclude:
      - "**/migrations/*.py"
      - "**/__pycache__/**"
      - "**/node_modules/**"
  docs:
    include:
      - "**/*.md"
      - "docs/**/*"

chunking:
  default_max_tokens: 3000
  overrides:
    "backend/**/models.py":
      strategy: "class_with_methods"
      max_tokens: 3000
    "backend/**/views.py":
      strategy: "class_with_methods"
      max_tokens: 4000
    "backend/**/tasks.py":
      strategy: "function"
      max_tokens: 2000

django:
  app_detection: true
  related_files:
    models.py: ["serializers.py", "views.py", "admin.py", "tests/test_models.py"]
    views.py: ["models.py", "serializers.py", "urls.py", "tests/test_views.py"]
    tasks.py: ["models.py", "services.py", "tests/test_tasks.py"]

security:
  exclude_patterns:
    - "**/.env*"
    - "**/secrets/**"
    - "**/*credential*"
    - "**/*secret*"
    - "**/*.pem"
    - "**/*.key"
```

### MCP Configuration

```json
// .mcp.json addition
{
  "evvy-clew": {
    "command": "clew",
    "args": ["serve", "--config", "./indexer/config.yaml"],
    "env": {
      "VOYAGE_API_KEY": "${VOYAGE_API_KEY}",
      "QDRANT_URL": "http://localhost:6333"
    }
  }
}
```

---

## 14. CLI Commands

**Note:** CLI wiring for search/index commands is deferred — search currently shows a placeholder message.

```bash
# Indexing
clew index                      # Incremental (git-aware)
clew index --full               # Full reindex
clew index --files path/to.py   # Specific files

# Search (debugging only - use Claude Code for normal queries)
clew search "query" --raw       # See scores, metadata (placeholder — wiring deferred)

# Status
clew status                     # Health, chunk counts, last indexed

# Inspect
clew inspect --file care/models.py  # Show chunks for a file

# Terminology
clew extract-terms              # Extract candidates for review

# MCP Server
clew serve --config config.yaml # Start MCP server
```

---

## 15. Evaluation Test Queries

### Baseline Queries (30 total)

Run these queries before and after implementation to measure quality.

#### Exact Match (6)

| Query | Expected Top Result |
|-------|---------------------|
| `PrescriptionFillOrder model` | `backend/care/models.py` |
| `ConsultState enum` | `backend/consults/models.py` |
| `WheelAPIClient` | `backend/consults/wheel/wheel.py` |
| `RechargeAPIClient` | `backend/subscriptions/recharge.py` |
| `send_wheel_consult task` | `backend/consults/wheel/tasks.py` |
| `RuleSet model` | `backend/business_rules/models.py` |

#### Natural Language - Domain (8)

| Query | Expected Top Results |
|-------|----------------------|
| "how do we handle expired prescriptions" | `care/models.py` prescription logic |
| "where is BV treatment recommendation logic" | `care/service.py`, `test_results/service.py` |
| "UTI consultation flow" | `consults/wheel/`, UTI intake models |
| "subscription renewal process" | `subscriptions/service.py`, `recharge.py` |
| "how does checkout create an order" | `ecomm/models/order.py`, webhooks |
| "what determines care eligibility" | `care/service.py` |
| "how are lab results processed" | `test_results/service.py` |
| "male partner treatment intake" | `consults/wheel/` male partner flow |

#### Cross-File (6)

| Query | Expected Top Results |
|-------|----------------------|
| "what calls create_order" | Order creation callers |
| "prescription to fill order flow" | `care/models.py`, `shipping/precision/` |
| "how does Shopify connect to our User model" | `ecomm/shopify/` |
| "consult state machine transitions" | `consults/models.py`, `service.py` |
| "what happens after lab results arrive" | `test_results/service.py` |
| "discount stacking logic" | Discount calculation |

#### Debugging (6)

| Query | Expected Top Results |
|-------|----------------------|
| "why would subscription order fail to create fill" | Subscription → fill logic |
| "lab order submission retry logic Junction" | `consults/wheel/tasks.py` |
| "missing user ID across orders" | User matching logic |
| "UTI test stuck in results received" | Lab order status handling |
| "Wheel consult creation 400 error" | Wheel API validation |
| "USPS tracking status updates" | `shipping/usps.py` |

#### Integration (4)

| Query | Expected Top Results |
|-------|----------------------|
| "Wheel API authentication" | `consults/wheel/wheel.py` |
| "Shopify webhook handlers" | `ecomm/shopify/` |
| "Precision Pharmacy integration" | `shipping/precision/` |
| "Recharge subscription webhooks" | `subscriptions/recharge.py` |

---

## 16. Implementation Roadmap

### Phase 1: Core Infrastructure

| Task | Acceptance Criteria |
|------|---------------------|
| Qdrant Docker setup | `docker compose up` starts Qdrant; health endpoint returns 200; data persists across restarts |
| Voyage tokenizer integration | Can count tokens for any Python/TS file; matches API token count |
| Basic AST chunker | Parses Python file with tree-sitter; outputs chunks with identity, content, metadata |
| Embedding pipeline | Embeds list of chunks; returns 1024-dim vectors; retries on rate limit |
| SQLite caching | Stores file hashes, chunk identities, embeddings; lookup by content hash works |
| Minimal CLI | `clew index --file path.py` works; `clew status` shows chunk count |
| Splitter fallback chain | tree-sitter → token-recursive → line split; all three tiers produce valid chunks within token limits |
| Embedding provider ABC | `EmbeddingProvider` ABC with Voyage implementation; `embed()` returns correct dimensions; provider switchable via config |
| File-hash change detection | `FileHashTracker` detects added/modified/unchanged files; integrates as fallback when git-diff unavailable |
| Ignore pattern loading | 5-source hierarchy loads and merges patterns; `.gitignore` syntax works via `pathspec`; env var overrides |
| Safety limits | Configurable limits enforced: 500K total chunks, per-collection, 1MB file-size cap; clear error on breach |

### Phase 2: Search Pipeline

| Task | Acceptance Criteria |
|------|---------------------|
| Hybrid search | Dense + BM25 fusion returns results; RRF ranking applied |
| Code tokenization for BM25 | camelCase and snake_case properly split |
| Re-ranking integration | Voyage rerank-2.5 improves result ordering |
| Query enhancement | Terminology expansion works; bypass logic for exact queries |
| Intent classification | Heuristics classify queries; debug intent includes test files |

### Phase 3: MCP Integration

| Task | Acceptance Criteria |
|------|---------------------|
| MCP server | All 4 tools implemented with specified schemas |
| Claude Code config | `.mcp.json` configured; tools appear in Claude Code |
| Error handling | Clear error messages for Qdrant/Voyage unavailable |
| Structural boosting | Same-module prefetch working; debug queries include tests |

### Phase 4: Polish & Evaluation

| Task | Acceptance Criteria |
|------|---------------------|
| Incremental updates | Git-aware indexing only re-embeds changed chunks |
| Full evaluation | All 30 test queries scored; results documented |
| Documentation | README, config examples, troubleshooting guide |
| Terminology extraction | Weekly cron extracts candidates to YAML |

### V1.1: NL Descriptions (Deferred)

| Task | Acceptance Criteria |
|------|---------------------|
| Description generation | LLM generates descriptions for chunks without docstrings |
| Description caching | Generated descriptions cached by content hash |
| Search integration | NL descriptions embedded alongside code |

### V1.2: Multi-hop Expansion (Deferred)

| Task | Acceptance Criteria |
|------|---------------------|
| Reference extraction | AST-based import/call extraction |
| Reference resolution | Maps references to indexed chunks |
| Expansion in search | 1-2 hop expansion available for context assembly |

---

## 17. Cost Estimates

| Component | Usage | Cost |
|-----------|-------|------|
| Voyage voyage-code-3 embeddings | Full index (~5K chunks) | ~$0.18 one-time |
| Voyage voyage-code-3 queries | 100/day | ~$0.006/month |
| Voyage rerank-2.5 | 100 queries/day | ~$0.15/day |
| Qdrant (self-hosted) | Docker | $0 |
| **Monthly Total (est.)** | | **~$5-10** |

---

## 18. Feature Phasing Summary

| Version | Features | Status |
|---------|----------|--------|
| **V1** | Core search, 2 collections, hybrid search, reranking, MCP tools, CLI | To implement |
| **V1.1** | NL descriptions for better semantic matching | Deferred |
| **V1.2** | Multi-hop reference expansion | Deferred |
| **V2** | Schema collection, git history collection, recency boosting | Future |

---

## 19. Safety Limits

Configurable limits prevent runaway indexing from consuming excessive API credits and storage. Adapted from claude-context's 450K hard limit — see [ADR-003](./adr/003-ported-features-from-claude-context.md#8-safety-limits).

### Default Limits

| Limit | Default | Configurable | Purpose |
|-------|---------|-------------|---------|
| Total chunks | 500,000 | `safety.max_total_chunks` | Prevent storage explosion |
| Per-collection chunks | None (unlimited) | `safety.max_chunks_per_collection` | Balance between collections |
| File size | 1 MB | `safety.max_file_size_bytes` | Skip minified/generated files |
| Batch size | 100 | `safety.batch_size` | API call size limit |

### Enforcement

```python
class SafetyChecker:
    def __init__(self, config: SafetyConfig):
        self.config = config

    def check_file(self, file_path: str, file_size: int) -> bool:
        """Return False if file should be skipped."""
        if file_size > self.config.max_file_size_bytes:
            logger.warning(f"Skipping {file_path}: {file_size} bytes > {self.config.max_file_size_bytes} limit")
            return False
        return True

    def check_total_chunks(self, current_count: int, new_chunks: int) -> bool:
        """Return False if adding chunks would exceed total limit."""
        if current_count + new_chunks > self.config.max_total_chunks:
            logger.error(
                f"Safety limit: {current_count + new_chunks} chunks would exceed "
                f"{self.config.max_total_chunks} limit"
            )
            return False
        return True
```

### Configuration

```yaml
# In config.yaml
safety:
  max_total_chunks: 500000
  max_file_size_bytes: 1048576  # 1 MB
  batch_size: 100
  # Optional per-collection limits
  collection_limits:
    code: 400000
    docs: 100000
```

**Implementation:** `clew/models.py` (`SafetyConfig`), `clew/indexer/pipeline.py` — See [IMPLEMENTATION.md](./IMPLEMENTATION.md)
