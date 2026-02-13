# V2 Consolidated Implementation Plan

**Goal:** Transform clew from "efficiently wrong" (1.72/3.0, NOT VIABLE) to a viable code intelligence platform (target: >=2.3/3.0) by combining search pipeline bug fixes with multi-vector index-time enrichment.

**Working directory:** `/Users/albertgwo/Repositories/clew`
**Test codebase:** `/Users/albertgwo/Work/evvy`

---

## BREAKING CHANGE

**Vector schema migration:** Existing Qdrant collections must be recreated with `clew index --full` after upgrading. The dense vector field name changes from `"dense"` to three named vectors (`"signature"`, `"semantic"`, `"body"`). Attempting to use an old index with the new code will fail. This is a one-time migration.

---

## Architecture Overview

Two parallel agents (Pipeline + Search) implement changes independently, followed by an Integration agent and a Validation agent. File ownership is strict — no two agents touch the same file.

```
Phase 1 (parallel)          Phase 2            Phase 3
┌──────────────┐
│  AGENT-PIPE  │──┐
│  Pipeline +  │  │     ┌───────────┐     ┌──────────────┐
│  Indexing    │  ├────▶│ AGENT-INT │────▶│  AGENT-VAL   │
│              │  │     │Integration│     │  Validation  │
└──────────────┘  │     └───────────┘     └──────────────┘
┌──────────────┐  │
│ AGENT-SEARCH │──┘
│  Search +    │
│  Ranking     │
└──────────────┘
```

---

## Shared Interfaces (Read Before Coding)

These contracts allow AGENT-PIPE and AGENT-SEARCH to code independently.

### 1. Qdrant Named Vectors

Collection schema changes from:
```python
vectors={"dense": VectorParams(size=1024, distance=Cosine)}
sparse_vectors={"bm25": SparseVectorParams()}
```
To:
```python
vectors={
    "signature": VectorParams(size=1024, distance=Cosine),
    "semantic": VectorParams(size=1024, distance=Cosine),
    "body": VectorParams(size=1024, distance=Cosine),
}
sparse_vectors={"bm25": SparseVectorParams()}
```

Both agents reference vectors by these exact string names.

### 2. SearchResult.importance_score

AGENT-PIPE stores `importance_score: float` (0.0-1.0) in Qdrant payload.
AGENT-SEARCH reads it from payload and adds it to `SearchResult`.

```python
# search/models.py — AGENT-SEARCH adds this field
@dataclass
class SearchResult:
    ...
    importance_score: float = 0.0
```

### 3. Payload Fields

AGENT-PIPE writes these payload fields per point:
```python
{
    "importance_score": 0.0-1.0,    # NEW — inbound edge count normalized
    "enriched": True/False,         # NEW — metadata flag, whether Pass 2 ran
    "description": "...",           # NEW — LLM-generated (Pass 2 only)
    "keywords": "...",              # NEW — LLM-generated (Pass 2 only)
    # ... existing fields unchanged
}
```

The `enriched` field is **metadata-only**. The search pipeline does not filter by it. It exists so `clew status` can report enrichment coverage (e.g., "423/2600 chunks enriched").

### 4. Intent-to-Vector Mapping

AGENT-SEARCH implements this routing:
```python
INTENT_VECTOR_MAP = {
    QueryIntent.LOCATION: "signature",
    QueryIntent.CODE: "semantic",
    QueryIntent.DEBUG: "semantic",
    QueryIntent.DOCS: "semantic",
}
```

### 5. Config Fields

AGENT-PIPE adds to `config.py`:
```python
CLEW_DESCRIPTION_MODEL: str = os.environ.get("CLEW_DESCRIPTION_MODEL", "claude-sonnet-4-5-20250929")
CLEW_FULL_INDEX_MODEL: str = os.environ.get("CLEW_FULL_INDEX_MODEL", "claude-opus-4-6")
CLEW_CONFIDENCE_THRESHOLD: float = float(os.environ.get("CLEW_CONFIDENCE_THRESHOLD", "0.65"))
```

### 6. Model Selection Logic

When `--full` flag is passed, use `CLEW_FULL_INDEX_MODEL` (defaults to Opus 4.6).
For incremental indexing (no `--full`), use `CLEW_DESCRIPTION_MODEL` (defaults to Sonnet 4.5).
Users can override either via env var.

```python
# In pipeline.py or cli.py:
if full_reindex:
    model = env.CLEW_FULL_INDEX_MODEL  # "claude-opus-4-6"
else:
    model = env.CLEW_DESCRIPTION_MODEL  # "claude-sonnet-4-5-20250929"
```

### 7. Pass 1 Vector Population

In Pass 1 (no LLM), vectors are populated as follows:
- **"signature"**: Always populated (deterministic from AST)
- **"semantic"**: Populated with a **stub** — same content as signature text + any available relationship data (callers/calls/imports from extractors). No description or keywords. This ensures CODE/DEBUG/DOCS queries return results even before enrichment, just at lower quality.
- **"body"**: Always populated (raw code)
- **"bm25"**: Sparse vector from raw code only

In Pass 2 (LLM enrichment), ALL vectors are re-embedded with full content. The semantic vector gets the full enriched text (description + keywords + relationships).

### 8. BM25 Text Composition

- **Pass 1:** BM25 sparse vector uses raw code only: `text_to_sparse_vector(chunk.content)`
- **Pass 2:** BM25 sparse vector uses **semantic text + raw code concatenated**: `text_to_sparse_vector(semantic_text + "\n" + chunk.content)`. This ensures keyword searches match against descriptions, keywords, relationship names, AND code identifiers.

---

## AGENT-PIPE: Pipeline + Indexing

**Owns:** All indexing, caching, embedding, extraction, CLI, config, and description provider changes.

**Files touched:**
| File | Changes |
|------|---------|
| `clew/clients/qdrant.py` | 3 named vectors schema (lines 46-71) |
| `clew/indexer/cache.py` | Enrichment tables, `get_all_relationship_pairs()`, schema v3 (lines 18-53, 106, 120-123, 208-233) |
| `clew/indexer/pipeline.py` | Two-pass pipeline, file summaries, importance storage, 3 embedding texts |
| `clew/indexer/extractors/django_models.py` | NEW — Django FK/M2M/O2O extractor |
| `clew/indexer/importance.py` | NEW — SQL edge count importance scoring |
| `clew/indexer/ignore.py` | `.codesearchignore` fallback (lines 51-54) |
| `clew/clients/description.py` | Enrichment prompt with relationship context, Keywords parsing |
| `clew/cli.py` | `clew reembed` command (line 54 ensure_collection call) |
| `clew/config.py` | CLEW_DESCRIPTION_MODEL, CLEW_FULL_INDEX_MODEL (lines 36-53) |
| `clew/models.py` | Enrichment config fields |

**Execution order:**

### P1. Qdrant Schema Migration
**File:** `clew/clients/qdrant.py:46-71`
**Depends on:** nothing

Update `ensure_collection()` to create 3 named dense vectors instead of 1:

```python
def ensure_collection(self, name: str, dense_dim: int = 1024) -> None:
    # Replace single "dense" vector with 3 named vectors
    vectors_config = {
        "signature": models.VectorParams(size=dense_dim, distance=models.Distance.COSINE),
        "semantic": models.VectorParams(size=dense_dim, distance=models.Distance.COSINE),
        "body": models.VectorParams(size=dense_dim, distance=models.Distance.COSINE),
    }
    sparse_vectors_config = {
        "bm25": models.SparseVectorParams(),
    }
    ...
```

Also update any `_upsert` or `_query` methods that reference `"dense"` — change to the appropriate named vector.

Update `delete_by_file_path()`, `hybrid_query()`, and any method that uses vector names.

**Tests:** Update `tests/unit/test_qdrant.py` — all tests referencing `"dense"` must use the new names.

### P2. Cache Schema Updates
**File:** `clew/indexer/cache.py`
**Depends on:** nothing (parallel with P1)

1. Increment `CURRENT_SCHEMA_VERSION` from 2 to 3 (line 106)
2. Add migration to `_MIGRATIONS` (lines 120-123)
3. Add `enrichment_cache` table to schema:
```sql
CREATE TABLE IF NOT EXISTS enrichment_cache (
    chunk_id TEXT PRIMARY KEY,
    description TEXT,
    keywords TEXT,
    enriched_at REAL
);
```
4. Add public method:
```python
def get_all_relationship_pairs(self) -> list[tuple[str, str]]:
    """Return all (source_entity, target_entity) pairs from code_relationships."""
    with self._connect() as conn:
        return conn.execute(
            "SELECT source_entity, target_entity FROM code_relationships"
        ).fetchall()
```
5. Add enrichment cache methods:
```python
def get_enrichment(self, chunk_id: str) -> tuple[str, str] | None:
    """Return (description, keywords) for a chunk, or None."""

def set_enrichment(self, chunk_id: str, description: str, keywords: str) -> None:
    """Store enrichment data for a chunk."""
```

**Tests:** `tests/unit/test_cache.py` — test migration, enrichment CRUD, relationship pairs query.

### P3. Config + Model Updates
**Files:** `clew/config.py:36-53`, `clew/models.py`
**Depends on:** nothing (parallel with P1, P2)

Add to `Environment` class:
```python
CLEW_DESCRIPTION_MODEL: str = os.environ.get("CLEW_DESCRIPTION_MODEL", "claude-sonnet-4-5-20250929")
CLEW_FULL_INDEX_MODEL: str = os.environ.get("CLEW_FULL_INDEX_MODEL", "claude-opus-4-6")
```

Add enrichment-related config fields to `models.py` if needed (e.g., confidence threshold).

### P4. Django Model Field Extractor
**File:** `clew/indexer/extractors/django_models.py` (NEW)
**Depends on:** nothing (parallel with P1-P3)

```python
RELATIONSHIP_FIELDS = {
    "ForeignKey": "has_fk",
    "OneToOneField": "has_o2o",
    "ManyToManyField": "has_m2m",
}

class DjangoModelFieldExtractor(RelationshipExtractor):
    def extract(self, tree, source, file_path):
        # Walk AST for class definitions inheriting from models.Model
        # Extract FK/M2M/O2O field calls
        # Map first positional arg to target model name
        # GUARD: ForeignKey("self") → replace with enclosing class_name
```

Register in `pipeline.py` `_extract_relationships` — add to the extractor list (2-line change, no conflict with pipeline rewrite since it's just appending to a list).

**Tests:** `tests/unit/test_django_model_extractor.py`
- ForeignKey extraction
- ManyToManyField extraction
- OneToOneField extraction
- ForeignKey("self") resolves to enclosing class name
- Non-model classes are ignored

### P5. Ignore Pattern Fix
**File:** `clew/indexer/ignore.py:51-54`
**Depends on:** nothing (parallel with everything)

```python
clewignore = self.project_root / ".clewignore"
codesearchignore = self.project_root / ".codesearchignore"
if clewignore.exists():
    all_patterns.extend(self._read_pattern_file(clewignore))
elif codesearchignore.exists():
    all_patterns.extend(self._read_pattern_file(codesearchignore))
```

`elif` ensures no double-loading. `.clewignore` takes priority.

**Tests:** Add to `tests/unit/test_ignore.py`.

### P5b. Importance Scoring Module
**File:** `clew/indexer/importance.py` (NEW)
**Depends on:** nothing (parallel with P1-P5)

This module lives in `clew/indexer/` (NOT `clew/search/`) because it runs at index time. AGENT-SEARCH reads the pre-computed score from Qdrant payload — it never calls this module.

```python
def compute_importance_scores(relationship_pairs: list[tuple[str, str]]) -> dict[str, float]:
    """Compute file importance from inbound edge count.

    Returns dict mapping file_path -> importance_score (0.0-1.0).
    """
    inbound_counts: dict[str, int] = {}
    for _source, target in relationship_pairs:
        file_path = target.split("::")[0] if "::" in target else target
        inbound_counts[file_path] = inbound_counts.get(file_path, 0) + 1

    if not inbound_counts:
        return {}

    max_count = max(inbound_counts.values())
    return {path: count / max_count for path, count in inbound_counts.items()}
```

**Tests:** `tests/unit/test_importance.py`
- Files with many incoming edges get higher scores
- Scores bounded 0.0-1.0
- Empty graph returns empty dict

### P6. Enrichment Prompt + Description Provider
**File:** `clew/clients/description.py`
**Depends on:** P2 (needs enrichment cache schema)

Update `AnthropicDescriptionProvider` to:
1. Accept relationship context (callers, callees, imports) in the prompt
2. Generate Description + Keywords (not just description)
3. Parse structured output (Description: ..., Keywords: ...)
4. Accept `model` parameter from config (Opus for full, Sonnet for incremental)

New prompt:
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

**Tests:** Update `tests/unit/test_description.py` — test prompt includes relationship context, test Keywords parsing.

### P7. Two-Pass Pipeline
**File:** `clew/indexer/pipeline.py`
**Depends on:** P1 (schema), P2 (cache), P3 (config), P5b (importance), P6 (enrichment prompt)

This is the largest work item. Rewrite `_embed_and_upsert` (lines 493-574) to:

**Pass 1 (basic index, no LLM):**
1. For each chunk, assemble "signature" text: `{chunk_id}\n{signature}\nclass: {class_name}\napp: {app_name}\nlayer: {layer}`
2. "body" text: raw code (unchanged)
3. Embed signature + body → 2 of 3 named vectors
4. BM25 sparse vector from raw code
5. Upsert with `enriched=False` in payload
6. Store importance_score in payload (from SQL edge count)

**Pass 2 (enrichment, LLM required):**
1. Read chunks from SQLite cache
2. Read relationships from cache (callers, callees, imports per chunk)
3. Call enrichment prompt (P6) → get description + keywords
4. Store in enrichment_cache table
5. Assemble "semantic" text: `[File]: {path}\n[Layer]: {layer}\n[App]: {app}\n[Description]: {desc}\n[Keywords]: {keywords}\n[Callers]: ...\n[Calls]: ...\n[Imports]: ...`
6. Re-embed ALL 3 vectors (signature, semantic, body) + enriched BM25
7. Upsert (overwrites Pass 1 via deterministic UUIDs)
8. Set `enriched=True` in payload

**File summary chunks (in Pass 1):**
After chunking a file, generate a synthetic chunk:
- `chunk_type="file_summary"`, `entity_type="file_summary"`
- Content: file path + all function/class signatures + module docstring + import list
- Embed into all 3 vectors (signature text = file path + signatures, semantic = same as signature for unenriched, body = same)

**Importance scoring storage:**
After relationship extraction + normalization:
1. Call `cache.get_all_relationship_pairs()`
2. Count inbound edges per file → normalize to 0.0-1.0
3. Store as `importance_score` in Qdrant payload during upsert

**`clew reembed` CLI command:**
Add to `cli.py`:
```bash
clew reembed [PROJECT_ROOT]
```
Implementation:
1. Read all chunks from SQLite chunk cache
2. For each chunk that has enrichment data in `enrichment_cache` table:
   a. Assemble "signature" text (deterministic)
   b. Assemble "semantic" text (using cached description + keywords + relationships)
   c. "body" text = raw code
3. Embed all 3 vectors via Voyage Code-3
4. Assemble enriched BM25 sparse vector (semantic text + raw code)
5. Upsert to Qdrant with `enriched=True`
6. Skip chunks without enrichment data (leave their Pass 1 vectors intact)

This command is the final step of the `/clew-enrich` skill flow: the skill generates descriptions+keywords via the host LLM, writes to cache, then invokes `clew reembed` to embed and upsert.

### P8. Normalization Verification
**File:** `tests/unit/test_indexing_pipeline.py`
**Depends on:** nothing (parallel with everything)

Write regression tests verifying recent commits (37025b5, ca2595b) fixed normalization:
- `target_entity="ecomm.tasks::send_ungated_rx_order_paid_event"` resolves to `"backend/ecomm/tasks.py::send_ungated_rx_order_paid_event"`
- Dotted targets resolve correctly
- Multi-hop trace works when depth-1 targets are properly normalized

If tests PASS, this is a no-op. If tests FAIL, fix the normalization code.

---

## AGENT-SEARCH: Search + Ranking

**Owns:** All search pipeline, ranking, reranking, and intent changes. Reads importance scores from Qdrant payload (computed by AGENT-PIPE at index time).

**Files touched:**
| File | Changes |
|------|---------|
| `clew/search/hybrid.py` | Query-adaptive vectors, confidence fallback, remove DEBUG boost (lines 36-127) |
| `clew/search/engine.py` | Importance boost, confidence orchestration (lines 42-134) |
| `clew/search/rerank.py` | PascalCase fix (line 50) |
| `clew/search/intent.py` | `_BARE_IDENTIFIER_RE` fix, intent-to-vector mapping (lines 40-43) |
| `clew/search/models.py` | `importance_score` field (lines 18-36) |

Note: Importance scoring computation lives in `clew/indexer/importance.py` (AGENT-PIPE's territory). AGENT-SEARCH reads the pre-computed `importance_score` from Qdrant payload — no cross-boundary import needed.

**Execution order:**

### S1. SearchResult Model Update
**File:** `clew/search/models.py:18-36`
**Depends on:** nothing

Add `importance_score: float = 0.0` to the `SearchResult` dataclass.

### S2. PascalCase Rerank Fix
**File:** `clew/search/rerank.py:50`
**Depends on:** nothing

Remove or relax the PascalCase skip condition at line 50:
```python
# REMOVE this line:
if re.match(r"^[A-Z][a-zA-Z0-9]+$", query):
```

PascalCase queries (PrescriptionFill, Order, TimeStampedModel) should use Voyage reranking, not skip it. The reranker needs to evaluate whether the BM25 hit (serializer) is more relevant than the model definition.

**Tests:** `tests/unit/test_rerank.py` — verify PascalCase queries are NOT skipped.

### S3. _BARE_IDENTIFIER_RE Fix
**File:** `clew/search/intent.py:40-43`
**Depends on:** nothing

Current regex:
```python
_BARE_IDENTIFIER_RE = re.compile(
    r"^(?:[A-Z][a-zA-Z0-9]*(?:[A-Z][a-z0-9]*)*|[a-z][a-z0-9]*(?:_[a-z0-9]+)*)$"
)
```

The snake_case branch `[a-z][a-z0-9]*` requires first char `[a-z]`, rejecting `_process_shopify_order_impl`. Fix: change to `_?[a-z]`:
```python
_BARE_IDENTIFIER_RE = re.compile(
    r"^(?:[A-Z][a-zA-Z0-9]*(?:[A-Z][a-z0-9]*)*|_?[a-z][a-z0-9]*(?:_[a-z0-9]+)*)$"
)
```

**Tests:** `tests/unit/test_intent.py`
- `"_process_shopify_order_impl"` → LOCATION
- `"PrescriptionFill"` → LOCATION
- `"how does order processing work"` → not LOCATION

### S4. DEBUG Test-Boost Removal
**File:** `clew/search/hybrid.py:109-126`
**Depends on:** nothing

Remove the entire block that injects test-file boost prefetch for DEBUG intent. This actively boosts test files for debugging queries, undermining the test demotion.

**Tests:** `tests/unit/test_hybrid_search.py` — verify DEBUG intent does NOT produce test-boost prefetch.

### S5. Query-Adaptive Vector Selection
**File:** `clew/search/hybrid.py:71-127`
**Depends on:** S3, S4

Rewrite `_build_prefetches()` to use intent-to-vector mapping:

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

Also update `_point_to_result` (lines 130-149) to read `importance_score` from payload:
```python
importance_score=payload.get("importance_score", 0.0),
```

**Tests:** `tests/unit/test_hybrid_search.py`
- LOCATION intent uses "signature" vector with bm25_limit=50
- CODE/DEBUG/DOCS intent uses "semantic" vector with bm25_limit=30
- importance_score read from payload

### S6. Confidence-Based Fallback
**File:** `clew/search/hybrid.py`
**Depends on:** S5

Add `_expand_search()` method:

```python
async def _expand_search(self, dense_vector, sparse_vector, primary_results):
    """Fan out to all vectors when primary confidence is low."""
    all_prefetches = [
        models.Prefetch(query=dense_vector, using="signature", limit=20),
        models.Prefetch(query=dense_vector, using="semantic", limit=20),
        models.Prefetch(query=dense_vector, using="body", limit=20),
        models.Prefetch(query=sparse_vector, using="bm25", limit=30),
    ]
    # Query, merge with primary results, take max score per chunk_id, return
```

Update `search()` method to check confidence after initial query:
```python
if results and results[0].score < 0.65:  # configurable threshold
    results = await self._expand_search(dense_vector, sparse_vector, results)
```

**Tests:** `tests/unit/test_hybrid_search.py`
- Low-confidence results trigger expansion
- High-confidence results skip expansion
- Expansion merges and deduplicates by chunk_id

### S7. Importance Boost in Engine
**File:** `clew/search/engine.py:114-134`
**Depends on:** S1

Add `_apply_importance_boost()` after reranking, before test demotion:

```python
def _apply_importance_boost(self, results: list[SearchResult]) -> list[SearchResult]:
    for result in results:
        if result.importance_score > 0:
            boost = 1.0 + (result.importance_score * 0.25)  # 1.0x to 1.25x
            result.score *= boost
    return results
```

Update search pipeline flow: enhance → classify → hybrid → rerank → **importance_boost** → test_demotion → dedupe → limit

**Tests:** `tests/unit/test_search_engine.py`
- Importance boost range is 1.0x-1.25x
- Zero importance = no boost
- Boost applied before test demotion

---

## AGENT-INT: Integration

**Owns:** MCP server updates, Claude Code skill, cross-component wiring.

**Files touched:**
| File | Changes |
|------|---------|
| `clew/mcp_server.py` | Update search for named vectors (lines 62-151) |
| `.claude/skills/clew-enrich/SKILL.md` | NEW — `/clew-enrich` skill |

**Depends on:** AGENT-PIPE and AGENT-SEARCH both complete.

### I1. MCP Server Updates
**File:** `clew/mcp_server.py`

Update `_compact_result_to_dict()` and `_result_to_dict()` (lines 62-86) to include new payload fields if present (enriched, importance_score).

Verify that `search()` tool (lines 97-151) works with the new schema — it calls `search_engine.search()` which calls `hybrid.search()` which now uses named vectors. No direct changes needed since the vector routing is internal to hybrid.py, but verify the flow works.

### I2. /clew-enrich Claude Code Skill
**File:** `.claude/skills/clew-enrich/SKILL.md` (NEW)

Create a Claude Code skill that:
1. Reads un-enriched chunks from clew's SQLite cache
2. For each chunk, generates description + keywords using the host LLM
3. Writes results back to cache via `cache.set_enrichment()`
4. Triggers `clew reembed` to re-embed with enriched content

The skill runs inside the Claude Code conversation, using the host model (Opus on Max subscriptions).

---

## AGENT-VAL: Validation

**Depends on:** ALL agents complete.

### V1. Full Unit Test Suite
```bash
python -m pytest tests/ -v --tb=short
```
ALL tests must pass. No regressions.

### V2. Lint + Type Check
```bash
ruff check .
ruff format --check .
mypy clew/
```

### V3. Re-Index Evvy (Pass 1)
```bash
clew index --full /Users/albertgwo/Work/evvy
```
Verify:
- More chunks than previous 2592 (new file summaries + Django FK edges)
- Qdrant healthy
- Relationships populated (trace returns results)

### V4. Enrich Evvy (Pass 2)
```bash
clew index --nl-descriptions /Users/albertgwo/Work/evvy
```
Or use `/clew-enrich` if testing the skill path.

### V5. Spot Checks
```
clew trace "_process_shopify_order_impl" --direction outbound --depth 2
# Expected: depth-1 AND depth-2 results

clew trace "mark_order_cart_as_purchased" --direction inbound --depth 1
# Expected: >= 2 callers

clew search "_process_shopify_order_impl" --raw
# Expected: ecomm/utils.py as top result

clew search "PrescriptionFill" --raw
# Expected: care/models.py above serializers

clew search "how does order processing work" --raw
# Expected: ecomm/utils.py in top 3
```

### V6. Viability Re-Test
Execute the 16-test A/B suite from `/Users/albertgwo/Work/evvy/docs/plans/2026-02-11-clew-viability-test-plan.md`.
Write results to `/Users/albertgwo/Work/evvy/docs/plans/2026-02-12-clew-viability-v2-results.md`.

**Target scores:**
- Overall average: >= 2.3 (up from 1.72)
- Accuracy: >= 1.5 (up from 0.63)
- Completeness: >= 1.2 (up from 0.56)
- Efficiency: maintained >= 2.8

---

## Dependency Graph

```
AGENT-PIPE                          AGENT-SEARCH
──────────                          ────────────
P1  (Qdrant schema)     ──┐        S1 (SearchResult model)  ──┐
P2  (Cache schema)       ──┤        S2 (Rerank fix)          ──┤
P3  (Config/models)      ──┤        S3 (Regex fix)           ──┤
P4  (Django extractor)   ──┤        S4 (DEBUG boost removal) ──┤
P5  (Ignore fix)         ──┤                                    │
P5b (Importance module)  ──┤        S5 (Adaptive vectors)    ──┤
P8  (Normalization)      ──┤          depends on: S3, S4        │
    ↑ all parallel          │                                    │
                            │        S6 (Confidence fallback) ──┤
P6  (Enrichment prompt)  ──┤          depends on: S5            │
    depends on: P2          │                                    │
                            │        S7 (Importance boost)    ──┤
P7  (Two-pass pipeline)  ──┤          depends on: S1            │
    depends on: P1,P2,      │                                    │
    P3,P5b,P6               │                                    │
                            │                                    │
                            ▼                                    ▼
                    ┌─────────────────────────────────────────────┐
                    │  I1 (MCP updates)    depends on: P7, S7    │
                    │  I2 (/clew-enrich)   depends on: P7        │
                    └─────────────────────────────────────────────┘
                                         │
                                         ▼
                    ┌─────────────────────────────────────────────┐
                    │  V1-V6 (Validation)  depends on: ALL       │
                    └─────────────────────────────────────────────┘
```

**Maximum parallelism in Phase 1:**

AGENT-PIPE can run P1, P2, P3, P4, P5, P5b, P8 **all in parallel** (no inter-dependencies).
Then P6 (needs P2), then P7 (needs P1+P2+P3+P5b+P6).

AGENT-SEARCH can run S1, S2, S3, S4 **all in parallel**.
Then S5 (needs S3+S4), then S6 (needs S5), then S7 (needs S1).

AGENT-PIPE and AGENT-SEARCH run fully in parallel — no cross-boundary imports. Importance scoring is computed by AGENT-PIPE at index time (P5b) and stored in Qdrant payload. AGENT-SEARCH reads it from payload (S5/S7).

---

## Agent Assignments

### AGENT-PIPE Prompt

```
You are implementing pipeline and indexing changes for clew V2.
Working directory: /Users/albertgwo/Repositories/clew

Execute tasks P1 through P8 respecting dependencies. P1-P5, P5b, and P8 can
run in any order (no inter-dependencies). P6 depends on P2.
P7 depends on P1+P2+P3+P5b+P6.

Read CLAUDE.md and docs/plans/2026-02-12-v2-consolidated-implementation.md for
full context. Read each file before modifying it.

CRITICAL RULES:
- Do NOT touch any file in clew/search/ — that's AGENT-SEARCH's territory
- Write tests for every change
- Run tests after each task: python -m pytest tests/ -v
- Use the shared interfaces exactly as documented in the plan
- For P7 (two-pass pipeline), maintain backward compatibility with the existing
  --nl-descriptions flag while adding the new Pass 1/Pass 2 architecture
- Importance scoring module (P5b) lives in clew/indexer/importance.py — NOT in
  clew/search/. AGENT-SEARCH reads the score from Qdrant payload only.
- In Pass 1, populate "semantic" vector with stub content (signature text +
  callers/calls/imports from relationships, without description/keywords).
  Do NOT leave it empty — search needs basic results before enrichment.
- In Pass 2, BM25 sparse vector = semantic_text + "\n" + raw_code concatenated

Start with the independent tasks (P1-P5, P5b, P8) then move to P6 → P7.
```

### AGENT-SEARCH Prompt

```
You are implementing search and ranking changes for clew V2.
Working directory: /Users/albertgwo/Repositories/clew

Execute tasks S1 through S7 respecting dependencies. S1-S4 can run in any order
(no inter-dependencies). S5 depends on S3+S4. S6 depends on S5. S7 depends on S1.

Read CLAUDE.md and docs/plans/2026-02-12-v2-consolidated-implementation.md for
full context. Read each file before modifying it.

CRITICAL RULES:
- Do NOT touch any file in clew/indexer/ or clew/clients/ — that's AGENT-PIPE's territory
- Do NOT create clew/search/importance.py — importance scoring computation lives
  in clew/indexer/importance.py (AGENT-PIPE). You only READ importance_score from
  Qdrant payload via payload.get("importance_score", 0.0)
- Write tests for every change
- Run tests after each task: python -m pytest tests/ -v
- Use the shared interfaces exactly as documented in the plan
- Mock Qdrant responses in tests — don't depend on AGENT-PIPE's schema being live
- The named vectors ("signature", "semantic", "body") are defined in the plan's
  Shared Interfaces section
- Confidence threshold is configurable via CLEW_CONFIDENCE_THRESHOLD env var
  (default 0.65)

Start with the independent tasks (S1-S4) then move to S5 → S6 → S7.
```

### AGENT-INT Prompt

```
You are implementing integration changes for clew V2.
Working directory: /Users/albertgwo/Repositories/clew

Execute tasks I1 and I2 AFTER AGENT-PIPE and AGENT-SEARCH have committed their
changes.

Read CLAUDE.md and docs/plans/2026-02-12-v2-consolidated-implementation.md for
full context. Read each file before modifying it.

Tasks:
1. I1: Update clew/mcp_server.py for new payload fields and verify search flow
2. I2: Create /clew-enrich Claude Code skill at .claude/skills/clew-enrich/SKILL.md

Run full test suite after: python -m pytest tests/ -v
```

### AGENT-VAL Prompt

```
You are validating the clew V2 implementation.
Working directory: /Users/albertgwo/Repositories/clew
Test codebase: /Users/albertgwo/Work/evvy

Execute V1-V6 in order. ALL previous agents must have committed their changes.

Read docs/plans/2026-02-12-v2-consolidated-implementation.md for validation
checklist and expected results.

1. Run full unit test suite — ALL must pass
2. Run linting and type checking
3. Re-index Evvy with --full
4. Enrich Evvy with --nl-descriptions
5. Run spot checks (trace, search)
6. Run 16-test viability suite from the test plan at
   /Users/albertgwo/Work/evvy/docs/plans/2026-02-11-clew-viability-test-plan.md
   Write results to /Users/albertgwo/Work/evvy/docs/plans/2026-02-12-clew-viability-v2-results.md
```

---

## Success Criteria

| Metric | Current | Target |
|--------|---------|--------|
| Overall viability score | 1.72/3.0 | >= 2.3/3.0 |
| Accuracy | 0.63/3.0 | >= 1.5/3.0 |
| Completeness | 0.56/3.0 | >= 1.2/3.0 |
| Efficiency | 3.00/3.0 | >= 2.8/3.0 |
| Unit tests | 491 passing | All passing (schema change requires `--full` re-index) |
| New dependencies | — | Zero (no jedi, no networkx) |
| `clew index --full` without API key | — | Works (basic quality) |
| `clew index --nl-descriptions` with API key | — | Works (enriched quality) |
| Indexing time (2600 chunks + enrichment) | — | < 15 minutes |

---

## Projected Score Improvements by Test

| Test | Current | Projected | Key Fixes |
|------|---------|-----------|-----------|
| 1.1 Pinpoint by name | 1.50 | 2.50 | BM25 boost via "signature" vector |
| 1.2 Pinpoint by type | 1.50 | 2.25 | Rerank fix + importance boost |
| 1.3 Pinpoint by desc | 1.50 | 2.00 | "semantic" vector + file summaries |
| 2.1 E2E outbound trace | 2.75 | 3.00 | Normalization (depth-2) |
| 2.2 E2E model relations | 1.75 | 2.50 | Django FK + "semantic" vector |
| 3.1 Impact inbound | 1.00 | 2.50 | Normalization + enriched descriptions |
| 3.2 Impact model deps | 1.75 | 2.50 | Django FK + importance scoring |
| 3.3 Impact cross-app | 1.75 | 2.25 | Normalization + rerank fix |
| 4.1 Model M2M | 1.75 | 2.50 | Django M2M extractor |
| 4.2 Model FK chain | 1.50 | 2.50 | Django FK + enriched keywords |
| 5.1 Test by function | 2.25 | 2.75 | BM25 boost + "signature" vector |
| 5.2 Test by module | 2.50 | 2.75 | Already decent + file summaries |
| 6.1 Debug by error | 2.00 | 2.50 | DEBUG boost removal + "semantic" vector |
| 6.2 Debug by pattern | 1.50 | 1.75 | Fundamental limitation (grep task) |
| 7.1 Compound query | 1.50 | 2.25 | File summaries + rerank + enrichment |
| 7.2 Debug workflow | 1.50 | 2.25 | Trace fix + DEBUG removal + enrichment |
| **Overall** | **1.72** | **~2.42** | |

---

## Future Phases (Not In Scope)

Documented in `docs/plans/2026-02-12-index-enrichment-design.md`:
- miniCOIL as optional BM25 replacement
- Dynamic confidence threshold (score-gap heuristic)
- HyDE query reformulation with Haiku 4.5
- ColBERT late interaction models
- Local model support (Ollama)
- Weaviate-style query agent
- Auto-generated synonym tables
- Embedding-time search keywords (Haiku 4.5 generates extra search terms per chunk)

---

## References

- Viability test results: `/Users/albertgwo/Work/evvy/docs/plans/2026-02-11-clew-viability-results.md`
- Viability test plan: `/Users/albertgwo/Work/evvy/docs/plans/2026-02-11-clew-viability-test-plan.md`
- Index enrichment design: `docs/plans/2026-02-12-index-enrichment-design.md`
- Plan review findings: `docs/plans/2026-02-12-plan-review-findings.md`
- Earlier evaluation: `docs/plans/2026-02-10-fix-evaluation-shortcomings.md`
