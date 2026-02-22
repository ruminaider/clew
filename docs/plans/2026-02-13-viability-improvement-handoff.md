# Viability Improvement Handoff: 2.17 -> 2.5+

**Date:** 2026-02-13
**Goal:** Improve clew's viability score from 2.17/3.0 (CONDITIONAL) to >=2.5/3.0 (STRONG VIABILITY).

---

## Current State

The V2 multi-vector architecture was implemented and tested. Overall viability went from 1.72 to 2.17 -- a significant improvement driven by accuracy and completeness gains. However, the efficiency dimension regressed badly, dragging the overall score below the strong viability threshold.

### Per-Dimension Scores (V1 -> V2)

| Dimension | V1 Score | V2 Score | Delta |
|-----------|----------|----------|-------|
| Accuracy | 0.63 | 2.13 | +1.50 (massive improvement) |
| Completeness | 0.56 | 2.00 | +1.44 (massive improvement) |
| Tool Calls | 2.81 | 2.81 | 0.00 (unchanged, excellent) |
| Efficiency | 3.00 | 1.69 | **-1.31 (regression, main problem)** |
| **Overall** | **1.72** | **2.17** | **+0.45** |

---

## Primary Problem: File-Level Content in Search Results

The single biggest issue dragging down the viability score is that `clew search` returns entire file contents (2832+ lines for `ecomm/utils.py`) instead of individual function/class-level chunks. This destroys the efficiency score because the agent's context window fills up with irrelevant code.

### Root Cause (Confirmed)

The root cause is in the `reembed()` method in `clew/indexer/pipeline.py` (line 974-1057). During Pass 2 (re-embedding with enrichment data), the code reads the ENTIRE source file and stores it as the `content` payload:

```python
# pipeline.py line 977 — reads the FULL file, not the chunk
content = Path(file_path).read_text(encoding="utf-8", errors="replace")

# pipeline.py line 1014-1015 — uses full file content as body text
body_text = content  # <-- THIS IS THE BUG

# pipeline.py line 1057 — stores full file as "content" payload
"content": data["body_text"],  # <-- Full file content ends up here
```

**Pass 1 is correct.** In the `_embed_and_upsert()` method (line 828), the content is set from `pt_chunk.content`, which is the actual AST-parsed function/class body. After Pass 1, search results contain properly scoped chunk content.

**Pass 2 overwrites it.** When `reembed()` runs (triggered by `clew reembed` or `clew index --nl-descriptions`), it overwrites the correctly-scoped content with full file contents. The code even has a comment acknowledging this: `"# Use the full file for now as a reasonable approximation"` (line 1013-1014).

The `reembed()` method cannot recover the original chunk content because the `chunk_cache` SQLite table only stores `file_path`, `file_hash`, and `chunk_ids` (a JSON list of chunk ID strings). It does NOT store the actual chunk content or line ranges.

### Impact on Viability

The viability test agent estimated that fixing this single issue would push efficiency from 1.69 to ~2.5+, which would push the overall score above 2.5. This is the highest-leverage fix available.

---

## Secondary Problem: Class-Level Trace Returns 0 Edges

When tracing class entities like `Order` or `PrescriptionFill` using the `trace` MCP tool, the result is 0 relationships. Only function-level traces work (e.g., `_process_shopify_order_impl`).

### Root Cause

The Python relationship extractor (`clew/indexer/extractors/python.py`) emits `calls` relationships with function-level source entities like `file_path::ClassName.method_name`. When an agent traces `file_path::ClassName`, the BFS traversal finds no edges because the stored entities use `ClassName.method_name` format, not bare `ClassName`.

While the extractor does emit class-level call edges for attribute access chains (line 278-293), these only fire when the call target is resolved to a `module::Class.method` pattern. The class itself is never a direct source or target entity for `calls` relationships.

The entity resolution logic in `cache.resolve_entity()` may also fail to map a bare class name to its qualified form (`file_path::ClassName`), causing the lookup to miss edges stored under a different key.

---

## Investigation Plan

### Phase 1: Fix File-Level Content in Reembed (High Priority)

**Files to modify:**
- `clew/indexer/pipeline.py` -- the `reembed()` method (line 880+)
- `clew/indexer/cache.py` -- the `chunk_cache` table schema

**Option A (Recommended): Store chunk content in SQLite cache**

Add a `chunk_content_cache` table (or add a `chunk_content` column to the existing `enrichment_cache` table) that stores the actual AST-parsed chunk content alongside the chunk ID during Pass 1.

Schema:
```sql
CREATE TABLE IF NOT EXISTS chunk_content_cache (
    chunk_id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    line_start INTEGER DEFAULT 0,
    line_end INTEGER DEFAULT 0
);
```

During Pass 1 (`_embed_and_upsert`), after building chunk metadata, store the chunk content:
```python
if self._cache:
    self._cache.set_chunk_content(chunk_id, pt_chunk.content, line_start, line_end)
```

During Pass 2 (`reembed`), read the cached chunk content instead of the full file:
```python
# Replace: content = Path(file_path).read_text(...)
# With:
chunk_content = self._cache.get_chunk_content(chunk_id)
if chunk_content is None:
    # Fallback to full file if cache miss
    content = Path(file_path).read_text(...)
else:
    content = chunk_content
```

Also fix the payload to include `line_start` and `line_end` from the cache (currently missing from `reembed()` payloads entirely).

**Option B: Re-parse the file during reembed**

Instead of storing content in SQLite, re-parse each file using the AST parser during `reembed()` and match chunks by chunk ID:

```python
chunks = split_file(file_path, content, self._max_tokens, self._parser)
chunk_map = {}
for chunk in chunks:
    cid = build_chunk_id(chunk.file_path, chunk.metadata.get("entity_type", "section"), ...)
    chunk_map[cid] = chunk
```

Then look up the actual chunk content by chunk ID. This avoids schema changes but is slower (re-parses every file).

**Option A is recommended** because it is simpler, faster, and makes line range information available during reembed. Option B has the disadvantage of re-running AST parsing and potentially producing different chunks if the file was modified between Pass 1 and Pass 2.

**Validation:**

After implementing the fix:
1. Run `clew index --full /Users/albertgwo/Work/evvy`
2. Run `clew index --nl-descriptions /Users/albertgwo/Work/evvy` (or `clew reembed`)
3. Run `clew search "_process_shopify_order_impl" --raw` and verify:
   - The `content` field contains only the function body (~200 lines), NOT the entire `ecomm/utils.py` file (~2832 lines)
   - `line_start` and `line_end` are populated (not 0)
4. Run `clew search "PrescriptionFill" --raw` and verify chunk-level content

### Phase 2: Fix Class-Level Trace (Medium Priority)

**Files to investigate:**
- `clew/indexer/extractors/python.py` -- the `_extract_call()` and `_walk()` methods
- `clew/indexer/cache.py` -- `resolve_entity()` and `traverse_relationships()`

**What to fix:**

1. **Ensure class entities appear as relationship targets.** When a method is defined inside a class, add an implicit `defines` or `contains` relationship: `file_path::ClassName` -> `file_path::ClassName.method_name`. This way tracing `ClassName` finds all its methods.

2. **Aggregate method-level edges to the class level.** When a function calls `ClassName.method()`, the extractor already emits a class-level edge (line 278-293). Verify this works for the target codebase entities (Order, PrescriptionFill).

3. **Fix entity resolution for bare class names.** If `cache.resolve_entity("Order")` does not resolve to `backend/ecomm/models.py::Order`, the trace will fail. Check the resolution logic.

**Validation:**

```bash
clew trace "Order" --direction both --depth 2
clew trace "PrescriptionFill" --direction inbound --depth 2
```

Both should return non-empty edge lists.

---

## Files to Read

The investigating agent should read these files in full before making changes:

| File | Why |
|------|-----|
| `clew/indexer/pipeline.py` | Contains both `_embed_and_upsert()` (Pass 1, correct) and `reembed()` (Pass 2, buggy). The fix goes here. |
| `clew/indexer/cache.py` | SQLite schema, `chunk_cache` table, enrichment methods. New table or columns needed here. |
| `clew/search/hybrid.py` | `_point_to_result()` reads `content` from Qdrant payload and puts it in `SearchResult.content`. No changes needed here, but understand how content flows to the agent. |
| `clew/search/engine.py` | Search orchestrator. `_maybe_rerank()` passes `c.content` to the reranker -- full file content means the reranker is processing 2832 lines per candidate, which is both slow and less accurate. |
| `clew/mcp_server.py` | `_build_snippet()` and `_result_to_dict()` show how search results are presented to agents. In compact mode, only a snippet is shown; in full mode, the entire `content` field is returned. The bug means full mode returns the entire file. |
| `clew/chunker/strategies.py` | `PythonChunker.extract_entities()` produces `CodeEntity` objects with correctly scoped `content` fields. This is where the correct content originates during Pass 1. |
| `clew/chunker/fallback.py` | `split_file()` and `_extract_ast_chunks()` show how chunks are created. The `Chunk.content` field contains the actual function/class body. |
| `clew/indexer/extractors/python.py` | Python relationship extractor. Relevant for the class-level trace fix. |
| `clew/indexer/metadata.py` | `extract_signature()` takes `content` as input -- during reembed, it receives the full file and extracts the wrong signature (first `def`/`class` in the file, not the chunk's). |

---

## Test Plan and Results References

| Document | Path |
|----------|------|
| Viability test plan (16 A/B tests) | `/Users/albertgwo/Work/evvy/docs/plans/2026-02-11-clew-viability-test-plan.md` |
| V1 results (1.72/3.0, NOT VIABLE) | `/Users/albertgwo/Work/evvy/docs/plans/2026-02-11-clew-viability-results.md` |
| V2 implementation plan | `docs/plans/2026-02-12-v2-consolidated-implementation.md` |
| Target codebase for testing | `/Users/albertgwo/Work/evvy` |

---

## Architecture Context

- **Qdrant collection `code`:** 12,087 points, 3 named vectors (signature 1024d, semantic 1024d, body 1024d) + BM25 sparse
- **Enrichment:** 8,910/12,087 chunks enriched with LLM descriptions + keywords
- **SQLite caches:** `{project}/.clew/cache.db` (embeddings, descriptions) and `{project}/.clew/state.db` (relationships, chunk mappings)
- **Query routing:** LOCATION intent -> signature vector; CODE/DEBUG/DOCS -> semantic vector
- **Confidence fallback:** top score < 0.65 -> fan out to all vectors

---

## Additional Bug Found During Investigation

The `reembed()` method also has a bug in `extract_signature()` (line 989):

```python
signature = extract_signature(entity_type, content)
```

Here `content` is the full file (from line 977), so `extract_signature()` extracts the first `def`/`class` line in the entire file rather than the chunk's actual signature. This means enriched chunks may have incorrect signature metadata. The fix is to use the cached chunk content (after implementing Option A) instead of the full file for signature extraction.

---

## Expected Impact

Fixing the file-level content bug alone is projected to:
- Push **Efficiency** from 1.69 to ~2.5+ (compact results return function bodies instead of entire files)
- Improve **Accuracy** slightly (reranker operates on focused content, not 2832-line files)
- Push **Overall** from 2.17 to ~2.5+ (crossing the STRONG VIABILITY threshold)

Fixing the class-level trace would further improve Completeness for categories 2 (E2E understanding) and 3 (impact analysis).

---

## Quick Start for the Implementing Agent

1. Read `clew/indexer/pipeline.py` in full -- understand both `_embed_and_upsert()` and `reembed()`
2. Read `clew/indexer/cache.py` -- understand the SQLite schema (version 3)
3. Add a `chunk_content_cache` table to the schema
4. In `_embed_and_upsert()`, store `(chunk_id, chunk.content, line_start, line_end)` to the new table
5. In `reembed()`, replace `Path(file_path).read_text()` with cache lookup
6. Fix `extract_signature()` in reembed to use chunk content
7. Add `line_start` and `line_end` to reembed payload
8. Run `pytest --cov=clew -v` to verify no regressions
9. Re-index Evvy: `clew index --full /Users/albertgwo/Work/evvy`
10. Re-enrich: `clew index --nl-descriptions /Users/albertgwo/Work/evvy` (or `clew reembed`)
11. Verify: `clew search "_process_shopify_order_impl" --raw` returns function-level content
12. Re-run viability tests from the test plan
