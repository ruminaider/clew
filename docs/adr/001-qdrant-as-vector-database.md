# ADR-001: Qdrant as Vector Database (over Milvus and Weaviate)

**Status:** Accepted
**Date:** 2026-02-05 (updated 2026-02-07 with Weaviate evaluation)
**Deciders:** Engineering team
**Related:** [ADR-002](./002-build-vs-adopt-claude-context.md), [DESIGN.md](../DESIGN.md)

---

## Context

We need a vector database for the code-search system that supports hybrid search (dense + sparse vectors), rich metadata filtering, and lightweight local deployment on developer laptops. Three candidates were evaluated:

- **Qdrant** — Rust-based, purpose-built vector database
- **Milvus** — Go/C++-based, used by [claude-context](https://github.com/zilliztech/claude-context) (Zilliz's code indexing tool)
- **Weaviate** — Go-based, AI-native vector database with built-in BM25

Evaluating claude-context revealed that Milvus is deeply embedded in its architecture. Weaviate was evaluated as a potential alternative to Qdrant given its native BM25 support and active ecosystem (~15.5K GitHub stars, BSD-3-Clause license).

### Requirements

| Requirement | Priority | Notes |
|---|---|---|
| Multi-stage filtered prefetch | Critical | Structural boosting: same-module boost, debug-intent test inclusion |
| Hybrid search (dense + BM25) with RRF | Critical | Dense vectors from Voyage AI + keyword matching for code identifiers |
| Rich metadata filtering | High | `chunk_type`, `app_name`, `layer`, `is_test`, `language` |
| Low resource footprint | High | Runs on developer laptop alongside main application |
| Incremental updates | High | Git-aware upsert of changed chunks, delete removed ones |
| Python async client | Medium | Async Voyage + vector DB calls in indexing and search pipelines |
| Self-hosted Docker (single container) | Medium | Minimal ops, no external dependencies |

## Decision

Use **Qdrant (self-hosted, Docker)** as the vector database for code-search.

## Rationale

### 1. Multi-Stage Filtered Prefetch (Qdrant-Unique)

Our structural boosting design ([DESIGN.md §11](../DESIGN.md#11-structural-boosting-prefetch-weighting)) depends on executing multiple independent sub-queries with different filters, then fusing results server-side. This is the single most important architectural requirement.

**Qdrant** has native multi-stage prefetch where each stage can target a different named vector space, apply its own filter, and return its own candidate limit — all fused in one `query_points` call:

```python
client.query_points(
    collection_name="code",
    prefetch=[
        # Base semantic search
        Prefetch(query=dense_vector, using="dense", limit=30),
        # Base keyword search
        Prefetch(query=sparse_vector, using="bm25", limit=30),
        # Structural boost: same module gets extra candidates
        Prefetch(
            query=dense_vector, using="dense",
            filter=Filter(must=[FieldCondition(key="app_name", match=MatchValue(value=module))]),
            limit=15,
        ),
        # Intent boost: debug queries include test files
        Prefetch(
            query=dense_vector, using="dense",
            filter=Filter(must=[FieldCondition(key="is_test", match=MatchValue(value=True))]),
            limit=10,
        ),
    ],
    query=FusionQuery(fusion=Fusion.RRF),
    limit=20,
)
```

**Milvus** requires orchestrating dense and sparse searches separately, then implementing fusion logic in application code. No server-side multi-stage pipeline exists.

**Weaviate** has a single-stage `hybrid()` call with one `alpha` parameter controlling dense vs BM25 weighting. There is **no prefetch mechanism**. To replicate structural boosting, you would need to issue multiple separate queries with different filters and fuse results client-side — adding latency, complexity, and losing server-side optimization.

**This alone is decisive.** The structural boosting design cannot be cleanly implemented on Milvus or Weaviate without substantial client-side orchestration that Qdrant handles natively.

### 2. HNSW Implementation: Filterable Graph with Payload-Aware Edges

All three databases use HNSW (Hierarchical Navigable Small World) as their core vector index algorithm. The critical difference is how they handle **filtered search** within the HNSW graph.

**Qdrant — Filterable HNSW + ACORN (two-layer approach):**

- **Index-time:** Builds extra HNSW graph edges per indexed payload value via the `payload_m` parameter. If `language`, `chunk_type`, and `app_name` are indexed, Qdrant maintains connected subgraphs within each value — so "all Python function chunks" has its own well-connected graph neighborhood.
- **Query-time:** ACORN (v1.16+) adds two-hop expansion during traversal for complex multi-filter cases where index-time edges alone may not guarantee connectivity.
- **Result:** Filtered searches traverse pre-built connected subgraphs without query-time overhead, with ACORN as a fallback.

```python
client.create_collection(
    collection_name="code",
    vectors_config={"dense": VectorParams(size=1024, distance=Distance.COSINE)},
    sparse_vectors_config={"bm25": SparseVectorParams(modifier=Modifier.IDF)},
    hnsw_config=HnswConfigDiff(
        m=16,            # Main graph edges
        payload_m=16,    # Filter-aware edges (tunable independently)
        ef_construct=128,
    ),
)
```

**Weaviate — ACORN only (query-time approach):**

- **Index-time:** Vanilla HNSW with no payload-aware modifications.
- **Query-time:** ACORN (default since v1.34) uses two-hop expansion to handle filtered nodes during traversal.
- **Result:** All filtering overhead is paid at query time. No pre-built subgraph connectivity for filtered search.

**Milvus:** Uses a traditional pre-filter then brute-force rescore approach for filtered vector search. No HNSW graph modification for filters.

**Why this matters for code search:** Our system always filters by project, language, and chunk_type. Qdrant's filterable HNSW pre-builds connected subgraphs for these values, meaning a search for "authentication middleware" filtered to `language:python, chunk_type:function` traverses a purpose-built connected graph — not a vanilla graph with query-time filtering overhead.

#### Other HNSW Feature Comparison

| Feature | Qdrant | Weaviate | Milvus |
|---|---|---|---|
| Filterable HNSW (index-time edges) | Yes (`payload_m`) | No | No |
| ACORN (query-time two-hop) | Yes (v1.16+) | Yes (v1.27+, default v1.34+) | No |
| Dynamic ef auto-tuning | No (manual per-query) | Yes (`ef = limit × factor`) | No |
| Incremental HNSW building | Yes (v1.14+, extends graph) | No (async queue, different approach) | No |
| HNSW healing after deletes | Yes (v1.15+) | No (tombstone cleanup) | No |
| HNSW on-disk mode | Yes (`on_disk: true`) | Partial (vector cache, not explicit) | Yes |
| Dynamic index (flat→HNSW) | Per-segment thresholds | Yes (10K object threshold) | No |

**Dynamic ef auto-tuning** (Weaviate-only) is not meaningful for our use case — we always request 10-20 results, so a fixed `hnsw_ef=160` suffices. This is a 3-line wrapper function, not a feature gap.

**Dynamic index** (Weaviate-only) transitions from flat to HNSW at ~10K objects. Our minimum collection size (5K chunks × 1024 dims × 4 bytes ≈ 20 MB) already exceeds the crossover point where HNSW outperforms brute-force. This feature is designed for multi-tenant scenarios with many tiny collections — irrelevant for code search.

**Incremental HNSW building** (Qdrant-only) extends the existing graph when new points are upserted, avoiding full rebuilds. Combined with **HNSW healing** (adds new links after deletions to prevent graph isolation), this is well-suited for our git-aware incremental update pipeline where files are constantly added, modified, and deleted.

### 3. BM25 / Sparse Vector Approach

Code search requires keyword matching for identifiers (`getUserById`, `PrescriptionFillOrder`, `send_wheel_consult`). The three databases handle this differently:

**Qdrant — Bring your own sparse vectors, server-side IDF:**

- Client generates term-frequency (TF) sparse vectors using custom code tokenization
- Server applies IDF weighting at query time via `modifier: "idf"` — updates automatically as documents are added/removed
- Full control over tokenization (critical for code: camelCase splitting, snake_case handling, dotted path decomposition)

**Weaviate — Built-in BM25F with per-property tokenization:**

- Native BM25F ranking with property-level boosting and tokenization options (`word`, `whitespace`, `trigram`, `lowercase`)
- No external sparse vector generation needed — simpler setup
- **But:** None of the tokenization options understand code identifiers. `word` tokenizer splits on non-alphanumeric characters (destroys `snake_case`), doesn't split camelCase, and lowercases everything. No code-aware tokenizer exists.

**Milvus — Sparse vector support but no built-in BM25:**

- Similar to Qdrant: bring your own sparse vectors
- No server-side IDF modification
- Requires client-side fusion of dense and sparse results

**Why Qdrant's approach wins for code search:** Our [DESIGN.md §7](../DESIGN.md#7-hybrid-search) already specifies a custom `tokenize_code_identifiers()` function that splits camelCase, snake_case, and dotted paths into BM25 tokens. Since we need custom tokenization regardless, Weaviate's built-in BM25 convenience is negated — its tokenizers cannot handle code. Qdrant's "bring your own sparse vectors" approach aligns naturally with our custom tokenization pipeline, while providing server-side IDF that Milvus lacks.

### 4. Deployment Simplicity and Resource Footprint

| Aspect | Qdrant | Weaviate | Milvus Standalone |
|---|---|---|---|
| Docker image size | ~100-150 MB | ~79 MB | ~2 GB+ |
| Required services | 1 container | 1 container | 3 containers (milvus + etcd + minio) |
| Idle memory | ~100 MB | ~2.5 GB (reported) | ~500 MB+ |
| Language / GC | Rust (no GC) | Go (GC with `MADV_FREE`) | Go + C++ |
| p99 latency | ~35 ms | ~65 ms | Varies |
| Throughput (RPS) | ~4x higher than Weaviate | Baseline | Comparable to Qdrant |

**Weaviate memory concerns:** Multiple community reports document unexpectedly high memory consumption:

- [Weaviate Forum: 35 GB memory with 100K records](https://forum.weaviate.io/t/weaviate-docker-container-consume-35gb-of-memory-with-only-100k-records/2246)
- Go runtime's `MADV_FREE` causes the OS to report memory as consumed even when it could be freed, making Docker memory limits unreliable
- Weaviate's team documented `GOMEMLIMIT` as a [workaround](https://weaviate.io/blog/gomemlimit-a-game-changer-for-high-memory-applications) for Go's aggressive memory retention

**Qdrant's Rust advantage:** No garbage collector means deterministic memory usage and no GC-induced latency spikes. On a 16 GB developer laptop running Docker alongside an IDE, browser, and the main application, predictable resource consumption matters. Independent benchmarks show Qdrant using ~40% less memory for equivalent workloads.

**Milvus deployment tax:** Requires etcd (consensus), MinIO (object storage), and the Milvus server — three containers with separate configurations. Unacceptable complexity for a developer productivity tool.

### 5. Python Client Quality

| Feature | Qdrant | Weaviate | Milvus |
|---|---|---|---|
| Async support | Full (`AsyncQdrantClient`) | Late addition (v4.7.0), batch still sync-only | Limited |
| Type hints | Comprehensive + `.pyi` stubs | Good in v4 | Basic |
| Local mode (no Docker) | `QdrantClient(":memory:")` | Not available | Not available |
| API stability | Stable, additive changes | v3→v4 complete breaking rewrite | Stable |
| Breaking changes | Rare | v4 dropped v3 compat entirely (Dec 2024) | Moderate |

Qdrant's local mode (`":memory:"` or `path="/local/db"`) is especially valuable — it enables unit testing without Docker and development without infrastructure, using the exact same API surface as production.

Weaviate's v3→v4 Python client migration renamed core concepts ("Class" → "Collection", "Schema" → "Configuration"), removed builder patterns, changed filter syntax, and altered return types. Planning for future breaking changes adds maintenance burden.

### 6. FormulaQuery for Structural Boosting (Qdrant v1.14+)

Beyond prefetch-level filtering, Qdrant v1.14 introduced `FormulaQuery` — a server-side score-boosting mechanism based on payload conditions. This enables boosting function/class definitions over comments or docstrings directly in the search query:

```python
results = client.query_points(
    collection_name="code",
    prefetch=[
        Prefetch(query=sparse_vector, using="bm25", limit=100),
        Prefetch(query=dense_vector, using="dense", limit=100),
    ],
    query=FormulaQuery(
        formula={
            "sum": [
                "$score",
                {"mult": [0.3, {"key": "chunk_type", "match": {"any": ["method", "function"]}}]},
                {"mult": [0.1, {"key": "chunk_type", "match": {"any": ["class"]}}]},
            ]
        }
    ),
    limit=10,
)
```

Neither Weaviate nor Milvus has an equivalent server-side score-boosting mechanism based on metadata. This feature was not available when ADR-001 was originally written (2026-02-05) and strengthens the case for Qdrant.

### 7. Schema Flexibility

**Qdrant:** Schemaless JSON payloads. Add new fields freely at any time. Payload indexes are created independently (no schema migration). Only changing vector dimensions requires collection recreation.

**Weaviate:** Typed schema with immutable constraints. Cannot delete properties, cannot change property data types, cannot change vectorizer after creation. All require collection recreation and full data migration ([GitHub Issue #843](https://github.com/weaviate/weaviate/issues/843), open since 2019).

**Milvus:** Schema defined at collection creation. Adding fields requires schema modification with limitations.

Our metadata schema evolves across versions (V1 → V1.1 adds `nl_description`, V2 adds `imports`, `references`, `last_modified`). Qdrant's schemaless payloads accommodate this without migration. Weaviate would require collection recreation for each schema change.

### 8. Quantization for Memory Reduction

At 500K chunks with 1024-dim vectors, raw vector storage is ~2 GB. All three databases support quantization:

| Method | Qdrant | Weaviate | Compression |
|---|---|---|---|
| Scalar (int8) | Yes | No | 4x |
| Product quantization | Yes | Yes (PQ) | Up to 64x |
| Binary quantization | Yes | Yes (BQ) | 32x |
| 1.5-bit / 2-bit | Yes (v1.15+) | No | 16-24x |
| Asymmetric quantization | Yes (v1.15+) | No | Varies |

Qdrant provides the widest range of quantization options. For code search, scalar quantization (int8, 4x compression) is the recommended default — it reduces 500K vectors from ~2 GB to ~500 MB with ~0.99 recall accuracy.

## Consequences

### Positive

- Simpler Docker Compose configuration (1 service vs 3 for Milvus, parity with Weaviate)
- Lower, more predictable resource consumption than both alternatives
- Native multi-stage prefetch enables our structural boosting design without client-side orchestration
- Filterable HNSW (`payload_m`) pre-builds connected subgraphs for our always-filtered fields
- FormulaQuery enables server-side score boosting by chunk_type
- Server-side IDF for sparse vectors enables incremental BM25 without client-side corpus statistics
- Schemaless payloads accommodate our evolving metadata schema (V1 → V1.1 → V2)
- Local mode (`":memory:"`) eliminates Docker dependency for unit tests
- Smaller attack surface (fewer exposed services than Milvus)

### Negative

- Cannot reuse claude-context's Milvus-based indexer — we build our own
- Qdrant's ecosystem is smaller than Weaviate's (~20K stars vs ~15.5K) and much smaller than Milvus/Zilliz's (~33K stars)
- Must generate sparse vectors externally (no built-in BM25 tokenization like Weaviate) — mitigated by our need for custom code tokenization regardless
- No search quality explainability API (no `_explain` endpoint) — must instrument our own relevance metrics
- RRF defaults to k=2 (paper recommends k=60) — must configure explicitly
- If we later need distributed deployment, Milvus has more mature sharding

### Mitigated

- "Build our own" is acceptable because we need Python, Voyage AI, and project-specific features regardless (see [ADR-002](./002-build-vs-adopt-claude-context.md))
- Qdrant Cloud exists as a managed option if self-hosted becomes a burden
- Custom code tokenization is required regardless of database choice — Weaviate's built-in BM25 tokenizers don't understand code identifiers
- Relevance tuning will use our 30 evaluation test queries ([DESIGN.md §15](../DESIGN.md#15-evaluation-test-queries)) with instrumented scoring

## Configuration Notes

Based on this evaluation, the following Qdrant-specific configuration choices should be applied at collection creation:

```python
client.create_collection(
    collection_name="code",
    vectors_config={
        "dense": VectorParams(size=1024, distance=Distance.COSINE)
    },
    sparse_vectors_config={
        "bm25": SparseVectorParams(modifier=Modifier.IDF)
    },
    hnsw_config=HnswConfigDiff(
        m=16,
        payload_m=16,     # Filter-aware HNSW edges for project/language/chunk_type
        ef_construct=128,
    ),
)

# Create payload indexes for filtered search
for field in ["chunk_type", "app_name", "layer", "is_test", "language"]:
    client.create_payload_index(
        collection_name="code",
        field_name=field,
        field_schema=PayloadSchemaType.KEYWORD,
    )
```

And at query time, override the RRF k parameter:

```python
query=FusionQuery(fusion=Fusion.RRF)  # Configure k=60 when available via API
```

## Alternatives Considered

### Weaviate

Weaviate was the strongest alternative. Its built-in BM25F with per-property tokenization and single-call `hybrid()` API provide a simpler path to hybrid search for natural language document search. However, for code search specifically:

1. **No prefetch mechanism** — Cannot implement our structural boosting design without client-side multi-query orchestration
2. **BM25 tokenizers don't understand code** — No camelCase splitting, no snake_case handling, no code-aware tokenizer available
3. **No filterable HNSW** — Relies entirely on query-time ACORN; no index-time payload-aware graph edges
4. **Unpredictable Go memory** — ~2.5 GB idle, `MADV_FREE` confusing Docker memory limits on developer laptops
5. **Schema rigidity** — Cannot delete properties or change types without collection recreation
6. **Python client instability** — v3→v4 was a complete breaking rewrite; future breakage expected

Weaviate would be a better choice for a system that: (a) searches natural language documents (not code), (b) doesn't need multi-stage structural boosting, (c) has dedicated server infrastructure (not developer laptops), and (d) values built-in BM25 convenience over custom tokenization control.

### Milvus

Milvus was evaluated during the claude-context analysis ([ADR-002](./002-build-vs-adopt-claude-context.md)). It was rejected due to:

1. **Deployment complexity** — 3 containers (milvus + etcd + minio) vs 1
2. **No server-side fusion** — Dense and sparse search results must be fused in application code
3. **Higher resource footprint** — ~500 MB+ baseline memory, ~2 GB+ Docker image
4. **No filtered prefetch** — Cannot filter within prefetch stages

Milvus would be a better choice for a system that: (a) operates at billion-vector scale, (b) needs mature distributed sharding, (c) has dedicated cluster infrastructure, and (d) has an operations team to manage multi-service deployments.

### Elasticsearch / OpenSearch

Not formally evaluated but worth noting: Elasticsearch has decades of investment in text analysis (custom tokenizers, stemming, code-specific analyzers) and now supports dense vector search. However, its resource footprint (JVM-based, ~1-2 GB baseline) and operational complexity (cluster management, shard configuration) make it unsuitable for a lightweight developer laptop tool. If search quality explainability becomes critical (the `_explain` API), Elasticsearch could be considered as a complement to Qdrant for the BM25 component.

### Purpose-Built Code Search (Zoekt, Sourcegraph)

Zoekt and Sourcegraph provide sub-second exact code search (trigram, regex, symbol navigation) but do not support semantic/vector search. Our system specifically targets natural language queries ("how do we handle expired prescriptions") that these tools cannot answer. If exact code search is later needed alongside semantic search, Zoekt could be added as a complement — but it does not replace the need for a vector database.
