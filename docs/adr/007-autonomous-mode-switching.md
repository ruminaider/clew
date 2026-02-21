# ADR-007: Autonomous Mode Switching Over Metadata Guidance

**Status:** Accepted
**Date:** 2026-02-20
**Deciders:** Engineering team
**Related:** [ADR-005](./005-bm25-identifier-matching-vs-grep.md), [V3 Plan](../plans/2026-02-18-v3-hybrid-exhaustive-search.md), [V3 Alternative Tactics](../plans/2026-02-20-v3-alternative-tactics.md)

---

## Context

V3 added substantial infrastructure on top of the V2 search engine: confidence scoring, ENUMERATION intent detection, grep integration, pattern generation, and peripheral surfacing (719 tests, ~2,200 lines). These features work correctly and are well-tested. The problem was delivery: V3 expected agents to cooperate.

**V3.0 delivery mechanism:** Features were implemented but not wired to CLI/MCP output. The `--mode exhaustive` flag existed, but 0/4 agents in the V3.0 evaluation used it despite the intent classifier correctly routing their queries to ENUMERATION internally.

**V3.1 delivery mechanism:** Metadata was surfaced in JSON output — `confidence_label`, `suggestion`, `related_files` as top-level fields, `suggested_patterns` in the response. Despite being visible, 0/4 agents reacted to any metadata field. Agents follow a fixed extraction pattern:

```python
# Typical agent behavior (observed in transcripts)
data = json.loads(output)
for r in data["results"]:
    print(r["file_path"])
```

Top-level fields outside `results` are systematically discarded. This is not an implementation bug — it is the expected behavior of agents optimized to extract actionable information (file paths, snippets) from tool output.

**Two failure modes confirmed:**

1. **V3.0 failure (agent never sees metadata):** Features implemented internally but not exposed; agent passes `--mode` flag that never gets used.
2. **V3.1 failure (agent sees metadata but doesn't act):** Metadata visible in JSON, but agents extract `results` array and ignore all surrounding context.

**The metadata-guidance strategy is fundamentally dead.** The evidence (0/4 agent behavior changes across both evaluations, despite metadata being syntactically present and visible) is dispositive. Any design that relies on agents reading and reacting to sidecar metadata fields — confidence labels, suggestions, related files, pattern hints — will fail for the same reason V3 failed.

**The calibration problem compounds this.** In V3.1, 10/11 searches returned `confidence_label: "high"`, meaning the `suggestion` field fired only once. Even when the metadata-guidance approach was structurally sound, the confidence thresholds were miscalibrated to a degree that most queries never generated actionable metadata.

---

## Decision

**The engine decides autonomously when to augment semantic search with grep.** The agent calls `clew search "query"` and receives results. The engine's internal decisions are invisible to the agent and require no cooperation.

### Trigger conditions

The engine internally triggers grep augmentation when:

**(a) Intent is ENUMERATION** — Any query classified as ENUMERATION ("find all X", "list all Y", "every instance of Z") gets grep augmentation automatically. ENUMERATION queries require completeness guarantees; semantic search alone cannot provide them (see ADR-005). Grep runs concurrently with semantic search, launched immediately after intent classification, so best-case latency impact is zero.

**(b) Confidence is low** — When `suggestion_type == SuggestionType.TRY_EXHAUSTIVE` and `project_root` is available, the engine runs grep after confidence computation. This handles cases where semantic search returns uncertain results for non-ENUMERATION queries.

### The `--mode` parameter is preserved as a hard-floor override

If the caller explicitly passes `mode="exhaustive"` or `--mode exhaustive`, the engine respects it unconditionally. Explicit user intent overrides autonomous decisions. The default (no mode specified) means the engine decides.

This preserves backward compatibility and allows power users and tests to force specific modes.

### Implementation: ~50 lines net, reorganization of existing code

The V3 computation infrastructure is preserved entirely. The change is in control flow:

**Before:**
```
agent passes --mode exhaustive  →  engine runs grep
                                   (never happened: 0/4 agents used --mode)
```

**After:**
```
engine classifies intent  →  if ENUMERATION: launch grep concurrently
engine computes confidence  →  if TRY_EXHAUSTIVE: run grep after semantic results
engine merges results  →  agent receives combined results
```

Concretely:

1. Add `project_root: Path | None = None` parameter to `SearchEngine.__init__()`
2. After confidence computation in `search()`, call `_should_augment_with_grep(intent, suggestion_type)`
3. If triggered, call `search_with_grep()` and merge results into `SearchResponse`
4. Remove manual exhaustive handling from `cli.py` (~-15 lines) and `mcp_server.py` (~-10 lines)
5. Recalibrate `confidence_high_threshold_reranked` from 0.7 to ~0.5 to fix the calibration problem observed in V3.1

---

## Alternatives Rejected

### Structured warnings in results array

Insert synthetic warning objects at position 0 of `results` when confidence is low.

**Rejected because:** Agents assume uniform result format and extract `file_path` and `line_start` from every result. A warning object without these fields causes extraction patterns to fail silently (producing `None`) or error out. This trades "agents ignore top-level metadata" for "agents crash or get confused by malformed results" — a worse failure mode. The fact that the warning is inside the `results` array does not make it more visible to agents; it makes it more destructive.

### Two-phase response

First call returns a search plan; second call executes it.

**Rejected because:** This reintroduces the agent cooperation problem in a more fragile form. The agent must read the plan response, recognize it as a plan rather than results, and explicitly call a follow-up tool. Based on V3.1 evidence, agents do not parse metadata from tool responses and adapt their behavior. If the agent ignores the plan and treats the first response as the final answer, the user receives zero results — worse than V3's current behavior of returning semantic results without grep augmentation.

### MCP `isError` for low-confidence results

Return `CallToolResult(isError=True)` when confidence is low, causing Claude Code to treat the search as an error and potentially retry with different parameters.

**Rejected because:** A search that returns uncertain results is not an error — it is a successful search with uncertain results. Abusing `isError` causes the agent to report "search failed" to the user and may trigger retries with the same query. Additionally, `isError` is an MCP protocol concept with no CLI equivalent, creating split behavior between `clew search --json` and MCP tool usage. Confidence signals are a search quality matter, not a protocol error.

### Separate MCP tools (clew_semantic + clew_exhaustive)

Expose two distinct MCP tools with different behavior, letting agents choose based on task context.

**Rejected because:** This requires agents to learn clew's tool taxonomy — specifically, that "find all X" queries need `clew_exhaustive` rather than `clew_semantic`. V3.0 showed that agents do not adapt their tool selection based on query type even when the `--mode` flag is documented and available. Higher-friction tool selection (must use a different tool name entirely) is unlikely to succeed where lower-friction mode selection (pass `--mode` flag) failed. The two-tool design also increases MCP schema complexity without improving outcomes.

---

## Rationale

### Why autonomous action survives agent piping

The critical advantage of autonomous mode switching is that it delivers improvements through the mechanism agents already use: the `results` array. The agent extracts file paths and snippets. Autonomous grep augmentation means the results array contains better, more complete results — the agent's extraction pattern produces better outputs without any behavioral change on its part.

This is the fundamental distinction from all rejected alternatives. Every rejected approach attempted to use a side channel (top-level metadata, warning objects, isError flags, separate tools) to guide agent behavior. Every side channel fails because agents are consumers of results, not collaborators in search strategy.

### Why the V3 computation infrastructure is worth preserving

The KILL verdict on V3 was based on the delivery mechanism failing, not the computation being wrong. The confidence scoring, ENUMERATION intent classification, pattern generation, and grep integration all work correctly. Discarding ~2,200 lines of functional code because the delivery mechanism was wrong would be a category error. The right response is to change the delivery mechanism while preserving the computation.

Autonomous mode switching is approximately 20 lines of control flow change in `engine.py`. The remaining V3 code — `grep.py` (310 lines), `intent.py` (131 lines), `engine.py` confidence scoring (44 lines) — is preserved and used.

### Why concurrent grep for ENUMERATION adds minimal latency

For ENUMERATION queries, grep is launched immediately after intent classification, running concurrently with semantic search (dense vector retrieval + reranking). On a typical project with a warm file system cache, ripgrep completes in 200-500ms. Voyage AI reranking takes 300-800ms. In the best case, grep completes before reranking finishes and the merge step is free. In the worst case, grep adds ~300ms to a 1.5s pipeline.

For confidence-triggered escalation (non-ENUMERATION queries where confidence turns out to be low), grep runs sequentially after confidence computation. This adds 1-5 seconds. This is the acceptable trade-off: queries that genuinely need more complete results get them, at the cost of latency that is disclosed to the user via the result count (more results than a pure semantic search would return).

---

## Consequences

**(+) Completeness guarantee for ENUMERATION queries without any agent involvement.** "Find all error handlers," "list all Django URL patterns," "every place we call the Stripe API" — these queries now automatically augment semantic search with grep. The agent gets complete results by doing nothing differently.

**(+) ~50 lines of net changes on ~2,200 lines of V3 code.** The computation infrastructure is reused entirely. This is the highest-leverage path from V3's current state to a functioning completeness story.

**(+) Result-level enrichment can be implemented alongside this change.** Embedding relationship context (callers, tests, inheritance) directly into each result's `related` field survives agent piping for the same reason autonomous grep does: agents read the results array. This is a supplementary improvement using the same architectural insight.

**(-) 1-5 second latency for confidence-escalated queries.** Mitigated by: (1) concurrent grep for ENUMERATION queries minimizes latency for the most common case; (2) escalation only triggers for `TRY_EXHAUSTIVE` queries, which are a subset of all searches; (3) the added latency is justified by the completeness improvement for these specific queries.

**(-) Confidence thresholds require empirical calibration.** V3.1 showed that 10/11 searches returned "high" confidence with the current threshold of 0.7, meaning the confidence-triggered escalation path effectively never fires. Lowering the threshold to ~0.5 is required for the escalation path to work. The correct threshold is an empirical question that depends on the score distribution for the target project; this calibration is deferred to post-implementation testing.

**(-) Project root must be available to the engine.** The engine currently does not know the project root (required for grep). The MCP server already has `_get_project_root()` which detects from git. This detection logic must be accessible to `SearchEngine`, either passed as a parameter at construction time or derived from the config. This is a wiring change, not an architectural problem.

---

## References

- Clew grep integration: `clew/search/grep.py`
- Clew intent classification: `clew/search/intent.py`
- Clew confidence scoring: `clew/search/engine.py:194-237`
- GrepRAG paper: [arxiv:2601.23254](https://arxiv.org/abs/2601.23254) (20-30% overlap between grep and semantic results)
- V3.0 evaluation results: Internal, 2026-02-19 (KILL: 3.84 clew vs 3.97 grep; 0/4 agents used --mode)
- V3.1 evaluation results: Internal, 2026-02-19 (KILL: 0/4 agent behavior changes despite metadata visible)
- V3 alternative tactics analysis: [docs/plans/2026-02-20-v3-alternative-tactics.md](../plans/2026-02-20-v3-alternative-tactics.md)
- ADR-005 (BM25 is not grep): [005-bm25-identifier-matching-vs-grep.md](./005-bm25-identifier-matching-vs-grep.md)
