# ADR-005: BM25 Identifier Matching Is Not Grep — Search Routing and Exhaustive Strategy

**Status:** Accepted
**Date:** 2026-02-18
**Deciders:** Engineering team
**Related:** [ADR-004](./004-code-retrieval-landscape.md), [V3 Plan](../plans/2026-02-18-v3-hybrid-exhaustive-search.md)

---

## Context

V2.3 viability testing showed clew wins 5/8 blind A/B tests against grep-only search but loses on completeness, particularly for exhaustive enumeration tasks (C1: 3.13/5.0, "find all Django URL patterns for ecommerce views"). The V3 plan proposes adding an ENUMERATION intent that routes queries to different search backends based on the query type.

An initial proposal was to route ENUMERATION queries to **sparse-only (BM25) search** in Qdrant, reasoning that Qdrant's sparse index is exact (inverted index, 100% recall) while HNSW dense search is approximate (73-97% recall). The assumption was that BM25-only would behave like grep for code.

**This assumption is wrong.** The distinction is the core of this ADR.

---

## The Fundamental Distinction: Identifier Matching vs Pattern Matching

### Clew's BM25 Tokenizer

Clew's BM25 sparse vectors are built by `clew/search/tokenize.py`, which:

1. Extracts identifiers matching `[a-zA-Z_][a-zA-Z0-9_]*`
2. Splits camelCase/PascalCase/snake_case into sub-tokens (e.g., `getUserById` → `["get", "user", "by", "id"]`)
3. Maps tokens to sparse vector indices via MD5 hash mod 2^31
4. Stores raw term counts; Qdrant applies IDF weighting at query time

**This is an identifier-matching engine, not a general-purpose text search engine.**

### What BM25 Finds vs What Grep Finds

Consider the query: "find all Django URL patterns for ecommerce views"

| Mechanism | How It Processes the Query | What It Matches |
|-----------|---------------------------|-----------------|
| **Clew BM25** | Tokenizes to identifiers: `["find", "all", "django", "url", "patterns", "for", "ecommerce", "views"]`. "find", "all", "for" are noise terms that match many documents. Effective terms: `["django", "url", "patterns", "ecommerce", "views"]` | Documents containing these *identifier tokens* — code that has variables/functions/classes named with these terms |
| **Grep (ripgrep)** | Takes a regex: `urlpatterns\|path\(\|re_path\(` | Every *line of text* matching the pattern, regardless of tokenization, identifier boundaries, or naming conventions |
| **HNSW dense** | Embeds the semantic meaning of the query | Documents *about* URL routing, even if they use different terminology |

### The Critical Gap

BM25 identifier matching misses:
- **Different naming conventions:** `re_path()` tokenizes to `["re", "path"]` while `path()` tokenizes to `["path"]`. A BM25 query for "URL patterns" finds both, but a query for "re_path" won't find `path()` and vice versa.
- **Non-identifier content:** String literals (`"/api/v1/orders/"`), comments, decorator arguments, and configuration values are extracted as identifiers but may not tokenize meaningfully.
- **Framework-specific patterns:** Django's `urlpatterns = [...]` is a list assignment. The identifier `urlpatterns` would match, but a URL registered via `include("ecommerce.urls")` would only match on the string `ecommerce` if it appears as an identifier, not the URL path string.
- **Negation and absence:** "Are there any Stripe API calls?" — BM25 can find documents containing `stripe`, but cannot determine that something is *absent* from the entire codebase.

Grep misses none of these. Grep operates on raw text and matches any pattern regardless of code structure, naming conventions, or tokenization rules.

### The Overlap: Where BM25 and Grep Agree

BM25 identifier matching IS reliable for:
- Finding all uses of a specific function/class name (e.g., `PrescriptionFill`)
- Finding files in a specific module (identifiers from file paths are indexed)
- Finding code using specific imports (import names are identifiers)

For these queries, BM25's exact inverted index provides completeness guarantees comparable to grep for identifiers. But BM25 is a subset of grep's capabilities.

---

## Decision

### 1. ENUMERATION intent routes to weighted hybrid (70/30 BM25/dense), not BM25-only

For queries classified as ENUMERATION, use a biased multi-prefetch:
- BM25 sparse: limit=200 (high, for completeness)
- Dense (semantic): limit=60 (reduced, for catching naming variations)
- Fusion: RRF with BM25 results weighted more heavily

This preserves semantic understanding (catches `re_path` when searching for "URL patterns") while biasing toward identifier completeness.

### 2. Grep integration is the true exhaustive solution, not BM25

The `exhaustive=True` mode (V3 Phase 2) runs ripgrep after semantic search. This is the *real* completeness guarantee. BM25 routing is an improvement over pure HNSW, but it is not grep-equivalent.

### 3. Expose explicit `mode` parameter on MCP search tool

Rather than relying solely on keyword heuristic classification, expose a `mode` parameter:
- `mode="semantic"` (default) — standard hybrid search, best for discovery
- `mode="keyword"` — BM25-biased hybrid, best for identifier-level completeness
- `mode="exhaustive"` — semantic + grep execution, best for true completeness guarantees

The automatic intent classifier can suggest a mode, but the consuming agent (Claude Code, Cursor, etc.) can override it. This addresses the risk of misclassification without removing the convenience of automatic routing.

---

## Rationale

### Why Not BM25-Only?

The GrepRAG paper (arxiv:2601.23254) found only **20-30% overlap** between grep results and semantic results. They find fundamentally different things. Routing ENUMERATION to BM25-only would sacrifice the 70-80% of results that only dense search finds. A weighted hybrid preserves both signal sources while biasing toward completeness.

### Why Not Just Grep for Everything?

Grep is exhaustive but dumb. For "find all Django URL patterns for ecommerce views," grep requires the user (or agent) to already know the patterns to search for (`urlpatterns`, `path(`, `re_path(`, `include(`, etc.). Semantic search understands the *concept* of URL routing and can bridge terminology gaps. The optimal pipeline is: **semantic search identifies WHAT to look for → grep ensures ALL instances are found.**

### Why Expose the Mode Parameter?

The V3 plan review identified that automatic intent classification has significant false positive/negative risk. The actual C1 failing query may have been "Django URL patterns for ecommerce views" (no "find all" keyword), which would not trigger ENUMERATION. An explicit `mode` parameter lets the consuming agent make the right call when it matters, while still providing automatic classification as a convenience.

---

## Consequences

1. **ENUMERATION is not truly exhaustive.** It is "more complete than standard search" but does not guarantee finding every match. The `exhaustive=True` mode (grep integration) is the completeness guarantee.

2. **Three search tiers with clear trade-offs:**
   - Standard (fast, semantic, approximate): best for "understand this code"
   - Keyword-biased (fast, identifier-focused, more complete): best for "find uses of X"
   - Exhaustive (slower, grep + semantic, complete): best for "find ALL instances of X"

3. **The consuming agent controls the trade-off.** Automatic classification is a convenience default, not a guarantee. When precision matters, the agent specifies the mode.

4. **BM25 tokenizer improvements may narrow the gap in future.** Adding stop-word filtering, string literal indexing, or natural language token support could make BM25 more grep-like. But these are V4+ enhancements — V3 accepts the current tokenizer's limitations.

---

## References

- clew BM25 tokenizer: `clew/search/tokenize.py`
- GrepRAG paper: [arxiv:2601.23254](https://arxiv.org/abs/2601.23254)
- Qdrant sparse vector indexing: [Qdrant docs](https://qdrant.tech/documentation/concepts/indexing/)
- Qdrant sparse search pruning: [GitHub issue #3029](https://github.com/qdrant/qdrant/issues/3029)
- V3 plan review: Internal review, 2026-02-18
