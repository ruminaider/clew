# ADR-001: Qdrant over Milvus as Vector Database

**Status:** Accepted
**Date:** 2026-02-05
**Deciders:** Engineering team
**Related:** [ADR-002](./002-build-vs-adopt-claude-context.md), [DESIGN.md](../DESIGN.md)

---

## Context

We need a vector database for the code-search system that supports hybrid search (dense + sparse vectors), rich metadata filtering, and lightweight local deployment. The two leading candidates are:

- **Qdrant** — Rust-based, purpose-built vector database
- **Milvus** — Go/C++-based, used by [claude-context](https://github.com/zilliztech/claude-context) (Zilliz's code indexing tool)

Evaluating claude-context revealed that Milvus is deeply embedded in its architecture. Choosing Qdrant means we cannot reuse claude-context's indexer directly, but the trade-offs strongly favor Qdrant for our use case.

## Decision

Use **Qdrant (self-hosted, Docker)** as the vector database for code-search.

## Rationale

### 1. Native Hybrid Search with RRF Fusion

Qdrant has built-in support for combining dense and sparse vector searches using Reciprocal Rank Fusion (RRF). A single `query_points` call with `prefetch` handles both retrieval paths and fuses results:

```python
client.query_points(
    prefetch=[
        Prefetch(query=dense_vector, using="dense", limit=30),
        Prefetch(query=sparse_vector, using="bm25", limit=30),
    ],
    query=FusionQuery(fusion=Fusion.RRF),
)
```

Milvus requires orchestrating dense and sparse searches separately, then implementing fusion logic in application code. This adds complexity and a potential source of bugs.

### 2. Superior Payload Filtering

Our metadata schema uses fields like `chunk_type`, `app_name`, `layer`, and `is_test` for structural boosting and intent-based search. Qdrant's payload filtering:

- Supports filtering within prefetch stages (pre-fusion)
- Uses indexed payload fields for efficient filtering
- Allows combining filters with vector search in a single operation

This is critical for features like "debug queries include test files" and "same-module prefetch boosting."

### 3. Deployment Simplicity

| Aspect | Qdrant | Milvus Standalone |
|--------|--------|-------------------|
| Docker image size | ~150 MB | ~2 GB+ |
| Required services | 1 container | 3 containers (milvus + etcd + minio) |
| Memory baseline | ~100 MB | ~500 MB+ |
| Configuration | Minimal env vars | YAML + multiple service configs |

For a developer productivity tool running on a laptop alongside the main application, resource footprint matters.

### 4. Consistent Resource Usage

Qdrant's Rust implementation provides predictable memory usage and CPU consumption. Under concurrent search loads, Qdrant maintains consistent latency. Community benchmarks (including Reddit's evaluation) confirm better filtering performance under load compared to Milvus.

### 5. Lower Operational Complexity

- Single binary, single data directory
- Built-in dashboard at `http://localhost:6333/dashboard`
- Health check with a simple HTTP request
- Data persists in a single Docker volume

## Consequences

### Positive

- Simpler Docker Compose configuration (1 service vs 3)
- Lower resource consumption on developer machines
- Native RRF fusion reduces application-layer code
- Better payload filtering enables our structural boosting design
- Smaller attack surface (fewer exposed services)

### Negative

- Cannot reuse claude-context's Milvus-based indexer — we build our own
- Qdrant's ecosystem is smaller than Milvus/Zilliz's (fewer integrations, smaller community)
- If we later need distributed deployment, Milvus has more mature sharding

### Mitigated

- "Build our own" is acceptable because we need Python, Voyage AI, and evvy-specific features regardless (see [ADR-002](./002-build-vs-adopt-claude-context.md))
- Qdrant Cloud exists as a managed option if self-hosted becomes a burden
