# V4 Viability Evaluation Handoff

**Date:** 2026-02-21
**Purpose:** Entry point for a fresh agent session to orchestrate the full V4 blind A/B viability evaluation.
**Primary reference:** `.clew-eval/v4/viability_test_plan.md` — contains all scenario text, scoring rubric, verdict thresholds, and methodology details. This handoff is self-contained but the test plan is the authoritative source for edge cases and rationale.

---

## 1. Current State

### V4 Code: Complete and Working

V4 implements autonomous mode switching (ADR-006, ADR-007): the search engine internally decides when to augment semantic search with grep, and enriches top results with relationship context. Key changes from V2.3:

| Feature | How It Works |
|---------|-------------|
| **ENUMERATION concurrent grep** | Queries like "find all X" auto-classify as ENUMERATION → grep runs concurrently with semantic search (zero added latency) |
| **Post-hoc grep escalation** | Low confidence (RRF gap < 0.02) → grep runs after semantic search (~1-5s added, triggers ~13% of non-ENUM queries) |
| **Result-level enrichment** | Top 5 results gain `context` field ("Called by: X \| Tests: Y") from relationship cache |
| **Calibrated thresholds** | RRF high=0.06, medium=0.02 (empirically calibrated on 30 queries) |
| **grep_response_cap** | Merged grep results capped at 100 (prevents noise blowup) |
| **No exposed metadata** | `confidence_label`, `suggestion`, `related_files` removed from output — agents can't see or ignore what isn't there |

774 tests passing, 86% coverage.

### V2.3 Baseline (for regression comparison)

- **Clew avg: 3.96/5.0** | **Grep avg: 3.98/5.0** | **Clew wins 5/8, Grep wins 3/8**
- Weakest result: C1 (exhaustive URL enumeration: 3.13/5.0)
- Full breakdown: `docs/plans/2026-02-17-v2.3-viability-results.md`

### Calibration Results

Calibration analysis at `.clew-eval/v4/calibration_analysis.md`:
- ENUMERATION detection: 7/7 perfect
- Post-hoc escalation: 3/23 non-ENUM queries (13%)
- Reranking systematically skipped (low_variance_threshold issue — deferred)
- All confidence goes through RRF path (5th-6th score gap)

---

## 2. Pre-flight Verification

Before starting any evaluation agents, verify ALL of the following. All checks must pass.

### Environment

```bash
# 1. Qdrant running
docker compose up -d qdrant

# 2. V4 code installed
cd /Users/albertgwo/Repositories/clew && pip3 install -e .

# 3. Target codebase exists
ls /Users/albertgwo/Work/evvy

# 4. Index current
clew status --project-root /Users/albertgwo/Work/evvy
# Should show ~12,000+ chunks

# 5. All tests pass
cd /Users/albertgwo/Repositories/clew && pytest
# Expect 774+ passing
```

### V4 Feature Verification

Each confirms a specific V4 feature works end-to-end:

```bash
# ENUMERATION auto-classification + concurrent grep
clew search "find all models" --project-root /Users/albertgwo/Work/evvy --json
# Verify: intent="enumeration" AND auto_escalated=true AND mode_used="exhaustive"

# Result enrichment
clew search "order processing" --project-root /Users/albertgwo/Work/evvy --json
# Verify: top results have "context" field (may be empty if enrichment cache is unpopulated)

# Trace resolution
clew trace "PrescriptionFill" --project-root /Users/albertgwo/Work/evvy --json
# Verify: resolves to Python model (not TypeScript generated type)
```

### Enrichment Cache Check

```bash
# Check if enrichment cache has data
clew status --project-root /Users/albertgwo/Work/evvy
# Look for enrichment stats. If enrichment cache is empty, context fields will be empty.
# This is acceptable — score as-is. But note it in the results document.
```

---

## 3. Test Scenarios (All 12)

### Track A: Regression (8 tests — identical to V2.3)

**A1: Subscription Renewal Failure Investigation**
> "A customer reported their subscription renewal didn't create a prescription fill. Investigate the code path from order webhook to PrescriptionFill creation and identify where failures can occur."

**A2: Adding a New Checkout Source Type**
> "We need to add a new checkout source type for a partner integration. What code needs to change? Provide a comprehensive list of files and code locations that reference or depend on the checkout source concept."

**A3: Pharmacy API Error Handling Investigation**
> "The pharmacy API is returning errors for some refill orders. Where in the codebase do we call the pharmacy API, how do we handle errors from it, and what retry/monitoring logic exists?"

**A4: Order Type Determination Logic**
> "Explain how the order processing system decides what type of order it is (e.g., new subscription vs. refill vs. one-time purchase) and how that determination affects downstream processing."

**B1: Impact Analysis for Signature Change**
> "We're considering changing the signature of the function that processes shopify orders for treatment refills. What would break? Find all callers, understand what arguments they pass, and identify any test coverage."

**B2: Model Relationship Mapping**
> "Map the relationship between Order, PrescriptionFill, and Prescription models. Include foreign keys, many-to-many relationships, through-tables, and any computed properties that bridge them."

**C1: Find All Django URL Patterns**
> "Find all Django URL patterns that involve ecomm-related views. List each URL pattern with its view and URL path."

**C2: Find All Stripe API Calls**
> "Find all Stripe API calls in the codebase. List each call site with the Stripe API method being called and the context in which it's used."

### Track B: V4-Advantaged (4 new tests)

**E1: Middleware Audit** (post-hoc escalation target)
> "Our application uses custom Django middleware for request processing. Map all custom middleware classes: what each one does, what order they run in, and how they interact with each other. Focus on application-specific middleware, not standard Django middleware. Also identify any middleware that conditionally skips processing based on request attributes."

**E2: Celery Task Inventory** (ENUMERATION + concurrent grep target)
> "Create a complete inventory of all Celery tasks in the codebase. For each task, identify: (1) the task function name and file location, (2) what arguments it accepts, (3) how it is enqueued (`.delay()`, `.apply_async()`, or `send_task()`), (4) what retry configuration it has (if any), and (5) the business purpose of the task."

**E3: Model Dependency Chain** (result enrichment target)
> "Starting from the Order model, trace how creating an order triggers the creation of related records. Map the full chain: which models are created as side effects of order processing, what service functions orchestrate this creation, and what happens if any step in the chain fails. Include the relationships between the created records."

**E4: Email Confirmation Debugging** (honesty check — grep should NOT trigger)
> "A user reported that their subscription order was processed successfully but they didn't receive a confirmation email. Investigate the email sending pipeline from order completion to email dispatch. Focus on identifying the specific failure path — where in the code could the email send fail silently? Do NOT catalog all email-related code in the codebase."

---

## 4. Explorer Agent Setup

### Grep Agent (all 12 tests)

**Subagent configuration:**
- Model: Sonnet 4.6
- subagent_type: `general-purpose`
- mode: `bypassPermissions`
- Tools available: Grep, Glob, Read ONLY (no Bash, no clew access)

**Prompt template:**
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

### Clew Agent (all 12 tests — same setup for Track A and Track B)

**Subagent configuration:**
- Model: Sonnet 4.6
- subagent_type: `general-purpose`
- mode: `bypassPermissions`
- Tools available: Bash and Read ONLY

**Prompt template:**
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

**CRITICAL:** No hints about modes, flags, exhaustive mode, or V4 capabilities. The agent knows how to call `clew search` and `clew trace` — nothing more.

---

## 5. Sanitization Rules

### Full Normalization Table

| Original | Sanitized |
|----------|-----------|
| `clew search "query" --project-root ... --json` | `search("query")` |
| `clew search "query" --json` | `search("query")` |
| `clew trace "entity" --project-root ... --json` | `search("code related to entity")` |
| `clew trace "entity" --direction outbound --depth 2 --json` | `search("code related to entity, outbound depth 2")` |
| `rg "pattern" --type py` / `Grep(pattern="...")` | `search("pattern")` |
| `Glob(pattern="...")` | `find_files("...")` |
| `Read(file_path="...")` | `read("...")` |
| `"source": "grep"` in result objects | Remove field |
| `"source": "semantic"` in result objects | Remove field |
| `"context": "Called by: X \| Tests: Y"` in results | Normalize to `"related": "Called by: X \| Tests: Y"` |
| Score fields (`"score": 0.94`, `"importance_score"`) | Remove |
| `confidence`, `confidence_label`, `suggestion_type` | Remove |
| `mode_used`, `auto_escalated`, `intent` | Remove |
| `query_enhanced`, `total_candidates` | Remove |
| Qdrant/embedding metadata (`chunk_type`, `enriched`, `collection`) | Remove |

**Critical blind-scoring rule:** Add `"related": ""` to ALL grep-tool results during sanitization. This ensures both tools' results have a `"related"` field — clew's may be populated (from enrichment), grep's will be empty. Without this, the presence of `"related"` identifies the tool.

### Sanitization Agent Prompt

```
You are sanitizing exploration transcripts for blind scoring. Your goal is to remove all information that could identify which search tool was used.

Apply these transformations:
1. Replace all tool invocations with generic labels:
   - Any search command → search("query text")
   - Any trace command → search("code related to entity")
   - Any file glob/find → find_files("pattern")
   - Any file read → read("file_path")

2. Remove tool-specific metadata from results:
   - Remove: score, source, confidence, confidence_label, suggestion_type, mode_used, auto_escalated, intent, query_enhanced, total_candidates, importance_score, chunk_type, enriched, collection
   - Normalize: "context" field → "related" field (keep the content)
   - ADD "related": "" to results that don't have a "related" field

3. Preserve: file paths, code content, line numbers, agent reasoning, final answer

4. Randomly assign "Alpha" or "Beta" label to each agent (coin flip)
5. Record the mapping (Alpha/Beta → tool identity) separately

Output the two sanitized transcripts and the mapping.
```

---

## 6. Verification Gate

### Verifier Agent Prompt

```
You are reviewing sanitized agent transcripts. For each test (12 total), you see two agent transcripts labeled Alpha and Beta. Your task: determine which agent used a semantic code search tool and which used pattern-matching tools (grep/ripgrep).

For each test, provide:
1. Your guess (which is the semantic search agent)
2. Your confidence (0-100%)
3. What evidence led to your guess

Important: The transcripts have been sanitized — tool names are generic. Focus on behavioral patterns: search strategy, result structure, query refinement approach.
```

### Pass Criteria

- Correct identification at >60% confidence on **no more than 3 of 12 tests** (25%)
- If >3 tests identified: re-sanitize with stricter rules, then re-verify
- If second verification also fails: proceed with documented caveat

---

## 7. Scorer Setup

### Scorer Agent Prompt (exact text — use verbatim)

> You are scoring two agent transcripts that attempted the same codebase exploration task. Score each agent independently on 5 dimensions using the rubric below. Provide integer ratings (1-5) for each dimension.
>
> **IMPORTANT:** Score each agent against the absolute rubric, not relative to the other agent. A score of 3 means "adequate" regardless of what the other agent scored. Do NOT compute aggregates or declare a winner — just rate each dimension.
>
> **Dimensions:**
>
> | Dimension | Weight | 5 (Excellent) | 4 (Good) | 3 (Adequate) | 2 (Weak) | 1 (Failed) |
> |-----------|--------|---------------|----------|---------------|----------|------------|
> | Discovery Efficiency (30%) | How quickly the agent reaches actionable understanding | Reaches understanding in ≤3 tool calls | 4-5 tool calls | 6-8 tool calls | 9-12 tool calls | 12+ calls or gives up |
> | Context Precision (25%) | Signal-to-noise ratio in loaded context | ≤10% noise | 10-20% noise | 20-40% noise | 40-60% noise | 60%+ noise |
> | Completeness (20%) | Coverage of key artifacts (see test checklist) | All checklist artifacts found | ≥90% found | ≥70% found | 50-70% found | <50% found |
> | Relational Insight (15%) | Connections surfaced beyond explicit searches | ≥3 unexpected connections | 2 connections | 1 connection | 0 but tool supports it | Tool has no relational capability |
> | Answer Confidence (10%) | Actionability of the final output | Immediately actionable | Needs 1 follow-up read | Needs 2-3 follow-ups | Needs significant follow-up | Not actionable |
>
> **Bonus discoveries:** If an agent finds valid artifacts not on the checklist, you may award a bonus to Completeness (e.g., 4 → 5) at your discretion.
>
> For each transcript, output your 5 ratings as integers only. Example format:
> ```
> Agent Alpha: Discovery=4, Precision=3, Completeness=5, Relational=4, Confidence=4
> Agent Beta: Discovery=3, Precision=4, Completeness=4, Relational=2, Confidence=3
> ```

### Scorer Configuration

- Model: Sonnet 4.6
- 2 scorers per test (24 agents total)
- Track separation: score Track A (A1-C2) and Track B (E1-E4) in separate sessions
- Track B scorers also receive the frozen ground-truth checklist from Phase -1

---

## 8. Computation

### Script Location

```bash
python3 scripts/viability_compute.py scores.json mapping.json
```

### Input Formats

**scores.json:**
```json
{
    "tests": {
        "A1": {
            "scorer_1": {
                "alpha": {"discovery": 4, "precision": 3, "completeness": 5, "relational": 4, "confidence": 4},
                "beta":  {"discovery": 3, "precision": 4, "completeness": 4, "relational": 2, "confidence": 3}
            },
            "scorer_2": {
                "alpha": {"discovery": 4, "precision": 4, "completeness": 4, "relational": 3, "confidence": 4},
                "beta":  {"discovery": 3, "precision": 3, "completeness": 4, "relational": 2, "confidence": 3}
            }
        }
    }
}
```

**mapping.json:**
```json
{
    "A1": {"alpha": "clew", "beta": "grep"},
    "A2": {"alpha": "grep", "beta": "clew"},
    "E1": {"alpha": "clew", "beta": "grep"}
}
```

### Verdict Thresholds (pre-registered, frozen)

| Verdict | Criteria |
|---------|----------|
| **Ship** | Overall avg ≥ 3.66 AND total wins ≥ 7/12 AND Track A avg ≥ 3.66 |
| **Iterate** | Overall avg ≥ 3.30 AND total wins ≥ 6/12 |
| **Kill** | Below Iterate |

Track assignments:
- Track A: A1, A2, A3, A4, B1, B2, C1, C2
- Track B: E1, E2, E3, E4

---

## 9. Post-Hoc Analysis Questions (Phase 5.5 — does NOT affect verdicts)

After Phase 5 computation, analyze raw (unsanitized) transcripts:

1. **ENUMERATION trigger count:** How many queries triggered autonomous grep? Which trigger path (ENUMERATION concurrent vs low-confidence post-hoc)?
2. **Enrichment visibility:** Did `context` field appear in clew results? Did agents reference relationship data from `context` in their reasoning?
3. **C1 improvement analysis:** Did "find all Django URL patterns" auto-classify as ENUMERATION? Did concurrent grep improve URL pattern completeness vs V2.3's 3.13?
4. **E4 honesty verification:** Did grep correctly NOT trigger for the focused debugging query? (Verify: `auto_escalated` should be false, `mode_used` should be "semantic")
5. **Cross-version stability:** How many Track A tests flipped winner direction vs V2.3? If >4 flipped, flag "agent variance dominates."
6. **Enrichment quality:** For tests where `context` was populated, was the relationship data accurate and useful? Or was it noise?

---

## 10. Edge Cases

| Edge Case | Handling |
|-----------|----------|
| Clew agent uses `rg` via Bash | Allowed. Sanitize as `search(...)`. Same as V2.3. |
| Tool timeout or rate limit | Re-run once. Second failure → score partial transcript. |
| Agent gives up early | Score as-is. Low output is valid data. |
| Enrichment cache empty | Score as-is. Note in results. Empty `context` fields mean enrichment wasn't populated — data gap, not tool failure. |
| Grep augmentation adds noise | Score as-is. Autonomous decisions have consequences — that's what we're measuring. |
| Agent reads CLAUDE.md or test plan | Invalid transcript — re-run with stricter isolation. |

---

## 11. Results Document Template

Produce results at `.clew-eval/v4/viability_results.md`:

```markdown
# V4 Viability Evaluation Results

**Date:** YYYY-MM-DD
**Verdict:** [Ship / Iterate / Kill]
**Overall Clew avg:** X.XX/5.0
**Overall Grep avg:** X.XX/5.0
**Win/Loss:** N clew / M grep / P tie (of 12)

## What Changed Since V2.3
[Summary of V4 changes]

## Methodology
[Link to test plan + any deviations]

## Track A: Regression (A1-C2)
- Clew avg: X.XX/5.0 (Ship threshold: 3.66)
- Grep avg: X.XX/5.0
- Win/Loss: N/M/P

### V2.3 Comparison
| Test | V2.3 Clew | V2.3 Winner | V4 Clew | V4 Winner | Delta |
[Cross-version comparison with calibration caveat]

## Track B: V4-Advantaged (E1-E4)
- Clew avg: X.XX/5.0
- Grep avg: X.XX/5.0
- Win/Loss: N/M/P

## Per-Test Results
[Full results table]

## Per-Test Dimension Scores
[Dimension breakdown for clew and grep]

## Sanitization Verification Results
[Verifier confidence per test, pass/fail]

## Scorer Agreement Analysis
[% within 1 point, disagreement details]

## Post-Hoc Analysis
### ENUMERATION Trigger Analysis
### Enrichment Visibility
### C1 Improvement Analysis
### E4 Honesty Check
### Cross-Version Stability

## What the Tool Does Well
## What the Tool Still Struggles With
## Confidence Notes
## Score History
[V2.3 → V4 comparison]
```

---

## 12. Execution Checklist

### Phase -1 + Phase 0 (parallel)
- [ ] Pre-flight checks pass (Section 2)
- [ ] Phase -1: Validate E1-E4 scenarios against target codebase
- [ ] Phase -1: Produce ground-truth checklists (≥5 artifacts each)
- [ ] Phase -1: Seal checklists

### Phase 1 (parallel)
- [ ] Track A: Launch 16 exploration agents (8 tests × 2 agents)
- [ ] Track B: Launch 8 exploration agents (4 tests × 2 agents, after Phase -1)
- [ ] All 24 transcripts collected

### Phase 2
- [ ] Launch 12 sanitization agents
- [ ] 24 sanitized transcripts produced
- [ ] Mapping file sealed

### Phase 3
- [ ] Launch verification agent
- [ ] ≤3 of 12 tests identified at >60% confidence → PASS
- [ ] If FAIL: re-sanitize and re-verify (or proceed with caveat)

### Phase 4
- [ ] Launch 24 scoring agents (2 per test)
- [ ] All ratings collected in scores.json format

### Phase 5
- [ ] Run `python3 scripts/viability_compute.py scores.json mapping.json`
- [ ] Record verdict

### Phase 5.5
- [ ] Analyze raw transcripts for ENUMERATION triggers, enrichment visibility, E4 honesty
- [ ] Document findings (does NOT affect verdict)

### Phase 6 (conditional)
- [ ] If scorer disagreements: launch tiebreaker scorers
- [ ] Re-run computation

### Finalize
- [ ] Write results document at `.clew-eval/v4/viability_results.md`
- [ ] Verify all post-hoc analysis questions answered

---

## References

| Document | Path | Purpose |
|----------|------|---------|
| **Test plan** | `.clew-eval/v4/viability_test_plan.md` | Authoritative reference for all methodology details |
| **Calibration analysis** | `.clew-eval/v4/calibration_analysis.md` | Confidence threshold calibration data |
| **Calibration data** | `.clew-eval/v4/calibration_raw.json` | Raw calibration query results |
| **Evaluation standards** | `docs/VIABILITY-EVALUATION-STANDARDS.md` | Generic methodology (Phase -1 through Phase 6) |
| **Computation script** | `scripts/viability_compute.py` | Programmatic aggregation with V4 thresholds |
| **V2.3 results** | `docs/plans/2026-02-17-v2.3-viability-results.md` | Baseline for Track A regression comparison |
| **ADR-006** | `docs/adr/006-agent-tool-design-boundary.md` | Agent-tool design boundary rationale |
| **ADR-007** | `docs/adr/007-autonomous-mode-switching.md` | Autonomous mode switching rationale |
| **Target codebase** | `/Users/albertgwo/Work/evvy` | Evaluation target |
