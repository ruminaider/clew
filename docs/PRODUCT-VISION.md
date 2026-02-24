# Clew Product Vision: V1-V5 Trajectory and Path to Beta

**Date:** 2026-02-24
**Status:** Living document -- updated as understanding evolves

---

## What Clew Is

Clew is **the semantic layer for AI agent code discovery.** When an agent doesn't know what to search for -- doesn't know the identifier names, the file structure, the framework patterns -- clew finds the relevant code through semantic understanding.

Clew handles what grep cannot: vocabulary bridging, structural tracing, intent-aware retrieval. Grep handles what clew cannot: exhaustive enumeration, pattern matching, structural completeness. Together, composed through agent skills, they form a complete code discovery toolkit.

**One sentence:** *Clew finds code you didn't know the name of.*

---

## Why Clew Exists

Traditional code search (grep, ripgrep, Sourcegraph) requires you to already know what you're looking for -- exact identifiers, patterns, filenames. But AI agents frequently receive vague tasks:

- *"Find where pharmacy API errors are handled"* -- the agent doesn't know the class is called `PrecisionAPIClient`
- *"What code implements the checkout flow?"* -- the agent doesn't know which files or functions are involved
- *"How does data flow from webhook to prescription?"* -- the agent needs to trace relationships it hasn't seen

Grep cannot solve these problems. You can't grep for something you don't know the name of. Clew bridges the vocabulary gap between natural language intent and code identifiers through semantic embeddings, NL descriptions, terminology expansion, and hybrid retrieval.

Four query classes drove the design:

1. **Multi-hop reasoning** -- "What happens when a subscription cancellation has an active fill in transit?"
2. **Impact analysis** -- "If I change the Prescription model, what else breaks?"
3. **Data flow navigation** -- "How does data flow from Shopify webhook to prescription creation?"
4. **Business-to-code mapping** -- "What code implements the prescription fulfillment process?"

No existing tool solves all four. Clew targets this gap.

---

## The Core Design Principle: Tool-Level Intelligence

> **Tools should be smarter so agents can be simpler.** (ADR-006)

This principle, validated across 6 evaluations and confirmed by industry research, is clew's architectural north star.

### Evidence: Agents Do Not Cooperate With Search Strategy

V3.0 and V3.1 tested the hypothesis that agents would read response-level metadata (confidence labels, mode suggestions, related files) and adjust their search strategy. The result was dispositive:

- `confidence_label`: present in 4/4 outputs, read by agents in **0/4** cases
- `suggestion`: fired in 1/11 searches, agents acted on it in **0/1** cases
- `related_files`: populated in 0/11 searches
- `--mode exhaustive`: available and documented, used by **0/4** agents

Root cause: agents systematically extract the `results` array and discard everything else through rational piping patterns (`| head -100`, `data['results']`). This is not a bug -- it is how agents are designed to efficiently process tool output (see: Anthropic's programmatic tool calling architecture).

### Industry Convergence

No production code search tool surfaces quality metadata to guide agent behavior:

| Tool | Pattern | Agent sees metadata? |
|------|---------|---------------------|
| Cursor | Separate tools (`codebase_search` + `grep_search`) | No -- agent chooses tool |
| Sourcegraph | Two-stage infrastructure (Zoekt + BM25F) | No -- infrastructure decides |
| GitHub Copilot | 13 consolidated tools, embedding-guided routing | No -- system decides |
| **clew V3** | **Response-level metadata** | **Yes, but agents ignored it** |
| **clew V4** | **Autonomous engine decisions** | **No -- engine decides** |
| **clew V5** | **Semantic engine + explicit modes** | **No -- agent skills compose** |

The industry puts intelligence at the tool layer, not the agent layer. V5 extends this insight: the right composition layer is agent skills, not autonomous engine heuristics.

### Consequence: Clew Must Be Excellent at What It Does

Clew's value is semantic discovery -- finding code by meaning when you don't know identifiers. The engine must be excellent at this core capability. Exhaustive search (grep) is a complementary tool, available through explicit mode or agent skills, not an automatic fallback triggered by opaque confidence thresholds.

---

## Version Trajectory: What Each Phase Taught

### Phases 1-3 + V1.1-V1.3: Building the Engine

Built the full stack: AST chunking, 3-vector hybrid search, BM25 tokenization, Qdrant integration, MCP server, CLI, compact responses, relationship graph. 472+ tests, 92% coverage. Solid infrastructure with no structural issues.

### V2.x: Finding the Value (Ship at V2.3)

**Breakthrough:** Multi-vector architecture (signature/semantic/body) + entity resolution + terminology expansion. V2.3 shipped with 5/8 wins.

**Key finding:** Clew wins on **semantic discovery** (finding `PrecisionAPIClient` from "pharmacy API errors") and loses on **exhaustive enumeration** (grep will always find every instance of a pattern). This is the fundamental axis -- clew and grep are complementary, not competitive.

### V3.x: The Metadata Hypothesis (Kill)

**Bet:** Surface confidence labels, mode suggestions, and related files so agents use them to refine search strategy.

**Falsification:** 0/4 agents read metadata. 0/4 agents changed behavior. The metadata-guidance strategy is fundamentally dead. See ADR-006 for full evidence.

**Lesson:** Agents are result consumers, not search strategists. This is clew's most important finding.

### V4.x: Autonomous Escalation (Ship at V4.1, Kill at V4.2-V4.3)

**Pivot:** Instead of asking agents to choose modes, the engine decides autonomously. Low confidence triggers auto-grep. No agent involvement needed.

**V4.1 shipped** (7/12 wins, avg 4.42/5.0) but with 49% escalation rate -- nearly half of all queries ran grep, diluting clew's identity.

**V4.2 and V4.3 tried to fix calibration** with revised gap ratios and Z-score self-calibration. Both failed: V4.2 at 0% escalation (never triggers), V4.3 at 64% (over-triggers). Three fundamentally different threshold approaches all failed because reranked score distributions are codebase-dependent, not query-dependent. See ADR-008 for full analysis.

**Lesson:** Threshold-based autonomous escalation is structurally unsolvable across codebases. The engine cannot reliably determine when it needs grep from score distributions alone.

### V5: Ship the Core Engine

**Pivot:** Remove autonomous escalation. The core semantic engine is the product. Grep is available through explicit mode (`--mode exhaustive`) and agent skills. Confidence scoring is informational, not a trigger.

**Key insight:** Clew and grep are complementary tools that should be composed at the agent skill layer, not fused inside the engine through unreliable confidence heuristics.

---

## What Clew Does Well (Validated Across All Evaluations)

**Consistently wins on:**

1. **Vocabulary bridging** -- "pharmacy API errors" finds `PrecisionAPIClient` (agents don't know identifier names)
2. **Semantic discovery** -- "how does checkout work?" finds relevant code with no keyword overlap
3. **Structural tracing** -- `trace` tool maps call chains without manual grep + read cycles
4. **Negative proofs** -- "does this codebase use Stripe?" finds efficient determination of absence
5. **Cross-vocabulary questions** -- business language maps to code identifiers

**Consistently loses on:**

1. **Exhaustive enumeration** -- "find ALL instances of X" (grep is provably complete; BM25 is not grep, see ADR-005)
2. **Pattern matching** -- "find all `raise CustomError`" (literal text, not semantic)
3. **Structural completeness** -- grep finds things in comments, strings, configs that BM25 misses

The losses are structural -- they stem from the fundamental difference between semantic similarity (ranked, approximate) and pattern matching (exhaustive, exact). These losses are addressed through explicit exhaustive mode and agent skills, not by trying to make semantic search exhaustive.

---

## Cross-Version Evaluation Data

| Version | Clew Avg | Grep Avg | Win Rate | Esc Rate | Verdict | Key Change |
|---------|----------|----------|----------|----------|---------|------------|
| V2.3 | 3.96 | 3.98 | 5/8 (63%) | N/A | **Ship** | Entity resolution fix |
| V3.0 | 3.84 | 3.97 | 3/8 (38%) | N/A | Kill | Features invisible to agents |
| V4.0 | 3.69 | 3.86 | 5/12 (42%) | 0% | Kill | Gap ratio: never triggers |
| V4.1 | 4.42 | 4.33 | 7/12 (58%) | 49% | **Ship** | Relaxed thresholds |
| V4.2 | 3.34 | 3.10 | 5/12 (42%) | 0% | Kill | Revised gap ratio: never triggers |
| V4.3 | 3.12 | 3.19 | 5/12 (42%) | 64% | Kill | Z-score: over-triggers |

**Evaluation methodology limitation:** The blind A/B approach with 8-12 tests has a noise floor of ~46%. Agent variance (different exploration strategies per run) dominates tool-quality signal. The methodology can distinguish large differences but not incremental improvements.

---

## Architecture: How the Engine Works

```
Agent calls: clew search "query"
              |
              v
  +--- Query Enhancement -----------+
  |  Terminology expansion           |
  |  (abbreviations + synonyms)      |
  +--------------+-------------------+
              |
              v
  +--- Intent Classification --------+
  |  DEBUG > LOCATION > DOCS > CODE  |
  |  Routes to appropriate vector(s) |
  +--------------+-------------------+
              |
              v
  +--- Hybrid Search ----------------+
  |  3 named vectors (sig/sem/body)  |
  |  + BM25 sparse                   |
  |  + structural boost (same app)   |
  |  + RRF fusion                    |
  +--------------+-------------------+
              |
              v
  +--- Reranking (Voyage 2.5) -------+
  |  Calibrated 0-1 relevance scores |
  |  Skip if <10 candidates or       |
  |  top_score > 0.92                 |
  +--------------+-------------------+
              |
              v
  +--- Confidence Assessment --------+
  |  Z-score: informational only     |
  |  Included in results metadata    |
  |  Does NOT trigger grep           |
  +--------------+-------------------+
              |
              v
  +--- Result Enrichment ------------+
  |  Relationship context per-result  |
  |  (callers, imports, tests)        |
  +--------------+-------------------+
              |
              v
        Agent receives results

  Explicit Exhaustive Mode:

  Agent calls: clew search "query" --mode exhaustive
              |
              v
        [Same pipeline as above]
              +
        [Grep runs in parallel]
              |
              v
        [Results merged + deduplicated]
              |
              v
        Agent receives combined results
```

Key infrastructure:
- **3 named vectors:** signature (1024-dim), semantic (1024-dim), body (1024-dim) + BM25 sparse
- **Two SQLite DBs:** `cache.db` (embeddings, descriptions, enrichment) and `state.db` (relationships, index state)
- **Qdrant:** Multi-stage filtered prefetch with server-side RRF fusion
- **Voyage AI:** voyage-code-3 embeddings + rerank-2.5 for calibrated relevance scoring

---

## Lessons Learned (Proven Across V1-V5)

### 1. Agent-Tool Communication Boundary

- Response-level metadata is invisible to agents (piped away)
- Result-level enrichment survives piping (agents iterate over results)
- Protocol signals (`isError`) influence behavior; sidecar metadata does not
- Tools should be smarter so agents can be simpler

### 2. BM25 Is Not Grep (ADR-005)

- Clew's BM25 extracts CODE IDENTIFIERS only (`[a-zA-Z_][a-zA-Z0-9_]*`)
- Splits camelCase/snake_case, applies IDF weighting
- Misses: string literals, framework patterns, naming convention variations, negation/absence
- BM25 and grep have only 20-30% result overlap (GrepRAG paper)
- Grep integration is the real completeness guarantee, not BM25 tuning

### 3. Keyword Heuristics Don't Match Agent Queries

- ENUMERATION auto-detection: 0/45 agent queries matched in V4.1
- Agents rephrase "find all X" into semantic queries ("Celery task decorator patterns")
- Intent classification must be robust to agent rephrasing, not dependent on imperative phrasing

### 4. Autonomous Decisions Beat Agent Cooperation -- But Have Limits

- V3 (metadata guidance) -> 0% agent cooperation
- V4 (autonomous escalation) -> features fire without agent involvement
- But: autonomous escalation calibration is unsolvable cross-codebase (ADR-008)
- The right composition layer is agent skills, not engine heuristics

### 5. Threshold-Based Escalation Is Structurally Unsolvable

- Gap ratio (V4.0): 0% escalation -- reranked scores too tightly clustered
- Revised gap ratio (V4.2): 0% escalation -- same structural issue
- Z-score (V4.3): 64% escalation -- codebase-dependent distributions
- Score distributions reflect corpus characteristics, not retrieval quality
- Three fundamentally different approaches, same structural failure

### 6. Evaluation Methodology Matters

- Self-assessed evaluations (V2) overestimate quality
- Strict independent evaluation (V2.1) showed V2 baseline was weaker than thought
- Blind A/B with 8-12 tests has ~46% noise floor -- good for large deltas, not incremental improvements
- Need new metrics: discovery hit rate, grep reduction, time-to-first-relevant-file

---

## Known Structural Limitations

1. **Model/class-level trace broken** -- Python extractor doesn't track ORM usage; `trace` fails on Django model relationships
2. **ENUMERATION detection dead** -- 0/45 matches; agents rephrase queries; keyword heuristics fundamentally flawed
3. **Evaluation ceiling** -- Blind A/B methodology cannot measure incremental improvements at current quality level

---

## Path to Beta: Clew as the Semantic Discovery Layer

### What Beta Means

A shippable beta for Claude Code agents where clew is the **semantic discovery layer** -- the tool agents call when they need to find code by meaning, not by name. Complemented by grep for exhaustive search and pattern matching, composed through agent skills for seamless discovery workflows.

### Must-Have (Correctness)

1. **Working relationship graph** -- `trace` is valuable but model-level tracing is broken. Fix the Python extractor to track ORM usage (Django models -> queries -> views).

2. **Remove dead code** -- ENUMERATION auto-detection (0% activation across 45 queries), response-level metadata suggestions (0% read rate). Ship what works.

3. **Clean separation of concerns** -- Semantic search does semantic search. Grep does exhaustive search. Agent skills compose them. No blurring of boundaries.

### Must-Have (Agent Ergonomics)

4. **Result-level enrichment only** -- Everything the agent needs must be inside each result object. Response-level fields are invisible. No exceptions.

5. **Clean MCP interface** -- 5 tools (search, get_context, explain, trace, index_status) with compact defaults. Already done and working.

6. **Reliable installation** -- `pip install clew` + `docker compose up qdrant` + `clew index` must Just Work. Error messages must tell the user how to fix the problem.

7. **Agent skills** -- `/clew-search` and `/clew-trace` skills that demonstrate effective combined use of clew and grep for common discovery patterns.

### Should-Have (Polish)

8. **Index freshness detection** -- Auto-detect stale index (commits since last index) and surface in `index_status`.

9. **Better evaluation methodology** -- Move beyond blind A/B to: discovery hit rate (>70% first-query relevance), grep reduction (30-50% fewer grep calls in clew sessions), time-to-first-relevant-file.

10. **Telemetry for future calibration** -- Log confidence scores, intent classifications, and result counts so future escalation approaches (if any) have real data to calibrate against.

11. **Multi-language extractor maturity** -- Python extractor is solid; TypeScript exists but less mature. Consider Go, Rust, Java for broader adoption.

### Won't-Have (Future Scope)

12. Business layer (blueprint YAML -> code mapping) -- V2+ roadmap
13. Multi-repo search
14. Incremental real-time indexing
15. Custom embedding model fine-tuning

### Success Criteria

Clew beta ships when:

- **Discovery hit rate >70%** -- First `clew search` call returns at least one relevant result 70%+ of the time
- **Zero dead features** -- Every feature in the codebase activates in production use
- **Agent-ergonomic** -- Agents call clew for semantic discovery, grep for exhaustive search, skills for composed workflows
- **Predictable behavior** -- No hidden mode switching, no surprise grep invocations, no opaque confidence triggers

---

## The Product Identity

Clew is the semantic layer for AI agent code discovery. It answers the question every agent asks when it lands in an unfamiliar codebase:

> *"Where do I even start?"*

Grep answers a different question: *"Where is every instance of this specific thing?"*

Both questions matter. Both tools are needed. Clew handles the first. Grep handles the second. Agent skills compose them into seamless discovery workflows.

That's the product. Everything else -- vectors, reranking, relationship graphs, compact responses -- is implementation detail in service of semantic discovery.
