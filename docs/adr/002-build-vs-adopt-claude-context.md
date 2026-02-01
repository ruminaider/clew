# ADR-002: Build Standalone System vs. Adopt claude-context

**Status:** Accepted
**Date:** 2026-02-05
**Deciders:** Engineering team
**Related:** [ADR-001](./001-qdrant-as-vector-database.md), [ADR-003](./003-ported-features-from-claude-context.md), [CLAUDE_CONTEXT_ANALYSIS.md](../CLAUDE_CONTEXT_ANALYSIS.md)

---

## Context

[claude-context](https://github.com/zilliztech/claude-context) is an open-source code indexing tool by Zilliz that provides MCP-based code search for Claude. It uses tree-sitter for AST parsing, Milvus for vector storage, and supports incremental indexing via a Merkle DAG.

We evaluated three options:
1. **Adopt claude-context directly** — use it as-is
2. **Fork and adapt** — fork claude-context and modify it for our needs
3. **Build standalone** — build code-search from scratch, porting specific ideas

## Decision

**Build code-search as a standalone system**, porting 8 specific patterns from claude-context (documented in [ADR-003](./003-ported-features-from-claude-context.md)).

## Rationale

### 1. Vector Database Mismatch

claude-context uses Milvus (backed by Zilliz, its creator). We chose Qdrant for its native hybrid search, lighter footprint, and superior payload filtering (see [ADR-001](./001-qdrant-as-vector-database.md)). The Milvus integration is deeply embedded in claude-context's storage layer — replacing it would require rewriting the entire persistence and query layer.

### 2. Language Mismatch

claude-context is written in TypeScript. Our stack is Python:
- Voyage AI's primary SDK is Python
- tree-sitter has excellent Python bindings
- Our team's expertise is Python (Django backend)
- Python's scientific/ML ecosystem (tokenizers, transformers) is needed for token counting

Porting TS→Python is not a trivial translation — it requires rethinking async patterns, error handling, dependency management, and testing approaches.

### 3. Missing Evvy-Specific Features

claude-context is a generic tool. Our design requires features it does not have:

| Feature | code-search | claude-context |
|---------|-------------|----------------|
| Terminology expansion (BV, UTI, STI) | Yes — static YAML + discovery | No |
| Django layer awareness (model/view/serializer) | Yes — structural boosting | No |
| Voyage AI reranking | Yes — rerank-2.5 integration | No |
| Intent classification (code/docs/debug) | Yes — heuristic + structural | No |
| Project config (per-file chunking rules) | Yes — YAML-driven strategies | Generic only |
| Code-specific BM25 tokenization | Yes — camelCase/snake_case splitting | Basic BM25 |

### 4. Generic Chunking vs. File-Type-Specific Strategies

claude-context uses a one-size-fits-all AST chunking approach. Our design specifies different strategies per file pattern:

- `models.py` → class + fields as unit, methods split if large
- `views.py` → class as unit, actions split if large
- `serializers.py` → class-level chunks
- `tasks.py` → function with decorators
- `*.tsx` → component boundaries

This file-type awareness is fundamental to our search quality and cannot be added to claude-context without major restructuring.

### 5. Fork Cost Analysis

Forking claude-context would require:
1. Rewrite TypeScript → Python (entire codebase)
2. Replace Milvus → Qdrant (storage + query layer)
3. Replace LangChain text splitters → our token-based splitter
4. Add terminology expansion system
5. Add Django layer awareness
6. Add Voyage reranking
7. Add intent classification
8. Add per-file chunking strategies
9. Add code-specific BM25 tokenization
10. Redesign configuration system

This is effectively a complete rewrite wearing the skin of a fork. Building from scratch with ported ideas is cleaner, more maintainable, and avoids inheriting architectural decisions that don't fit our needs.

## Consequences

### Positive

- Clean architecture designed for our exact requirements
- Python-native codebase matching team expertise
- No upstream dependency on claude-context's release cadence
- Freedom to choose Qdrant, Voyage reranking, and file-specific strategies
- No LangChain dependency (lighter, fewer transitive deps)

### Negative

- More initial development effort (no head start from existing code)
- Must implement AST parsing, embedding pipeline, and MCP server ourselves
- Cannot benefit from claude-context's future improvements automatically

### Mitigated

- We ported 8 specific patterns from claude-context to avoid reinventing good ideas (see [ADR-003](./003-ported-features-from-claude-context.md))
- The core components (tree-sitter, Qdrant client, Voyage SDK) are well-documented libraries — the integration work is manageable
- claude-context remains a reference implementation we can consult for specific problems
