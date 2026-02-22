# V4 Calibration Analysis

**Date:** 2026-02-21
**Queries:** 30 (10 Semantic, 8 Location, 7 Enumeration, 5 Borderline)
**Target codebase:** Evvy (12,087 chunks indexed)

---

## Key Findings

### 1. Reranking Is Systematically Skipped

The Voyage reranker is configured and API key is available, but `should_skip_rerank()` returns True for all queries because `score_variance < low_variance_threshold (0.1)`. Hybrid search RRF scores have variance ~0.001-0.01, always below 0.1.

**Impact:** All confidence scoring goes through the RRF path (score gap between 5th and 6th result). The reranked thresholds (0.7/0.4) never apply. The reranker is wired but dormant.

**Recommendation:** Out of scope for V4 evaluation. Fixing `low_variance_threshold` would change the entire confidence regime and requires its own calibration cycle.

### 2. ENUMERATION Detection: Perfect (7/7)

All 7 Category C queries correctly classified as ENUMERATION intent and triggered concurrent grep. This is the primary V4 mechanism and works exactly as designed.

| Query | Intent | Grep Results | Correct |
|-------|--------|-------------|---------|
| C01: find all Django URL patterns | enumeration | 2,594 | Yes |
| C02: list all Celery tasks with retry | enumeration | 3,674 | Yes |
| C03: find all API endpoints + auth | enumeration | 2,638 | Yes |
| C04: list all models + TimeStampedModel | enumeration | 9,397 | Yes |
| C05: find all uses of Stripe API | enumeration | 3,025 | Yes |
| C06: enumerate all serializer classes | enumeration | 1,721 | Yes |
| C07: find all instances custom middleware | enumeration | 1,814 | Yes |

### 3. Post-Hoc Escalation: Rare and Noisy

Only 1/23 non-ENUMERATION queries (A09) triggered post-hoc grep. The escalation produced **11,284 grep results** — catastrophic noise. The query "what is the data flow from shopify webhook to internal processing" triggered framework patterns for "webhook" and "api" that matched thousands of files.

**Root cause:** `grep_response_cap = 100` is defined in SearchConfig but never enforced in `_merge_grep_results()`. All grep results are merged without limit.

### 4. Confidence Distribution (Non-ENUM, RRF Path)

Confidence = score gap between 5th and 6th result (how well top-5 separates from rest).

| Range | Count | Label | Queries |
|-------|-------|-------|---------|
| < 0.005 | 1 | low | A09 (0.0001) |
| 0.005-0.01 | 0 | low | — |
| 0.01-0.02 | 2 | medium | D05 (0.014), B04 (0.015) |
| 0.02-0.03 | 4 | medium | B03, A03, B02, B05 |
| 0.03-0.05 | 3 | high | A05, B07, A06 |
| 0.05-0.10 | 5 | high | A08, B08, D01, D03, B01 |
| 0.10-0.20 | 8 | high | D04, A01, A10, A07, B06, A04, A02 |

Natural gap at 0.02: below this, results have flat distributions (5th and 6th nearly identical scores). Above this, there's meaningful separation.

---

## Proposed Thresholds

### Changes

| Threshold | Current | Proposed | Rationale |
|-----------|---------|----------|-----------|
| `confidence_high_threshold_rrf` | 0.03 | 0.06 | More selective "high" label; natural break in distribution at ~0.05 |
| `confidence_medium_threshold_rrf` | 0.01 | 0.02 | Pushes genuinely flat distributions (B04, D05) into escalation zone |
| `confidence_high_threshold_reranked` | 0.7 | 0.7 | Unchanged (dormant due to reranking skip) |
| `confidence_medium_threshold_reranked` | 0.4 | 0.4 | Unchanged (dormant) |
| `ambiguity_threshold` | 0.05 | 0.05 | Unchanged |

### Expected Behavior with Proposed Thresholds

| Category | Total | High | Medium | Low (escalated) | Target | Result |
|----------|-------|------|--------|-----------------|--------|--------|
| A: Semantic | 10 | 7 | 2 | 1 (A09) | false <=1 | PASS |
| B: Location | 8 | 3 | 4 | 1 (B04) | triggers <=2 | PASS |
| C: Enumeration | 7 | — | — | — (all via ENUM) | 7/7 | PASS |
| D: Borderline | 5 | 3 | 1 | 1 (D05) | triggers 3-5 | PARTIAL |
| **Non-ENUM total** | **23** | **13** | **7** | **3 (13%)** | **20-30%** | **BELOW** |

### Deviation from Plan Target

The plan targeted 20-30% non-ENUM escalation. Actual: 13%. Achieving 20%+ requires `confidence_medium_threshold_rrf >= 0.022`, which would push A03 ("what happens when payment fails") into escalation — an A-category false positive.

**Why this is acceptable:**
1. ENUMERATION intent is the primary V4 mechanism (7/7 perfect)
2. Post-hoc escalation is inherently noisy (A09 produced 11k results)
3. The confidence metric (5th-6th score gap) measures cluster separation, not search quality
4. A flat tail (low gap) often means many decent results, not no good results
5. Higher escalation rates would increase noise without proportional benefit

### grep_response_cap Enforcement (Fix)

Add cap enforcement to `_merge_grep_results()` in the search engine:
- Cap merged grep results at `grep_response_cap` (default 100)
- Prevents catastrophic cases like A09 (11k results → 100 max)
- Already defined in SearchConfig, just not enforced

---

## Validation Run

After applying proposed thresholds, re-run calibration to verify.

### Expected Results

- Cat A: 1 escalation (A09 at 0.0001 << 0.02)
- Cat B: 1 escalation (B04 at 0.0146 < 0.02)
- Cat C: 7/7 via ENUMERATION (unaffected by RRF thresholds)
- Cat D: 1 escalation (D05 at 0.0143 < 0.02)
- B03 (0.0205 >= 0.02): now medium, not low — correct, "Order model" is a specific lookup
- B02 (0.0215 >= 0.02): now medium, not low — correct, specific function name
- Non-ENUM escalation: 3/23 = 13%

### Escalation Quality Assessment

| Query | Confidence | Escalation Benefit |
|-------|-----------|-------------------|
| A09: shopify webhook data flow | 0.0001 | Low — semantic results were good (top score 1.15), grep adds noise |
| B04: checkout source field | 0.0146 | Medium — grep can find exact field declaration |
| D05: third-party service config | 0.0143 | Medium — grep can find config patterns across the codebase |

---

## Additional Observations

### D03 Near-Miss: "all places where we send email notifications"

D03 was NOT classified as ENUMERATION despite containing "all places." The ENUMERATION_PHRASES list requires exact phrase matches like "find all", "list all", "all instances" — "all places" is not in the list. This is intentional (too broad a match would over-trigger), but worth noting as a gap.

### Reranking Skip Issue (Future Work)

The `low_variance_threshold = 0.1` in `should_skip_rerank()` effectively disables reranking for all hybrid search results. Hybrid/RRF score variance is always << 0.1. If reranking were enabled:
- Confidence would use top reranked score (0.4-0.9 range)
- The reranked thresholds (0.7/0.4) would provide better calibrated labels
- But this changes behavior significantly and requires its own testing

This is deferred to post-V4 evaluation.
