# V4.2 Viability Evaluation Results

**Date:** 2026-02-21
**Engine:** V4.2 (reranker variance skip removed, ENUMERATION auto-detection removed, expanded DEBUG intent)
**Methodology:** Reformed evaluation standards with behavioral metrics, stability analysis, feature health cards
**Rubric:** R2 (frozen from V4.1 Ship)

---

## Verdict: Kill (LOW CONFIDENCE)

| Metric | Value | Threshold |
|--------|-------|-----------|
| Overall avg | **4.46** | ≥3.66 (Ship) ✓ |
| Grep avg | 4.42 | — |
| Win rate | **5/12 (42%)** | ≥7/12 (Ship) ✗ |
| Track A avg | **4.55** | ≥3.66 (Ship) ✓ |
| Track A wins | 2/8 | — |
| Track B wins | 3/4 | — |
| P(noise) | **46.5%** | <30% for confidence |

Averages easily pass Ship thresholds, but win rate (5/12) falls below even Iterate (6/12). The Kill is driven by narrow grep wins in Track A structural tasks (A1, A2, B1, B2) where both tools score 4.6-5.0 and completeness differences of 0.5-1.0 decide the winner.

---

## Per-Test Results

| Test | Track | Clew | Grep | Winner | Gap |
|------|-------|------|------|--------|-----|
| A1 | A | 4.62 | 4.70 | GREP | -0.08 |
| A2 | A | 4.15 | 4.42 | GREP | -0.27 |
| A3 | A | 4.85 | 4.85 | TIE | 0.00 |
| A4 | A | 4.85 | 4.85 | TIE | 0.00 |
| B1 | A | 4.65 | 5.00 | GREP | -0.35 |
| B2 | A | 4.80 | 5.00 | GREP | -0.20 |
| C1 | A | 4.25 | 3.33 | CLEW | +0.92 |
| C2 | A | 4.25 | 4.05 | CLEW | +0.20 |
| E1 | B | 4.70 | 4.65 | CLEW | +0.05 |
| E2 | B | 4.83 | 4.70 | CLEW | +0.13 |
| E3 | B | 3.95 | 3.95 | TIE | 0.00 |
| E4 | B | 3.60 | 3.50 | CLEW | +0.10 |

### Patterns

- **Grep dominates structural completeness (A1, A2, B1, B2):** Grep scores 5.0 completeness consistently on callers/relationships tasks; clew scores 3.0-4.0. Grep's exhaustive scanning finds every caller/reference.
- **Clew dominates grep-disadvantaged tasks (C1, C2):** C1 is the strongest clew signal (+0.92). Clew found more URL patterns via semantic understanding; grep agent found fewer. C2 both correctly identified no Stripe API calls, but clew found more string occurrences.
- **Track B is strong for clew (3/4 wins):** E1, E2, E4 all won. Clew's semantic search + post-hoc grep provides good coverage on feature tasks.
- **Perfect ties on narrative tasks (A3, A4):** Both tools produced near-identical answers with perfect 5.0 scores across most dimensions.

---

## Feature Health Assessment

### Reranker Activation: PASS ✓
- **Target:** ≥70% of queries
- **Actual:** 100% (12/12)
- The variance skip fix works. All queries now get reranked. Score range 0.27-1.67 (calibrated Voyage reranker scores), vs V4.1's 0.001-0.314 (raw RRF scores).

### Escalation Rate: ABOVE CEILING ✗
- **Target:** 10-20%
- **Actual:** 42% (5/12)
- Improved from V4.1's 49% but still above target. Queries A2, A4, B1, B2, E1 escalated via post-hoc grep. Reranker now runs but confidence values for multi-term queries still fall below the medium threshold (0.35).
- Confidence values of escalated queries: 0.006, 0.024, 0.027, 0.036, 0.038 — all extremely low despite reranker running.

### DEBUG Intent Detection: PARTIAL PASS △
- **Target:** ≥80% of E4-type queries
- **Actual:** 67% (2/3 test queries)
- A3 ("pharmacy API error handling retry") → correctly classified as DEBUG
- E4b ("email sending fails silently investigate bug") → correctly classified as DEBUG
- E4 ("subscription order processed but no confirmation email investigate failure") → classified as CODE. "failure" doesn't match soft keyword "fail" (exact word matching).

---

## Cross-Version Comparison

| Version | Avg (clew) | Avg (grep) | Wins | Verdict | Escalation |
|---------|------------|------------|------|---------|------------|
| V2.3 | 3.96 | 3.98 | 5/8 | Ship | N/A |
| V4 | 3.69 | 3.86 | 5/12 | Kill | 2/12 (17%) |
| V4.1 | 4.42 | 4.33 | 7/12 | Ship | 22/45 (49%) |
| **V4.2** | **4.46** | **4.42** | **5/12** | **Kill** | **5/12 (42%)** |

### Key Observations

1. **V4.2 has the highest average score (4.46) but the lowest win rate alongside V4.** Score inflation from high-scoring tiebreaker-free tests masks the underlying problem: when both tools score 4.8+, small differences in completeness decide winners.

2. **V4.1 → V4.2 regression:** 7 wins → 5 wins (-2). The reranker fix changes result ordering, which changes what agents read, which changes scores. Agent behavior is the dominant variable, not engine quality.

3. **Score compression:** V4.2 mean across both tools is 4.44/5.0 with 15/24 dimension averages at exactly 5.0. The rubric is saturating — most tests score near ceiling.

### Win Flips vs V4.1

| Test | V4.1 Winner | V4.2 Winner | Change |
|------|------------|-------------|--------|
| A1 | clew | grep | FLIP |
| A2 | grep | grep | stable |
| A3 | clew | tie | FLIP |
| A4 | clew | tie | FLIP |
| B1 | clew | grep | FLIP |
| B2 | grep | grep | stable |
| C1 | grep | clew | FLIP |
| C2 | clew | clew | stable |
| E1 | clew | clew | stable |
| E2 | clew | clew | stable |
| E3 | grep | tie | FLIP |
| E4 | clew | clew | stable |

**6/12 tests flipped (50%)** — highest volatility across any version pair. This confirms agent behavior is the dominant variable.

---

## Scorer Agreement

- Total dimension ratings: 240 (12 tests × 2 tools × 2 scorers × 5 dimensions)
- Disagreements requiring tiebreaker: 3 tests (A2 relational, E2 discovery, E3 discovery)
- E3 tiebreaker resolved: Discovery=3 for both (tie preserved)
- A2 and E2 tiebreakers: not verdict-impacting (A2 can't flip, E2 already clew win)

---

## Methodology Notes

1. **24 exploration agents** (12 tests × 2 tools) used Sonnet 4.6
2. **Sanitization verification:** 7/24 identified >60% confidence (from inherent tool capability differences, not metadata leaks). Proceeded per V2.3/V4.1 precedent.
3. **24 scoring agents + 1 tiebreaker** used Sonnet 4.6
4. **Behavioral metrics** collected via direct clew search queries (agents' tool call logs not preserved in raw transcripts)
5. **Total agents used:** ~50 (24 exploration + 24 scoring + 1 verification + 1 tiebreaker)

---

## Diagnosis: Why Kill Despite High Scores

The fundamental problem is not tool quality — it's evaluation sensitivity.

1. **Rubric saturation:** When both tools score 4.8-5.0 on precision/relational/confidence, the winner is determined by ±1 on completeness or discovery. These narrow margins (0.05-0.35) are within noise.

2. **Agent variance dominates:** 50% of tests flipped between V4.1 and V4.2, despite the same target codebase and similar scenarios. The agent's search strategy and reading path vary more than the tool's contribution.

3. **Grep's structural advantage persists:** For "find all X" tasks (callers, references, relationships), grep's exhaustive scan consistently finds 100% of artifacts. Clew's semantic search finds 80-90% — enough for a high score but not enough to win when grep also scores high on other dimensions.

4. **Clew's semantic advantage is narrow:** C1 (+0.92) shows clew can significantly outperform grep on semantic tasks, but there are only 2 such tests in the evaluation suite (C1, C2). Most tests are structural/trace tasks where grep has a natural edge.

---

## Implications

Given 5 evaluations (V2.3, V3.0, V4, V4.1, V4.2) with verdicts Ship/Kill/Kill/Ship/Kill:
- The evaluation methodology cannot distinguish between the tools with confidence
- P(noise) > 40% on every evaluation
- Win rates oscillate between 42-63% across versions
- Average scores are consistently within 0.04-0.17 of each other

The evidence suggests clew and grep produce equivalent-quality results for the task types in this evaluation suite, with clew having a slight edge on semantic/conceptual tasks and grep having a slight edge on exhaustive enumeration tasks.
