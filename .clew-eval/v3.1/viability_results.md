# V3.1 Focused Re-Evaluation Results

**Date:** 2026-02-19
**Verdict: Kill V3 line**
**Clew avg: 4.11/5.0 | Grep avg: 3.67/5.0 | Clew wins 3/4, Grep wins 1/4**

---

## Executive Summary

V3.1 made V3 features (confidence scoring, suggestion text, related_files surfacing, grep integration) visible in CLI `--json` and rich output. Despite strong win rate (3/4) and high absolute scores (4.11 avg), the evaluation **fails the feature visibility criterion**: V3 features remain invisible to agents in practice.

The kill verdict is driven by:
- **0/4 agents reacted to V3 metadata** (threshold: >=2/4)
- **1/4 tests had actionable V3 features visible** (threshold: >=3/4)
- Agents pipe `--json` output through `head` or `python3 -c`, discarding all metadata fields
- Even when D4 agent received an explicit suggestion ("Low confidence -- consider refining query or trying a different mode"), it did not change behavior
- System prompt hints about `--mode`/`--exhaustive` flags were ignored by both D1 and D4 agents

---

## Per-Test Results

| Test | Track | Clew | Grep | Winner | Margin |
|------|-------|------|------|--------|--------|
| B1 | A (Regression) | **4.75** | 3.95 | **CLEW** | +0.80 |
| C1 | A (Regression) | 3.60 | 3.60 | **CLEW** (completeness tiebreaker: 5.0 vs 3.5) | 0.00 |
| D1 | B (Modes) | 3.85 | **3.92** | **GREP** | -0.07 |
| D4 | B (Modes) | **4.22** | 3.20 | **CLEW** | +1.02 |

### Per-Test Dimension Scores

**Clew:**

| Test | Discovery (30%) | Precision (25%) | Completeness (20%) | Relational (15%) | Confidence (10%) | Weighted |
|------|----------------|-----------------|--------------------|--------------------|-----------------|----------|
| B1 | 5.0 | 4.0 | 5.0 | 5.0 | 5.0 | **4.75** |
| C1 | 3.0 | 3.0 | 5.0 | 3.0 | 5.0 | **3.60** |
| D1 | 3.0 | 4.0 | 5.0 | 3.0 | 5.0 | **3.85** |
| D4 | 4.0 | 4.0 | 5.0 | 3.5 | 5.0 | **4.22** |
| **Avg** | **3.75** | **3.75** | **5.00** | **3.62** | **5.00** | **4.11** |

**Grep:**

| Test | Discovery (30%) | Precision (25%) | Completeness (20%) | Relational (15%) | Confidence (10%) | Weighted |
|------|----------------|-----------------|--------------------|--------------------|-----------------|----------|
| B1 | 3.5 | 3.5 | 5.0 | 3.5 | 5.0 | **3.95** |
| C1 | 4.0 | 4.0 | 3.5 | 2.0 | 4.0 | **3.60** |
| D1 | 3.0 | 4.0 | 5.0 | 3.5 | 5.0 | **3.92** |
| D4 | 2.0 | 3.0 | 5.0 | 3.0 | 4.0 | **3.20** |
| **Avg** | **3.12** | **3.62** | **4.62** | **3.00** | **4.50** | **3.67** |

---

## Verdict Criteria Evaluation

| Criterion | Result | Threshold | Status |
|-----------|--------|-----------|--------|
| Win rate | 3/4 clew wins | >=3/4 | PASS |
| No regression | Clew avg 4.11 | >=3.50 | PASS |
| Feature visibility | 1/4 tests had suggestion visible | >=3/4 | **FAIL** |
| Agent behavior change | 0/4 agents adjusted behavior | >=2/4 | **FAIL** |

**Verdict: Kill V3 line** (features still invisible -- falls into "features still invisible" kill condition)

---

## Feature Visibility Analysis (Phase 5.5)

### Visibility Matrix

| Test | confidence_label | suggestion | related_files | grep_results | Agent reacted? |
|------|-----------------|------------|---------------|--------------|---------------|
| C1 | YES (in JSON) | NO (JSON truncated by `head`) | NO | N/A | NO |
| B1 | YES (in JSON) | NO (not triggered -- high conf) | NO (empty) | N/A | NO |
| D1 | YES (in JSON) | NO (not triggered -- high conf) | NO | NO | NO |
| D4 | YES (in JSON) | **YES** (1 of 4 searches) | NO (empty) | NO | **NO** |

### Why Features Remain Invisible

**Problem 1: Agent piping patterns destroy metadata**

All agents used `--json` mode and piped output through filtering:
- `| head -100` / `| head -200` -- truncates JSON, cutting off fields after `results` array
- `| python3 -c "... data['results'] ..."` -- extracts only the `results` array, discarding all top-level metadata

This means `confidence_label`, `suggestion`, `related_files`, `grep_results`, `mode`, and `suggested_patterns` are systematically discarded by standard agent behavior.

**Problem 2: V3 fields only populated under rare conditions**

- `suggestion`: Only appears on low confidence. 10 of 11 searches returned "high" confidence. The 1 low-confidence case (C1 L12) was truncated by `head`.
- `related_files`: Empty for all queries -- requires relationships in the graph for returned results.
- `grep_results`/`grep_total`: Requires `--exhaustive` mode, which no agent used.
- `suggested_patterns`: Only appears alongside `suggestion`.

**Problem 3: Agents do not follow system prompt hints**

D1 and D4 agents received explicit hints about `--mode` and `--exhaustive` flags. Neither agent ran `clew search --help` or used these flags. This is consistent with known agent behavior: Sonnet 4.6 agents tend to use tools in familiar patterns rather than exploring new flags.

### Chain of Failure

```
Code fix (YES) -> JSON output (PARTIAL) -> Agent receives it (RARELY) -> Agent reacts (NEVER)
```

---

## Scorer Agreement

- **8 scorer agents** (2 per test)
- **Exact agreement:** 34/40 dimensions (85.0%)
- **Within 1 point:** 40/40 dimensions (100.0%)
- **Disagreements >1 point:** 0/40 (no tiebreakers needed)

Minor 1-point gaps (5 of 40):
- C1: grep/completeness (4 vs 3)
- B1: grep/discovery (4 vs 3), grep/precision (4 vs 3), grep/relational (4 vs 3)
- D1: grep/relational (3 vs 4)
- D4: clew/relational (4 vs 3)

---

## Comparison with V3.0

| Metric | V3.0 | V3.1 | Delta |
|--------|------|------|-------|
| Clew avg | 3.84 (12 tests) | 4.11 (4 tests) | +0.27 |
| Grep avg | 3.97 (12 tests) | 3.67 (4 tests) | -0.30 |
| Clew win rate | 3/8 Track A | 3/4 | Improved |
| Features visible | 0/12 | 1/4 (marginal) | Minimal improvement |
| Agent reactions | 0/12 | 0/4 | No improvement |

The score improvement is likely due to **test selection** (4 focused tests vs 12 broad tests) and **agent variance**, not V3.1 features. The critical finding: V3.1 code changes did not solve the agent visibility problem.

---

## Key Insight: The V3 Approach Is Structurally Flawed

V3's strategy was: embed search metadata (confidence, suggestions, related files, grep results) in CLI/MCP output to help agents make better search decisions. This evaluation conclusively demonstrates that:

1. **Agents don't read search metadata.** They extract result file paths and read files. All other output is noise.
2. **CLI piping is destructive.** Agents use `| head -N` and `| python3 -c` to extract only what they need, which is always the `results` array.
3. **System prompt hints don't change agent behavior.** Even explicit instructions to explore `--help` and use `--mode`/`--exhaustive` were ignored.
4. **Low-confidence signals rarely fire.** The confidence scorer returned "high" for 10/11 searches, meaning suggestion text almost never appears.
5. **related_files requires pre-existing graph data** that doesn't exist for most search queries.

The fundamental issue is that V3 tries to make the *agent* smarter by giving it more information. But the agent is already following a working pattern (search -> get file paths -> read files). V3 metadata is outside this pattern.

---

## Recommendation

**Kill the V3 line.** Accept that:
- V2.3 (shipped) represents the ceiling for the "embed metadata in output" approach
- V3's features (confidence scoring, mode selection, grep integration, peripheral surfacing) are correctly implemented but cannot reach the agent through CLI/MCP output
- Future improvements should target the **search results themselves** (better ranking, better snippets, better entity resolution) rather than adding metadata *around* results

If pursuing V4, consider:
- **Autonomous mode switching** (clew internally decides when to fan out to grep, rather than asking the agent to switch modes)
- **Result-level enrichment** (embed relationship context directly in result snippets, not as separate `related_files` field)
- **Reducing noise in results** rather than adding signals that agents ignore

---

## Artifacts

| Artifact | Location |
|----------|----------|
| Raw transcripts | `.clew-eval/v3.1/raw-transcripts/` (8 JSONL files) |
| Sanitized transcripts | `.clew-eval/v3.1/sanitized-transcripts/` (8 MD files) |
| A/B mapping | `.clew-eval/v3.1/mapping.json` |
| Verification report | `.clew-eval/v3.1/verification.md` |
| Raw scores | `.clew-eval/v3.1/scores/` (8 JSON files) |
| Computation output | `.clew-eval/v3.1/scores/viability_results.json` |
| Feature visibility | `.clew-eval/v3.1/feature_visibility.md` |
| This document | `.clew-eval/v3.1/viability_results.md` |

**Methodology:** Blind A/B evaluation per `docs/VIABILITY-EVALUATION-STANDARDS.md`. 8 exploration agents (Sonnet 4.6), 8 scoring agents (2 per test), programmatic computation, post-hoc feature visibility analysis on raw transcripts.
