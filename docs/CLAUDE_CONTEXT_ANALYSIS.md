# claude-context Analysis

**Status:** Reference document
**Date:** 2026-02-05
**Related:** [ADR-001](./adr/001-qdrant-as-vector-database.md), [ADR-002](./adr/002-build-vs-adopt-claude-context.md), [ADR-003](./adr/003-ported-features-from-claude-context.md)

This document analyzes [claude-context](https://github.com/zilliztech/claude-context) by Zilliz and records what we adopted, what we rejected, and why. claude-context is **not** a runtime dependency — this is analysis-only.

---

## 1. Overview

claude-context is an open-source TypeScript tool that indexes codebases into vector databases for use with Claude via MCP (Model Context Protocol). It was built by Zilliz, the company behind Milvus.

**Key characteristics:**
- Language: TypeScript/Node.js
- Vector DB: Milvus (Zilliz's product)
- Parsing: tree-sitter with LangChain fallback
- Change detection: Merkle DAG
- Integration: MCP server for Claude Code
- Scope: Generic code indexing (no project-specific configuration)

**Repository stats (as evaluated):**
- ~5,000 lines of TypeScript
- 8 MCP tools exposed
- Supports Python, TypeScript, JavaScript, Java, Go, Rust, C/C++

---

## 2. Architecture Deep Dive

### 2.1 Merkle DAG for Change Detection

claude-context builds a Merkle DAG (Directed Acyclic Graph) from file content hashes. Each file is a leaf node, and directory nodes aggregate child hashes. When a file changes, only the path from that file to the root is invalidated.

```
root (hash: abc123)
├── src/ (hash: def456)
│   ├── models.py (hash: aaa111)
│   └── views.py (hash: bbb222)
└── tests/ (hash: ghi789)
    └── test_models.py (hash: ccc333)
```

**Strengths:**
- Works without git (standalone tool)
- Efficient for detecting changes in large trees
- Deterministic — same content always produces same hash

**Limitations for us:**
- We always have git available — `git diff` is faster and more informative
- Merkle DAG doesn't classify changes (add/modify/delete/rename)
- Requires maintaining the DAG structure in storage

### 2.2 AST Parsing Pipeline

claude-context uses tree-sitter for AST parsing with a three-tier fallback:

1. **tree-sitter** — Parses supported languages into AST, extracts functions/classes/methods
2. **LangChain RecursiveCharacterTextSplitter** — Falls back to character-based recursive splitting
3. **Generic line splitter** — Last resort for files that resist structured parsing

The tree-sitter integration is well-implemented, with language detection by file extension and configurable node types for extraction.

### 2.3 Embedding Pipeline

```
Files → AST Parse → Chunk → Batch (100/batch) → Embed → Upsert to Milvus
                                                    ↓
                                              Progress callbacks
```

Key design choices:
- Batch size of 100 chunks per API call
- Callbacks for progress reporting
- Multi-provider abstraction (primarily OpenAI embeddings)
- No embedding caching (re-embeds on every full index)

### 2.4 Milvus Storage

claude-context creates collections in Milvus with:
- Dense vectors for semantic search
- Sparse vectors (BM25) for keyword matching
- Metadata fields for filtering

The Milvus integration requires orchestrating dense and sparse searches separately, then fusing results in application code.

### 2.5 MCP Tools

claude-context exposes 8 MCP tools:
1. `search_code` — Semantic code search
2. `search_symbol` — Symbol-specific search
3. `get_file` — Retrieve file contents
4. `get_directory` — List directory contents
5. `get_file_tree` — Full file tree
6. `index_status` — Indexing status
7. `trigger_index` — Trigger re-indexing
8. `get_config` — Current configuration

---

## 3. What We Adopted (8 Features)

### 3.1 AST Fallback Chain

**Source:** `src/chunker/` — tree-sitter parsing with LangChain fallback

**Why adopted:** Files that tree-sitter can't parse (malformed code, unsupported languages, configuration files) still need to be indexed. A fallback chain ensures no file is silently dropped.

**How we adapted:** Replaced LangChain with a lightweight token-recursive splitter (~100 lines Python). Our splitter is token-aware (uses Voyage tokenizer) rather than character-based, preventing chunks that exceed embedding model token limits.

**Implementation:** `code_search/chunker/fallback.py`

### 3.2 Hybrid Change Detection

**Source:** `src/indexer/merkle.ts` — Merkle DAG implementation

**Why adopted:** Robust change detection is essential for incremental indexing. The concept of content-hashing for change detection is sound.

**How we adapted:** Made git-diff the primary detection method (faster, provides change classification) and file-hashing a secondary fallback for edge cases (shallow clones, squashed merges).

**Implementation:** `code_search/indexer/git.py` (primary), `code_search/indexer/file_hash.py` (secondary)

### 3.3 Batch Embedding

**Source:** `src/embedder/batch.ts` — 100 chunks/batch with progress callbacks

**Why adopted:** Batching is essential for API efficiency and the batch size of 100 is well-validated.

**How we adapted:** Configurable batch size (default 100) with `rich` progress bars instead of callbacks.

**Implementation:** `code_search/indexer/batch.py`

### 3.4 Embedding Provider Abstraction

**Source:** `src/embedder/providers/` — Multi-provider interface

**Why adopted:** Decoupling the embedding model from the indexing pipeline is good software design and enables testing, fallback, and future flexibility.

**How we adapted:** Python ABC with `embed()`, `embed_query()`, `dimensions`, and `model_name`. Defaults to Voyage AI; OpenAI and Ollama as optional providers.

**Implementation:** `code_search/clients/base.py`

### 3.5 Chunk Overlap

**Source:** `src/chunker/splitter.ts` — 300 chars overlap from previous chunk

**Why adopted:** Overlap helps maintain context continuity when chunks split mid-concept.

**How we adapted:** Reduced to 200 tokens (token-based, not character-based) and restricted to non-AST fallback chunks only. AST-parsed entities (functions, classes) are self-contained and should not bleed into adjacent chunks.

**Implementation:** `code_search/chunker/fallback.py`

### 3.6 Ignore Pattern Hierarchy

**Source:** `src/config/ignore.ts` — 5-level ignore pattern hierarchy

**Why adopted:** A single ignore list is too rigid. Different levels of configuration allow defaults, project, and runtime overrides.

**How we adapted:** Aligned with `.gitignore` syntax (via `pathspec` library) and integrated with our YAML config system. Our 5 levels: defaults → `.gitignore` → `.codesearchignore` → `config.yaml` → env vars.

**Implementation:** `code_search/indexer/ignore.py`

### 3.7 Dual Chunk ID Strategy

**Source:** `src/chunker/identity.ts` — SHA256(path:start:end:content)

**Why adopted:** Stable chunk IDs are critical for incremental updates — without them, every re-index would re-embed everything.

**How we adapted:** Entity-based IDs for named code (stable across content changes that don't rename) + content-hash IDs for anonymous code. Superior to claude-context's offset-based approach, which invalidates chunks when unrelated code shifts offsets.

**Implementation:** `code_search/chunker/identity.py`

### 3.8 Safety Limits

**Source:** `src/indexer/limits.ts` — 450K chunk hard limit

**Why adopted:** Without limits, a misconfigured include pattern could index `node_modules` and consume excessive API credits and storage.

**How we adapted:** Multi-level configurable limits: 500K total chunks, per-collection limits, 1MB file-size cap, 100 chunks/batch. More granular than claude-context's single hard limit.

**Implementation:** `code_search/models.py` (`SafetyConfig`)

---

## 4. What We Rejected (6 Items)

### 4.1 Milvus as Vector Database

**Why rejected:** See [ADR-001](./adr/001-qdrant-as-vector-database.md). Qdrant provides native hybrid search with RRF fusion, superior payload filtering, and a dramatically lighter deployment footprint (1 container vs 3).

### 4.2 TypeScript as Implementation Language

**Why rejected:** Our team's expertise is Python. Voyage AI's primary SDK is Python. The tokenizer ecosystem (HuggingFace transformers) is Python-native. Writing the tool in TypeScript would require a language bridge for embedding operations and add operational complexity.

### 4.3 LangChain Dependency

**Why rejected:** claude-context uses LangChain's `RecursiveCharacterTextSplitter` as a fallback chunker. LangChain adds ~50+ transitive dependencies for a single text-splitting function. Additionally, it's character-based rather than token-aware, which can produce chunks exceeding embedding model limits. Our token-recursive splitter is ~100 lines of Python with zero additional dependencies.

### 4.4 File Watcher for Live Indexing

**Why rejected:** claude-context can watch the filesystem for changes and re-index in real time. For our use case, git-based change detection triggered manually or via pre-commit hooks is sufficient. File watching adds complexity (debouncing, lock contention with editors, handling rapid saves) with minimal benefit — developers don't need sub-second index freshness.

### 4.5 Generic MCP Tools (8 tools)

**Why rejected:** claude-context exposes 8 MCP tools including file browsing, directory listing, and file tree traversal. Claude Code already has these capabilities natively. Our 4 tools (`search`, `get_context`, `explain`, `index_status`) focus on the value-add: semantic search and code understanding that Claude Code cannot do on its own.

### 4.6 Simple BM25 Tokenization

**Why rejected:** claude-context uses standard whitespace/punctuation tokenization for BM25 sparse vectors. Code identifiers like `getUserById` and `get_user_by_id` are treated as single tokens, reducing keyword matching effectiveness. Our code-specific BM25 tokenizer splits camelCase and snake_case identifiers into constituent words, significantly improving keyword recall for code queries.

---

## 5. Comparative Architecture

| Layer | claude-context | code-search |
|-------|---------------|-------------|
| **Language** | TypeScript | Python |
| **Vector DB** | Milvus (3 containers) | Qdrant (1 container) |
| **Embeddings** | OpenAI (primary) | Voyage AI (primary), ABC for providers |
| **Reranking** | None | Voyage rerank-2.5 |
| **AST Parsing** | tree-sitter | tree-sitter |
| **Fallback Chunking** | LangChain (character-based) | Token-recursive splitter (token-aware) |
| **Change Detection** | Merkle DAG | git-diff + file-hash hybrid |
| **Search Fusion** | Application-layer RRF | Qdrant native RRF |
| **BM25 Tokenization** | Standard whitespace | Code-aware (camelCase, snake_case) |
| **Ignore Patterns** | 5-level proprietary format | 5-level .gitignore-compatible |
| **Chunk IDs** | SHA256(path:offset:content) | Entity-based + content-hash dual |
| **Safety Limits** | 450K hard limit | Multi-level configurable |
| **MCP Tools** | 8 (includes file browsing) | 4 (search-focused) |
| **Configuration** | Minimal | Rich YAML per-file strategies |
| **Domain Features** | None | Terminology expansion, Django awareness, intent classification |

---

## 6. Lessons Learned

### What claude-context does well

1. **Merkle DAG is elegant** — Even though we don't use it, the concept of content-addressable change detection is well-implemented and instructive.
2. **Fallback chain is essential** — Every code indexer needs graceful degradation when AST parsing fails. We would have discovered this requirement late without seeing claude-context's approach.
3. **Safety limits prevent disasters** — Without explicit limits, a misconfigured indexer can rack up thousands of dollars in embedding API costs. This is the kind of feature you don't appreciate until you need it.
4. **Ignore patterns need hierarchy** — A single ignore list doesn't scale. Different granularities (defaults, project, runtime) are necessary.

### What we learned from their limitations

1. **Generic tools lose to specific tools** — claude-context's lack of domain-specific features (terminology, layer awareness, per-file strategies) means search quality will be mediocre for domain-specific codebases. The lesson: build for your use case first, generalize later.
2. **Character-based splitting is a footgun** — Chunks that exceed token limits silently degrade embedding quality. Token-aware splitting should be the default.
3. **Offset-based chunk IDs are fragile** — Adding a comment above a function changes the offsets of everything below it, invalidating chunk IDs unnecessarily. Identity should be based on semantic structure, not byte positions.
4. **Light dependencies win** — claude-context's LangChain dependency pulls in ~50 packages for one function. This adds install time, security surface, and version conflicts. When the functionality is simple, write it yourself.
