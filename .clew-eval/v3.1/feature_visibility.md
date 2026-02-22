# V3.1 Feature Visibility Analysis

**Date:** 2026-02-19
**Purpose:** Determine whether V3.1 visibility fixes made V3 features visible to agents and whether agents reacted to them.

---

## Feature Visibility Table

| Test | confidence visible? | suggestion visible? | related_files visible? | grep_results visible? | Agent reacted? | Evidence |
|------|--------------------|--------------------|----------------------|---------------------|---------------|----------|
| C1   | YES (2/2 searches) | NO (truncated by `head -100`) | NO | N/A | NO | L8: `"confidence_label": "high"`, L12: `"confidence_label": "low"` but JSON cut off before `suggestion` field |
| B1   | YES (2/2 searches) | NO (not triggered — both high confidence) | NO (not returned — no relationships) | N/A | NO | L8: `"confidence_label": "high"`, L12: `"confidence_label": "high"` |
| D1   | YES (1/1 search) | NO (not triggered — high confidence) | NO | NO | NO | L8: `"confidence_label": "high"`. Only 1 clew search total — agent pivoted to grep/read immediately |
| D4   | YES (4/4 searches) | YES (1/4 searches) | NO (not returned) | NO | NO | L18: `"suggestion": "Low confidence — consider refining query or trying a different mode"`, `"suggested_patterns": [...]`. Agent did NOT react — continued with same search pattern |

---

## Summary Counts

| Metric | Count | Threshold |
|--------|-------|-----------|
| Tests with confidence_label visible | 4/4 | N/A |
| Tests with suggestion visible | 1/4 | >=3/4 for Iterate |
| Tests with related_files visible | 0/4 | >=3/4 for Iterate |
| Tests with grep_results visible | 0/2 (D1, D4 only) | N/A |
| Tests where agent reacted to V3 metadata | 0/4 | >=2/4 for Ship |
| Tests where agent used --mode or --exhaustive | 0/4 | N/A |

---

## Root Cause Analysis

### Why features remain invisible (despite code fixes)

1. **Agent piping destroys V3 metadata (C1, B1, D1)**
   - C1 agent: piped through `| head -100` (truncated JSON) and `| python3 -c "... data['results'] ..."` (extracted only results array)
   - B1 agent: piped through `| head -200` (JSON survived but `suggestion`/`related_files` not triggered due to high confidence) and `| python3 -c "..."` (extracted only results)
   - D1 agent: piped through `| head -100` (truncated), then abandoned clew entirely after 1 search

2. **V3 fields only populated under specific conditions**
   - `suggestion`: Only appears when confidence is low AND the search engine has actionable guidance. Only triggered in 1 of ~11 total clew searches across all 4 tests.
   - `related_files`: Requires relationships to exist in the graph for returned results. Was empty (`[]`) or not present in all searches. The V3.1 surfacing module works but has no data to surface for these queries.
   - `grep_results` / `grep_total`: Only populated in exhaustive mode. No agent ever used `--exhaustive`.
   - `suggested_patterns`: Only appears alongside `suggestion`. Appeared once (D4 L18).

3. **Agents ignore V3 metadata even when visible (D4)**
   - D4 agent received `"suggestion": "Low confidence — consider refining query or trying a different mode"` with `"suggested_patterns"` at L18.
   - Agent did NOT react: continued with standard semantic search, never tried `--mode keyword` or `--exhaustive`.
   - D4 agent also received system prompt hint about `--mode` and `--exhaustive` flags but never used them.

4. **System prompt hints ineffective (D1, D4)**
   - Both D1 and D4 agents received: "Run `clew search --help` to see available options including `--mode` and `--exhaustive` flags."
   - Neither agent ran `clew search --help`.
   - Neither agent used `--mode` or `--exhaustive` in any search command.

### Feature visibility chain failures

```
Code fix -> JSON output -> Agent sees it -> Agent reacts -> Agent changes behavior
   YES         PARTIAL         RARELY            NEVER            NEVER
```

- **Code fix**: All V3.1 features correctly implemented (738 tests pass, pre-flight verification passed)
- **JSON output**: Fields present in output, but:
  - `confidence_label`/`confidence`: Always present (YES)
  - `suggestion`: Only present when low confidence (1/11 searches)
  - `related_files`: Empty for all queries (no graph data for these search patterns)
  - `grep_results`/`grep_total`: Never populated (requires `--exhaustive` which no agent used)
- **Agent sees it**: Agents pipe `--json` output through `head` or `python3 -c`, discarding all metadata
- **Agent reacts**: Even when D4 agent received suggestion text, it did not change behavior
- **Agent changes behavior**: Zero mode switches, zero `--exhaustive` usage, zero `--help` invocations

---

## Verdict Input

Per Section 12 of the evaluation handoff:

| Criterion | Result | Threshold | Status |
|-----------|--------|-----------|--------|
| Feature visibility | 1/4 tests had suggestion visible; 4/4 had confidence_label | >=3/4 | FAIL |
| Agent behavior change | 0/4 agents adjusted behavior | >=2/4 | FAIL |
| Win rate | 3/4 clew wins | >=3/4 | PASS |
| No regression | Clew avg 4.11 | >=3.50 | PASS |

**Feature visibility criterion FAILS.** Only `confidence_label` was reliably visible (4/4), but this alone does not constitute "V3 features visible" — the actionable features (`suggestion`, `related_files`, `grep_results`, mode guidance) were invisible or ignored.
