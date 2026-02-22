# V3: Hybrid Exhaustive Search

**Goal:** Close clew's completeness gap by adding intent-based routing, low-confidence signaling, grep integration, and peripheral code surfacing. Make clew viable as both an MCP tool (agent-assisted) and a standalone product.

**Motivation:** V2.3 viability results (SHIP, 3.96/5.0, 5/8 wins) show clew wins on discovery and precision but loses on completeness. The worst test (C1: 3.13/5.0, exhaustive URL enumeration) exposes a fundamental gap: semantic search returns "most relevant," not "all matching." Industry research confirms no tool solves this in one system — the universal pattern is layered: semantic search for understanding, grep/keyword for exhaustive matching.

**Key insight:** Clew's BM25 sparse vectors are **identifier matching with IDF weighting**, not general-purpose text search. The tokenizer extracts code identifiers (`[a-zA-Z_][a-zA-Z0-9_]*`), splits camelCase/snake_case, and hashes to sparse indices. This is fundamentally different from grep, which matches arbitrary text patterns. BM25 can improve completeness for identifier-level queries but cannot replace grep for true exhaustive search. See [ADR-005](../adr/005-bm25-identifier-matching-vs-grep.md).

**Non-goals (V4):**
- Embedding freshness automation (incremental re-indexing, file watchers, CI/CD integration)
- Query decomposition (keyword-based heuristics have too many failure modes per plan review; consuming LLM agents already handle decomposition better)
- HyDE query reformulation, ColBERT late interaction, local model support (Ollama)
- Business layer (blueprint → code entity mapping)

---

## Architectural Decisions

### ADR-005: BM25 Identifier Matching Is Not Grep — Search Routing and Exhaustive Strategy

Full ADR at `docs/adr/005-bm25-identifier-matching-vs-grep.md`. Key decisions:

1. **ENUMERATION intent routes to weighted hybrid (70/30 BM25/dense), not BM25-only.** Preserves semantic understanding while biasing toward identifier completeness.
2. **Grep integration is the true exhaustive solution.** The `exhaustive` mode runs ripgrep after semantic search — this is the real completeness guarantee.
3. **Expose explicit `mode` parameter on MCP search tool.** `mode="semantic"` (default), `mode="keyword"` (BM25-biased), `mode="exhaustive"` (semantic + grep). The consuming agent can override automatic classification when precision matters.

### ADR-006: Confidence Signaling and Grep Pattern Generation

**Context:** When clew's semantic search returns low-confidence results, the consuming agent has no signal to fall back to grep. This leads to incomplete answers on exhaustive tasks.

**Decision:** Add regime-aware confidence scoring to SearchResponse. Scores come from different distributions depending on the pipeline path (RRF fusion scores vs Voyage reranker scores vs raw cosine similarity). Use the appropriate metric per regime:
- **When reranking is applied:** Use reranker score of top result (calibrated probability in [0,1])
- **When reranking is skipped:** Use score gap between rank 1 and rank 5 as a proxy
- **Ambiguity detection:** Score gap between rank 1 and rank 2 (small gap = ambiguous results)

When confidence is low, include: (1) a human-readable suggestion, (2) machine-readable suggested grep patterns derived from both the query itself and the semantic results.

**Consequences:** MCP responses grow slightly larger. Standalone mode adds a ripgrep subprocess dependency. Pattern generation is best-effort.

---

## Research Summary

Competitive landscape analysis (3 parallel research agents, Feb 2026) found:

| Tool | Approach | Exhaustive? |
|------|----------|-------------|
| Cursor | Agent picks between `codebase_search` (vector) and `grep_search` (ripgrep) | Via grep tool |
| Sourcegraph | Zoekt (trigram) + Deep Search (agentic AI). Moved AWAY from embeddings at enterprise scale | `count:all` mode |
| GitHub | Blackbird (trigram, purely lexical) + Copilot (separate semantic) | Via Blackbird |
| Greptile | NL descriptions + function-level chunking + graph context | No exhaustive mode |
| Cognition (Devin) | SWE-grep: RL-trained agent that generates grep commands | Via trained grep agent |
| Claude Code | Pure ripgrep + agentic iteration, no vector search | Via ripgrep |

**Key findings:**
1. No tool positions as "semantic + grep completeness guarantees" in one system
2. Qdrant's sparse vector index is exact (inverted index), but clew's custom tokenizer limits it to identifier matching — not equivalent to grep
3. GrepRAG paper: only 20-30% overlap between grep and semantic results — they find fundamentally different things
4. Greptile's NL-first embedding approach (same as clew's) shows 12% similarity improvement
5. Sourcegraph's embedding backlash is enterprise-scale-specific; embeddings remain practical for single-project tools

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| HNSW vs BM25 | Both — weighted hybrid for ENUMERATION (70/30 BM25/dense) | BM25 is identifier matching, not grep. Need dense search to catch naming variations. See ADR-005. |
| Grep integration | The true exhaustive solution. Dual-mode: suggest in MCP, execute in standalone | BM25 improves completeness but can't replace grep. Grep is the completeness guarantee. |
| Query decomposition | **Deferred to V4** | Keyword heuristics have too many failure modes. LLM agents already decompose better. |
| Confidence metric | Regime-aware: reranker score when available, score-gap otherwise | RRF, reranker, and cosine scores are on different scales — a single threshold is meaningless |
| Suggested patterns | Dual-track: from query terms (domain knowledge) + from result metadata | Cold-start problem: when confidence is low, results may be wrong, so query-derived patterns are essential |
| Ripgrep dependency | Optional subprocess, not linked library | Widely available, battle-tested, no build complexity |
| `mode` parameter | Explicit on MCP tool, overrides automatic classification | Automatic intent classification has high false-negative risk. The actual C1 query may not have contained "find all" keywords. |
| ENUMERATION result ordering | By importance score, then file path — not raw BM25 score | BM25 ordering ranks by term frequency (file mentioning `urlpatterns` 10x beats the canonical definition). Not useful for code. |
| ENUMERATION response format | Compact: file paths + line numbers + snippets, not full content | limit=200 at 300 tokens/chunk = 60K tokens. Too much for LLM context. Full content available via `get_context` on demand. |

---

## Implementation Phases

### Phase 1: Confidence Scoring + ENUMERATION Intent (parallel agents)

Two independent workstreams that share no files until integration.

#### Agent A: Confidence Scoring + Low-Confidence Signaling

**Files:**
- Modify: `clew/search/models.py` — add fields to `SearchResponse`
- Modify: `clew/search/engine.py` — compute confidence, generate suggestions
- Modify: `clew/mcp_server.py` — include confidence info in MCP responses, add `mode` parameter
- Test: `tests/unit/test_engine.py`, `tests/unit/test_mcp_server.py`

**Task A.1: Extend SearchResponse with confidence fields**

```python
@dataclass
class SearchResponse:
    results: list[SearchResult]
    query_enhanced: str
    total_candidates: int
    intent: QueryIntent
    # V3: Confidence signaling
    confidence: float = 1.0  # 0.0-1.0
    confidence_label: str = "high"  # "high", "medium", "low"
    suggestion: str | None = None  # Human-readable fallback suggestion
    suggested_patterns: list[str] | None = None  # Grep-ready regex patterns
    # V3: Peripheral surfacing
    related_files: list[RelatedFile] | None = None
```

**Task A.2: Implement regime-aware confidence computation in SearchEngine**

After reranking and before applying limit, compute confidence using the appropriate signal:

```python
def _compute_confidence(self, results: list[SearchResult], was_reranked: bool) -> tuple[float, str]:
    """Compute confidence score using regime-appropriate metric."""
    if not results:
        return 0.0, "low"

    if was_reranked:
        # Reranker scores are calibrated probabilities in [0,1]
        confidence = results[0].score
    else:
        # RRF/cosine scores: use gap between rank 1 and rank 5
        scores = [r.score for r in results[:5]]
        if len(scores) >= 5:
            confidence = scores[0] - scores[4]  # Score spread
        else:
            confidence = scores[0] if scores else 0.0

    # Ambiguity detection: small gap between rank 1 and rank 2
    ambiguity = 0.0
    if len(results) >= 2:
        ambiguity = results[0].score - results[1].score

    # Combined label
    if confidence >= 0.7 and ambiguity >= 0.05:
        return confidence, "high"
    elif confidence >= 0.4:
        return confidence, "medium"
    else:
        return confidence, "low"
```

Thresholds are initial guesses — calibrate on Evvy query distributions (see Open Questions).

When low or medium: populate `suggestion` and `suggested_patterns`.

**Task A.3: Implement dual-track grep pattern generation**

Generate patterns from two sources:
1. **Query-derived patterns:** Extract likely code patterns from query terms using domain knowledge (e.g., "Django URL patterns" → `urlpatterns|path\(|re_path\(|include\(`)
2. **Result-derived patterns:** Extract from semantic result metadata (function names, decorators, imports, file paths)

This addresses the cold-start problem: when confidence is low, results may be wrong, so query-derived patterns provide a safety net.

**Task A.4: Add `mode` parameter to MCP search tool**

```python
@mcp.tool()
async def search(
    query: str,
    limit: int = 5,
    collection: str = "code",
    active_file: str | None = None,
    intent: str | None = None,
    filters: dict[str, str] | None = None,
    detail: str = "compact",
    mode: str = "semantic",  # V3: "semantic", "keyword", "exhaustive"
) -> list[dict[str, Any]] | dict[str, str]:
```

Mode behavior:
- `mode="semantic"` (default): Standard hybrid search. Automatic intent classification applies. Equivalent to V2.3 behavior.
- `mode="keyword"`: Forces ENUMERATION-style weighted hybrid (70/30 BM25/dense), limit=200. Bypasses intent classifier. Results ordered by importance + file path, not BM25 score.
- `mode="exhaustive"`: Runs semantic search first, then ripgrep with generated patterns. Returns merged results with `source` field ("semantic" or "grep"). Requires `project_root` to be configured.

When `mode` is explicitly set, it takes precedence over automatic intent classification. When `mode` is not set, automatic classification may suggest a mode via `suggestion` field.

**Task A.5: Wire confidence + mode into MCP response**

Include in all search responses:
```json
{
    "results": [...],
    "confidence": 0.82,
    "confidence_label": "high",
    "intent": "code",
    "mode": "semantic"
}
```

Low-confidence response additionally includes:
```json
{
    "suggestion": "Results may be incomplete. Consider mode='keyword' or mode='exhaustive' for broader coverage.",
    "suggested_patterns": ["urlpatterns", "path\\(", "re_path\\("]
}
```

#### Agent B: ENUMERATION Intent + Weighted Hybrid Routing

**Files:**
- Modify: `clew/search/intent.py` — add ENUMERATION intent + keywords
- Modify: `clew/search/models.py` — add ENUMERATION to QueryIntent enum (coordinate with Agent A)
- Modify: `clew/search/hybrid.py` — weighted hybrid mode for ENUMERATION
- Test: `tests/unit/test_intent.py`, `tests/unit/test_hybrid.py`

**Task B.1: Add ENUMERATION to QueryIntent**

```python
class QueryIntent(str, Enum):
    CODE = "code"
    DOCS = "docs"
    DEBUG = "debug"
    LOCATION = "location"
    ENUMERATION = "enumeration"  # V3: completeness-biased matching
```

**Task B.2: Add ENUMERATION keywords to intent classifier**

```python
ENUMERATION_PHRASES = [
    "find all",
    "list all",
    "every instance",
    "all instances",
    "all uses",
    "all callers",
    "all references",
    "enumerate",
    "how many",
    "count all",
]
```

Priority order: DEBUG > ENUMERATION > LOCATION > DOCS > CODE

Note: Automatic classification is a convenience, not a guarantee. The `mode` parameter on the MCP tool provides the explicit override.

**Task B.3: Implement weighted hybrid routing in HybridSearchEngine**

For ENUMERATION intent (or `mode="keyword"`):
- **Still embed the query** (dense vectors needed for naming variation coverage)
- BM25 sparse prefetch: limit=200 (high, configurable via `CLEW_ENUMERATION_LIMIT`)
- Dense prefetch: limit=60 (reduced but present, catches naming variations)
- Fusion: RRF with both prefetch branches
- Skip reranking (completeness > fine-grained relevance ordering)
- Apply stop-word filtering to the sparse query vector: remove common English words ("find", "all", "the", "for", etc.) that would match many documents without adding signal
- Post-sort results by importance score then file path (not raw BM25/RRF score)

```python
# Stop words for ENUMERATION queries — remove noise terms from sparse vector
ENUMERATION_STOP_WORDS = frozenset({
    "find", "all", "the", "for", "in", "of", "to", "is", "are", "how",
    "many", "every", "each", "list", "show", "get", "what", "where",
})

def _build_enumeration_prefetches(
    self,
    dense_vector: list[float],
    sparse_vector: models.SparseVector,
) -> list[models.Prefetch]:
    enum_limit = int(os.environ.get("CLEW_ENUMERATION_LIMIT", "200"))
    return [
        models.Prefetch(query=sparse_vector, using="bm25", limit=enum_limit),
        models.Prefetch(query=dense_vector, using="semantic", limit=60),
    ]
```

**Task B.4: Add sparse index coverage check**

Before executing ENUMERATION routing, verify that the sparse vector field has data. If the collection was indexed before sparse vectors were added (schema migration), the sparse field may be empty. Degrade gracefully: fall back to standard hybrid search and log a warning.

**Task B.5: Update MCP search tool to accept "enumeration" intent**

Add "enumeration" to the valid intent values. Document that `mode="keyword"` is the explicit equivalent.

**Task B.6: Empirically validate Qdrant pruning behavior**

Before finalizing the ENUMERATION limit, test:
- Run sparse-only queries with limit=50, 200, 500, 1000 on the Evvy index
- Compare result counts and verify no silent pruning at lower limits
- Document findings in test results

Qdrant applies pruning on posting lists ([GitHub #3029](https://github.com/qdrant/qdrant/issues/3029)). At high limits, pruning should be minimal, but this must be verified empirically.

---

### Phase 2: Grep Integration (depends on Phase 1)

**Elevated from "nice-to-have" to core feature.** Per ADR-005, BM25 is identifier matching, not grep. Grep integration is the **real** exhaustive solution.

#### Agent C: Semantic-to-Grep Pattern Generation + Optional Execution

**Files:**
- Create: `clew/search/grep.py` — pattern generation and optional ripgrep execution
- Modify: `clew/search/engine.py` — wire grep into `mode="exhaustive"` path
- Test: `tests/unit/test_grep.py`

**Task C.1: Implement dual-track grep pattern generation**

```python
def generate_grep_patterns(
    results: list[SearchResult],
    query: str,
    intent: QueryIntent,
) -> list[str]:
    """Generate grep-ready patterns from query terms AND semantic results."""
```

Two pattern sources:
1. **Query-derived patterns:** Use domain knowledge to extract likely code patterns. "Django URL patterns" → `urlpatterns|path\(|re_path\(|include\(`. "Stripe API calls" → `stripe\.|Stripe\(|STRIPE_`. This requires a small mapping of framework-specific pattern templates triggered by query keywords.
2. **Result-derived patterns:** Extract from semantic result metadata:
   - Function/class names → `def function_name|class ClassName`
   - Decorator patterns → `@decorator_name`
   - Import patterns → `from module import|import module`
   - File path patterns → `*/app_name/*.py`

Return both sets merged and deduplicated.

**Task C.2: Implement optional ripgrep execution**

```python
@dataclass
class GrepResult:
    file_path: str
    line_number: int
    line_content: str
    pattern_matched: str

async def run_grep(
    patterns: list[str],
    project_root: Path,
    file_globs: list[str] | None = None,
    timeout: float = 10.0,
) -> list[GrepResult]:
    """Execute ripgrep with generated patterns. Returns empty list if rg not available."""
```

- Subprocess call to `rg` (ripgrep)
- Graceful fallback: if `rg` not found, return empty list + log warning
- Timeout: 10 seconds max
- File type filtering based on indexed languages

**Task C.3: Wire grep into `mode="exhaustive"` pipeline**

When `mode="exhaustive"`:
1. Run semantic search as normal (produces ranked results)
2. Generate grep patterns from query + results (Task C.1)
3. Execute ripgrep with those patterns (if available)
4. Merge: semantic results (ranked, with `source: "semantic"`) + grep-only results (with `source: "grep"`, deduplicated against semantic results)
5. Deduplicate by file_path + line range

**Interaction with ENUMERATION intent:** When `mode="exhaustive"` is set, it takes precedence. The pipeline runs semantic search (not ENUMERATION-biased) followed by grep. The `mode` parameter is the primary control; intent classification is secondary.

**Task C.4: Add `exhaustive` CLI flag**

```bash
clew search "django URL patterns" --exhaustive
# equivalent to mode="exhaustive" in MCP
```

---

### Phase 3: Peripheral Code Surfacing (depends on Phase 1)

**Origin:** V2.3 roadmap item #2. Addresses the pattern where grep agents explore more broadly than clew agents (tests, admin, constants, scripts).

#### Agent D: Automatic Related File Suggestions

**Files:**
- Modify: `clew/search/engine.py` — add peripheral surfacing step after primary search
- Modify: `clew/search/models.py` — add `RelatedFile` dataclass
- Modify: `clew/mcp_server.py` — include related files in response
- Test: `tests/unit/test_engine.py`

**Task D.1: Surface peripheral files via trace edges**

After primary search returns results, use the trace graph to find related files not in the result set:
- For each top-3 result entity, traverse outbound edges (depth=1)
- Collect target entities in categories: tests, admin, constants, scripts, configs
- Deduplicate and return as `related_files` in SearchResponse
- Cap at 5 related files to avoid noise

```python
@dataclass
class RelatedFile:
    file_path: str
    relationship: str  # "tests", "imported_by", "calls", etc.
    entity: str  # the entity that connects this file to the results

@dataclass
class SearchResponse:
    # ... existing fields ...
    related_files: list[RelatedFile] | None = None
```

**Task D.2: Wire into MCP response**

Include `related_files` in compact search responses when non-empty:
```json
{
    "results": [...],
    "related_files": [
        {"file_path": "tests/test_orders.py", "relationship": "tests", "entity": "care/models.py::Order"},
        {"file_path": "care/admin.py", "relationship": "imported_by", "entity": "care/models.py::Order"}
    ]
}
```

---

## MCP Response Schema (V3)

### Standard search (confidence signaling)
```json
{
    "results": [
        {"file_path": "...", "snippet": "...", "score": 0.82, ...}
    ],
    "confidence": 0.82,
    "confidence_label": "high",
    "intent": "code",
    "mode": "semantic",
    "related_files": [
        {"file_path": "tests/test_orders.py", "relationship": "tests", "entity": "..."}
    ]
}
```

### Low-confidence search (with suggestions)
```json
{
    "results": [
        {"file_path": "...", "snippet": "...", "score": 0.31, ...}
    ],
    "confidence": 0.31,
    "confidence_label": "low",
    "suggestion": "Results may be incomplete. Consider mode='keyword' or mode='exhaustive' for broader coverage.",
    "suggested_patterns": ["urlpatterns", "path\\(", "re_path\\("],
    "intent": "code",
    "mode": "semantic"
}
```

### Keyword mode (ENUMERATION-biased)
```json
{
    "results": [
        {"file_path": "...", "snippet": "...", "score": 0.65, ...}
    ],
    "total_candidates": 47,
    "confidence": 0.65,
    "confidence_label": "medium",
    "intent": "enumeration",
    "mode": "keyword",
    "suggested_patterns": ["urlpatterns", "path\\("]
}
```

### Exhaustive mode (semantic + grep)
```json
{
    "results": [
        {"file_path": "...", "snippet": "...", "score": 0.82, "source": "semantic", ...},
        {"file_path": "...", "line_content": "...", "source": "grep", ...}
    ],
    "confidence": 0.82,
    "confidence_label": "high",
    "intent": "code",
    "mode": "exhaustive",
    "grep_total": 47,
    "grep_patterns_used": ["urlpatterns", "path\\("]
}
```

---

## File Ownership (Parallel Agent Safety)

| File | Phase 1A | Phase 1B | Phase 2 | Phase 3 |
|------|----------|----------|---------|---------|
| `clew/search/models.py` | A (confidence + related fields) | B (ENUMERATION enum) | — | — |
| `clew/search/engine.py` | A (confidence computation) | — | C (grep wiring) | D (peripheral surfacing) |
| `clew/search/intent.py` | — | B (ENUMERATION keywords) | — | — |
| `clew/search/hybrid.py` | — | B (weighted hybrid mode) | — | — |
| `clew/search/tokenize.py` | — | B (stop-word filtering) | — | — |
| `clew/mcp_server.py` | A (confidence + mode param) | — | — | — |
| `clew/search/grep.py` | — | — | C (new) | — |

**Conflict: `clew/search/models.py` touched by both A and B.** Resolution: Agent A adds confidence fields + `RelatedFile` to `SearchResponse`. Agent B adds `ENUMERATION` to `QueryIntent` enum. Non-overlapping changes. Integration agent merges.

**Sequential dependency: `engine.py`** is modified by A (confidence), then C (grep), then D (peripheral). Integration agent applies in order.

---

## Testing Strategy

- Unit tests per task (TDD: write failing tests first)
- Integration test: full pipeline with ENUMERATION intent on test Qdrant collection
- **Qdrant pruning validation:** Empirical test of sparse query result counts at various limits (Task B.6)
- Confidence scoring test: verify regime-aware thresholds with synthetic score distributions from both RRF and reranker paths
- Grep pattern generation test: verify both query-derived and result-derived patterns
- Grep integration test: mock ripgrep subprocess, verify merge and deduplication
- MCP response test: verify new fields (confidence, mode, related_files, suggested_patterns) in compact and full modes
- **Regression test:** Run V2.3 A1-A4 discovery queries and verify no degradation in standard `mode="semantic"` path
- **C1 scenario test:** Run the actual C1 query ("Django URL patterns for ecommerce views") through the intent classifier and all three modes. Verify that `mode="keyword"` and `mode="exhaustive"` produce better completeness than `mode="semantic"`.

---

## Success Criteria

1. **ENUMERATION intent correctly classified** for "find all X" queries (>90% accuracy on test set of 20+ queries)
2. **Weighted hybrid (70/30) returns more unique results** than standard hybrid for ENUMERATION queries on Evvy codebase
3. **Low-confidence signaling triggers** on C1-type queries in standard semantic mode
4. **Suggested grep patterns are useful** — running them via ripgrep finds results that semantic search missed
5. **`mode="exhaustive"` improves completeness** over `mode="semantic"` on C1/B1 scenario queries
6. **No regression on discovery tasks** — A1-A4 type queries in `mode="semantic"` maintain current quality
7. **All existing tests pass** — V3 changes are additive, no breaking changes to V2.3 behavior
8. **Peripheral surfacing provides non-obvious files** — at least 2/5 related files are not in the primary result set

---

## Consolidation: Prior V3 Proposals

This plan consolidates all V3 proposals from across the codebase:

| Source | Item | Disposition |
|--------|------|-------------|
| V2.3 results roadmap | Exhaustive mode (`--exhaustive`) | Phase 2, `mode="exhaustive"` |
| V2.3 results roadmap | Peripheral code surfacing | Phase 3, Agent D |
| V2.3 results roadmap | Low-confidence signaling | Phase 1, Agent A |
| V2.3 results roadmap | MCP-native evaluation | Deferred — methodology, not feature |
| V2.3 results roadmap | Human evaluation | Deferred — methodology, not feature |
| V2 enrichment design | Dynamic confidence threshold (score-gap) | Incorporated into regime-aware confidence scoring |
| V2 enrichment design | HyDE query reformulation | Deferred to V4+ |
| V2 enrichment design | ColBERT late interaction | Deferred to V4+ |
| V2 enrichment design | Local model support (Ollama) | Deferred to V4+ |
| V2 enrichment design | Weaviate-style query agent | Deferred — consuming LLM agents handle decomposition better |
| Three-layer design | Business layer (blueprint → code) | Deferred to V4+ |
| This session | Query decomposition | **Deferred to V4** — review found keyword heuristics too fragile |
| This session | Grep pattern generation | Phase 2, Agent C |
| This session | Embedding freshness automation | Deferred to V4 |

---

## Review Findings Incorporated

This plan was reviewed by an independent agent (2026-02-18) with industry research. Key changes from the review:

| Finding | Impact | Resolution |
|---------|--------|------------|
| BM25 tokenizer is identifier-matching, not grep | **Critical** | Changed ENUMERATION from BM25-only to weighted hybrid (70/30). Created ADR-005. |
| Intent classifier may miss the actual C1 query | **Critical** | Added explicit `mode` parameter. Automatic classification is convenience, not guarantee. |
| Query decomposition has too many failure modes | **Critical** | Deferred Phase 2 (decomposition) to V4. |
| Confidence scores come from different regimes | **Medium** | Implemented regime-aware scoring: reranker score when available, score-gap otherwise. |
| Qdrant sparse search has pruning behavior | **Medium** | Added Task B.6: empirical pruning validation before finalizing limits. |
| `exhaustive` + ENUMERATION interaction unclear | **Medium** | Specified: `mode` parameter is primary control; takes precedence over intent classification. |
| limit=200 at 300 tokens/chunk = 60K tokens | **Medium** | ENUMERATION responses use compact format (file paths + snippets, not full content). |

---

## Open Questions

1. **Confidence threshold tuning:** The 0.4/0.7 thresholds and 0.05 ambiguity gap are initial guesses. Need to calibrate on real query distributions from Evvy codebase across both RRF and reranker score regimes.
2. **ENUMERATION limit cap:** 200 is initial. Empirical Qdrant pruning validation (Task B.6) will determine the right internal limit. May need higher internal limit (500+) with post-filtering.
3. **Grep pattern quality:** Patterns generated from both query terms and results may be too broad or too narrow. Need empirical testing on C1/B1 scenarios with the Evvy codebase.
4. **Standalone vs MCP priority:** Should `mode="exhaustive"` (grep execution) be available by default or gated behind a config flag? If standalone product is near-term, default. If MCP-only for now, gated.
5. **Peripheral surfacing scope:** How aggressively to surface related files? Cap at 5 files. Need to tune category filters and depth limits against Evvy data.
6. **Framework pattern templates:** How many framework-specific pattern templates (Django URLs, React components, API endpoints) are needed for useful query-derived grep patterns? Start small (Django, React) and expand based on usage.
7. **Sparse index coverage:** What percentage of existing indexed collections have sparse vectors populated? Need a migration path for collections indexed before BM25 was added.
