# Index-Time Enrichment Design

**Goal:** Improve clew's search accuracy from 0.63/3.0 to ≥1.8/3.0 by enriching what gets indexed, while maintaining the existing 80-95% context reduction (efficiency 3.0/3.0).

**Architecture:** Multi-vector Qdrant schema (signature, semantic, body) with a two-pass indexing pipeline. Pass 1 builds a basic index from AST and relationships alone (no LLM). Pass 2 enriches chunks with LLM-generated descriptions and keywords, then re-embeds into the full multi-vector schema. Search uses query-adaptive vector selection with confidence-based fallback.

---

## Context

Clew's viability test against the Evvy Django codebase scored 1.72/3.0 (NOT VIABLE). Efficiency was 3.0/3.0 (excellent) but accuracy was 0.63/3.0 (catastrophically low). The tool is "efficiently wrong."

Industry research (Greptile, GitHub Copilot, Sourcegraph) converges on one conclusion: the biggest accuracy gains in code search come from improving what you INDEX, not how you QUERY. Greptile's recursive docstring generation achieves 12% cosine similarity improvement. GitHub's custom embedding model achieved 37.6% retrieval improvement.

Clew already has NL description generation (V1.1) but it's opt-in, shallow (1-2 sentences), and doesn't include relationship data. This design makes enrichment comprehensive, default, and multi-vector.

## Goals

1. Improve search accuracy from 0.63/3.0 to ≥1.8/3.0
2. Maintain the existing 80-95% context reduction (efficiency 3.0)
3. Work across codebases (Python, TypeScript, etc.) without language-specific tooling
4. Progressive quality: basic index works without LLM, enrichment enhances it
5. Support both API key users and Claude Max subscription users

## Non-Goals

- Query-time reformulation (deferred to future phase)
- Replacing Voyage Code-3 with a custom embedding model
- Real-time index updates (batch indexing is fine)

---

## Qdrant Collection Schema

Breaking change — existing indexes require `clew index --full` after upgrade.

Current schema:
```python
vectors={
    "dense": 1024 dims (Voyage Code-3),
    "bm25": sparse vector
}
```

New schema:
```python
vectors={
    "signature": 1024 dims,   # name + signature + file_path + layer + app
    "semantic": 1024 dims,    # NL description + keywords + callers + calls + imports
    "body": 1024 dims,        # raw code (unchanged from current "dense")
    "bm25": sparse vector     # enriched text (all context concatenated)
}
```

Storage impact: 3x dense vectors per chunk. For Evvy (~2600 chunks): ~30MB dense, ~7.5MB with scalar quantization. Trivially small even at 50K chunks.

---

## Enrichment Schema: What Goes Into Each Vector

### "signature" vector text

```
backend/ecomm/utils.py::_process_shopify_order_impl
def _process_shopify_order_impl(order_data: dict, processing_monitor: ProcessingMonitor) -> Order
class: (module-level function)
app: ecomm
layer: service
```

All deterministic — no LLM needed. Assembled from AST parser output + metadata.

### "semantic" vector text

```
[File]: backend/ecomm/utils.py
[Layer]: service
[App]: ecomm
[Description]: Processes incoming Shopify webhook payloads to create or update
orders, trigger prescription fill creation, and coordinate downstream fulfillment
including payment capture and notification dispatch.
[Keywords]: shopify webhook order processing ecommerce fulfillment prescription
fill payment capture notification
[Callers]: webhook_receiver, process_shopify_order, retry_failed_order_task
[Calls]: mark_order_cart_as_purchased, process_shopify_order_for_treatment_refill,
send_ungated_rx_order_paid_event, validate_order_payload
[Imports]: django.db.transaction, ecomm.models.Order, care.models.PrescriptionFill
```

The LLM generates only 2 fields: **Description** (2-3 sentences) and **Keywords** (8-15 terms). Everything else is deterministic from AST/relationships.

### "body" vector text

Raw code, unchanged from current behavior.

### "bm25" sparse vector text

Concatenation of semantic vector text + raw code. This ensures keyword searches match against all context (identifiers, descriptions, relationships, code).

---

## LLM Enrichment Prompt

The enrichment prompt provides structural context to the LLM so it can generate better descriptions and keywords:

```
Generate a description and search keywords for this code entity.

Entity: {name}
Type: {entity_type}
File: {file_path} ({layer} layer, {app_name} app)
Called by: {callers_comma_separated}
Calls: {callees_comma_separated}
Imports: {imports_comma_separated}

```{language}
{code}
```

Respond in exactly this format:
Description: <2-3 sentences: what it does, why it exists, what domain concept it represents>
Keywords: <8-15 space-separated terms a developer might search for>
```

The prompt gives the LLM relationship context it didn't have before (V1.1 only showed the code). This enables keywords like "webhook," "fulfillment," "payment capture" that the raw code alone might not suggest.

---

## Model Strategy

Tiered by operation type:

| Operation | Model | When | Cost (2600 chunks) |
|-----------|-------|------|---------------------|
| `clew index --full` | Opus 4.6 | Initial index, rare full re-indexes | ~$13 |
| `clew index` (incremental) | Sonnet 4.5 | Code changes, new files | ~$5.20 |
| Configurable | User's choice | Always | Varies |

Configuration via environment variable: `CLEW_DESCRIPTION_MODEL=claude-opus-4-6`

The existing `AnthropicDescriptionProvider` already accepts a `model` parameter. The `--full` flag sets the model to Opus; incremental indexing defaults to Sonnet. Users can override via env var.

---

## Pipeline Architecture: Two-Pass with Progressive Quality

### Pass 1: Basic Index (no LLM required)

```
clew index --full /path
  1. Discover files (git-aware, .clewignore/.codesearchignore)
  2. Chunk files (AST parse via tree-sitter) → CodeEntity objects
  3. Extract relationships (tree-sitter extractors) → SQLite cache
  4. Normalize relationship targets → resolve module-qualified names
  5. Compute importance scores (SQL edge count) → SQLite cache
  6. Embed raw code → single "body" vector + basic BM25
  7. Upsert to Qdrant

Result: functional index with basic search quality. Usable immediately.
No API key or LLM access required.
```

### Pass 2: Enrichment (LLM required)

```
/clew-enrich (Claude Code skill) OR clew index --nl-descriptions (API path)
  1. Read chunks from SQLite cache
  2. Read relationships from SQLite cache (populated in Pass 1)
  3. Read importance scores from cache
  4. Generate descriptions + keywords via LLM (Opus/Sonnet)
  5. Write enrichment data back to SQLite cache
  6. Assemble 3 embedding texts per chunk:
     a. "signature" text = name + signature + file_path + layer + app
     b. "semantic" text = description + keywords + callers + calls + imports + file + layer
     c. "body" text = raw code (unchanged)
  7. Embed all 3 → 3 named vectors + enriched BM25
  8. Upsert to Qdrant (overwrites Pass 1 points via deterministic UUIDs)

Result: fully enriched multi-vector index. Best quality.
```

### Why Two-Pass Works

The embedding model (Voyage Code-3) is stateless — it produces identical vectors regardless of when it's called. Relationship data persists in SQLite between passes. Qdrant point IDs are deterministic UUIDs from `chunk_id` (pipeline.py:558), so Pass 2 upserts cleanly overwrite Pass 1 points.

This gives progressive quality: basic index to enriched index, with no wasted work.

---

## Integration Model

### Path A: API Key (CI/CD, enterprises, headless)
```bash
export ANTHROPIC_API_KEY=sk-...
clew index --full /path              # Pass 1: basic index
clew index --nl-descriptions /path   # Pass 2: enrich + re-embed
```

### Path B: Claude Code Skill (Max subscribers, interactive)
```
clew index --full /path    # Pass 1: basic index (run in terminal)
/clew-enrich               # Pass 2: Claude Code skill uses host LLM
```

The `/clew-enrich` skill:
1. Runs inside the Claude Code conversation
2. Reads un-enriched chunks from clew's SQLite cache
3. Uses the host LLM (whatever model Claude Code is running — Opus on Max, etc.)
4. Writes descriptions + keywords back to cache
5. Triggers `clew reembed` to re-embed with enriched content

### Path C: Future — Local Models (Ollama)
```bash
export CLEW_DESCRIPTION_PROVIDER=ollama
export CLEW_OLLAMA_MODEL=qwen2.5-coder:32b
clew index --full --nl-descriptions /path
```

Lower quality than Opus/Sonnet, but works offline with no API costs.

---

## Search Pipeline Changes

### Query-Adaptive Vector Selection

The intent classifier (intent.py) routes queries to the optimal named vector:

| Intent | Primary Vector | BM25 Limit | Rationale |
|--------|----------------|------------|-----------|
| LOCATION (bare identifier) | "signature" | 50 | Name matching is BM25's strength |
| CODE (NL about code) | "semantic" | 30 | Description/keyword matching |
| DEBUG (error-related) | "semantic" | 30 | Description/keyword matching |
| DOCS (documentation) | "semantic" | 30 | Description/keyword matching |

Fast path: 1 dense query (primary vector) + 1 BM25 query. Same latency as today.

### Confidence-Based Fallback

After the fast path, check the top-1 similarity score:

```
If top_score >= 0.65 → return results (fast path complete)
If top_score < 0.65  → expand to ALL 3 vectors:
    - "signature" limit=20
    - "semantic" limit=20
    - "body" limit=20
    - "bm25" limit=30
  Merge results, take max score per chunk_id, re-rank
```

The threshold (0.65) is a tunable configuration parameter. Calibrate against the viability test suite after implementation. The slow path adds ~200ms (2 extra Qdrant queries).

Confidence is assessed by clew internally — the agent always receives the best results in one tool call. The agent never needs to evaluate result quality and re-query.

### Code Changes

**hybrid.py** — `_build_prefetches`:
```python
def _build_prefetches(self, intent, dense_vector, sparse_vector):
    primary_vector = {
        QueryIntent.LOCATION: "signature",
        QueryIntent.CODE: "semantic",
        QueryIntent.DEBUG: "semantic",
        QueryIntent.DOCS: "semantic",
    }.get(intent, "semantic")

    bm25_limit = 50 if intent == QueryIntent.LOCATION else 30

    return [
        models.Prefetch(query=dense_vector, using=primary_vector, limit=30),
        models.Prefetch(query=sparse_vector, using="bm25", limit=bm25_limit),
    ]
```

**hybrid.py** — new `_expand_search` for confidence fallback:
```python
def _expand_search(self, dense_vector, sparse_vector, primary_results):
    """Fan out to all vectors when primary confidence is low."""
    all_prefetches = [
        models.Prefetch(query=dense_vector, using="signature", limit=20),
        models.Prefetch(query=dense_vector, using="semantic", limit=20),
        models.Prefetch(query=dense_vector, using="body", limit=20),
        models.Prefetch(query=sparse_vector, using="bm25", limit=30),
    ]
    # Query, merge with primary results, take max score per chunk_id
    ...
```

---

## Drop-In Improvements

### miniCOIL as Optional BM25 Replacement

miniCOIL is a learned sparse retrieval model from Qdrant's team. Unlike BM25 which treats every occurrence of "model" the same, miniCOIL produces 4-dimensional per-word vectors that capture word meaning in context.

Integration via Qdrant's FastEmbed:
```python
# Current BM25 (tokenize.py)
sparse = text_to_sparse_vector(chunk.content)

# miniCOIL (drop-in replacement)
from fastembed import SparseTextEmbedding
model = SparseTextEmbedding("Qdrant/minicoil-v1")
sparse = model.embed(chunk.content)
```

Same sparse vector format, same Qdrant storage. No schema change needed.

Risk: miniCOIL is trained on English text, not code. May perform worse on identifier matching. Benchmark against viability suite before making default.

Configuration: `CLEW_SPARSE_MODEL=minicoil` (default: `bm25`).

### File Summary Chunks

Synthetic "file overview" chunk — one per file, containing all function/class signatures aggregated. Helps broad queries find the right FILE before drilling into functions.

Integrated into Pass 1 of the pipeline (no LLM needed — just signature aggregation).

---

## Potential Future Improvements

### Dynamic Confidence Threshold

The static 0.65 confidence threshold could be replaced with a score-gap heuristic: if the difference between top-1 and top-2 scores is small (< 0.05), confidence is low regardless of absolute score. This captures "I found two things that look equally good" which is a stronger signal than absolute score. Deferred because the static threshold is sufficient to ship and the score-gap approach requires calibration data.

### Query Reformulation with HyDE

HyDE (Hypothetical Document Embeddings) generates a hypothetical code snippet from the query, embeds it, and searches for similar real documents. Academic results show 10-20% accuracy improvement on natural language code queries.

Implementation: Use Haiku 4.5 (~$1/1K queries, ~150ms latency) to generate a hypothetical code snippet. Only fire for natural language queries (not identifiers/file paths). Use the intent classifier to decide. Only invoke when initial retrieval confidence is low ("retry with HyDE" pattern).

Deferred to a future phase. The index-time enrichment is expected to capture most of the same benefit at zero query-time cost.

### ColBERT / Late Interaction Models

ColBERT represents chunks as multiple token-level vectors (not single pooled vectors). Each query token matches its best document token independently, then scores are summed. Qdrant supports this natively via multivector fields (since Qdrant 1.10).

Qdrant's testing shows +8% NDCG@10 using the same embedding model with late interaction vs single-vector. Storage cost: 3-5x per chunk (mitigated by scalar quantization).

Deferred because multi-vector named vectors (signature/semantic/body) capture much of the same benefit with less storage overhead. ColBERT would be an additional layer on top.

### Weaviate-Style Query Agent

A full LLM-powered query planning agent that translates natural language into structured retrieval operations (filter selection, collection routing, aggregations). Weaviate's implementation has ~14 second latency — unusable for interactive search. Could be valuable for batch analysis or complex multi-step queries in a future "deep search" mode. Deferred indefinitely.

### Local Model Support (Ollama)

Add an `OllamaDescriptionProvider` that calls a local model (Qwen 2.5 Coder, Llama 3, etc.) for enrichment generation. Enables fully offline indexing with no API costs. Quality would be lower than Opus/Sonnet but better than no enrichment. Implementation: new provider class following the existing `DescriptionProvider` ABC pattern.

### Auto-Generated Synonym Tables

During indexing, auto-generate synonym tables from the codebase: extract variable names to type names, build co-occurrence graphs from import statements, map abbreviations to full names. Store as searchable metadata in Qdrant. Replaces the current manual YAML-based synonym expansion with codebase-specific terminology. Zero query-time cost (index-time only).

### Embedding-Time Search Keywords

Use Haiku 4.5 at index time to generate 5-10 additional search keywords per chunk (beyond the Description + Keywords from the enrichment prompt). Store as a separate payload field. Match with BM25 at query time. Similar to synonym expansion but more targeted and LLM-generated.

---

## Implementation Order

### Phase 1: Core Enrichment (this plan)
1. Update Qdrant collection schema (3 named vectors + BM25)
2. Implement enrichment prompt with relationship context
3. Implement two-pass pipeline (basic index, enrich, reembed)
4. Update search pipeline for query-adaptive vector selection
5. Add confidence-based fallback
6. Add file summary chunks
7. Create `/clew-enrich` Claude Code skill
8. Re-index Evvy, re-run 16-test viability suite

### Phase 2: Drop-In Improvements
9. Benchmark miniCOIL vs BM25 on viability suite
10. If miniCOIL wins, add as optional sparse model

### Phase 3: Query-Time Enhancements (deferred)
11. HyDE with Haiku 4.5 for NL queries
12. Dynamic confidence threshold (score-gap heuristic)

### Phase 4: Advanced (deferred)
13. ColBERT late interaction
14. Local model support (Ollama)
15. Auto-generated synonym tables

---

## Key Files to Modify

| File | Changes |
|------|---------|
| `clew/clients/qdrant.py` | Update collection creation for 3 named vectors |
| `clew/clients/description.py` | Update prompt with relationship context; add Keywords output parsing |
| `clew/indexer/pipeline.py` | Two-pass support; assemble 3 embedding texts; reembed command |
| `clew/search/hybrid.py` | Query-adaptive vector selection; confidence fallback; expand_search |
| `clew/search/engine.py` | Integrate confidence check; importance boost |
| `clew/search/intent.py` | Map intents to primary vectors |
| `clew/cli.py` | Add `clew reembed` command |
| `clew/config.py` | Add CLEW_DESCRIPTION_MODEL, CLEW_SPARSE_MODEL config |
| `clew/models.py` | Add enrichment-related config fields |
| `clew/mcp_server.py` | Update search to use named vectors |

---

## Success Criteria

1. Viability re-test overall average >= 2.0 (up from 1.72)
2. Accuracy dimension >= 1.5 (up from 0.63)
3. Completeness dimension >= 1.2 (up from 0.56)
4. Efficiency dimension maintained at >= 2.8
5. `clew index --full` works without any API key (basic quality)
6. `/clew-enrich` works for Claude Max subscribers
7. `clew index --nl-descriptions` works for API key users
8. Indexing time for Evvy (2600 chunks) under 15 minutes including enrichment

---

## References

- Viability test results: `/Users/albertgwo/Work/evvy/docs/plans/2026-02-11-clew-viability-results.md`
- Revised improvement plan: `~/.claude/plans/synthetic-doodling-kernighan.md`
- Plan review findings: `/Users/albertgwo/Repositories/clew/docs/plans/2026-02-12-plan-review-findings.md`
- [Greptile: Semantic Codebase Search](https://www.greptile.com/blog/semantic-codebase-search)
- [GitHub Custom Embedding Model](https://www.infoq.com/news/2025/10/github-embedding-model/)
- [miniCOIL](https://qdrant.tech/articles/minicoil/)
- [ColBERT in Qdrant](https://qdrant.tech/articles/late-interaction-models/)
- [HyDE Paper](https://arxiv.org/abs/2212.10496)
- [Qdrant Code Search Tutorial](https://qdrant.tech/documentation/advanced-tutorials/code-search/)
- [Weaviate Query Agent](https://weaviate.io/blog/query-agent)
