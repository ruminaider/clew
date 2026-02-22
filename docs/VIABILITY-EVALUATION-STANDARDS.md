# Viability Evaluation Standards

Reusable methodology for running blind, agent-based A/B evaluations of tool effectiveness. Developed through four iterations (V1-V2.3) of evaluating clew against grep baselines, with methodology improvements from V3.0 planning review.

These standards apply whenever you need to answer: "Does tool X provide meaningful value over baseline Y for task Z?"

---

## Core Principles

### 1. Pre-register everything

All rules, thresholds, scoring formulas, and winner-determination logic must be written down BEFORE any agent runs. No post-hoc corrections, re-weighting, or rule changes after results are in. If a scorer makes an error, the mechanical formula overrides their stated conclusion.

**Why:** V2.2 required a post-hoc correction (A1 scorer arithmetic error) and post-hoc rule clarification (relational insight for grep). Both undermined credibility even though the corrections were justified.

### 2. Measure what matters, not what's easy

Test scenarios should reflect the tool's intended use case, not the baseline's strengths. If the tool is designed for semantic discovery, test semantic discovery — don't test exact-string lookup speed.

**Why:** V1-V2.1 tested "Can clew find function X faster than `Grep('def X')`?" — the wrong question. V2.2 switched to scenario-based prompts ("Investigate why subscription renewal failed") and results immediately became more meaningful.

### 3. Include honesty checks

Always include tests where the baseline is expected to win. These validate the evaluation framework itself. If the tool somehow wins on the baseline's home turf, the methodology is suspect.

**Why:** V2.2 Category C (grep-advantaged) tests confirmed grep won both, validating the scoring wasn't systematically biased toward clew.

### 4. Separate judgment from computation

Scorers provide raw ratings. Aggregation, weighting, and winner determination are programmatic. Scorers should never compute weighted averages or declare winners.

**Why:** V2.2's A1 scorer miscalculated a weighted average (reported 4.25 vs 4.25, actual was 4.35 vs 4.15) and broke the non-existent tie incorrectly.

---

## Blind Evaluation Pipeline

Every evaluation follows this 7-phase pipeline:

```
Phase -1: Scenario validation (verify scenarios against target codebase)
Phase 0: Pre-flight checks
Phase 1: Exploration (2 agents per test, independent)
Phase 2: Sanitization (normalize transcripts)
Phase 3: Verification (can a reader identify the tool?)
Phase 4: Scoring (2+ scorers per test, raw ratings only)
Phase 5: Computation (programmatic aggregation)
Phase 5.5: Post-hoc feature analysis (optional, qualitative)
Phase 6: Disagreement resolution (conditional tiebreakers)
```

### Phase -1: Scenario Validation

Before any exploration begins, a dedicated validation agent verifies each scenario is testable against the target codebase.

**Steps:**

1. For each scenario, the validation agent searches the target codebase to confirm relevant artifacts exist
2. Produce a **ground-truth checklist**: a concrete, named list of artifacts (files, classes, functions, endpoints) that a complete answer should reference
3. Each checklist must contain **≥5 concrete artifacts** — scenarios with fewer are too narrow for meaningful scoring
4. **Seal checklists** before exploration begins — no post-hoc modification once agents start running

**Replacement protocol:** If a scenario fails validation (insufficient artifacts, ambiguous scope, or structurally unsolvable by one tool), replace it with a new scenario from the same category. Document all replacements.

**Why:** Without validation, scenarios may be untestable or trivial. Ground-truth checklists convert subjective completeness scoring ("did they find enough?") into objective measurement ("did they find X, Y, Z?").

### Phase 0: Pre-flight

Verify the test environment before any agent runs:

- Tool under test is functional (health checks, sample queries)
- Baseline tool is functional
- Index/data is current (if applicable)
- Fix under test is installed and verified
- Agent environments are clean (no access to test plans, documentation, or prior results)

### Phase 1: Exploration

For each test scenario, launch 2 independent agents:

**Baseline agent:**
- Has access only to baseline tools (e.g., Grep, Glob, Read)
- No access to the tool under test
- Receives only the scenario description — no hints about file names, function names, or codebase structure

**Test agent:**
- Has access to the tool under test (plus Read for follow-up)
- Receives the same scenario description as the baseline agent
- Does not receive hints about tool features — must discover them organically

**Symmetric capability hints:** When testing specific tool features (not just tool existence), both agents should receive symmetric capability hints so the evaluation measures feature effectiveness rather than feature discoverability:
- Test agent: "This tool supports multiple modes. Run `--help` to see options."
- Baseline agent: "Your tools support various flags. Run `--help` to see options."

This eliminates coaching asymmetry while letting agents discover features organically. Omit hints when the evaluation intentionally measures discoverability.

**Critical constraints for BOTH agents:**
- No access to: test plans, CLAUDE.md, codebase documentation, prior evaluation results
- Start cold with zero codebase knowledge
- Same scenario text, same working directory

**Soft exploration budget:** Recommend a soft tool-call budget (e.g., ~20 calls) for exploration agents. This standardizes exploration length and makes Discovery Efficiency scoring more comparable across tests. The budget is a soft cap — agents may slightly exceed it — but exploration transcripts significantly beyond the budget should be noted in scoring.

**Why:** Without a budget, agents range from 8 to 30+ calls with no guidance, making discovery efficiency scores less comparable across tests.

**Parallelization:** All test pairs can run in parallel. Each agent is fully independent.

### Phase 2: Transcript Sanitization

A dedicated sanitization agent (separate from explorers and scorers) processes each raw transcript:

**What to normalize:**

| Category | Action |
|----------|--------|
| Tool invocation syntax | Replace all tool-specific syntax with generic labels (`search("...")`, `read("...")`, `find_files("...")`, `trace("...")`) |
| Tool-specific metadata | Remove scores, collection names, chunk IDs, enrichment flags, model names |
| Tool-specific output format | Strip JSON structure markers that only one tool produces |
| Agent labels | Randomly assign Alpha/Beta per test (coin flip, recorded in sealed mapping file) |

**What to preserve:**
| Category | Rationale |
|----------|-----------|
| File paths | Both tools return these |
| Code content | This is what the agent found — it's the result, not the tool |
| Line numbers | Both tools produce these |
| Agent reasoning | This is what we're scoring |
| Final answer | This is the primary evaluation target |

**Output:** 2 sanitized transcripts per test + 1 sealed mapping file (Alpha/Beta → tool identity).

### Phase 3: Verification Gate

A single verification agent reads all sanitized transcripts and attempts to identify which tool each agent used. For each test, it reports a confidence level (0-100%).

**Pass criteria:** The verifier guesses correctly with >60% confidence on no more than 25% of tests.

**Escalation on failure:**

1. **First failure:** Re-run Phase 2 with stricter sanitization (normalize query text, remove intermediate reasoning, keep only tool calls + results + final answer)
2. **Second failure:** Proceed with documented caveat — behavioral fingerprints may persist despite sanitization. The scoring rubric is absolute and tool-independent, which mitigates identification bias.

Pre-register this escalation so no post-hoc justification is needed.

**Why this matters:** If a reader can identify the tool from the transcript, the scoring is not truly blind. This gate converts "we tried to anonymize" into "we verified anonymization worked." The escalation prevents an infinite loop when sanitization can't fully anonymize (which V2.3 demonstrated is realistic).

### Phase 4: Scoring

2 independent scorers per test. Each scorer:

1. Receives both sanitized transcripts (Alpha and Beta) for a single test
2. Receives the scoring rubric with dimension definitions
3. Provides integer ratings (1-5) for each dimension for each transcript
4. Does NOT compute aggregates or declare a winner

**Scorer prompt template:**

> You are scoring two agent transcripts that attempted the same codebase exploration task. Score each agent independently on [N] dimensions using the rubric provided. Provide integer ratings (1-5) for each dimension.
>
> IMPORTANT: Score each agent against the absolute rubric, not relative to the other agent. A score of 3 means "adequate" regardless of what the other agent scored. Do NOT compute aggregates or declare a winner.

### Phase 5: Programmatic Computation

A script (not an agent) performs all aggregation:

1. Reads all scorer ratings
2. Averages ratings from multiple scorers per dimension
3. Computes weighted averages per test per agent
4. Determines winners per test (higher weighted average wins)
5. Unmasks Alpha/Beta using the sealed mapping file
6. Computes category and overall averages
7. Applies viability thresholds
8. Flags scorer disagreements (>1 point on any dimension)

**Reusable tooling:** `scripts/viability_compute.py` provides a starting point for programmatic computation. Thresholds and track assignments should be customized per evaluation, but the aggregation logic (weighted average, median tiebreaker, winner determination) is reusable.

### Phase 5.5: Post-hoc Feature Analysis (optional)

After programmatic computation, optionally analyze raw (unsanitized) transcripts for qualitative insights:

- Measure **feature usage**, not tool quality (e.g., "did confidence signaling change agent behavior?", "how often did agents use the new mode?")
- Does NOT affect verdicts or scores — published alongside quantitative results as a separate section
- Useful when the version under test adds new user-facing capabilities

**Why:** Quantitative scores tell you IF the tool improved. Post-hoc analysis tells you WHY (or why not). This phase is explicitly separated from scoring to prevent qualitative observations from influencing quantitative verdicts.

### Phase 5.5a: Feature Health Assessment (optional)

Pre-register a **feature health card** for each new feature being evaluated. Feature health is diagnostic — it measures whether features work as designed, independent of whether the tool produces good results.

**Health card format:**

| Feature | Metric | Target | Impact |
|---------|--------|--------|--------|
| (feature name) | (measurable metric) | (target range) | Advisory |

**Rules:**
- Feature health metrics are always **Advisory** — published alongside scores as diagnostic context, never verdict-affecting
- Feature health failure caps the verdict at **Iterate** (never Kill). A tool that produces good results with broken mechanisms should be improved, not killed
- Health cards must be pre-registered in the evaluation handoff BEFORE any agents run
- Metrics must be computable from raw (unsanitized) transcripts or tool logs

**Rationale:** V3.1 demonstrated the problem with verdict-affecting feature criteria: a tool won 3/4 tests but was killed because features were invisible to agents. Feature health should inform iteration priorities, not override outcome quality. Making feature health always advisory prevents perverse incentives (optimizing for metric compliance rather than user outcomes).

### Phase 5.5b: Counterfactual Analysis (optional)

For tools with augmentation or fallback mechanisms, compute the marginal contribution of each mechanism:

1. For each query where augmentation fired, extract the set of results from each source
2. Compute: `mechanism_unique = final_results - primary_results`
3. Compute: `marginal_contribution = |mechanism_unique| / |final_results|`
4. Aggregate: average marginal contribution, % of queries where mechanism found novel results

**Advisory thresholds:**
- `<10%` average marginal contribution: "mostly noise" — mechanism adds little value
- `>50%` average marginal contribution: "primary genuinely incomplete" — primary method has real gaps

This analysis runs on raw (unsanitized) transcripts. Results are published in the results document as diagnostic context.

**Tooling:** `scripts/counterfactual_analysis.py` automates this computation from structured behavioral data.

### Phase 6: Disagreement Resolution

If any scorer pair disagrees by >1 point on any dimension for a test:

1. Launch a third tiebreaker scorer for that test only
2. Use the median of 3 scores for each dimension
3. Re-run Phase 5 computation

---

## Scoring Rubric Design

### Dimension Selection

Choose 3-6 scoring dimensions. Each dimension should:
- Measure something distinct (no overlapping dimensions)
- Be observable from the transcript (scorers can't rate what they can't see)
- Have clear 1-5 anchor definitions

Assign weights that reflect the tool's value proposition. Pre-register weights before any agent runs.

### Reference Dimensions

These dimensions have been validated across V2.2-V2.3 evaluations. Use as-is or adapt:

| Dimension | Weight | What It Measures | Good For |
|-----------|--------|------------------|----------|
| Discovery Efficiency | 30% | How quickly the agent reaches actionable understanding | Tools that accelerate finding relevant code |
| Context Precision | 25% | Signal-to-noise ratio in loaded context | Tools that reduce irrelevant results |
| Completeness | 20% | Coverage of key artifacts per test checklist | Tools that find all relevant code |
| Relational Insight | 15% | Connections surfaced that the agent didn't explicitly search for | Tools with graph/trace capabilities |
| Answer Confidence | 10% | Whether the final output is actionable without further investigation | Overall quality of the tool-assisted workflow |

### Rating Scale

Use a 1-5 integer scale. Prefer dimension-specific anchors to reduce inter-scorer variance:

**Dimension-specific anchors (recommended):**

| Score | Discovery Efficiency | Context Precision | Completeness | Relational Insight | Answer Confidence |
|-------|---------------------|-------------------|--------------|-------------------|-------------------|
| 5 | ≤5 tool calls | ≤10% noise | All checklist artifacts found | ≥3 unexpected connections | Immediately actionable |
| 4 | 6-7 tool calls | 10-20% noise | ≥90% found | 2 connections | Needs 1 follow-up read |
| 3 | 8-12 tool calls | 20-40% noise | ≥70% found | 1 connection | Needs 2-3 follow-ups |
| 2 | 13-15 tool calls | 40-60% noise | 50-70% found | 0 but tool supports it | Needs significant follow-up |
| 1 | 15+ calls or gives up | 60%+ noise | <50% found | No relational capability | Not actionable |

**Generic fallback anchors** (for custom dimensions without specific anchors):

| Score | Meaning |
|-------|---------|
| 5 | Excellent — meets all criteria with no gaps |
| 4 | Good — meets most criteria with minor gaps |
| 3 | Adequate — meets core criteria but has notable gaps |
| 2 | Weak — misses important criteria |
| 1 | Failed — does not meaningfully address the dimension |

### Bonus Discovery

When using ground-truth checklists (from Phase -1), scorers may award bonus credit for valid discoveries beyond the checklist — artifacts that are genuinely relevant but were not anticipated during scenario validation.

**Rules:**
- The checklist itself is never modified post-hoc
- Bonus discoveries must be justified in the scorer's notes
- Bonus credit should not exceed +0.5 on the Completeness dimension (prevents runaway inflation)

**Why:** Without this, agents that find more than expected get no credit, discouraging thorough exploration. The checklist remains the scoring floor; bonus credit rewards genuine insight.

### Winner Determination

Pre-register the formula. Recommended:

```
weighted_score = sum(dimension_score * dimension_weight for each dimension)

if tool_weighted > baseline_weighted:
    winner = "tool"
elif baseline_weighted > tool_weighted:
    winner = "baseline"
else:
    winner = <pre-registered tiebreaker>  # e.g., higher completeness
```

---

## Viability Thresholds

Define three verdict tiers before running evaluations:

| Verdict | Meaning | Typical Criteria |
|---------|---------|------------------|
| **Ship** | Tool provides sufficient value. Move forward. | avg >= X AND wins >= N/total |
| **Iterate** | Tool shows promise but needs specific improvements. | avg >= Y AND wins >= M/total |
| **Kill** | Tool does not provide meaningful value. | Below Iterate thresholds |

### Setting Thresholds

- **Ship** should be ambitious but achievable. A tool that barely beats the baseline on most tests should Ship.
- **Iterate** should be the "there's clearly something here" bar. The tool wins on its designed strengths even if it loses elsewhere.
- **Kill** is the absence of signal. If the tool can't beat the baseline on ANY test in its target category, it's not viable.

### Regression Guardrails

When re-evaluating after improvements (not the first evaluation), add a regression threshold:

```
regression_threshold = prior_score - variance_buffer
```

- **Variance buffer** should be calibrated from observed score variance across runs (e.g., ±0.3 based on V2.2-V2.3 experience)
- If the new score falls below `regression_threshold`, flag as regression even if it's above the absolute Ship threshold
- This catches real regressions without failing on noise

**Example:** If V2.3 scored 3.96, set V3.0 regression threshold at 3.96 - 0.30 = 3.66. A V3.0 score of 3.60 would trigger a regression flag even though it's above the absolute Ship threshold of 3.50.

### Category-Specific Thresholds (optional)

If tests span categories with different expected outcomes (tool-advantaged, mixed, baseline-advantaged), consider category-specific thresholds in addition to global ones:

```
Ship = global avg >= 3.50 AND global wins >= 5/8
Strong Iterate = tool-advantaged category avg >= X AND wins >= N in that category
```

### Multi-Track Evaluation

When an evaluation both validates existing quality AND tests new capabilities, use a multi-track pattern:

**Regression track:**
- Reuses prior scenarios with default tool configuration
- Validates that improvements didn't break existing quality
- Ship threshold = `prior_score - variance_buffer`
- Can start immediately (no scenario validation needed for reused scenarios)

**Feature track:**
- New scenarios designed to test new capabilities
- Independent Ship/Iterate/Kill thresholds
- Requires Phase -1 scenario validation before exploration

**Rules:**
- Track separation during scoring: don't mix tracks in a single scorer session
- Independent thresholds per track — a feature track failure doesn't block shipping if the regression track passes
- Both tracks use the same pipeline (Phases 0-6) but with independent scenario sets
- Parallel execution: regression track starts immediately while feature track validates scenarios

---

## Behavioral Metrics

Behavioral metrics measure HOW a tool achieves its results, complementing the scoring rubric which measures WHAT results were achieved. All behavioral metrics are **advisory** — published alongside scores as diagnostic context, never verdict-affecting.

### Escalation Rate

For tools with automatic fallback/augmentation mechanisms:

- **Definition:** `auto_escalated_queries / total_eligible_queries` (from raw clew transcripts). "Eligible" excludes queries where augmentation is architecturally excluded (e.g., LOCATION/DEBUG intents).
- **Target range:** 15-40% of eligible queries
- **Advisory ceiling:** 50% ("effectively always-on" — the mechanism fires indiscriminately)
- **Advisory floor:** 5% ("effectively never activates" — the mechanism's triggers are too narrow)

Escalation rate outside the target range is a diagnostic signal, not a failure. A tool with 80% escalation rate that produces excellent results is still excellent — the escalation rate tells you the mechanism could be more surgical, not that the results are bad.

### Feature Activation Rate

For tools with new user- or agent-facing features:

- **Definition:** `queries_where_feature_activated / total_queries`
- **0% activation** across all queries means the feature is dead code in practice (regardless of unit test coverage)
- Published per-feature in the results document

### Reporting

Behavioral metrics are collected during Phase 5.5b and reported in a dedicated section of the results document. The computation script (`scripts/viability_compute.py`) accepts an optional behavioral metrics file and flags values outside advisory ranges.

---

## Rubric Stability Policy

Scoring rubric changes between versions create incomparable absolute scores. This policy manages that tension.

### Anchor Freeze Rule

Once a rubric version produces a **Ship** verdict, its dimension anchors are frozen for all subsequent evaluations using the same test scenarios. This ensures cross-version comparisons are meaningful.

### Change Protocol

If anchors must change (e.g., the evaluation context fundamentally shifted):

1. Document the rationale BEFORE any agents run under the new anchors
2. Assign a new rubric version identifier (e.g., R1, R2, R3)
3. Mark absolute scores as **incomparable** to scores from prior rubric versions
4. Use only **win rates** for cross-version comparison (win/loss is robust to anchor changes since both tools are scored under the same rubric)

### Rubric Version Tracking

Every results document and computation output must include the rubric version used. The computation script includes a `rubric_version` field in its output header.

**History:**
| Version | Changes | First Used |
|---------|---------|------------|
| R1 | Original anchors (Discovery: 5/5 ≤3 calls) | V2.3 |
| R2 | Relaxed discovery anchors (5/5 ≤5 calls) | V4.1 |

---

## Stability Analysis

Agent-based evaluations have inherent variance — the same tool can score differently across runs due to non-deterministic agent behavior. Stability analysis estimates whether an observed win margin is likely real or could be noise.

### Flip Rate

The **flip rate** is the proportion of test results that changed winner between two consecutive versions:

```
flip_rate = tests_where_winner_changed / total_tests
```

Historical flip rates: V2.3→V3.0: 75% (6/8), V3.0→V4: 37.5% (3/8), V4→V4.1: 25% (3/12).

### Noise Probability

Given a flip rate `p` and an observed win margin `m` over `n` tests, estimate the probability that the margin arose from noise alone:

```
P(noise) = P(|wins - n/2| >= m | each test flips with probability p)
```

This is modeled as a binomial: if each test result is treated as a coin flip with probability `p` of changing, what's the chance of seeing the observed margin or greater?

### Confidence Flag

If `P(noise) > 30%`, the verdict is flagged as **LOW CONFIDENCE** in the results document. This does not change the verdict — it's an advisory flag that the margin is within the noise floor.

### Computation

The stability analysis is computed by `scripts/viability_compute.py` when provided with historical flip rate data. Cost: 0 additional agents (uses only prior results).

---

## Test Scenario Design

### Scenario Categories

Structure tests into 3 tiers:

| Category | Purpose | Expected Winner |
|----------|---------|-----------------|
| **Tool-advantaged** (40-50% of tests) | Tasks where the tool's unique capabilities should help | Tool |
| **Mixed** (20-30% of tests) | Tasks where both tools have strengths | Either |
| **Baseline-advantaged** (20-30% of tests) | Tasks where the baseline is inherently better | Baseline |

Including baseline-advantaged tests is mandatory. They validate evaluation honesty.

**Mode-negative tests:** When testing specific tool features (e.g., a new search mode), include at least one test where the feature should HURT performance relative to the default mode. This validates the evaluation framework: if the tool wins using the feature on a scenario where the feature should be harmful, the test design is suspect. This generalizes the baseline-advantaged concept to cover within-tool feature testing.

### Scenario Quality Checklist

Each scenario should:
- [ ] Start from a realistic question (not a lookup query)
- [ ] Have a clear checklist of key artifacts the agent should find
- [ ] Not hint at specific file names, function names, or code structure
- [ ] Be solvable by both tools (neither is structurally blocked)
- [ ] Test a distinct capability (no two scenarios measuring the same thing)

### Reusing Scenarios Across Versions

Reusing scenarios enables direct comparison but risks "teaching to the test." This is acceptable when:
- The fix being tested is general-purpose (not hard-coded for a specific scenario)
- ALL scenarios are re-run (not just the ones expected to improve)
- The concern is acknowledged in the results document

---

## Edge Cases

Pre-registered handling for situations that arise during evaluation:

| Situation | Handling | Rationale |
|-----------|----------|-----------|
| Agent uses the other tool via Bash | Allowed; sanitize normally | Agents are resourceful — constraining Bash would be artificial |
| Tool timeout or rate limit | Re-run once; if it recurs, score partial transcript | Infrastructure failure ≠ tool quality |
| Agent gives up early | Score as-is | Giving up is valid data about tool effectiveness |
| Agent doesn't discover features | Score as-is | Measures real feature discoverability |
| Agent produces empty/trivial output | Score as-is with minimum ratings | Don't discard inconvenient data |

**General principle:** Score all exploration transcripts as-is. Only re-run for infrastructure failure (timeout, crash, rate limit), never for suboptimal agent behavior. Suboptimal behavior IS the data.

---

## Common Pitfalls

Lessons from V1-V3.0:

| Pitfall | Version | Lesson |
|---------|---------|--------|
| Baseline given exact queries | V1 | Don't give the baseline agent hints the tool agent doesn't get |
| Self-assessment | V2 | Never let the same agent that explored also score its own work |
| Testing with broken features | V2.1 | Verify the tool works before evaluating it (the reembed bug) |
| Testing with wrong output mode | V2.1 | Test the intended user experience, not a debug mode |
| Tool names visible in transcripts | V2.2 | Sanitize tool invocations AND output format, then verify |
| Scorer computes aggregates | V2.2 | Scorers rate dimensions only; aggregation is programmatic |
| Post-hoc rule changes | V2.2 | Pre-register all rules; no corrections after results are in |
| Single scorer per test | V2.2 | Use 2+ scorers with disagreement resolution protocol |
| N/A dimension for one tool | V2.2 | Score both tools on all dimensions; don't create asymmetric rubrics |
| Same model for all agents | V2.2 | Acknowledged limitation; mitigate by using independent sessions |
| No scenario validation | V3.0 | Validate scenarios against codebase before exploration; produce ground-truth checklists |
| No exploration budget | V2.3 | Agents ranged 8-30+ calls; soft budget standardizes discovery scoring |
| Single verification attempt | V2.3 | Pre-register escalation levels for verification gate failure |
| No edge case protocol | V2.3 | Pre-register handling for agent gives-up, timeout, cross-tool usage |
| Feature criteria as Kill gate | V3.0-V3.1 | Feature health should cap at Iterate, not override outcome quality |
| Rubric anchor changes mid-eval | V4→V4.1 | Freeze anchors after Ship; use win rates for cross-rubric comparison |
| Uncalibrated behavioral metrics | V4.1 | Pre-register advisory thresholds; track escalation rate as diagnostic |

---

## Results Document Template

Every evaluation produces a results document with this structure:

```markdown
# V[X.Y] Viability Evaluation Results

**Date:** YYYY-MM-DD
**Rubric Version:** R[N]
**Verdict:** [Ship / Iterate / Kill]
**Stability:** [CONFIDENT / LOW CONFIDENCE (P(noise) = X%)]
**Tool Average:** X.XX/5.0
**Baseline Average:** X.XX/5.0
**Win/Loss:** N tool / M baseline

## What Changed Since Previous Version
## Methodology (link to standards + any deviations)
## Per-Test Results (table with scores + key reasoning)
## Per-Test Dimension Scores (full breakdown)
## Category Breakdown (analysis by test category)
## Behavioral Metrics (escalation rate, feature activation, advisory flags)
## Counterfactual Analysis (grep marginal contribution, if applicable)
## Feature Health Cards (per-feature status vs pre-registered targets)
## Stability Analysis (flip rate, P(noise), confidence flag)
## Sanitization Verification Results
## Scorer Agreement Analysis
## What the Tool Does Well
## What the Tool Still Struggles With
## Confidence Notes (methodological strengths + weaknesses)
## Iteration Targets (if not Ship)
## Score History (cross-version comparison with methodology caveats)
```

---

## References

- V3.0 test plan: `docs/plans/2026-02-18-v3.0-viability-test-plan.md`
- V2.3 test plan: `docs/plans/2026-02-17-v2.3-viability-test-plan.md`
- V2.2 results: `docs/plans/2026-02-17-v2.2-viability-results.md`
- V2.2 test plan: `docs/plans/2026-02-16-v2.1-revised-viability-test-plan.md`
- V2 results: `docs/plans/2026-02-13-v2-viability-results.md`
- Computation script: `scripts/viability_compute.py`
- Counterfactual analysis: `scripts/counterfactual_analysis.py`
