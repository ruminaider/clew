# Plan: Fix Clew's Core Shortcomings

> **NOTE**: This is a working document for planning purposes. Do not commit to git or add to .gitignore.

## Context

Clew is our semantic code search tool (hybrid Voyage AI embeddings + BM25 + Qdrant). A 31-test evaluation across 7 categories revealed a 48% failure rate driven by **three systemic root causes** that account for ~60% of all failures. This plan addresses all three, plus secondary issues (weak `explain` tool, staleness detection, intent classification).

**Codebase:** `/Users/albertgwo/Repositories/clew/`
**Evaluation branch:** `dvy-3780/remediate-unfilled-orders` in the Evvy repo

---

## Workstream 1: Fix Asymmetric Entity Naming (Trace System)

**Impact:** Fixes 4 FAIL tests (3.1, 3.3, 3.4, 3.5) — all inbound traces and multi-hop BFS

### Root Cause

Source entities use full paths (`/abs/path/utils.py::process_shopify_order`) but target entities store bare AST names (`process_shopify_order`). This breaks:
- **Inbound traces:** `WHERE target_entity = '/abs/path/...'` finds nothing (targets are bare)
- **Multi-hop BFS:** Bare target from hop 1 can't match `source_entity` for hop 2

### Approach: Hybrid — post-extraction normalization + query-time resilience

#### 1a. Post-extraction target resolution

**File:** `clew/indexer/pipeline.py` (around line 162-232)

Current flow processes files one at a time and stores relationships immediately. Change to:
- Accumulate all relationships across the batch
- Build a **symbol index** from all `source_entity` values containing `::`
- For each bare `target_entity`: if the symbol index has exactly 1 match, rewrite to full path
- Skip `self.method` patterns and dotted external references (`models.Model`)
- Store after normalization

New methods: `_build_symbol_index(rels) -> dict[str, set[str]]` and `_resolve_targets(rels, index) -> list[Relationship]`

#### 1b. BFS re-resolution between hops

**File:** `clew/indexer/cache.py` lines 402-459 (`traverse_relationships`)

Before each `get_relationships()` call, re-resolve bare entities:
```python
resolved_current = self.resolve_entity(current) if "::" not in current else current
neighbors = self.get_relationships(resolved_current, ...)
```

The `"::" not in current` check avoids unnecessary resolution for already-qualified entities.

#### 1c. Inbound query fallback

**File:** `clew/indexer/cache.py` lines 249-309 (`get_relationships`)

When inbound exact match returns 0 results and entity contains `::`, extract the symbol portion and retry:
```python
if not rows and "::" in entity:
    symbol = entity.rsplit("::", 1)[1]
    rows = conn.execute("... WHERE target_entity = ?", [symbol]).fetchall()
```

This is exact match on the symbol (not LIKE), so no false-positive risk from common names like `save`. All callers are returned, which is correct for "who calls X?".

#### 1d. Schema migration for existing indexes

**File:** `clew/indexer/cache.py`

Add `schema_version` table. On init, if version < 2, run a one-time normalization pass over all existing `code_relationships` rows using the symbol index approach from 1a. Idempotent — safe to run multiple times.

#### 1e. CLI trace fix

**File:** `clew/cli.py` (around line 259)

Add `resolve_entity()` call before `traverse_relationships` (MCP server already does this, CLI doesn't).

---

## Workstream 2: Fix Search Ranking Bias Against Production Code

**Impact:** Fixes ~3 PARTIAL/FAIL tests (2.2, 2.3, 2.6) and improves all search quality

### Root Cause

`is_test` metadata is stored in Qdrant but never propagated to `SearchResult` or used for scoring. The reranker only sees content text. No post-rerank adjustments exist.

#### 2a. Propagate `is_test` through search pipeline

**File:** `clew/search/models.py` line 35

Add `is_test: bool = False` to `SearchResult` dataclass.

**File:** `clew/search/hybrid.py` (`_point_to_result`)

Extract `is_test` from Qdrant payload: `is_test=payload.get("is_test", False)`

#### 2b. Post-rerank metadata adjustments

**File:** `clew/models.py` (SearchConfig)

Add configurable penalties:
```python
test_file_penalty: float = 0.15      # for CODE/LOCATION/DOCS intent
test_file_penalty_debug: float = 0.05 # reduced for DEBUG intent
```

**File:** `clew/search/engine.py` lines 79-85

Insert new step between rerank and deduplicate:
```python
results = self._maybe_rerank(query_enhanced, candidates)
results = self._apply_metadata_adjustments(results, intent)  # NEW
results = self._deduplicate(results)
results.sort(key=lambda r: r.score, reverse=True)            # re-sort after adjustment
```

The `_apply_metadata_adjustments` method subtracts the intent-appropriate penalty from `is_test=True` results. Subtraction (not multiplication) gives a consistent, tunable offset.

#### 2c. Remove DEBUG test-file boost prefetch

**File:** `clew/search/hybrid.py` lines 110-125

Remove the prefetch that explicitly injects test-file candidates into RRF fusion for DEBUG intent. With post-rerank adjustments (2b), test files surface naturally when semantically relevant.

#### 2d. Fix layer classification for test files

**File:** `clew/indexer/metadata.py` lines 27-42

Add test path detection **before** filename lookup in `classify_layer()`:
```python
if _is_test_path(file_path):
    return "test"
```

This means `tests/models.py` correctly gets `layer="test"` instead of `layer="model"`.

#### 2e. Consolidate `is_test_file` utility

Three duplicate implementations exist:
- `clew/indexer/pipeline.py` lines 66-79
- `clew/indexer/extractors/tests.py` lines 11-23
- New `_is_test_path` in `metadata.py`

Consolidate into a single `is_test_file()` in `metadata.py`, import from there.

#### 2f. Refine intent classification

**File:** `clew/search/intent.py` lines 31-50

Split `DEBUG_KEYWORDS` into hard (always DEBUG: "bug", "error", "crash", "exception", "traceback", "debug") and soft (need error context: "fix", "broken", "why"). Add explicit debug phrases ("why does", "failing test"). This prevents "fix the user model" from triggering DEBUG mode.

---

## Workstream 3: Fix Infrastructure — Ignore Patterns, Staleness, Commit Tracking

**Impact:** Fixes 5 FAIL tests (2.4, 2.7, 3.5, 4.2, 7.5) — all caused by `.codesearchignore` excluding production code

#### 3a. Add `.codesearchignore` fallback in Clew

**File:** `clew/indexer/ignore.py` lines 51-54

Change from:
```python
clewignore = self.project_root / ".clewignore"
if clewignore.exists():
    all_patterns.extend(self._read_pattern_file(clewignore))
```
To:
```python
clewignore = self.project_root / ".clewignore"
codesearchignore = self.project_root / ".codesearchignore"
if clewignore.exists():
    all_patterns.extend(self._read_pattern_file(clewignore))
elif codesearchignore.exists():
    all_patterns.extend(self._read_pattern_file(codesearchignore))
```

`elif` ensures no double-loading. `.clewignore` takes priority.

#### 3b. Fix Evvy ignore patterns (Evvy repo change)

**File:** `/Users/albertgwo/Work/evvy/.codesearchignore` → rename to `.clewignore`

Replace `backend/test_results/` (line 13) with targeted exclusions:
```
backend/test_results/tests/
backend/test_results/data/
```

This preserves ~20,700 lines of production code (lab services, models, signals) while excluding actual test files.

#### 3c. Fix MCP commit tracking

**File:** `clew/mcp_server.py` lines 348-356

After `index_files()` completes in the trigger action, save the commit hash:
```python
from clew.indexer.change_detector import ChangeDetector
detector = ChangeDetector(root, components.cache)
commit = detector.get_current_commit()
if commit:
    components.cache.set_last_indexed_commit("code", commit)
```

Also include `last_commit` in the trigger response dict.

#### 3d. Add staleness info to `index_status`

**File:** `clew/mcp_server.py` lines 312-326

After retrieving `last_commit`, compare with HEAD:
```python
if last_commit:
    head = GitChangeTracker(Path.cwd()).get_current_commit()
    if head and head != last_commit:
        staleness = {"stale": True, "commits_behind": count_commits(last_commit, head)}
```

Include `stale`, `commits_behind`, `head_commit`, `indexed_commit` in the response. `git rev-list --count` is sub-millisecond.

---

## Workstream 4: Improve the `explain` Tool

**Impact:** Improves 2 PARTIAL tests (4.1, 4.4) — currently just a search wrapper

#### 4a. Heuristic explanation (no LLM required)

**File:** `clew/mcp_server.py` lines 206-248

Add a `_heuristic_explain()` function that assembles: target signature, docstring, file locations of related code, and relationships (if available from trace). Returns structured text, not just chunk list.

#### 4b. LLM-powered explanation (optional, when ANTHROPIC_API_KEY set)

Add `_llm_explain()` that passes the question + related chunks to Claude Haiku with a focused prompt. Falls back to heuristic if no API key or on timeout (5s).

Both approaches add an `explanation` string field to the `explain` response.

---

## Implementation Order

| Phase | Workstream | Re-index? | Estimated Effort |
|-------|-----------|-----------|-----------------|
| 1 | 3a: `.codesearchignore` fallback | No | 15 min |
| 2 | 3b: Fix Evvy ignore patterns | Yes (full) | 10 min |
| 3 | 3c: MCP commit tracking | No | 20 min |
| 4 | 3d: Staleness in index_status | No | 30 min |
| 5 | 2a-2b: `is_test` propagation + post-rerank penalty | No | 45 min |
| 6 | 2c: Remove DEBUG test boost | No | 15 min |
| 7 | 2d-2e: Layer classification + consolidate utility | Yes (for layer) | 30 min |
| 8 | 2f: Intent classification refinement | No | 30 min |
| 9 | 1a-1c: Entity naming fix (extraction + query) | Yes (for normalization) | 2 hours |
| 10 | 1d: Schema migration | No (auto-migrates) | 30 min |
| 11 | 1e: CLI trace fix | No | 10 min |
| 12 | 4a-4b: Explain tool improvement | No | 1 hour |
| 13 | Tests for all workstreams | — | 2 hours |

**Total:** ~8 hours

Phases 1-4 (infrastructure) can be done first and validated immediately with a re-index. Phases 5-8 (search ranking) work without re-indexing. Phases 9-11 (trace) are the most complex and benefit from the infrastructure fixes being in place.

---

## Verification Plan

### After Phases 1-4 (Infrastructure)
1. `clew index --full .` from Evvy root — verify `backend/test_results/lab_services/` files are now indexed
2. `clew status` — verify `last_commit` is populated and matches HEAD
3. `clew search "Junction lab provider client"` — verify lab services code appears (was excluded before)
4. `clew search "Test model for vaginal microbiome"` — verify `test_results/models/test.py` appears

### After Phases 5-8 (Search Ranking)
5. `clew search "PrescriptionFillOrder model"` — verify production `care/models.py` outranks test files
6. `clew search "subscription renewal flow"` — verify service files outrank test files
7. `clew search "fix the user model"` — verify intent classified as CODE, not DEBUG
8. `clew search "why does login fail"` — verify intent classified as DEBUG

### After Phases 9-11 (Trace)
9. `clew trace "backend/ecomm/utils.py::process_shopify_order" --direction inbound` — verify callers found
10. `clew trace "backend/ecomm/utils.py::process_shopify_order" --direction outbound --depth 3` — verify multi-hop chain
11. `clew trace "backend/care/models.py::PrescriptionFill" --direction inbound --types tests` — verify test files found

### After Phase 12 (Explain)
12. `clew explain backend/ecomm/utils.py --question "why could prescription_ids be stale"` — verify explanation text (not just search results)

### Re-run Evaluation Suite
13. Re-run the full 31-test evaluation from the original plan. Target: ≥75% PASS rate (up from 23%).

---

## Key Files (Clew Repo)

| File | Changes |
|------|---------|
| `clew/indexer/ignore.py` | `.codesearchignore` fallback (3a) |
| `clew/indexer/pipeline.py` | Post-extraction target normalization (1a), consolidate `_is_test_file` import (2e) |
| `clew/indexer/cache.py` | BFS re-resolution (1b), inbound fallback (1c), schema migration (1d) |
| `clew/indexer/metadata.py` | `is_test_file()` consolidation (2e), `classify_layer` test detection (2d) |
| `clew/indexer/extractors/tests.py` | Import `is_test_file` from metadata (2e) |
| `clew/search/models.py` | Add `is_test` to `SearchResult` (2a) |
| `clew/search/hybrid.py` | Extract `is_test` from payload (2a), remove DEBUG boost (2c) |
| `clew/search/engine.py` | Post-rerank metadata adjustments (2b) |
| `clew/search/intent.py` | Hard/soft keyword split (2f) |
| `clew/models.py` | `test_file_penalty` config fields (2b) |
| `clew/mcp_server.py` | Commit tracking (3c), staleness (3d), explain improvement (4a-4b) |
| `clew/cli.py` | CLI trace resolve_entity (1e) |

## Key Files (Evvy Repo)

| File | Changes |
|------|---------|
| `.codesearchignore` → `.clewignore` | Rename + fix `backend/test_results/` pattern (3b) |
