# ADR-008: Remove Autonomous Escalation — Ship the Core Engine

**Status:** Accepted
**Date:** 2026-02-24
**Deciders:** Engineering team
**Related:** [ADR-006](./006-agent-tool-design-boundary.md), [ADR-007](./007-autonomous-mode-switching.md), [ADR-005](./005-bm25-identifier-matching-vs-grep.md), [PRODUCT-VISION](../PRODUCT-VISION.md)

---

## Context

ADR-007 established the principle that the engine should autonomously decide when to augment semantic search with grep, removing agent involvement entirely. V4.0 through V4.3 attempted to implement this through confidence-based escalation: when the engine assessed low confidence in semantic results, it would automatically run grep and merge the results.

The principle was correct. The implementation was not achievable.

### Three Calibration Approaches, Three Failures

**V4.0 — Gap ratio (0% escalation):** Used the ratio between top-1 and top-2 reranked scores as a confidence signal. Threshold: gap_ratio > 0.30 = HIGH, > 0.20 = MEDIUM, else LOW. Result: 0/12 queries triggered escalation. The gap ratio never dropped below the MEDIUM threshold because Voyage rerank-2.5 produces tightly clustered scores in the 0.3-0.8 range. The spread between top-1 and top-2 is consistently small regardless of result quality.

**V4.2 — Revised gap ratio with dead code removal (0% escalation):** Attempted to recalibrate thresholds after removing dead ENUMERATION detection code and fixing a reranker variance skip bug. Result: 0/12 queries triggered escalation. The fundamental problem remained — reranked score distributions do not correlate with result quality in a way that a fixed threshold can capture.

**V4.3 — Z-score self-calibrating confidence (64% escalation):** Replaced fixed thresholds with a statistical approach: compute the Z-score of the gap between top-1 and top-2 relative to the distribution of all inter-score gaps. H_THRESHOLD=1.0, M_THRESHOLD=0.0. Result: 64% of queries escalated to grep, far above the 15-25% target. The Z-score approach had two structural problems:

1. **Cross-codebase variance.** Larger codebases (e.g., Evvy with ~5,000 chunks) produce flatter score distributions, yielding systematically lower Z-scores. Evvy mean Z=0.58 vs clew mean Z=1.10. A single threshold cannot work across codebases with different score distribution shapes.

2. **Degenerate cases.** With exactly 5 results (the default limit), if gaps are uniform, std approaches 0 and the formula becomes unstable. When signal_gap equals expected_gap, Z=0.0, which maps to the MEDIUM boundary — the wrong default for a degenerate case.

### V4.1 — The Exception That Proves the Rule

V4.1 shipped successfully (7/12 wins, avg 4.42/5.0) with a 49% escalation rate. But this "success" was misleading: clew was running grep on nearly half of all queries, effectively operating as a grep wrapper with semantic pre-filtering. The 49% rate masked the calibration failure — escalation was happening too often, not at the right times.

### The Structural Problem

The three calibration attempts share a common failure mode: **reranked score distributions are a function of the codebase, not the query.** A codebase with many similar functions (e.g., Django REST viewsets) produces tight score distributions regardless of whether the top result is correct. A codebase with diverse code (e.g., a utility library) produces wide distributions regardless of result quality.

No fixed threshold, ratio, or statistical measure computed from score distributions can reliably distinguish "the engine found the right answer" from "the engine found something similar-looking but wrong" — because the score distribution shape is dominated by corpus characteristics, not retrieval quality.

This is not a tuning problem. It is a structural limitation of threshold-based escalation applied to reranked scores.

### Cross-Version Evidence Summary

| Version | Approach | Escalation Rate | Target | Result |
|---------|----------|----------------|--------|--------|
| V4.0 | Gap ratio (0.30/0.20) | 0% | 15-25% | Never triggers |
| V4.1 | Relaxed thresholds | 49% | 15-25% | Over-triggers |
| V4.2 | Revised gap ratio | 0% | 15-25% | Never triggers |
| V4.3 | Z-score (1.0/0.0) | 64% | 15-25% | Over-triggers |

---

## Decision

**Remove autonomous escalation from the search engine.** Grep augmentation is available only through explicit mode selection (`--mode exhaustive` / `mode="exhaustive"`), not through confidence-based automatic triggering.

The core semantic engine — multi-vector hybrid search, BM25 fusion, reranking, intent classification, terminology expansion, structural boosting — is the product. The autonomous escalation layer was an attempt to make semantic search handle cases it structurally cannot (exhaustive enumeration, pattern matching). Those cases belong to grep, and the decision of when to use grep belongs to the caller (agent or user), not to the engine.

### What Changes

1. **Remove confidence-triggered grep.** The engine no longer evaluates whether to run grep after computing confidence. Confidence scoring (Z-score) is retained as informational metadata in results but does not trigger any autonomous action.

2. **Preserve explicit exhaustive mode.** `--mode exhaustive` and `mode="exhaustive"` continue to work. When the caller explicitly requests exhaustive search, the engine runs grep and merges results. The caller knows when they need completeness; the engine does not.

3. **Add agent skill support.** Provide `/clew-search` and `/clew-trace` agent skills (cookbook patterns) that demonstrate effective combined use of clew semantic search and grep. The agent skill layer is the right place for search strategy composition — it has task context that the engine lacks.

4. **Retain telemetry hooks.** Confidence scores, intent classification, and result counts are logged for future calibration research. If a reliable escalation signal is discovered (e.g., result count heuristic, embedding distance clustering), the infrastructure is ready.

### What Does Not Change

- Multi-vector hybrid search (signature/semantic/body + BM25)
- RRF fusion with structural boosting
- Voyage rerank-2.5 integration
- Intent classification (DEBUG > LOCATION > DOCS > CODE)
- Query enhancement (terminology expansion)
- Relationship graph and trace
- Compact MCP responses
- All 5 MCP tools

---

## Alternatives Rejected

### Continue calibrating thresholds with larger evaluation sets

More data could theoretically reveal a threshold that works across codebases. **Rejected because:** The problem is structural, not statistical. Score distributions are codebase-dependent, and no single threshold can span the range of corpus characteristics. Three fundamentally different approaches (fixed ratio, revised ratio, statistical Z-score) all failed for the same underlying reason. A fourth attempt would face the same structural constraint.

### Per-codebase calibration (run calibration queries after indexing)

Index-time calibration could establish per-codebase thresholds. **Rejected because:** This adds complexity (calibration queries, threshold storage, staleness detection) for a feature whose value proposition is uncertain. V4.1 shipped at 49% escalation and still won 7/12 — but the wins were primarily on queries where clew's semantic search was already strong (vocabulary bridging, structural tracing), not where escalation helped. The cost-benefit ratio is unfavorable.

### Result count heuristic (fewer than N results = low confidence)

If the engine returns fewer than K results above a minimum score, trigger grep. **Rejected for V5 because:** While more promising than score-distribution approaches (result count is somewhat codebase-independent), this has not been tested. It is preserved as a future option with telemetry data to inform the threshold. Shipping an untested heuristic would repeat the V4.0-V4.3 pattern.

### Remove grep integration entirely

Strip all grep code from the engine. **Rejected because:** Explicit exhaustive mode is valuable for power users and agent skills. The grep integration code is tested and functional. Removing it eliminates a useful capability; preserving it as opt-in costs nothing.

---

## Rationale

### The core engine is the value

Across all evaluations (V2.3 through V4.3), clew consistently wins on the same capabilities:

1. **Vocabulary bridging** — "pharmacy API errors" finds `PrecisionAPIClient` (every evaluation)
2. **Structural tracing** — call chains mapped without manual grep+read (B1/B2 in V4.3)
3. **Debugging context** — relevant error handling code surfaced semantically (E4 in V4.3)
4. **Negative proofs** — efficient absence determination ("does this use Stripe?")

These wins occur regardless of escalation calibration. They are properties of the multi-vector search architecture, not of the escalation layer. Removing escalation does not weaken these capabilities.

### Grep and clew are complementary, not competitive

ADR-005 established that BM25 is not grep — they have only 20-30% result overlap. V2.3 established that clew wins on semantic discovery and loses on exhaustive enumeration. These are different tools for different tasks:

- **clew:** Find code by meaning when you don't know identifiers
- **grep:** Find all instances of a known pattern

The "single tool" vision (ADR-007) attempted to make clew handle both. Four versions of calibration attempts proved this is not achievable with current technology. The correct architecture is complementary tools composed at the agent skill layer, not a monolithic tool that tries to be everything.

### Agent skills are the right composition layer

Agent skills (`.claude/commands/`) have task context that the engine lacks. A skill can reason about whether a query needs exhaustive results based on the user's task description, not just score distributions. For example:

- "Find all usages of deprecated API X" — skill routes to grep
- "How does authentication work" — skill routes to clew search
- "What calls this function" — skill routes to clew trace

This is the same architecture Cursor uses (separate `codebase_search` and `grep_search` tools selected by the agent), but with the added benefit of skill-level guidance rather than raw agent decision-making.

---

## Consequences

**(+) Predictable behavior.** The engine always runs semantic search. No hidden grep invocations, no latency surprises, no results that are "half semantic, half grep" without the caller knowing.

**(+) Clearer product identity.** Clew is the semantic discovery layer. Grep is the exhaustive search layer. Together they form a complete toolkit. This is easier to explain, document, and reason about than "clew sometimes runs grep based on opaque confidence thresholds."

**(+) Reduced complexity.** Removing the confidence-to-escalation control flow simplifies the search engine. Fewer code paths, fewer edge cases, fewer things that can miscalibrate.

**(+) Preserved future option.** Confidence scoring and grep integration remain in the codebase. If a reliable escalation signal is discovered through telemetry data, autonomous escalation can be re-enabled without rebuilding infrastructure.

**(-) Agents must choose between tools.** Without autonomous escalation, an agent that needs both semantic and exhaustive results must call both clew and grep. This is the same model Cursor uses, but it does place search strategy decisions back on the agent. Mitigated by agent skills that encode effective search patterns.

**(-) V4.1's "always grep" approach no longer available.** V4.1 won 7/12 partly because 49% escalation meant many queries got grep results. Removing escalation means those queries will rely on semantic search alone. Mitigated by: V4.1's wins were concentrated on semantic-strength queries, not escalation-dependent queries.

---

## References

- V4.0 evaluation: Internal, 2026-02-21 (KILL: 0% escalation, gap ratio never triggers)
- V4.1 evaluation: Internal, 2026-02-22 (SHIP: 49% escalation, 7/12 wins)
- V4.2 evaluation: Internal, 2026-02-22 (KILL: 0% escalation, revised gap ratio)
- V4.3 evaluation: Internal, 2026-02-24 (KILL: 64% escalation, Z-score over-triggers)
- ADR-005 (BM25 is not grep): [005-bm25-identifier-matching-vs-grep.md](./005-bm25-identifier-matching-vs-grep.md)
- ADR-006 (Tool-level intelligence): [006-agent-tool-design-boundary.md](./006-agent-tool-design-boundary.md)
- ADR-007 (Autonomous mode switching): [007-autonomous-mode-switching.md](./007-autonomous-mode-switching.md)
- GrepRAG paper: [arxiv:2601.23254](https://arxiv.org/abs/2601.23254)
