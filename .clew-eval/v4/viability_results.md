# V4 Viability Evaluation Results

**Date:** 2026-02-21
**Verdict: KILL**
**Clew Average:** 3.69/5.0
**Grep Average:** 3.86/5.0
**Win/Loss:** 5 clew / 6 grep / 1 tie (12 tests)

**Previous:** V2.3 scored 3.96/5.0 with 5/8 wins — verdict SHIP. V3.0 scored 3.84/5.0 with 4/12 wins — verdict KILL. V3.1 scored 4.11/5.0 with 3/4 wins but failed feature visibility — verdict KILL.

---

## Executive Summary

V4 introduced autonomous mode switching: the search engine internally decides when to augment semantic search with grep (no agent involvement required). Two trigger paths: (1) ENUMERATION intent detection → concurrent grep, (2) low confidence → post-hoc grep. V4 also added result-level enrichment (`context` field with "Called by: X | Tests: Y").

**Results:** Clew averages 3.69/5.0 across 12 tests, winning 5 of 12. This passes the Ship average threshold (3.66) but fails the win count threshold (need 7/12). Track A regression tests show 3.79 avg with 4/8 wins — the average passes but wins regress from V2.3's 5/8. Track B (V4-advantaged scenarios) was catastrophic: 3.48 avg with 1/4 wins.

**Root cause:** V4's autonomous features barely activated. Across 12 clew transcripts, ENUMERATION intent was never detected, auto-escalation fired only twice (one incorrectly on a focused debugging query), and result enrichment was visible in only 1 of 12 tests. The features are implemented correctly in the codebase but the activation thresholds are miscalibrated — confidence scores are too high for escalation to trigger, and ENUMERATION keyword heuristics don't match agent query patterns.

**Verdict: KILL.** Clew wins 5/12 (need ≥6 for Iterate, ≥7 for Ship). Track B failure (1/4 wins) confirms V4 does not deliver its intended value. The autonomous architecture is sound but requires threshold calibration before re-evaluation.

---

## What Changed Since V2.3

### Code Changes

V4 is a major architectural shift (ADR-006, ADR-007). Key changes:

| Component | Change |
|-----------|--------|
| `clew/search/engine.py` | Autonomous mode switching: engine decides when to run grep internally |
| `clew/search/intent.py` | ENUMERATION intent detection via keyword heuristics |
| `clew/search/engine.py:305-348` | `_compute_confidence()` — threshold-based confidence scoring |
| `clew/search/enrichment.py` | `CacheResultEnricher` — adds `context` field to top-5 results |
| `clew/models.py:65-87` | `SearchConfig` — configurable thresholds (not calibrated) |
| MCP/CLI output | Simplified: no confidence_label, suggestion, related_files metadata |

**774 tests passing, 86% coverage.**

### Architecture: Autonomous Intelligence

V3 proved that embedding metadata in output for agents to read is structurally flawed — agents pipe away all non-result data. V4 moved intelligence inside the engine:

- **ENUMERATION intent** → concurrent grep (no added latency for most queries)
- **Low confidence** → post-hoc grep (~1-5s added, triggers rarely)
- **Result enrichment** → `context` field on individual results (survives piping)
- **No agent involvement** — engine makes all decisions autonomously

### Methodology Changes

| Aspect | V2.3 | V4 |
|--------|------|-----|
| Test count | 8 | 12 (8 Track A regression + 4 Track B new) |
| Track B design | N/A | V4-advantaged scenarios with ground-truth checklists |
| Ship threshold | avg ≥ 3.50, wins ≥ 5/8 | avg ≥ 3.66, wins ≥ 7/12, Track A avg ≥ 3.66 |
| Iterate threshold | avg ≥ 2.50, wins ≥ 3/8 | avg ≥ 3.30, wins ≥ 6/12 |
| Scorer agreement target | Within 1 point | Same |
| Total agents | 44 | ~64 (24 explorers + 12 sanitizers + 1 verifier + 25 scorers) |

---

## Methodology

Follows `docs/VIABILITY-EVALUATION-STANDARDS.md`. Same blind A/B pipeline as V2.3 with expanded test suite.

### Blind Evaluation Pipeline

1. **Phase -1: Scenario Validation** — 4 agents validated Track B ground-truth checklists (≥5 artifacts each)
2. **Phase 0: Pre-flight** — Verified Qdrant, index, V4 features via smoke tests
3. **Phase 1: Exploration** — 24 agents (2 per test × 12 tests), each starting cold
4. **Phase 2: Sanitization** — Python script normalized tool names, metadata, output formats; random Alpha/Beta assignment (seed 20260221)
5. **Phase 3: Verification** — 1 agent attempted to identify tools from sanitized transcripts (failed gate twice, proceeded with caveat)
6. **Phase 4: Scoring** — 25 agents (2 scorers × 12 tests + 1 C2 tiebreaker)
7. **Phase 5: Computation** — Programmatic aggregation via `scripts/viability_compute.py`
8. **Phase 5.5: Post-hoc analysis** — 4 research agents analyzed raw transcripts (does NOT affect verdicts)
9. **Phase 6: Disagreement resolution** — C2 tiebreaker (relational dimension, >1-point gap)

### Scoring Rubric (unchanged)

| Dimension | Weight | 5 | 3 | 1 |
|-----------|--------|---|---|---|
| Discovery Efficiency | 30% | ≤3 calls to understanding | 6-8 calls | 12+ calls |
| Context Precision | 25% | ≤10% noise | 20-40% noise | 60%+ noise |
| Completeness | 20% | All artifacts found | ≥70% found | <50% found |
| Relational Insight | 15% | ≥3 unexpected connections | 1 connection | No capability |
| Answer Confidence | 10% | Immediately actionable | 2-3 follow-ups | Not actionable |

### Verdict Criteria (pre-registered)

| Verdict | Criteria |
|---------|----------|
| **Ship** | Overall avg ≥ 3.66 AND wins ≥ 7/12 AND Track A avg ≥ 3.66 |
| **Iterate** | Overall avg ≥ 3.30 AND wins ≥ 6/12 |
| **Kill** | Below Iterate |

---

## Per-Test Results

| Test | Track | Category | Clew | Grep | Winner |
|------|-------|----------|------|------|--------|
| A1 | A | Discovery | 3.75 | 3.85 | GREP |
| A2 | A | Discovery | 3.67 | 3.50 | CLEW |
| A3 | A | Discovery | 3.50 | 3.85 | GREP |
| A4 | A | Discovery | 3.98 | 3.98 | TIE |
| B1 | A | Structural | 4.03 | 4.58 | GREP |
| B2 | A | Structural | 3.75 | 3.73 | CLEW |
| C1 | A | Grep-Advantaged | 3.70 | 3.48 | CLEW |
| C2 | A | Grep-Advantaged | 3.95 | 3.50 | CLEW |
| E1 | B | Autonomous Escalation | 3.85 | 3.77 | CLEW |
| E2 | B | ENUMERATION + grep | 3.62 | 5.00 | GREP |
| E3 | B | Result Enrichment | 3.35 | 3.77 | GREP |
| E4 | B | Honesty Check | 3.08 | 3.33 | GREP |

### Per-Test Dimension Scores

**Clew:**

| Test | Discovery | Precision | Completeness | Relational | Confidence | Weighted |
|------|-----------|-----------|--------------|------------|------------|----------|
| A1 | 1.5 | 4.5 | 5.0 | 4.5 | 5.0 | 3.75 |
| A2 | 1.0 | 4.5 | 5.0 | 5.0 | 5.0 | 3.67 |
| A3 | 2.0 | 3.5 | 4.5 | 4.5 | 4.5 | 3.50 |
| A4 | 2.0 | 4.5 | 5.0 | 5.0 | 5.0 | 3.98 |
| B1 | 3.5 | 4.0 | 4.0 | 4.5 | 5.0 | 4.03 |
| B2 | 2.0 | 4.0 | 4.5 | 5.0 | 5.0 | 3.75 |
| C1 | 1.5 | 4.5 | 5.0 | 4.5 | 4.5 | 3.70 |
| C2 | 2.0 | 5.0 | 5.0 | 4.0 | 5.0 | 3.95 |
| E1 | 2.0 | 4.0 | 5.0 | 5.0 | 5.0 | 3.85 |
| E2 | 1.5 | 4.0 | 5.0 | 4.5 | 5.0 | 3.62 |
| E3 | 1.0 | 4.0 | 4.0 | 5.0 | 5.0 | 3.35 |
| E4 | 2.0 | 3.5 | 2.5 | 4.0 | 5.0 | 3.08 |
| **Avg** | **1.83** | **4.17** | **4.54** | **4.62** | **4.92** | **3.69** |

**Grep:**

| Test | Discovery | Precision | Completeness | Relational | Confidence | Weighted |
|------|-----------|-----------|--------------|------------|------------|----------|
| A1 | 2.0 | 4.0 | 5.0 | 5.0 | 5.0 | 3.85 |
| A2 | 1.0 | 4.5 | 4.5 | 4.5 | 5.0 | 3.50 |
| A3 | 2.0 | 4.0 | 5.0 | 5.0 | 5.0 | 3.85 |
| A4 | 2.0 | 4.5 | 5.0 | 5.0 | 5.0 | 3.98 |
| B1 | 4.0 | 4.5 | 5.0 | 5.0 | 5.0 | 4.58 |
| B2 | 2.0 | 3.5 | 5.0 | 5.0 | 5.0 | 3.73 |
| C1 | 2.5 | 4.0 | 3.0 | 4.5 | 4.5 | 3.48 |
| C2 | 1.0 | 5.0 | 5.0 | 3.0 | 5.0 | 3.50 |
| E1 | 2.0 | 4.0 | 5.0 | 4.5 | 5.0 | 3.77 |
| E2 | 5.0 | 5.0 | 5.0 | 5.0 | 5.0 | 5.00 |
| E3 | 2.0 | 4.5 | 4.0 | 5.0 | 5.0 | 3.77 |
| E4 | 2.5 | 3.5 | 3.0 | 4.0 | 5.0 | 3.33 |
| **Avg** | **2.33** | **4.25** | **4.54** | **4.62** | **4.96** | **3.86** |

### Dimension Comparison

| Dimension | Clew Avg | Grep Avg | Delta | Advantage |
|-----------|----------|----------|-------|-----------|
| Discovery | 1.83 | 2.33 | -0.50 | Grep |
| Precision | 4.17 | 4.25 | -0.08 | ~Tied |
| Completeness | 4.54 | 4.54 | 0.00 | Tied |
| Relational | 4.62 | 4.62 | 0.00 | Tied |
| Confidence | 4.92 | 4.96 | -0.04 | ~Tied |

Discovery efficiency is the only dimension with meaningful separation — grep leads by 0.50 points. This is driven by grep's E2 score (5.0) and B1 score (4.0). All other dimensions are effectively tied.

---

## Track Analysis

### Track A: Regression (8 tests, identical to V2.3)

| Metric | V4 | V2.3 | Change |
|--------|-----|------|--------|
| Clew avg | 3.79 | 3.96 | -0.17 |
| Grep avg | 3.81 | 3.98 | -0.17 |
| Clew wins | 4 | 5 | -1 |
| Grep wins | 3 | 3 | 0 |
| Ties | 1 | 0 | +1 |

Track A passes the regression threshold (3.79 ≥ 3.66) but loses one win. Both tools declined equally (-0.17), suggesting scorer calibration shift rather than tool regression.

### Track B: V4-Advantaged (4 new tests)

| Test | Expected V4 Advantage | Actual Winner | Analysis |
|------|----------------------|---------------|----------|
| E1 | Post-hoc grep on borderline query | CLEW (3.85 vs 3.77) | Only Track B win. Narrow margin. |
| E2 | ENUMERATION → concurrent grep | GREP (5.00 vs 3.62) | Catastrophic. ENUMERATION never activated. |
| E3 | Result enrichment aids navigation | GREP (3.77 vs 3.35) | Enrichment not visible in output. |
| E4 | Honesty: grep should NOT trigger | GREP (3.33 vs 3.08) | Honesty check FAILED (grep triggered). |

Track B failed to demonstrate V4's value. The features designed to help (ENUMERATION detection, enrichment) didn't activate or weren't visible.

---

## Cross-Version Comparison (V2.3 → V4)

### Test-Level Stability

| Test | V2.3 Clew | V4 Clew | Δ | V2.3 Grep | V4 Grep | Δ | V2.3 Winner | V4 Winner | Flipped? |
|------|-----------|---------|---|-----------|---------|---|-------------|-----------|----------|
| A1 | 3.73 | 3.75 | +0.02 | 4.10 | 3.85 | -0.25 | GREP | GREP | No |
| A2 | 3.95 | 3.67 | -0.28 | 3.48 | 3.50 | +0.02 | CLEW | CLEW | No |
| A3 | 4.38 | 3.50 | -0.88 | 3.67 | 3.85 | +0.18 | CLEW | GREP | YES |
| A4 | 4.38 | 3.98 | -0.40 | 4.10 | 3.98 | -0.12 | CLEW | TIE | YES |
| B1 | 3.55 | 4.03 | +0.48 | 4.30 | 4.58 | +0.28 | GREP | GREP | No |
| B2 | 3.67 | 3.75 | +0.08 | 3.60 | 3.73 | +0.13 | CLEW | CLEW | No |
| C1 | 3.13 | 3.70 | +0.57 | 4.32 | 3.48 | -0.84 | GREP | CLEW | YES |
| C2 | 4.85 | 3.95 | -0.90 | 4.30 | 3.50 | -0.80 | CLEW | CLEW | No |

**3 of 8 Track A tests flipped** (37.5% volatility). This is lower than V2.2→V2.3 (5/8 flipped) but still high, confirming agent variance dominates tool quality differences.

### Notable Movements

- **C1 reversal (GREP→CLEW):** V2.3's weakest test (3.13) improved to 3.70. Grep declined from 4.32 to 3.48. This is the only signal that V4's autonomous grep integration helped on enumeration. However, it's a single data point amid high variance.
- **A3 regression (CLEW→GREP):** Clew dropped 0.88 points (4.38→3.50). Largest single-test regression. A3 involved DEBUG intent triggering exhaustive mode — possible false positive.
- **C2 score compression:** Both tools dropped ~0.85 points. Scorer calibration shifted; C2 was V2.3's highest clew score (4.85).
- **Discovery dimension collapsed:** Clew discovery dropped from 3.12 (V2.3) to 1.83 (V4). This is the primary driver of lower scores — but grep dropped similarly (3.00→2.33).

### Discovery Dimension Crisis

| Version | Clew Discovery Avg | Grep Discovery Avg |
|---------|-------------------|-------------------|
| V2.3 | 3.12 | 3.00 |
| V4 | 1.83 | 2.33 |
| **Change** | **-1.29** | **-0.67** |

Both tools scored dramatically lower on discovery in V4. This suggests scorer calibration shifted rather than tool regression — V4 scorers may have applied the rubric more strictly. Clew's drop is larger because V4 agents made more search calls on average (the exploration agents may have been more thorough but less efficient).

---

## Post-Hoc Analysis (does NOT affect verdicts)

### V4 Feature Activation

| Feature | Expected | Actual | Tests Activated |
|---------|----------|--------|----------------|
| ENUMERATION intent detection | E2, C1 should trigger | 0/12 detected | None |
| Auto-escalation (low confidence) | E1, E3 might trigger | 2/12 (A3, E4) | A3 (correct-ish), E4 (incorrect) |
| Result enrichment visible | All 12 | 1/12 | B1 only |
| Agent used enrichment | Where visible | 0/12 | None |
| Mode = semantic | Default | 12/12 | All |

**Critical finding:** V4's autonomous features essentially didn't fire. The engine ran in pure semantic mode for nearly all searches. The two instances where exhaustive mode appeared were:
- **A3:** DEBUG intent detected → exhaustive. Reasonable but not the intended trigger path.
- **E4:** Focused debugging query classified as exhaustive. This is a false positive — the honesty check FAILED.

### E2 Catastrophic Analysis

E2 ("find all Celery tasks") was designed to showcase ENUMERATION detection. Instead:
- **Grep agent:** 1 regex (`@shared_task|@app\.task|@celery\.task`) → found all 95 tasks in 15 files → scored 5.00/5.00
- **Clew agent:** 5 semantic searches (low confidence) → fell back to glob + manual file reading → found ~95 tasks across 14 calls → scored 3.62/5.00

ENUMERATION never activated because the clew agent's queries ("Celery task decorator", "apply_async delay celery") didn't match the keyword heuristics in `clew/search/intent.py` ("find all", "list all", etc.). The queries were semantic descriptions, not enumeration commands.

**Lesson:** ENUMERATION detection based on query keywords is fragile. Agent query phrasing is unpredictable and rarely matches the predefined keyword list. A confidence-based approach (low semantic confidence → automatic grep) would be more robust, but the confidence thresholds are currently too high for this to trigger.

### E4 Honesty Check

E4 was designed so grep should NOT trigger (focused debugging, high semantic confidence expected). Search 3 ("shopify order paid webhook email notification") was classified as exhaustive mode — a false positive. Despite this, both agents produced similar-quality answers. The 0.25 point gap (grep 3.33, clew 3.08) reflects discovery efficiency differences, not mode-switching harm.

### Scorer Agreement

| Metric | V4 | V2.3 |
|--------|-----|------|
| Exact agreement | 82.9% | ~91% |
| Within 1 point | 100% | 91.25% |
| Confidence dimension agreement | 100% | ~100% |
| Tiebreakers needed | 1 (C2) | 3 (A1, A4, C1) |

100% within-1-point agreement is stronger than V2.3. The lower exact-match rate reflects more deliberation, not less consistency. Confidence dimension had perfect agreement across all tests.

---

## Lessons Learned

### 1. Threshold Calibration is Prerequisites, Not Post-Implementation

V4 shipped with default confidence thresholds that were never empirically calibrated. The plan included a calibration phase (30 queries across 4 categories) but evaluation proceeded before calibration was complete. Result: features didn't activate.

**Fix:** Run `scripts/calibration_queries.py` against the target codebase, analyze the confidence distribution, and tune thresholds to achieve 20-30% escalation rate before re-evaluation.

### 2. Keyword Heuristics Don't Match Agent Query Patterns

ENUMERATION detection relies on queries containing "find all", "list all", etc. Agents phrase queries semantically ("Celery task decorator") not imperatively ("find all Celery tasks"). The heuristic has zero recall against real agent queries.

**Fix:** Replace keyword heuristics with confidence-based escalation. If the semantic result confidence is below threshold AND the query has broad scope indicators (multiple entity types, plural nouns), trigger grep.

### 3. Result Enrichment Is Invisible Without Agent Protocol Changes

The `context` field was visible in 1/12 transcripts and used in 0/12. Agents extract `results[].file_path` and `results[].content` — they don't read auxiliary fields.

**Fix:** This is a display problem. Options: (1) prepend context to the `content` field so it's always visible, (2) include it in the `snippet` compact output, (3) add a separate "navigational aids" section in the response summary.

### 4. Cross-Version Instability Remains High

3/8 Track A tests flipped (37.5%), consistent with prior evaluations. Agent variance is the dominant signal in test outcomes. To extract genuine tool quality differences:
- Need ≥20 tests to overcome variance
- Or need repeated evaluations (3+ runs per version) with statistical testing
- Or need drastically different test categories where one tool is structurally advantaged (e.g., regex pattern matching vs semantic concept search)

### 5. Discovery Dimension Needs Rubric Recalibration

Discovery scores collapsed from 3.12→1.83 for clew and 3.00→2.33 for grep. The "≤3 calls" anchor for a score of 5 may be too strict for 12-test evaluations where agents are given more complex scenarios. Consider adjusting to "≤5 calls" for 5, "8-12 calls" for 3, "15+ calls" for 1.

---

## Recommendations

### If Continuing V4 Development

1. **Calibrate thresholds first.** Run the 30-query calibration script. Target: ENUMERATION triggers on 7/7 enumeration queries, post-hoc grep triggers on 20-30% of non-ENUMERATION queries, ≤1 false trigger on focused debugging queries.

2. **Replace ENUMERATION keyword heuristics.** Use confidence-based triggering instead. If top-5 semantic results have confidence < X and there are patterns suggesting broad scope, run grep.

3. **Make enrichment visible.** Prepend `context` to the snippet/content field. Test with 3-5 manual explorations to verify agents actually see and use it.

4. **Re-evaluate with calibrated thresholds.** Same 12 tests, same methodology. Expected improvement: E2 should trigger ENUMERATION (grep concurrent), E4 should NOT trigger (honesty preserved), 3-5 additional tests should benefit from post-hoc grep.

### If Pivoting

V4's autonomous architecture is sound but the "smarter tools" thesis remains unproven at the evaluation level. Consider:

- **Infrastructure path:** Position clew as developer infrastructure (like Sourcegraph) rather than agent-facing tool. Optimize for human CLI usage.
- **Separate tools path:** Follow Cursor's model — expose `semantic_search` and `grep_search` as separate MCP tools. Let the agent decide. This gives up the "smarter tools" thesis but aligns with how agents actually work.
- **Hybrid path:** Keep autonomous mode switching but add a `grep` MCP tool for when agents want explicit pattern matching. Belt and suspenders.

---

## Appendix: Raw Data Locations

| File | Description |
|------|-------------|
| `.clew-eval/v4/raw-transcripts/` | 24 unsanitized exploration transcripts |
| `.clew-eval/v4/sanitized-transcripts/` | 24 sanitized transcripts + `mapping.json` |
| `.clew-eval/v4/ground-truth/` | 4 Track B ground-truth checklists |
| `.clew-eval/v4/scores/` | 25 individual scorer files + `scores.json` + `viability_results.json` |
| `.clew-eval/v4/viability_test_plan.md` | Full test plan with 12 scenarios |
| `.clew-eval/v4/evaluation_handoff.md` | Self-contained evaluation instructions |
| `scripts/viability_compute.py` | Mechanical score aggregation |
| `scripts/assemble_scores.py` | Score file assembly |
| `scripts/sanitize_transcripts.py` | Transcript sanitization |
