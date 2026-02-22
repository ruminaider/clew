# V4.1 Viability Test Plan: Calibrated ENUMERATION Detection + Broadened Post-Hoc Grep

**Date:** 2026-02-21
**Tests:** V4.1 code (calibrated ENUMERATION detection with "all [noun]" regex, broadened post-hoc grep on medium confidence, lowered reranked thresholds, updated discovery rubric)
**Goal:** Verify V4.1 fixes V4's activation failures while maintaining search quality

---

## What Changed Since V4

V4 was KILLED because its features didn't activate: 0/12 ENUMERATION detections, 2/12 post-hoc grep triggers (1 false positive). The engine ran in pure semantic mode for all 12 tests. V4.1 recalibrates detection and thresholds:

| Change | File | Impact |
|--------|------|--------|
| **Broadened ENUMERATION detection** | `intent.py` | 5 new phrases + "all [noun]" regex with false-positive guard. Agent queries like "all Celery tasks" now match. |
| **Lowered reranked thresholds** | `models.py` | high 0.70→0.65, medium 0.40→0.35. Post-hoc grep fires more often on borderline results. |
| **Post-hoc grep on medium confidence** | `engine.py` | Triggers on BOTH TRY_KEYWORD and TRY_EXHAUSTIVE (was TRY_EXHAUSTIVE only). Excludes LOCATION/DEBUG. |
| **MCP output enrichment** | `mcp_server.py` | `confidence_label` always included; `mode_used`/`auto_escalated` conditional. |
| **Updated discovery rubric** | `VIABILITY-EVALUATION-STANDARDS.md` | 5=≤5 calls, 4=6-7, 3=8-12, 2=13-15, 1=15+ (relaxed from V4's 5=≤3). |

### Expected Activation Rates (from calibration analysis)

| Category | V4 Rate | Expected V4.1 Rate |
|----------|---------|-------------------|
| ENUMERATION detection | 0/12 | 7+/7 Category C queries |
| Post-hoc grep | 2/12 (1 false positive) | 2-3/5 Category D queries |
| False positive grep | 1/12 (E4) | ≤1/10 Category A queries |

---

## Evaluation Structure

### Design Principles

1. **No feature-visibility criteria.** V4.1 features are autonomous. Score improvement is the only signal.
2. **Purely quantitative verdicts.** Win rate + avg score + regression check.
3. **V2.3 baseline.** V2.3 (3.96/5.0, 5/8 wins) is the SHIP version for regression comparison.
4. **Updated discovery rubric.** 5=≤5 calls (was ≤3 in V4). All other dimensions unchanged.
5. **12 tests.** Same scenarios as V4.

### Two Tracks

| Track | Tests | Purpose | Comparison |
|-------|-------|---------|------------|
| **A: Regression** | 8 (A1-C2) | Verify V4.1 ≥ V2.3 quality | V4.1 clew vs grep |
| **B: V4-Advantaged** | 4 (E1-E4) | Demonstrate autonomous improvement | V4.1 clew vs grep |

### Combined Verdict

| Verdict | Criteria |
|---------|----------|
| **Ship** | Overall avg ≥ 3.66 AND wins ≥ 7/12 AND Track A avg ≥ 3.66 |
| **Iterate** | Overall avg ≥ 3.30 AND wins ≥ 6/12 |
| **Kill** | Below Iterate |

---

## Scoring Rubric

### Dimensions

| Dimension | Weight | What It Measures |
|-----------|--------|------------------|
| Discovery Efficiency | 30% | How quickly the agent reaches actionable understanding |
| Context Precision | 25% | Signal-to-noise ratio in loaded context |
| Completeness | 20% | Coverage of key artifacts per test checklist |
| Relational Insight | 15% | Connections surfaced that the agent did not explicitly search for |
| Answer Confidence | 10% | Whether the final output is actionable without further investigation |

### Rating Scale (Updated Discovery Anchors)

| Score | Discovery Efficiency | Context Precision | Completeness | Relational Insight | Answer Confidence |
|-------|---------------------|-------------------|--------------|-------------------|-------------------|
| 5 | Reaches understanding in ≤5 tool calls | ≤10% noise | All checklist artifacts found | ≥3 unexpected connections | Immediately actionable |
| 4 | 6-7 tool calls | 10-20% noise | ≥90% found | 2 connections | Needs 1 follow-up read |
| 3 | 8-12 tool calls | 20-40% noise | ≥70% found | 1 connection | Needs 2-3 follow-ups |
| 2 | 13-15 tool calls | 40-60% noise | 50-70% found | 0 but tool supports it | Needs significant follow-up |
| 1 | 15+ calls or gives up | 60%+ noise | <50% found | Tool has no relational capability | Not actionable |

### Winner Determination

```
weighted_score = (discovery * 0.30) + (precision * 0.25) + (completeness * 0.20) + (relational * 0.15) + (confidence * 0.10)

if clew_weighted > grep_weighted:
    winner = "clew"
elif grep_weighted > clew_weighted:
    winner = "grep"
else:  # exact tie
    winner = "higher completeness score"  # tiebreaker
```

---

## Test Scenarios

### Track A: Regression (8 tests)

**A1:** "A customer reported their subscription renewal didn't create a prescription fill. Investigate the code path from order webhook to PrescriptionFill creation and identify where failures can occur."

**A2:** "We need to add a new checkout source type for a partner integration. What code needs to change? Provide a comprehensive list of files and code locations that reference or depend on the checkout source concept."

**A3:** "The pharmacy API is returning errors for some refill orders. Where in the codebase do we call the pharmacy API, how do we handle errors from it, and what retry/monitoring logic exists?"

**A4:** "Explain how the order processing system decides what type of order it is (e.g., new subscription vs. refill vs. one-time purchase) and how that determination affects downstream processing."

**B1:** "We're considering changing the signature of the function that processes shopify orders for treatment refills. What would break? Find all callers, understand what arguments they pass, and identify any test coverage."

**B2:** "Map the relationship between Order, PrescriptionFill, and Prescription models. Include foreign keys, many-to-many relationships, through-tables, and any computed properties that bridge them."

**C1:** "Find all Django URL patterns that involve ecomm-related views. List each URL pattern with its view and URL path."

**C2:** "Find all Stripe API calls in the codebase. List each call site with the Stripe API method being called and the context in which it's used."

### Track B: V4-Advantaged (4 tests)

**E1: Middleware Audit** (post-hoc escalation target)
> "Our application uses custom Django middleware for request processing. Map all custom middleware classes: what each one does, what order they run in, and how they interact with each other. Focus on application-specific middleware, not standard Django middleware. Also identify any middleware that conditionally skips processing based on request attributes."

**E2: Celery Task Inventory** (ENUMERATION + concurrent grep target)
> "Create a complete inventory of all Celery tasks in the codebase. For each task, identify: (1) the task function name and file location, (2) what arguments it accepts, (3) how it is enqueued (`.delay()`, `.apply_async()`, or `send_task()`), (4) what retry configuration it has (if any), and (5) the business purpose of the task."

**E3: Model Dependency Chain** (result enrichment target)
> "Starting from the Order model, trace how creating an order triggers the creation of related records. Map the full chain: which models are created as side effects of order processing, what service functions orchestrate this creation, and what happens if any step in the chain fails. Include the relationships between the created records."

**E4: Email Confirmation Debugging** (honesty check — grep should NOT trigger)
> "A user reported that their subscription order was processed successfully but they didn't receive a confirmation email. Investigate the email sending pipeline from order completion to email dispatch. Focus on identifying the specific failure path — where in the code could the email send fail silently? Do NOT catalog all email-related code in the codebase."

---

## Sanitization Rules

### Normalization Table

| Original | Sanitized |
|----------|-----------|
| `clew search "query" --json` | `search("query")` |
| `clew search "query" --project-root ... --json` | `search("query")` |
| `clew trace "entity" --json` | `search("code related to entity")` |
| `rg "pattern" --type py` | `search("pattern")` |
| `Grep(pattern="...")` | `search("...")` |
| `Glob(pattern="...")` | `find_files("...")` |
| `Read(file_path="...")` | `read("...")` |
| `"source": "grep"` in result objects | Remove field |
| `"source": "semantic"` in result objects | Remove field |
| `"context": "Called by: X \| Tests: Y"` | Normalize to `"related": "..."` (keep content) |
| Score fields (`"score": 0.94`) | Remove |
| `confidence`, `confidence_label` | Remove |
| `mode_used`, `auto_escalated` | Remove |
| `intent` field | Remove |
| `suggestion_type` | Remove |
| Qdrant/embedding metadata | Remove |

**Critical:** Add empty `"related": ""` to grep-tool results so the field's presence/absence doesn't identify the tool.

---

## Agent Prompts

### Grep Agent (all tests)

```
You are exploring a codebase to answer a question. You have access to Grep, Glob, and Read tools only.

Working directory: /Users/albertgwo/Work/evvy

TASK:
{scenario_text}

INSTRUCTIONS:
- You have a budget of approximately 20 tool calls. Prioritize finding the most important artifacts first.
- Provide a comprehensive answer with specific file paths and code references.
- Do NOT access any files outside the working directory.
- Do NOT read any CLAUDE.md, .claude/, or documentation files about tools.
```

### Clew Agent (all tests)

```
You are exploring a codebase to answer a question. You have access to a code search tool called `clew` (via Bash) and the Read tool for viewing files.

Working directory: /Users/albertgwo/Work/evvy

SEARCH TOOL USAGE:
- Search: clew search "your query" --project-root /Users/albertgwo/Work/evvy --json
- Trace: clew trace "entity_name" --project-root /Users/albertgwo/Work/evvy --json
- Help: clew search --help

TASK:
{scenario_text}

INSTRUCTIONS:
- You have a budget of approximately 20 tool calls. Prioritize finding the most important artifacts first.
- Provide a comprehensive answer with specific file paths and code references.
- Do NOT access any files outside the working directory.
- Do NOT read any CLAUDE.md, .claude/, or documentation files about tools.
```

### Scorer Prompt

```
You are scoring two agent transcripts that attempted the same codebase exploration task. Score each agent independently on 5 dimensions using the rubric below. Provide integer ratings (1-5) for each dimension.

**IMPORTANT:** Score each agent against the absolute rubric, not relative to the other agent. A score of 3 means "adequate" regardless of what the other agent scored. Do NOT compute aggregates or declare a winner — just rate each dimension.

**Dimensions:**

| Dimension | Weight | 5 (Excellent) | 4 (Good) | 3 (Adequate) | 2 (Weak) | 1 (Failed) |
|-----------|--------|---------------|----------|---------------|----------|------------|
| Discovery Efficiency (30%) | How quickly the agent reaches actionable understanding | Reaches understanding in ≤5 tool calls | 6-7 tool calls | 8-12 tool calls | 13-15 tool calls | 15+ calls or gives up |
| Context Precision (25%) | Signal-to-noise ratio in loaded context | ≤10% noise | 10-20% noise | 20-40% noise | 40-60% noise | 60%+ noise |
| Completeness (20%) | Coverage of key artifacts (see test checklist) | All checklist artifacts found | ≥90% found | ≥70% found | 50-70% found | <50% found |
| Relational Insight (15%) | Connections surfaced beyond explicit searches | ≥3 unexpected connections | 2 connections | 1 connection | 0 but tool supports it | Tool has no relational capability |
| Answer Confidence (10%) | Actionability of the final output | Immediately actionable | Needs 1 follow-up read | Needs 2-3 follow-ups | Needs significant follow-up | Not actionable |

**Bonus discoveries:** If an agent finds valid artifacts not on the checklist, you may award a bonus to Completeness (e.g., 4 → 5) at your discretion.

For each transcript, output your 5 ratings as integers only. Example format:
```
Agent Alpha: Discovery=4, Precision=3, Completeness=5, Relational=4, Confidence=4
Agent Beta: Discovery=3, Precision=4, Completeness=4, Relational=2, Confidence=3
```
```

---

## Execution Pipeline

```
Phase 0: Pre-flight ✅
  ├──→ Phase 1: Exploration (24 agents, 12 tests × 2)
  └──→ Ground-truth: Reuse V4 checklists (target codebase unchanged)
Phase 2: Sanitization (12 agents)
  → Phase 3: Verification (1 agent)
    → Phase 4: Scoring (24 agents, 2 per test)
      → Phase 5: Computation (script)
        → Phase 5.5: Post-hoc V4.1 feature analysis
          → Phase 6: Disagreement resolution (conditional)
```

### V4.1-Specific Post-Hoc Questions (Phase 5.5)

1. How many queries triggered broadened ENUMERATION detection? (e.g., "all Celery tasks" without "find" prefix)
2. How many post-hoc grep triggers from medium confidence (TRY_KEYWORD) vs low confidence (TRY_EXHAUSTIVE)?
3. E4 honesty: grep should NOT trigger (verify `auto_escalated` is false, `mode_used` is "semantic")
4. Did `context` enrichment field appear in results? Did agents reference it?
5. Did `mode_used`/`auto_escalated` MCP fields appear when expected?
6. Cross-version stability: how many Track A tests flipped vs V4 and V2.3?

### V2.3 Rebaseline Decision

**Skipped.** The discovery rubric change only affects the discovery dimension (30% weight). The delta is symmetric — both V2.3 and V4.1 scores would benefit equally from relaxed anchors. Instead, V4.1 uses the updated rubric and compares raw outcomes (wins/losses) against V4 and V2.3 as context.

---

## Agent Models

| Role | Model |
|------|-------|
| Exploration agents | Sonnet 4.6 |
| Sanitization agents | Sonnet 4.6 |
| Verification agent | Sonnet 4.6 |
| Scoring agents | Sonnet 4.6 |
| Tiebreaker agents | Sonnet 4.6 |
| Orchestration | Opus 4.6 |

---

## Comparison Baselines

| Version | Overall Avg | Win Rate | Track A Avg | Verdict |
|---------|-------------|----------|-------------|---------|
| V2.3 | 3.96 | 5/8 (63%) | 3.96 | Ship |
| V4 | 3.69 | 5/12 (42%) | 3.79 | Kill |
| V4.1 | ? | ? | ? | ? |

---

## References

| Document | Path |
|----------|------|
| V4 test plan | `.clew-eval/v4/viability_test_plan.md` |
| V4 results | `.clew-eval/v4/viability_results.md` |
| V4 ground-truth | `.clew-eval/v4/ground-truth/` |
| V2.3 results | `docs/plans/2026-02-17-v2.3-viability-results.md` |
| Evaluation standards | `docs/VIABILITY-EVALUATION-STANDARDS.md` |
| Computation script | `scripts/viability_compute.py` |
| Target codebase | `/Users/albertgwo/Work/evvy` |
