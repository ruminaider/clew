# V4 Viability Test Plan: Autonomous Mode Switching + Result Enrichment

**Date:** 2026-02-21
**Tests:** V4 code (autonomous grep escalation, ENUMERATION concurrent grep, result-level enrichment, calibrated confidence thresholds)
**Goal:** Verify V4 maintains Ship quality on V2.3 scenarios AND demonstrates improvement on completeness-focused tasks via autonomous intelligence

---

## What Changed Since V2.3

V2.3 shipped at 3.96/5.0 (5/8 wins). V3 (two iterations) was KILLED because its delivery mechanism — embedding metadata in search output to guide agent behavior — was structurally incompatible with how agents process tool output. Agents pipe away top-level metadata (`| head -100`, `| python3 -c "data['results']"`), and ignore system prompt hints about `--mode`/`--exhaustive` flags.

V4 preserves V3's computation (confidence scoring, ENUMERATION detection, grep integration) but changes the delivery mechanism to autonomous intelligence: the engine decides when to augment, and enrichment is embedded in individual results where it survives piping.

| Change | Impact |
|--------|--------|
| **Autonomous grep for ENUMERATION** | "Find all X" queries trigger concurrent grep alongside semantic search — zero added latency, no agent involvement |
| **Post-hoc grep for low confidence** | When confidence is low (RRF gap < 0.02), grep runs after semantic search to augment results (~1-5s added) |
| **Result-level enrichment** | Top 5 results gain a `context` field ("Called by: X \| Tests: Y") with relationship data — survives piping because agents iterate over results |
| **Calibrated confidence thresholds** | RRF high=0.06, medium=0.02 (empirically calibrated against 30 queries — see calibration_analysis.md) |
| **grep_response_cap enforcement** | Merged grep results capped at 100 (prevents catastrophic noise like the 11K-result case in calibration) |
| **No mode flags exposed** | `--mode` preserved as hard-floor override but NOT surfaced as agent guidance. Engine decides autonomously. |
| **No metadata in responses** | `confidence_label`, `suggestion`, `related_files` removed from CLI/MCP output. Agent can't see or ignore what isn't there. |

**Key design insight (ADR-006):** Tools should be smarter so agents can be simpler. Response-level metadata is invisible to agents (piped away). Result-level enrichment survives piping (agents iterate over results). V4 acts on this insight.

---

## Evaluation Structure

### Design Principles

1. **No feature-visibility criteria.** V4 features are autonomous — the engine decides when to augment. There is nothing for agents to "see" or "adopt." Score improvement is the only signal.
2. **Purely quantitative verdicts.** Win rate + avg score + regression check. No qualitative gates.
3. **V2.3 baseline.** V2.3 (3.96/5.0, 5/8 wins) is the SHIP version for regression comparison.
4. **Same rubric.** Reuse the validated 5-dimension scoring rubric from V2.3.
5. **12 tests minimum.** Control for agent variance (6/8 Track A tests flipped in V3.0).

### Two Tracks

| Track | Tests | Purpose | Comparison |
|-------|-------|---------|------------|
| **A: Regression** | 8 (reuse V2.3 scenarios A1-C2) | Verify V4 default behavior ≥ V2.3 quality | V4 clew vs grep |
| **B: V4-Advantaged** | 4 (new scenarios E1-E4) | Demonstrate V4 autonomous improvement on diverse tasks | V4 clew vs grep |

**Why two tracks:**
- Track A prevents regressions. V4's autonomous ENUMERATION classification and post-hoc grep should help even without agent awareness, but the primary goal is "no worse than V2.3."
- Track B tests V4's unique value proposition: does autonomous intelligence improve results when the engine can choose to augment? Includes ENUMERATION (concurrent grep), borderline (post-hoc grep), enrichment (context field), and a negative honesty check (grep should NOT trigger).

### Combined Verdict

| Verdict | Criteria |
|---------|----------|
| **Ship** | Overall avg ≥ 3.66 AND total wins ≥ 7/12 AND Track A avg ≥ 3.66 |
| **Iterate** | Overall avg ≥ 3.30 AND total wins ≥ 6/12 |
| **Kill** | Below Iterate |

**Regression guardrail:** 3.66 = V2.3 (3.96) minus 0.30 variance buffer. V2.3 demonstrated ±0.3 score swings from agent variance alone. Track A below 3.66 indicates a real regression.

**Simplified verdict tiers:** V3.0 had Ship (Improved) / Ship (Maintained) — unnecessarily complex. V4 uses a single Ship tier: either V4 is good enough to ship, or it isn't.

---

## Methodology

Follows `docs/VIABILITY-EVALUATION-STANDARDS.md` with the same improvements established in V2.3:

- Pre-registered methodology (this document)
- 2+ scorers per test with tiebreaker protocol
- Transcript sanitization with verification gate
- Programmatic winner determination via committed script (`scripts/viability_compute.py`)
- Relational insight scored for both tools

### Agent Models

| Role | Model | Rationale |
|------|-------|-----------|
| Exploration agents | Sonnet 4.6 | Matches V2.3 exploration agents |
| Sanitization agents | Sonnet 4.6 | Consistent with V2.3 |
| Verification agent | Sonnet 4.6 | Consistent with V2.3 |
| Scoring agents | Sonnet 4.6 | Consistent with V2.3 |
| Tiebreaker agents | Sonnet 4.6 | Consistent with V2.3 |
| Orchestration | Opus 4.6 | Coordinates pipeline execution |
| Scenario validation | Sonnet 4.6 | Pre-exploration codebase analysis |
| Post-hoc analysis | Sonnet 4.6 | Feature usage analysis |

### Methodology Notes for V4

**1. No tool-awareness hints for either agent**

Unlike V3.0, V4 does not expose modes for agents to discover. Both Track A and Track B agents receive only the scenario description. No hints about `--mode`, `--exhaustive`, `--help`, or any other flags. V4's value comes from autonomous engine behavior, not agent feature discovery.

**2. V4-specific sanitization**

V4 introduces result-level enrichment that needs careful sanitization:
- `"source": "grep"` field on grep-originated results → remove
- `"context": "Called by: X | Tests: Y"` field on enriched results → normalize to `"related": "..."`
- Add empty `"related": ""` to grep-tool results during sanitization so the field's presence/absence doesn't identify the tool

**3. Soft tool-call budget**

All exploration agents receive: "You have a budget of approximately 20 tool calls. Prioritize finding the most important artifacts first."

**4. Separate Track A and Track B during scoring**

Score Track A (A1-C2) and Track B (E1-E4) in separate scorer sessions. Don't mix tracks.

---

## Scoring Rubric

### Dimensions (unchanged from V2.3)

| Dimension | Weight | What It Measures |
|-----------|--------|------------------|
| Discovery Efficiency | 30% | How quickly the agent reaches actionable understanding |
| Context Precision | 25% | Signal-to-noise ratio in loaded context |
| Completeness | 20% | Coverage of key artifacts per test checklist |
| Relational Insight | 15% | Connections surfaced that the agent did not explicitly search for |
| Answer Confidence | 10% | Whether the final output is actionable without further investigation |

### Rating Scale

| Score | Discovery Efficiency | Context Precision | Completeness | Relational Insight | Answer Confidence |
|-------|---------------------|-------------------|--------------|-------------------|-------------------|
| 5 | Reaches understanding in ≤3 tool calls | ≤10% noise | All checklist artifacts found | ≥3 unexpected connections | Immediately actionable |
| 4 | 4-5 tool calls | 10-20% noise | ≥90% found | 2 connections | Needs 1 follow-up read |
| 3 | 6-8 tool calls | 20-40% noise | ≥70% found | 1 connection | Needs 2-3 follow-ups |
| 2 | 9-12 tool calls | 40-60% noise | 50-70% found | 0 but tool supports it | Needs significant follow-up |
| 1 | 12+ calls or gives up | 60%+ noise | <50% found | Tool has no relational capability | Not actionable |

### Winner Determination (unchanged from V2.3)

```
weighted_score = (discovery * 0.30) + (precision * 0.25) + (completeness * 0.20) + (relational * 0.15) + (confidence * 0.10)

if clew_weighted > grep_weighted:
    winner = "clew"
elif grep_weighted > clew_weighted:
    winner = "grep"
else:  # exact tie
    winner = "higher completeness score"  # tiebreaker
```

When 2 scorers disagree on winner direction, use the average of both scorers' weighted scores.

### Completeness Scoring

- Track A: qualitative checklists from V2.3 (validated across multiple rounds)
- Track B: ground-truth checklists produced by Phase -1 scenario validation agent
- Bonus discoveries: scorers may award up to +0.5 for valid artifacts beyond the checklist

---

## Track A: Regression Scenarios

Reuse all 8 V2.3 scenarios. The clew agent runs V4 code. ENUMERATION auto-classification and post-hoc grep escalation are active autonomously — the agent has no way to influence them.

| Test | Category | Scenario | V2.3 Clew | V2.3 Winner |
|------|----------|----------|-----------|-------------|
| A1 | Discovery | Subscription renewal → PrescriptionFill creation failure | 3.73 | grep |
| A2 | Discovery | Add new checkout source type — what code changes? | 3.95 | clew |
| A3 | Discovery | Pharmacy API errors — call sites, error handling, retry logic | 4.38 | clew |
| A4 | Discovery | Order type determination and downstream processing | 4.38 | clew |
| B1 | Structural | Impact of changing Shopify order processing function signature | 3.55 | grep |
| B2 | Structural | Map Order / PrescriptionFill / Prescription model relationships | 3.67 | clew |
| C1 | Grep-Advantaged | Find all Django URL patterns for ecomm-related views | 3.13 | grep |
| C2 | Grep-Advantaged | Find all Stripe API calls in the codebase | 4.85 | clew |

### Full Scenario Text (identical to V2.3)

**A1:**
> "A customer reported their subscription renewal didn't create a prescription fill. Investigate the code path from order webhook to PrescriptionFill creation and identify where failures can occur."

**A2:**
> "We need to add a new checkout source type for a partner integration. What code needs to change? Provide a comprehensive list of files and code locations that reference or depend on the checkout source concept."

**A3:**
> "The pharmacy API is returning errors for some refill orders. Where in the codebase do we call the pharmacy API, how do we handle errors from it, and what retry/monitoring logic exists?"

**A4:**
> "Explain how the order processing system decides what type of order it is (e.g., new subscription vs. refill vs. one-time purchase) and how that determination affects downstream processing."

**B1:**
> "We're considering changing the signature of the function that processes shopify orders for treatment refills. What would break? Find all callers, understand what arguments they pass, and identify any test coverage."

**B2:**
> "Map the relationship between Order, PrescriptionFill, and Prescription models. Include foreign keys, many-to-many relationships, through-tables, and any computed properties that bridge them."

**C1:**
> "Find all Django URL patterns that involve ecomm-related views. List each URL pattern with its view and URL path."

**C2:**
> "Find all Stripe API calls in the codebase. List each call site with the Stripe API method being called and the context in which it's used."

### Expected V4 Impact on Track A

**Automatic improvements (no agent involvement):**
- **C1:** "Find all Django URL patterns" should auto-classify as ENUMERATION, triggering concurrent grep. Expected: completeness improvement from V2.3's 3.13.
- **C2:** "Find all Stripe API calls" should auto-classify as ENUMERATION. Concurrent grep finds literal `stripe.` calls. V2.3 already scored 4.85 — ceiling effect likely.
- **A2:** "comprehensive list of files" may trigger ENUMERATION. If so, grep catches file references that semantic search missed.
- **B1:** "Find all callers" may trigger ENUMERATION. More callers discovered via grep.

**Enrichment improvements:**
- Top 5 results now include `context` field ("Called by: X | Tests: Y"). Agents iterating over results see relationship data without additional trace calls. This could improve Discovery Efficiency and Relational Insight across all tests.

**Post-hoc escalation (rare):**
- Only fires when confidence is low (RRF gap < 0.02). Calibration showed this triggers on ~13% of non-ENUMERATION queries. Most Track A queries have moderate-to-high confidence, so post-hoc escalation is unlikely for most tests.

**Regression risks:**
- ENUMERATION misclassification: if "find all bugs" triggers ENUMERATION instead of DEBUG, grep noise could hurt precision
- Grep augmentation noise: even with the 100-result cap, grep additions could reduce context precision
- Enrichment noise: `context` field adds text that may not always be relevant

---

## Track B: V4-Advantaged Scenarios

Four new scenarios testing V4's autonomous intelligence across different task shapes. No tool-awareness hints for either agent — V4's value comes from the engine, not agent behavior.

---

### Test E1: Middleware Audit (post-hoc escalation target)

**Scenario given to both agents:**

> "Our application uses custom Django middleware for request processing. Map all custom middleware classes: what each one does, what order they run in, and how they interact with each other. Focus on application-specific middleware, not standard Django middleware. Also identify any middleware that conditionally skips processing based on request attributes."

**Qualitative checklist (ground-truth produced by Phase -1 validation):**
- All custom middleware classes (names and file locations)
- Processing order (MIDDLEWARE setting or equivalent)
- Purpose of each middleware (logging, auth, rate limiting, etc.)
- Middleware interactions (one middleware depends on another's output)
- Conditional skip logic (request path exemptions, feature flags, etc.)

**Why this tests V4:**
This is a borderline semantic/enumeration task. The query mentions "all custom middleware" (ENUMERATION-adjacent) but also asks about interactions and conditional logic (semantic). If the engine classifies it as non-ENUMERATION but confidence is low, post-hoc grep should fire and catch middleware classes that semantic search missed. If ENUMERATION fires, concurrent grep helps with completeness.

**Expected advantage:** Clew (V4 autonomous) > Grep > Clew (V2.3 semantic only)

---

### Test E2: Celery Task Inventory (ENUMERATION + concurrent grep target)

**Scenario given to both agents:**

> "Create a complete inventory of all Celery tasks in the codebase. For each task, identify: (1) the task function name and file location, (2) what arguments it accepts, (3) how it is enqueued (`.delay()`, `.apply_async()`, or `send_task()`), (4) what retry configuration it has (if any), and (5) the business purpose of the task."

**Qualitative checklist (ground-truth produced by Phase -1 validation):**
- All `@shared_task` or `@app.task` decorated functions with locations
- Arguments for each task
- All `.delay()` and `.apply_async()` call sites
- Retry configuration per task (`autoretry_for`, `max_retries`, `retry_backoff`)
- Business context for each task

**Why this tests V4:**
"Complete inventory of all Celery tasks" should trigger ENUMERATION, launching concurrent grep for `@shared_task`, `@app.task`, `.delay()`, `.apply_async()` patterns alongside semantic search. Grep provides exhaustive enumeration while semantic search provides business context. This is V4's primary mechanism.

**Expected advantage:** Clew (V4 ENUMERATION + grep) > Grep > Clew (V2.3 semantic only)

---

### Test E3: Model Dependency Chain (result enrichment target)

**Scenario given to both agents:**

> "Starting from the Order model, trace how creating an order triggers the creation of related records. Map the full chain: which models are created as side effects of order processing, what service functions orchestrate this creation, and what happens if any step in the chain fails. Include the relationships between the created records."

**Qualitative checklist (ground-truth produced by Phase -1 validation):**
- Order model and its creation path
- Related models created during order processing (PrescriptionFill, etc.)
- Service functions that orchestrate multi-model creation
- Error handling / transaction management in the creation chain
- Relationships between created models (ForeignKey, M2M, through-tables)

**Why this tests V4:**
V4's `context` enrichment field on top-5 results provides "Called by: X | Tests: Y" relationship data. An agent reading search results now sees navigational scaffolding — it knows which functions call the result and what tests cover it, without needing a separate trace call. This should improve both Discovery Efficiency (fewer follow-up searches needed) and Relational Insight (connections surfaced automatically).

**Expected advantage:** Clew (V4 enrichment) > Clew (V2.3 no enrichment) ≥ Grep

---

### Test E4: Email Confirmation Debugging (honesty check — grep should NOT trigger)

**Scenario given to both agents:**

> "A user reported that their subscription order was processed successfully but they didn't receive a confirmation email. Investigate the email sending pipeline from order completion to email dispatch. Focus on identifying the specific failure path — where in the code could the email send fail silently? Do NOT catalog all email-related code in the codebase."

**Qualitative checklist (ground-truth produced by Phase -1 validation):**
- Order completion trigger point (where email send is initiated)
- Email sending function/service
- Template selection logic
- Error handling around email dispatch
- At least one plausible silent failure mode

**Why this is the honesty check:**
This is a focused debugging task. The scenario explicitly says "do NOT catalog all email-related code." Semantic search should handle this efficiently — find the order→email path and trace the failure modes. The query should NOT trigger ENUMERATION (no "find all" / "list all" language). Confidence should be moderate-to-high, so post-hoc grep should NOT fire. If V4's grep augmentation triggers here, it would add noise (every occurrence of "email" in the codebase) without benefit.

This validates calibration correctness: the 0.02/0.06 RRF thresholds and ENUMERATION detection should correctly leave this query in semantic-only mode.

**Expected advantage:** Clew (semantic only) > Grep ≥ Clew (if grep wrongly triggered)

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
| `confidence`, `confidence_label`, `suggestion_type` | Remove |
| `mode_used`, `auto_escalated` | Remove |
| `intent` field | Remove |
| Qdrant/embedding metadata | Remove |

**Critical for blind scoring:** Add empty `"related": ""` to grep-tool results during sanitization so the field's presence/absence doesn't identify the tool. Both tools' results should have a `"related"` field — clew's populated, grep's empty.

### What to Preserve

| Category | Rationale |
|----------|-----------|
| File paths | Both tools return these |
| Code content | This is the search result, not the tool |
| Line numbers | Both tools produce these |
| Agent reasoning | This is what we're scoring |
| Final answer | Primary evaluation target |

---

## Execution Pipeline

### Pipeline Overview

```
Phase 0: Pre-flight (5 min, manual)
  ├──→ Phase 1A: Track A exploration (8 tests × 2 agents = 16 agents)
  └──→ Phase -1: Track B scenario validation (1-2 agents)
         └──→ Phase 1B: Track B exploration (4 tests × 2 agents = 8 agents)
                  ↓ (both tracks complete)
Phase 2: Sanitization (12 agents, 1 per test)
  → Phase 3: Verification (1 agent)
    → Phase 4: Scoring (24 agents, 2 per test)
      → Phase 5: Computation (script — no agents)
        → Phase 5.5: Post-hoc analysis (1-2 agents, does NOT affect verdicts)
          → Phase 6: Disagreement resolution (0-12 agents, conditional)
```

### Phase -1: Scenario Validation + Ground-Truth Checklists

A validation agent analyzes `/Users/albertgwo/Work/evvy` to verify each Track B scenario (E1-E4) is viable.

**For each scenario:**
1. Run searches to confirm sufficient artifacts exist (≥5 concrete items per scenario)
2. Produce ground-truth checklist of specific named artifacts
3. Seal checklists before Track B exploration starts

**Viability threshold:** ≥5 concrete artifacts per checklist. If a scenario fails:
- Replace with alternative from same category
- Document replacement and reason

**Timing:** Runs in parallel with Track A exploration.

### Phase 0: Pre-flight

- [ ] Qdrant running: `docker compose up -d qdrant`
- [ ] V4 code installed: `pip3 install -e .` (in `/Users/albertgwo/Repositories/clew`)
- [ ] Target codebase exists: `/Users/albertgwo/Work/evvy`
- [ ] Index current: `clew status --project-root /Users/albertgwo/Work/evvy` (should show enriched index)
- [ ] V4 features verified:
  - [ ] ENUMERATION auto-classification: `clew search "find all models" --project-root /Users/albertgwo/Work/evvy --json` → confirm `intent` is `enumeration` and `auto_escalated` is true
  - [ ] Enrichment: `clew search "order processing" --project-root /Users/albertgwo/Work/evvy --json` → confirm top results have `context` field
  - [ ] Trace working: `clew trace "PrescriptionFill" --project-root /Users/albertgwo/Work/evvy --json` → resolves to Python model
- [ ] All tests pass: `pytest` (expect 774+ passing)
- [ ] Agent environment clean: test agents do NOT have access to this plan, CLAUDE.md, or documentation

### Phase 1: Exploration (24 agents)

For each of the 12 tests, launch 2 exploration agents:

**Grep agent (all tests):**
- Tools: Grep, Glob, Read (in target codebase)
- No Bash, no clew access
- Receives only the scenario description
- No access to test plan, CLAUDE.md, or codebase documentation
- Working directory: `/Users/albertgwo/Work/evvy`

**Clew agent (all tests — Track A and Track B identical setup):**
- Tools: Bash (for clew CLI), Read (for follow-up)
- Receives only the scenario description
- No access to test plan, CLAUDE.md, or codebase documentation
- No hints about modes, flags, features, or V4 capabilities
- Working directory: `/Users/albertgwo/Work/evvy`

**Soft tool-call budget:** All exploration agents receive: "You have a budget of approximately 20 tool calls. Prioritize finding the most important artifacts first."

**Parallelization:** All 8 Track A test pairs can run in parallel. Track B starts after Phase -1 completes.

### Phase 2: Sanitization (12 agents, 1 per test)

For each test, a sanitization agent:
1. Reads both raw transcripts
2. Randomly assigns Alpha/Beta labels (coin flip, recorded in mapping file)
3. Applies the normalization table (see Sanitization Rules above)
4. Produces two sanitized transcripts
5. Records Alpha/Beta → clew/grep mapping in sealed file

Output: 24 sanitized transcripts + 1 mapping file.

### Phase 3: Verification (1 agent)

A single verification agent reads all 24 sanitized transcripts and attempts to identify which tool each agent used. Reports confidence per test.

**Pass criteria:** Correct identification at >60% confidence on no more than 3 of 12 tests (25%).

**Escalation:**
1. **First failure (>3 tests identified):** Re-sanitize with stricter rules (normalize query text, remove intermediate reasoning)
2. **Second failure:** Proceed with documented caveat (consistent with V2.3 precedent)

### Phase 4: Scoring (24 agents, 2 per test)

For each test, 2 independent scoring agents:
1. Receive both sanitized transcripts (Alpha and Beta)
2. Receive the scoring rubric with dimension-specific anchors
3. For Track B tests: also receive the frozen ground-truth checklist from Phase -1
4. Rate each transcript on 5 dimensions (integer 1-5)
5. Do NOT compute weighted averages or declare a winner

**Scorer prompt (exact text):**

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
> **Bonus discoveries:** If an agent finds valid artifacts not on the checklist, you may award a bonus to Completeness (e.g., 4 → 5) at your discretion. Do not penalize for missing items not on the checklist.
>
> For each transcript, output your 5 ratings as integers only. Example format:
> ```
> Agent Alpha: Discovery=4, Precision=3, Completeness=5, Relational=4, Confidence=4
> Agent Beta: Discovery=3, Precision=4, Completeness=4, Relational=2, Confidence=3
> ```

**Track separation:** Score Track A (A1-C2) and Track B (E1-E4) in separate scoring sessions.

### Phase 5: Computation (programmatic, no agents)

Run `scripts/viability_compute.py`:

1. Reads all scorer ratings from `scores.json`
2. Averages ratings from 2 scorers per dimension
3. Computes weighted averages per test per agent
4. Determines winner per test
5. Unmasks Alpha/Beta using `mapping.json`
6. Computes Track A, Track B, and overall averages
7. Applies verdict thresholds:
   - Ship: overall avg ≥ 3.66 AND total wins ≥ 7/12 AND Track A avg ≥ 3.66
   - Iterate: overall avg ≥ 3.30 AND total wins ≥ 6/12
   - Kill: below Iterate
8. Flags scorer disagreements (>1 point on any dimension)

### Phase 5.5: Post-Hoc Analysis (does NOT affect verdicts)

After computation, analyze raw (unsanitized) transcripts for qualitative insights:

1. **ENUMERATION trigger analysis:** How many queries triggered autonomous grep? Which trigger path (ENUMERATION concurrent vs low-confidence post-hoc)?
2. **Enrichment visibility:** Did `context` field appear in results? Did agents read/reference the relationship data?
3. **C1 improvement:** Did ENUMERATION auto-classify? Did concurrent grep improve URL pattern completeness vs V2.3's 3.13?
4. **E4 honesty check:** Did grep correctly NOT trigger for the focused debugging query?
5. **Cross-version stability:** How many Track A tests flipped direction vs V2.3?

### Phase 6: Disagreement Resolution (conditional)

If any scorer pair disagrees by >1 point on any dimension:
1. Launch third tiebreaker scorer for that test only
2. Use median of 3 scores for each dimension
3. Re-run Phase 5 computation

---

## Edge Cases

| Edge Case | Handling | Rationale |
|-----------|----------|-----------|
| **Clew agent uses grep via Bash** | Allowed. Sanitize `rg` commands as `search(...)`. | Same policy as V2.3. |
| **Tool timeout or rate limit** | Re-run once. If it recurs, score partial transcript as-is. | Infra failure ≠ tool quality. |
| **Agent gives up early** | Score as-is. | Giving up is valid data. |
| **Grep augmentation adds noise** | Score as-is. | Autonomous decisions have consequences — that's what we're measuring. |
| **Enrichment `context` field is empty** | Score as-is. | Empty enrichment (no relationships in cache) is a data gap, not a tool failure. |

---

## Agent Budget

| Phase | Agents | Notes |
|-------|--------|-------|
| Scenario validation | 1-2 | Track B validation (parallelizes with Track A exploration) |
| Exploration | 24 | 2 per test × 12 tests |
| Sanitization | 12 | 1 per test |
| Verification | 1 | Sequential |
| Scoring | 24 | 2 per test × 12 tests |
| Tiebreaker | 0-12 | Only if disagreements |
| Post-hoc analysis | 1-2 | Qualitative only |
| **Total** | **64-78** | |

---

## Expected Outcomes

### Optimistic: Ship

V4's ENUMERATION auto-classification improves C1 (V2.3's weakest at 3.13). Enrichment `context` field improves Discovery Efficiency and Relational Insight across the board. Track A maintains or improves V2.3 (avg ~4.0, 6/8 wins). Track B shows clear autonomous improvement (avg ~3.8, 3-4 wins).

**Predicted:** Ship — overall avg ~4.0, wins 8-9/12, Track A avg ~4.0

### Realistic: Ship (borderline)

Track A maintains V2.3 quality (avg ~3.8, 5/8 wins). ENUMERATION helps C1 slightly but doesn't flip it. Enrichment provides marginal benefit. Track B: E2 (ENUMERATION) wins convincingly, E3 (enrichment) marginal, E1 (post-hoc) depends on calibration, E4 (honesty) correctly scored. Total wins 7-8/12.

**Predicted:** borderline Ship — overall avg ~3.7, wins 7/12, Track A avg ~3.7

### Pessimistic: Iterate

Agent variance dominates (as in V3.0 where 6/8 Track A tests flipped). Enrichment `context` field is empty (enrichment cache not populated). Track A scores ~3.5, wins 4/8. Track B: E2 wins, E4 tie, E1 and E3 lose.

**Predicted:** Iterate — overall avg ~3.5, wins 6/12

---

## Comparison with V3.0 Methodology

| Aspect | V3.0 | V4 |
|--------|------|-----|
| Agent hints | Symmetric tool-awareness hints (Track B) | None (V4 is autonomous) |
| Feature visibility criteria | Implicit (features expected to appear in output) | None (autonomous = no visibility needed) |
| Mode flags | `--mode`, `--exhaustive` exposed to agents | Not exposed (engine decides) |
| Sanitization complexity | High (mode flags, confidence fields, grep_results keys) | Lower (no mode artifacts; only source and context fields) |
| Track B design | Tests mode discoverability + effectiveness | Tests autonomous intelligence + enrichment |
| Verdict tiers | Ship (Improved) / Ship (Maintained) / Iterate / Kill | Ship / Iterate / Kill |
| Feature analysis | Phase 5.5 analyzed confidence signaling, peripheral surfacing | Phase 5.5 analyzes trigger paths, enrichment visibility |
| V3 failure mode addressed | N/A | Response-level metadata → result-level enrichment |

---

## Post-Evaluation

Regardless of verdict, produce a results document containing:

1. Per-test dimension scores for both tools, both tracks
2. V2.3 comparison table (Track A side-by-side, with cross-version calibration caveat)
3. Scorer agreement analysis (% within 1 point)
4. Sanitization verification results
5. ENUMERATION trigger analysis (which Track A tests auto-classified)
6. Enrichment visibility analysis (did `context` appear? did agents use it?)
7. E4 honesty check results (did grep correctly NOT trigger?)
8. Cross-version stability (Track A flip count vs V2.3)

### If Ship
V4 autonomous intelligence is validated. Document and move to:
- MCP-native evaluation (test MCP tools, not CLI)
- Human evaluation for subset of tests
- Broader codebase testing (beyond Evvy)

### If Iterate
Identify specific regression points. Likely causes:
- Enrichment cache empty (need to verify enrichment before eval)
- ENUMERATION misclassification producing noise
- Confidence thresholds still miscalibrated
- Agent variance (check Track A flip count)

### If Kill
V4 autonomous approach doesn't work. Possible pivots:
- Abandon grep integration (simplify to V2.3 + enrichment only)
- Investigate whether result-level enrichment alone provides value
- Consider alternative architectures (separate tools like Cursor)

---

## References

- Calibration analysis: `.clew-eval/v4/calibration_analysis.md`
- Calibration data: `.clew-eval/v4/calibration_raw.json`
- V2.3 results: `docs/plans/2026-02-17-v2.3-viability-results.md`
- V2.3 test plan: `docs/plans/2026-02-17-v2.3-viability-test-plan.md`
- V3.0 test plan: `docs/plans/2026-02-18-v3.0-viability-test-plan.md`
- Evaluation standards: `docs/VIABILITY-EVALUATION-STANDARDS.md`
- ADR-006 (agent-tool boundary): `docs/adr/006-agent-tool-design-boundary.md`
- ADR-007 (autonomous mode switching): `docs/adr/007-autonomous-mode-switching.md`
- Computation script: `scripts/viability_compute.py`
- Target codebase: `/Users/albertgwo/Work/evvy`
