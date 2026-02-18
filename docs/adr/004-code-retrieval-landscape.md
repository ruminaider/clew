# ADR-004: Code Retrieval Landscape — Why Clew Exists

**Status:** Accepted
**Date:** 2026-02-12
**Deciders:** Engineering team
**Related:** [ADR-001](./001-qdrant-as-vector-database.md), [ADR-002](./002-build-vs-adopt-claude-context.md), [Three-Layer Knowledge Design](../plans/2026-02-06-three-layer-knowledge-design.md)

---

## Context

Code retrieval — finding the right code to answer a question or complete a task — is a problem every developer tool must solve. The approaches vary widely, and each makes trade-offs that leave specific classes of queries unsolved. This ADR surveys the landscape, identifies what each approach gets right and what it misses, and positions clew at the intersection of capabilities that no single existing tool covers.

The landscape is categorized by retrieval mechanism, not by product, because most products combine multiple mechanisms. What matters is which mechanism is primary and what that implies for capability gaps.

---

## 1. Syntactic Search

**Examples:** Sourcegraph Code Search, GitHub Code Search (Blackbird), Zoekt, ripgrep

**How it works:** Trigram indexes, regex matching, and symbol tables. The user provides an exact pattern (identifier name, regex, structural query) and the system finds all matches. Sourcegraph adds precise code intelligence via SCIP/LSIF — compiler-grade go-to-definition and find-references built from language-specific indexers at build time.

**What it gets right:**
- Exhaustive: finds *every* match, not a ranked sample
- Sub-second latency at massive scale (thousands of repos)
- Precise symbol navigation (SCIP/LSIF) is genuinely superior to anything inferred from static analysis
- Multi-repo search is a solved problem in this paradigm

**What it misses:**
- Requires knowing *what* to search for. "Where is `getUserById` called?" works. "How do we handle expired prescriptions?" doesn't — no code chunk contains that phrase
- No semantic understanding — can't bridge vocabulary gaps between a developer's mental model and the codebase's naming conventions
- No intent awareness — a debugging query and a documentation query return the same results
- Multi-hop reasoning is manual — the developer must chain searches themselves

**Query classes that fail:**
| Query | Why it fails |
|-------|-------------|
| "How do we handle expired prescriptions?" | No identifier matches this natural language |
| "What happens when a subscription cancellation has an active fill in transit?" | Requires chaining concepts across files |
| "What code implements the prescription fulfillment process?" | Business concept doesn't map to any identifier |
| "Show me the authentication flow" | "Flow" is a conceptual query, not a pattern |

---

## 2. Agentic Syntactic Search

**Examples:** Sourcegraph Deep Search

**How it works:** An LLM agent iteratively formulates regex/symbol searches against a syntactic search backend, reads files, follows references via code navigation, and synthesizes a structured answer. The retrieval mechanism is still syntactic search — the intelligence is in the LLM's ability to decompose a natural language question into a sequence of syntactic queries.

**What it gets right:**
- Accepts natural language questions — bridges the vocabulary gap that syntactic search alone cannot
- Can perform multi-hop reasoning by chaining searches
- Produces structured, human-readable answers with citations
- Leverages the exhaustiveness of the underlying syntactic search

**What it misses:**
- **LLM cost per query:** Every question triggers multiple LLM round-trips. When the consumer is itself an LLM agent (e.g., Claude Code), this creates recursive LLM inference — an agent calling an agent calling an agent
- **Latency:** Multiple LLM round-trips per query vs. single-pass vector retrieval (~100-300ms)
- **Not agent-native:** Produces human-readable prose, not structured context optimized for LLM consumption. An AI agent receiving a Deep Search answer must parse prose rather than receiving ranked code chunks with metadata
- **No offline semantic index:** Cannot answer questions without LLM access. Every query requires live LLM inference
- **Sampling, not exhaustive:** The agentic loop samples results rather than returning comprehensive matches — the LLM decides when it has "enough," which may miss relevant code
- **No domain awareness:** Generic — no terminology expansion, no layer classification, no project-specific configuration

---

## 3. Generic Embedding RAG

**Examples:** Cursor (@Codebase), Augment Code Context Engine, claude-context (Zilliz)

**How it works:** Code is split into chunks (via AST or character-based splitting), embedded with a general-purpose or code-specific embedding model, and stored in a vector database. At query time, the question is embedded and nearest-neighbor search finds semantically similar chunks.

**What it gets right:**
- Semantic search works — "authentication middleware" finds auth-related code even if identifiers use different naming
- No LLM cost at query time (after initial indexing)
- Low latency retrieval
- Cursor's privacy model (embeddings in cloud, source code local) is well-designed

**What it misses:**
- **Similarity =/= relevance:** This is the fundamental critique (articulated by both PageIndex and Greptile). Vector similarity finds code that *looks like* the query, not necessarily code that *answers* the query. "Session management code" might retrieve files that mention "management" or "session" in comments rather than the actual session management implementation
- **Code-language gap:** Greptile's research found 12% lower similarity between queries and raw code vs. queries and natural language descriptions of that code. Embedding raw code without description enrichment produces mediocre retrieval quality
- **Generic chunking:** Most tools use one-size-fits-all AST chunking or character-based splitting. No awareness that a Django model should be chunked differently than a React component
- **No structural knowledge:** Finding a function doesn't tell you what calls it, what it imports, or how it fits into the dependency graph. Multi-hop questions require the agent to perform additional searches
- **No keyword precision for identifiers:** Pure embedding search is poor at exact identifier matching. Searching for `getUserById` might return `fetchUserProfile` because they're semantically similar — but the developer wanted the exact function
- **No domain awareness:** No terminology expansion, no layer classification, no project-specific vocabulary
- **Cloud dependency (Cursor):** Cursor sends embeddings through Turbopuffer (cloud). Not viable for air-gapped or privacy-sensitive environments. Augment Code similarly requires cloud infrastructure

**Greptile's key finding:** "Semantic search on codebases works better if you first translate the code to natural language before generating embedding vectors" and "chunk more tightly — on a per-function level rather than a per-file level." This validates two of clew's design decisions (NL descriptions in V1.1, AST-level chunking from V1).

---

## 4. Vectorless Reasoning RAG

**Examples:** PageIndex (VectifyAI)

**How it works:** Documents are organized into a hierarchical JSON tree (like a table of contents) preserving natural structure. At query time, an LLM traverses the tree through multi-step reasoning: reads section titles/summaries, picks the most promising branch, drills down, evaluates if it found enough, loops back if not. No embeddings, no vector database.

**What it gets right:**
- Preserves document structure — no arbitrary chunking that fragments meaning
- Reasoning-based retrieval can find answers that embedding similarity misses (the "similarity =/= relevance" thesis)
- Interpretable — shows exactly which sections answered the query and why
- Can follow cross-references ("see Appendix G") through structural reasoning
- No embedding infrastructure required

**What it misses:**
- **Designed for documents, not code:** A financial report has a table of contents. Code doesn't have a reading order — it has a dependency graph. Functions aren't related by proximity (Section 3 after Section 2) but by imports, calls, and inheritance. A tree is the wrong data structure for code relationships
- **LLM cost per query:** Same recursive inference problem as Deep Search — every question triggers an agentic LLM loop
- **No keyword search:** When a developer searches for `PrescriptionFillOrder`, they need exact identifier matching, not LLM reasoning about which tree branch might contain it
- **No structural edges:** Code entities relate through imports, calls, inheritance, and decorators — cross-tree edges that a hierarchical tree cannot represent. The relationships that matter in code are precisely the ones that break tree structure
- **Scale limitation:** The entire tree index must fit in the LLM's context window. Large codebases (100K+ entities) would exceed context limits or require aggressive summarization

**Where the thesis holds for code:** The "similarity =/= relevance" critique is valid. A vector search for "how do we handle expired prescriptions" might find code mentioning "prescription" and "expired" but miss the actual business logic in a function named `check_fill_status()`. This gap exists in all embedding-based systems and is partially addressed (but not eliminated) by reranking, NL descriptions, and terminology expansion.

---

## 5. Specialized Code Embedding RAG (Clew's Position)

Clew combines techniques from multiple categories while avoiding their specific limitations:

### Addressing the similarity =/= relevance problem

| Technique | How it helps |
|-----------|-------------|
| **NL descriptions (V1.1)** | LLM-generated descriptions prepended to code before embedding. Bridges the code-language gap that Greptile measured at 12%. The description of `check_fill_status()` would include "expired prescriptions," making it retrievable by that query |
| **Hybrid search (dense + BM25)** | Embedding similarity for semantic queries + code-aware BM25 for identifier matching. `getUserById` is found by exact keyword match, "authentication flow" is found by semantic similarity |
| **Code-aware BM25 tokenization** | camelCase and snake_case splitting produces searchable subwords. `getUserById` becomes `[get, user, by, id]`. No other tool in the landscape does this |
| **Reranking (Voyage rerank-2.5)** | Second-pass scoring on the candidate set, which catches cases where embedding similarity ranked the wrong chunk highest |
| **Terminology expansion** | Project-specific vocabulary (abbreviations, domain terms) mapped in YAML. Searching "BV" expands to include "bacterial vaginosis" — pure embedding search would miss this entirely |

### Addressing the structural knowledge gap

| Technique | How it helps |
|-----------|-------------|
| **AST-extracted relationships (V1.2)** | imports, calls, inherits, decorates, renders, tests, calls_api — deterministic edges extracted from the same AST parse used for chunking |
| **`trace` MCP tool** | BFS graph traversal from any entity. "What depends on `Prescription`?" is a single tool call, not a chain of regex searches |
| **Cross-language API boundary tracking** | Frontend `fetch('/api/care/prescriptions/')` linked to backend `PrescriptionViewSet` through URL pattern matching |
| **Structural boosting in search** | Same-module code gets a retrieval boost via Qdrant's multi-stage prefetch. Debug-intent queries automatically include test files |

### Addressing the agent-native gap

| Technique | How it helps |
|-----------|-------------|
| **MCP protocol** | Designed as a tool for AI agents, not a web UI for humans |
| **Compact responses** | ~20x token reduction by default (signature + docstring preview). Agent can request `detail="full"` selectively. No other tool optimizes for the consumer's context window |
| **No LLM cost at query time** | Index once with embeddings + NL descriptions, then retrieve with pure math. The agent doesn't pay LLM inference for retrieval — unlike Deep Search, PageIndex, or any agentic retrieval approach |
| **Intent classification** | Query is classified as DEBUG / LOCATION / DOCS / CODE before search, routing to different prefetch strategies. A debugging query includes test files; a docs query prioritizes markdown |
| **Domain-specific configuration** | Per-file chunking strategies (Django models chunked differently than React components), layer classification (model/view/serializer/task), app-name detection |

### Three-layer knowledge model

No tool in the landscape combines all three layers:

| Layer | What it answers | Clew | Others |
|-------|----------------|------|--------|
| **Semantic** | "What code is *about* this topic?" | Hybrid embedding + BM25 search with NL descriptions | Cursor, Augment (generic embedding only) |
| **Structural** | "What *calls/depends on/imports* what?" | AST-extracted relationship graph with `trace` | Sourcegraph (SCIP/LSIF — more precise but requires build-time indexers) |
| **Business** | "What code *implements* this business process?" | V2 roadmap: blueprint YAML → code entity mapping | No tool attempts this |

---

## Comparative Matrix

| Capability | Sourcegraph Code Search | Sourcegraph Deep Search | Cursor | Augment Code | claude-context | PageIndex | Clew |
|------------|------------------------|------------------------|--------|-------------|----------------|-----------|------|
| Natural language queries | No | Yes (LLM) | Yes (embedding) | Yes (embedding) | Yes (embedding) | Yes (LLM) | Yes (embedding + NL descriptions) |
| Exact identifier search | Yes (regex) | Yes (via regex) | Weak | Weak | Weak | No | Yes (code-aware BM25) |
| No LLM cost at query time | Yes | No | Yes | Yes | Yes | No | Yes |
| Structural navigation | Yes (SCIP/LSIF) | Yes (via code nav) | No | Limited | No | No | Yes (AST relationships + trace) |
| Domain-specific config | No | No | No | No | No | No | Yes (terminology, layers, per-file strategies) |
| Agent-native (MCP) | Partial | No | No | Partial | Yes | Yes (MCP available) | Yes (compact responses, intent routing) |
| Token-efficient responses | N/A | No (prose) | N/A | N/A | No | N/A | Yes (~20x reduction) |
| Self-hosted / local | Enterprise only | Enterprise only | Cloud (Turbopuffer) | Cloud | Self-hosted | Cloud or self-hosted | Self-hosted (1 Docker container) |
| Multi-repo | Yes | Yes | Workspace | Yes (400K+ files) | Single project | Single document | Single project (multi-collection) |

---

## Where Clew is Not the Right Tool

Intellectual honesty requires acknowledging where other tools are superior:

- **Multi-repo search at scale:** Sourcegraph is unmatched for searching across hundreds of repositories in an organization. Clew indexes a single project.
- **Precise code intelligence:** Sourcegraph's SCIP/LSIF provides compiler-grade go-to-definition and find-references. Clew's AST-extracted relationships are heuristic — they catch ~80% of edges but miss dynamic dispatch, dependency injection, and computed method names.
- **Enterprise scale and compliance:** Augment Code's Context Engine processes 400K+ files with ISO/IEC 42001 certification. Clew is a developer tool, not an enterprise platform.
- **Document understanding:** PageIndex excels at long-form documents (financial reports, legal filings). Clew is for source code and adjacent documentation, not arbitrary PDFs.
- **Exhaustive pattern matching:** When you need *every* instance of a pattern across a codebase, syntactic search (Sourcegraph, ripgrep) is the right tool. Clew returns ranked results, not exhaustive matches.

---

## Viability Testing Results (V2.1)

V2.1 viability testing was conducted in February 2026 against a real production Django/React codebase to measure clew's effectiveness against a baseline of standard agent tools (grep, file reading, manual code navigation). The results clarify where clew provides genuine value and where it does not, leading to a sharper positioning of the tool.

### Methodology

A 5-agent team executed the evaluation: 4 tester agents (2 running clew, 2 running baseline grep+read) plus 1 independent scorer agent. The test suite comprised 16 tests across 7 categories:

1. **Semantic search** — natural language queries for functions, business logic
2. **Structural trace** — call chain mapping, dependency analysis
3. **Caller analysis** — finding all callers of a function
4. **Cross-language** — frontend-to-backend API boundary tracing
5. **Exhaustive usage** — finding all uses of a model/pattern
6. **Complex multi-aspect** — queries requiring multiple dimensions of understanding
7. **Vocabulary bridging** — queries using wrong or approximate names

The target codebase contained approximately 13,000 indexed chunks with 10,000+ enriched via LLM-generated descriptions (80% enrichment rate — the remaining 20% are `file_summary` chunks, intentionally skipped).

### Where Clew Excels

**Semantic discovery when you don't know what to grep for.** Test 1.3 searched for "function that checks if all order items can be refilled." Clew returned `can_refill_entire_order` as the top-1 result with score 1.24 and zero false positives. The baseline grep approach required 3 separate calls with 30+ false positives because the word "refill" appears throughout the codebase in unrelated contexts. This is the core value proposition: when the agent starts from a description of *behavior* rather than a known identifier, semantic search dramatically reduces the search space.

**Vocabulary bridging via enrichment.** Test 7.2 searched for `can_fill_all_order_products` — a plausible but incorrect function name. Clew correctly returned `can_refill_entire_order` (the actual name) because the enrichment description bridges the vocabulary gap between "fill all order products" and "refill entire order." Grep would return zero results for the wrong name. This matters in practice because agents working from bug reports, Slack messages, or user stories frequently use approximate terminology that doesn't match the codebase's naming conventions.

**Structural understanding in a single call.** Test 2.1 ran a single `trace` call on `_process_shopify_order_impl` and returned 471 relationships at depth 2, mapping the entire call chain from the Shopify webhook handler through order processing, prescription creation, payment handling, and notification dispatch. The baseline approach required 6+ manual read-and-follow cycles to reconstruct the same understanding. For an AI agent operating under context window constraints, one tool call returning a complete dependency map is qualitatively different from iteratively reading files and guessing which references to follow next.

**Outperforming baseline on complex multi-aspect queries.** Test 6.1 asked about error handling for Shopify order processing. Clew found all 3 aspects: the error path, the retry mechanism, and the monitoring/alerting integration. The baseline found only 2 of 3 — it missed the monitoring integration because there was no obvious grep pattern to find it. Semantic search surfaced it through the enrichment description, which mentioned "error monitoring" even though the code itself used `sentry_sdk.capture_exception`.

**Zero false positive precision on function-level trace.** Test 3.1 asked for all callers of a specific function. Clew trace returned 3/3 callers with zero false positives. Function-level trace is precise because the AST extractor deterministically identifies call sites.

### Where Clew Does Not Replace Existing Tools

**Exact pattern matching is a grep job.** The test "find all `raise ValidationError` in the ecommerce module" is fundamentally a string search. Clew returned semantically similar but noisy results — code that *handles* validation errors, code that *catches* validation errors, configuration related to validation. Grep gave an immediate, definitive, exhaustive answer (in this case: there are none). When the agent knows the exact string pattern it needs, grep is the correct tool and clew adds no value.

**Exhaustive usage counting requires syntactic search.** Test 5.1 asked "who uses PrescriptionFill?" Grep found 58 files containing 499 occurrences — a comprehensive map of every reference. Clew trace found only 1 relationship (a TypeScript import). Model-level trace is weak because the Python extractor does not track ORM usage patterns like `PrescriptionFill.objects.get()`, `PrescriptionFill.objects.filter()`, or foreign key traversals. For "find every place this model is referenced," grep remains the right tool.

**Known-string lookups where grep is already efficient.** When the agent already knows the exact function name `def _process_shopify_order_impl`, grep finds it in 1 call. Clew search also finds it in 1 call. There is no improvement when the query is already a precise identifier — both tools converge to the same result with the same effort.

### Known Structural Limitations

These limitations are architectural and inform the V2+ roadmap:

- **Model/class-level trace is weak.** The Python extractor identifies `imports`, `calls`, `inherits`, and `decorates` relationships but does not track ORM query usage (`Model.objects.get()`, `.filter()`, `.select_related()`). This means `trace("PrescriptionFill")` returns only explicit import and inheritance edges, missing the vast majority of actual usage in a Django codebase.
- **External base class inheritance not tracked.** If a class inherits from a framework base class (e.g., `django.db.models.Model`), that edge is not captured because the extractor only sees the local AST, not installed packages.
- **Entity resolution fragile for generic names.** Searching for "Order" matched a TypeScript import, not the Python Django model. Entity names without module qualification are ambiguous, and the current resolver picks the first match rather than applying language or layer heuristics.
- **Migration files not indexed.** Django migrations contain schema history and are excluded from indexing. This means trace cannot follow the schema evolution path from a model to its migrations.

### When to Use Clew vs. Grep

The viability testing clarifies that clew and grep are complementary tools serving different query classes. The decision matrix:

| Scenario | Best Tool | Why |
|----------|-----------|-----|
| Agent starts from a vague bug report or feature description | Clew search + trace | Semantic matching bridges the vocabulary gap between the report's language and the codebase's naming |
| Agent knows the exact function or class name | Grep | Direct string match, no overhead, exhaustive |
| Understand a feature's full call chain and dependencies | Clew trace | One call replaces 6-10 manual read-and-follow cycles |
| Find all instances of a specific pattern or string | Grep | Exhaustive matching, not ranked sampling |
| Discover related code you didn't know existed | Clew search + trace | Surfaces structural connections and semantically related code across module boundaries |
| Count every usage of a model across the codebase | Grep | Exhaustive reference counting, not approximate ranking |
| Navigate from approximate/wrong function name to correct code | Clew search | Enrichment descriptions bridge vocabulary gaps; grep returns zero results for wrong names |
| Understand how a Django model is actually used (ORM queries) | Grep (for now) | Clew trace does not yet track ORM usage patterns; search can find M2M through-tables but trace is weak on models |

---

## Decision

Clew occupies a specific niche that no existing tool fills: **semantic code retrieval optimized for AI agent consumption, with structural awareness and domain-specific configuration, running locally with no query-time LLM cost.**

The closest alternatives each miss a critical piece:
- Sourcegraph Deep Search: agent-native retrieval without recursive LLM inference
- Cursor/Augment: structural knowledge, domain awareness, identifier precision, self-hosted
- claude-context: search quality (no reranking, no NL descriptions, no code-aware BM25, no domain config)
- PageIndex: code-appropriate data structures (graphs, not trees) and identifier search

V2.1 viability testing confirms that clew's value is **discovery and understanding**, not grep replacement. When an AI agent already knows what to search for — an exact function name, a specific pattern, an identifier — grep is the right tool and clew adds no value over it. Clew's value emerges precisely when the agent *does not* know what to search for: when starting from a natural language description of behavior, when using approximate or wrong terminology, when needing to map an entire call chain from a single entry point, or when exploring unfamiliar code where the agent cannot formulate effective grep patterns. The enrichment pipeline's vocabulary bridging and the trace tool's single-call structural mapping are the two capabilities with no equivalent in the baseline toolkit. Future work should focus on strengthening these differentiators — particularly ORM-aware model tracing and more robust entity resolution — rather than attempting to compete with grep on exhaustive pattern matching.

The three-layer roadmap (semantic → structural → business) extends into territory no current tool is pursuing — mapping business processes to code entities so that agents can understand not just *what code exists* but *why it exists* and *what it implements*.

## References

- [Sourcegraph Deep Search Docs](https://sourcegraph.com/docs/deep-search)
- [Greptile: Codebases are uniquely hard to search semantically](https://www.greptile.com/blog/semantic)
- [PageIndex: Vectorless Reasoning-Based RAG](https://github.com/VectifyAI/PageIndex)
- [How Cursor Indexes Codebases Fast](https://read.engineerscodex.com/p/how-cursor-indexes-codebases-fast)
- [Augment Code Context Engine](https://www.augmentcode.com/)
- [claude-context by Zilliz](https://github.com/zilliztech/claude-context)
