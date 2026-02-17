# Viability Evaluation Standards

Reusable methodology for running blind, agent-based A/B evaluations of tool effectiveness. Developed through four iterations (V1-V2.3) of evaluating clew against grep baselines.

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

Every evaluation follows this 6-phase pipeline:

```
Phase 0: Pre-flight checks
Phase 1: Exploration (2 agents per test, independent)
Phase 2: Sanitization (normalize transcripts)
Phase 3: Verification (can a reader identify the tool?)
Phase 4: Scoring (2+ scorers per test, raw ratings only)
Phase 5: Computation (programmatic aggregation)
Phase 6: Disagreement resolution (conditional tiebreakers)
```

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

**Critical constraints for BOTH agents:**
- No access to: test plans, CLAUDE.md, codebase documentation, prior evaluation results
- Start cold with zero codebase knowledge
- Same scenario text, same working directory

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

**Pass criteria:** The verifier guesses correctly with >60% confidence on no more than 25% of tests. If it exceeds this threshold, Phase 2 must be re-run with stricter sanitization before scoring proceeds.

**Why this matters:** If a reader can identify the tool from the transcript, the scoring is not truly blind. This gate converts "we tried to anonymize" into "we verified anonymization worked."

### Phase 4: Scoring

2 independent scorers per test. Each scorer:

1. Receives both sanitized transcripts (Alpha and Beta) for a single test
2. Receives the scoring rubric with dimension definitions
3. Provides integer ratings (1-5) for each dimension for each transcript
4. Does NOT compute aggregates or declare a winner

**Scorer prompt template:**

> You are scoring two agent transcripts that attempted the same codebase exploration task. Score each agent independently on [N] dimensions using the rubric provided. Provide integer ratings (1-5) for each dimension.
>
> IMPORTANT: Score each agent against the absolute rubric, not relative to the other agent. A score of 3 means "good" regardless of what the other agent scored. Do NOT compute aggregates or declare a winner.

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

Use a 1-5 integer scale with explicit anchors for each dimension. Example:

| Score | Meaning |
|-------|---------|
| 5 | Excellent — meets all criteria with no gaps |
| 4 | Good — meets most criteria with minor gaps |
| 3 | Adequate — meets core criteria but has notable gaps |
| 2 | Weak — misses important criteria |
| 1 | Failed — does not meaningfully address the dimension |

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

### Category-Specific Thresholds (optional)

If tests span categories with different expected outcomes (tool-advantaged, mixed, baseline-advantaged), consider category-specific thresholds in addition to global ones:

```
Ship = global avg >= 3.50 AND global wins >= 5/8
Strong Iterate = tool-advantaged category avg >= X AND wins >= N in that category
```

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

## Common Pitfalls

Lessons from V1-V2.3:

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

---

## Results Document Template

Every evaluation produces a results document with this structure:

```markdown
# V[X.Y] Viability Evaluation Results

**Date:** YYYY-MM-DD
**Verdict:** [Ship / Iterate / Kill]
**Tool Average:** X.XX/5.0
**Baseline Average:** X.XX/5.0
**Win/Loss:** N tool / M baseline

## What Changed Since Previous Version
## Methodology (link to standards + any deviations)
## Per-Test Results (table with scores + key reasoning)
## Per-Test Dimension Scores (full breakdown)
## Category Breakdown (analysis by test category)
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

- V2.3 test plan: `docs/plans/2026-02-17-v2.3-viability-test-plan.md`
- V2.2 results: `docs/plans/2026-02-17-v2.2-viability-results.md`
- V2.2 test plan: `docs/plans/2026-02-16-v2.1-revised-viability-test-plan.md`
- V2 results: `docs/plans/2026-02-13-v2-viability-results.md`
