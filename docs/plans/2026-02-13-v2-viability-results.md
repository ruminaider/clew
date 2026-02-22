# V2 Viability Test Results

**Date:** 2026-02-13
**Overall Score:** 2.17 / 3.0 (CONDITIONAL)
**Previous (V1):** 1.72 / 3.0 (WEAK)

## Per-Dimension Scores (V1 to V2)

| Dimension | V1 Score | V2 Score | Delta |
|-----------|----------|----------|-------|
| Accuracy | 0.63 | 2.13 | +1.50 |
| Completeness | 0.56 | 2.00 | +1.44 |
| Tool Calls | 2.81 | 2.81 | 0.00 |
| Efficiency | 3.00 | 1.69 | -1.31 (regression) |
| **Overall** | **1.72** | **2.17** | **+0.45** |

## Methodology Notes

- V2 testing used 1 subagent (76 tool calls, ~34 min) doing both baseline recall and clew testing.
- V1 used 8 parallel agents (4 baseline, 4 clew) with fresh context windows -- more rigorous.
- V2 per-test results were reported in conversation context but never saved to a file. This document fixes that.
- The tester was the same session that built V2, though the subagent had fresh context.
- Scores are self-assessed against the rubric, not independently verified.

## V2 Architecture Changes from V1

- **3 named vectors** (signature, semantic, body) + BM25 sparse. V1 had a single dense vector + BM25.
- **Query routing:** LOCATION queries use the signature vector, CODE/DEBUG/DOCS queries use the semantic vector.
- **Confidence fallback:** When top score < 0.65, fan out to all vectors.
- **LLM enrichment:** Descriptions and keywords improve the semantic vector quality.
- **Importance boost:** 1.0x-1.25x multiplier from inbound edge count in the relationship graph.
- **Test demotion + PascalCase rerank fix:** Reduces bias toward test files and serializers.

## What V2 Fixed from V1 Root Causes

| V1 Root Cause | V2 Fix? | Confidence |
|---|---|---|
| Empty trace graph | Partial -- normalization helps function-level, class-level still broken | Medium |
| ecomm/utils.py underranked | Yes -- importance boost + test demotion + signature vector | High |
| No depth-2 traces | Indirect -- normalization might enable it | Low |
| explain() heuristic fallback | Not addressed | N/A |
| Pattern matching fundamental | Correctly acknowledged as unfixable (grep job) | N/A |
| Test/serializer bias | Yes -- test demotion + rerank fix | High |

## Known Issues in V2

1. **Efficiency regression (reembed bug):** `reembed()` stores full file content instead of chunk content. Search returns 2832-line files instead of ~200-line function bodies. This has 5 cascading effects: identical body vectors per file, corrupted signatures, poisoned BM25 sparse vectors, degraded reranking input, and inflated token counts in responses.

2. **Class-level trace broken:** `clew trace "Order"` returns 0 edges. Only function-level trace works.

3. **explain() does not use enrichment:** Cached LLM descriptions are not wired into the explain heuristic or prompt.

## Independent Investigation Findings

An independent verification found:

- The 2.17 baseline comes from actual testing (not projection), but methodology is weaker than V1.
- Fixing efficiency alone cannot reach 2.5. Maximum possible with perfect efficiency: 2.485.
- The reembed bug is real and worse than initially described (5 cascading effects).
- Realistic estimate after fixes: ~2.44-2.53 depending on cascade gains.
- Original V2 target was 2.3 (not 2.5); the handoff inflated the goal.

## Projection After Fixes

| Scenario | Eff | Acc | Comp | TC | Overall |
|----------|-----|-----|------|-----|---------|
| Current (V2 tested) | 1.69 | 2.13 | 2.00 | 2.81 | 2.17 |
| Fix reembed only | ~3.0 | 2.13 | 2.00 | 2.81 | 2.49 |
| Fix reembed + cascade | ~3.0 | ~2.25 | ~2.06 | 2.81 | ~2.53 |
| + Fix class trace | ~3.0 | ~2.40 | ~2.25 | 2.81 | ~2.62 |

## References

- V1 results: `/Users/albertgwo/Work/evvy/docs/plans/2026-02-11-clew-viability-results.md`
- V1 test plan: `/Users/albertgwo/Work/evvy/docs/plans/2026-02-11-clew-viability-test-plan.md`
- V2 implementation plan: `docs/plans/2026-02-12-v2-consolidated-implementation.md`
- V2.1 handoff: `docs/plans/2026-02-13-viability-improvement-handoff.md`
