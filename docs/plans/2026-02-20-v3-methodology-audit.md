# V3.1 Methodology Audit Report

**Date:** 2026-02-20
**Auditor scope:** Determine whether the V3.1 viability evaluation followed its own pre-registered rules, and whether the methodology supports the KILL conclusion.

---

## Question A: Were the V3.1 verdict criteria pre-registered?

**Finding: YES -- the criteria were pre-registered in the evaluation handoff before any agents ran.**

The V3.1 evaluation handoff (`docs/plans/2026-02-19-v3.1-evaluation-handoff.md`, Section 12) explicitly defines four verdict criteria with thresholds:

> | Criterion | Threshold | V3.0 Baseline |
> |-----------|-----------|--------------|
> | Feature visibility | V3 features visible in >=3/4 clew transcripts | 0/12 visible |
> | Agent behavior change | >=2/4 clew agents adjust behavior based on V3 metadata | 0/12 reacted |
> | Win rate | Clew wins >=3/4 tests | 3/8 (Track A) |
> | No regression | Clew avg >=3.50 | 3.84 |

The handoff also defines explicit verdict rules mapping criteria combinations to Ship/Iterate/Kill outcomes:

> | Verdict | Criteria |
> |---------|----------|
> | **Kill V3 line** | Features visible but wins <=1/4, OR features still invisible |

These criteria are structurally embedded in the handoff document, which was written as an entry point for a fresh evaluation session. The handoff's execution checklist (Section 14) sequences Phase 5.5 (feature visibility) before Phase 7 (verdict), and the verdict rules reference the feature visibility thresholds.

**Evidence of pre-registration timing:** The handoff document references the V3.0 results (`docs/plans/2026-02-19-v3.0-viability-results.md`) as a known input, and its Section 4 (Test Selection) cites V3.0 scores for each selected test. This confirms the handoff was written after V3.0 results were known but before V3.1 evaluation began -- which is the correct sequencing for a pre-registered follow-up evaluation.

**One concern:** The V3.0 results document itself recommends the exact test set used in V3.1: "Re-evaluate with visibility fix. Once features are visible, re-run a focused 4-test evaluation (C1, B1, D1, D4 -- the completeness-focused tests) to measure whether visible features actually change agent behavior" (V3.0 results, line 457). This means the V3.1 handoff was directly informed by V3.0 post-hoc analysis. This is a legitimate sequential design (V3.0 diagnosis leads to V3.1 test design) but it does mean the test selection was not independent of prior results. See Question E for further analysis.

---

## Question B: Is the feature visibility criterion a legitimate specialization or an internal contradiction?

**Finding: INTERNAL TENSION, but not a contradiction that invalidates the verdict.**

The general evaluation standards (`docs/VIABILITY-EVALUATION-STANDARDS.md`, Phase 5.5) state:

> After programmatic computation, optionally analyze raw (unsanitized) transcripts for qualitative insights:
> - Measure **feature usage**, not tool quality
> - Does NOT affect verdicts or scores -- published alongside quantitative results as a separate section

The V3.1 handoff elevated feature visibility from an optional qualitative analysis to a hard verdict criterion. This is in direct tension with the standards' "does NOT affect verdicts" language.

**However, the tension is mitigated by three factors:**

1. **The standards explicitly say "Pre-register everything" (Core Principle 1).** The V3.1 handoff pre-registered feature visibility as a verdict criterion before any V3.1 agents ran. The general standards describe a default pipeline; version-specific handoffs specialize it. Pre-registration is the controlling principle.

2. **The purpose of V3.1 was specifically to test feature visibility.** The handoff states: "This evaluates whether making V3 features visible to agents actually improves their performance" (Section 1). The entire point of V3.1 was that V3.0 features were invisible, so measuring visibility was the primary experimental question, not a post-hoc qualitative curiosity.

3. **The general standards use "optionally" for Phase 5.5.** This describes a default stance, not a prohibition. A version-specific protocol that elevates an optional phase to a required one with hard criteria is a specialization, not a violation.

**The tension remains real:** A strict reading of "does NOT affect verdicts" would preclude what V3.1 did. The standards should be updated to acknowledge that version-specific handoffs can override the default pipeline, or Phase 5.5 should be reframed to say "does not affect verdicts *by default* -- pre-registered overrides are permitted."

**Impact on KILL verdict:** The feature visibility criterion produced a FAIL result. Without this criterion, the quantitative-only verdict would be ambiguous: clew won 3/4 tests with a 4.11 average, both passing the Ship thresholds for win rate and regression. The feature visibility criterion is what drives the KILL. If you reject the criterion as illegitimate, the quantitative results alone would support SHIP (3/4 wins, 4.11 avg, both above threshold). This is the single most important methodological question in the audit.

---

## Question C: Is the dismissal of confidence_label visibility consistent with pre-registered definitions?

**Finding: PARTIALLY INCONSISTENT -- the handoff's visibility definition is ambiguous, and the verdict document resolved the ambiguity in a reasonable but not pre-determined direction.**

**What the handoff says about visibility (Section 11):**

The feature visibility table asks five questions per test:
- "Did `confidence_label` appear in the output?"
- "Did `suggestion` appear in the output?"
- "Did `related_files` appear in the output?"
- "Did the agent react to V3 metadata?"
- "Did `grep_results` appear? (D1/D4 only)"

The success criterion (Section 12) says: "Feature visibility: V3 features visible in >=3/4 clew transcripts."

**What actually happened:**

The feature visibility analysis (`feature_visibility.md`) confirms `confidence_label` was present in JSON output for 4/4 clew transcripts. The `suggestion` field was present in 1/4 (D4 only). `related_files` was present in 0/4. `grep_results` was present in 0/4 (D1, D4).

The verdict document then states: "Only `confidence_label` was reliably visible (4/4), but this alone does not constitute 'V3 features visible' -- the actionable features (`suggestion`, `related_files`, `grep_results`, mode guidance) were invisible or ignored."

**The ambiguity:** The handoff says "V3 features visible in >=3/4" but does not define what counts as a "V3 feature" being "visible." The feature visibility table tracks five distinct features. Is the criterion satisfied if ANY one feature is visible in >=3/4 tests? Or must ALL tracked features be visible? Or must the "actionable" subset be visible?

**Transcript verification:** My grep of the raw transcripts confirms the claims:
- `confidence_label` appears in: C1-clew.jsonl (2 occurrences), B1-clew.jsonl (2), D1-clew.jsonl (1), D4-clew.jsonl (4). Total: 4/4 clew transcripts.
- `suggestion` appears in: D4-clew.jsonl only (1 occurrence, line 18). Total: 1/4 clew transcripts.
- `related_files` appears in: 0/4 clew transcripts (zero grep matches across all raw transcripts).
- `grep_results` appears in: 0/4 clew transcripts (zero grep matches across all raw transcripts).

**Assessment:** The verdict document's dismissal of `confidence_label` visibility is substantively reasonable -- `confidence_label: "high"` appearing in JSON that the agent pipes away via `| head -100` or `| python3 -c "data['results']"` is technically "present in output" but not "visible to the agent." The D4 transcript at line 18 shows the full JSON including `confidence_label: "high"` reaching the agent, but the agent extracted only the `results` array.

However, the dismissal is not cleanly pre-registered. The handoff could have defined "visible" as "the agent demonstrably processed the field" rather than "the field appeared in the tool output." This ambiguity was resolved during the verdict phase, not before it -- which violates Core Principle 1 ("no post-hoc corrections").

**Impact on KILL verdict:** If `confidence_label` presence in JSON output counts as "visible," then the feature visibility criterion passes at 4/4. Combined with the 3/4 win rate and 4.11 average, the verdict would shift toward Iterate or Ship. The dismissal is the second-most important methodological question after Question B.

---

## Question D: Did anonymization failure introduce scorer bias?

**Finding: NO DETECTABLE BIAS PATTERN, despite 8/8 identification failure.**

The verification report (`verification.md`) shows all 8 transcripts were identified at >60% confidence, a clear failure of the <=3/8 threshold. The identification was correct in all cases, driven by structural differences in output format (JSON with `chunk_type`/`snippet` fields vs. plain `file:line:content` format), query style (natural language vs. regex patterns), and explicit metadata leaks (`intent: "code"`, `mode: "semantic"` in B1-B).

**Scorer bias analysis:**

I examined all 8 scorer files and the mapping to determine whether scores systematically favored the identified tool. The mapping is:
- C1: alpha=grep, beta=clew
- B1: alpha=grep, beta=clew
- D1: alpha=clew, beta=grep
- D4: alpha=clew, beta=grep

**Per-test scorer patterns:**

| Test | Clew label | Clew won? | Scorer 1 clew > grep? | Scorer 2 clew > grep? |
|------|-----------|-----------|----------------------|----------------------|
| C1 | Beta | Yes (tie, completeness tiebreaker) | Beta: 3.60, Alpha: 3.60 (tie) | Beta: 3.60, Alpha: 3.40 (beta wins) |
| B1 | Beta | Yes (+0.80) | Beta: 4.75, Alpha: 4.30 (beta wins) | Beta: 4.75, Alpha: 3.60 (beta wins) |
| D1 | Alpha | No (-0.07) | Alpha: 3.85, Beta: 3.85 (tie) | Alpha: 3.85, Beta: 4.00 (beta wins) |
| D4 | Alpha | Yes (+1.02) | Alpha: 4.30, Beta: 3.15 (alpha wins) | Alpha: 4.15, Beta: 3.15 (alpha wins) |

If scorers were biased toward clew (having identified it), we would expect systematically inflated clew scores. The evidence does not support this:

- **D1**: Clew (alpha) lost. If scorers were biased toward the tool they identified as clew, D1 should show clew winning. Instead, grep edged ahead on relational insight.
- **C1**: Exact tie on weighted scores, with clew winning only on the completeness tiebreaker. A biased scorer would not produce a tie.
- **Scorer agreement is high**: 34/40 dimensions had exact agreement (85%), 40/40 within 1 point (100%). Biased scorers operating on identification would likely diverge more, since identification confidence varied (65-80%) across transcripts.

**However, identification could have introduced a subtler bias:** Scorers may have unconsciously held clew (the specialized tool) to a higher standard on dimensions like Discovery Efficiency, while being more lenient on grep (the familiar tool). This would depress clew scores rather than inflate them. The D1 result (clew loses by 0.07 on relational insight alone) is consistent with this hypothesis but is too narrow to confirm.

**The methodology's own mitigation:** The evaluation standards (Phase 3, Escalation on failure) pre-register that after verification failure, the evaluation proceeds with a documented caveat: "behavioral fingerprints may persist despite sanitization. The scoring rubric is absolute and tool-independent, which mitigates identification bias." V3.1 failed on the first attempt and should have re-run sanitization. The verification report does not document a re-sanitization attempt, which is a procedural deviation.

**Impact on KILL verdict:** The lack of a detectable bias pattern means the scores are not obviously corrupted. But the 8/8 identification rate is a serious procedural failure. The evaluation should have either re-sanitized (per the escalation protocol) or explicitly documented why it proceeded. Neither is evident in the artifacts.

---

## Question E: Were the V3.1 test selections pre-registered or post-hoc?

**Finding: PRE-REGISTERED in the V3.1 handoff, but the selection was directly derived from V3.0 post-hoc analysis.**

The V3.1 handoff (Section 4) lists the four tests with explicit rationale:

> | Test | Category | Why Selected | V3 Feature Under Test |
> |------|----------|-------------|----------------------|
> | **C1** | Grep-Advantaged (ENUMERATION) | V3.0's weakest category | ENUMERATION auto-classification + keyword mode guidance + `suggested_patterns` |
> | **B1** | Structural | Tests peripheral surfacing | `related_files` (should surface test files, callers) |
> | **D1** | Exhaustive Enumeration | Tests exhaustive mode + grep integration | `grep_results`, `grep_total`, mode selection |
> | **D4** | Exhaustive Enumeration | Tests mode selection guidance | `suggestion` field guiding agent to switch modes |

This selection is pre-registered relative to V3.1 execution. However, the V3.0 results document (line 457) explicitly recommended this exact set: "re-run a focused 4-test evaluation (C1, B1, D1, D4 -- the completeness-focused tests)." The V3.1 handoff adopted this recommendation verbatim.

**Is this problematic?** In clinical trial methodology, adaptive designs where Phase N results inform Phase N+1 design are standard practice. The key requirement is that the adaptation rule is documented before Phase N+1 begins. The V3.1 handoff satisfies this: it documents the test selection with rationale before any V3.1 agents run.

**Potential concern -- cherry-picking risk:** The 4 selected tests include 2 where clew already won in V3.0 (C1: 3.65 vs 2.90, D4: 4.05 vs 4.55 -- actually D4 was a grep win in V3.0) and 2 where grep won (B1: 3.58 vs 3.98, D1: 3.75 vs 3.80). The selection is balanced on prior outcomes (2 clew, 2 grep from V3.0). This argues against cherry-picking.

**The real concern is focus bias:** By selecting tests specifically designed to showcase V3 features, the evaluation measures best-case feature visibility rather than typical feature visibility. The V3.1 results acknowledge this: "The score improvement is likely due to test selection (4 focused tests vs 12 broad tests) and agent variance, not V3.1 features." This self-awareness mitigates the concern.

**Impact on KILL verdict:** The focused test selection, if anything, gave V3.1 the best possible chance to demonstrate feature visibility. The fact that features remained invisible even on hand-picked tests strengthens the KILL conclusion rather than weakening it.

---

## Question F: Do the feature visibility and agent behavior change criteria double-count?

**Finding: YES, there is partial overlap, but the criteria measure different things along a causal chain.**

The two criteria map to different stages of a causal chain:

```
Feature visible in output -> Agent perceives feature -> Agent changes behavior
         ^                            ^                          ^
   Feature visibility           (not measured)          Agent behavior change
      (>= 3/4)                                              (>= 2/4)
```

A feature can be "visible" (present in output) without the agent "changing behavior" (adjusting search strategy). The D4 case demonstrates this: `suggestion` was visible in the JSON output, but the agent did not react. This would fail the behavior change criterion but pass the visibility criterion for that test.

Conversely, an agent cannot change behavior based on a feature that is not visible. So failing visibility necessarily fails behavior change. In the V3.1 results:

- Feature visibility: FAIL (1/4 for suggestion, 4/4 for confidence_label -- classified as overall FAIL)
- Agent behavior change: FAIL (0/4)

**The double-counting question:** If `confidence_label` visibility at 4/4 had been accepted as meeting the visibility criterion (see Question C), then the two criteria would produce different results: visibility PASS, behavior change FAIL. In that scenario, the two criteria are clearly measuring different things and there is no double-counting.

In the actual evaluation, both criteria failed, which creates the appearance of double-counting the same observation ("agents don't use V3 features"). But even here, the criteria are logically distinct:
- Visibility answers: "Did the code fix work? Can agents see the features?"
- Behavior change answers: "Given visibility, do features actually influence agent decisions?"

**The verdict rules handle the overlap correctly.** The Kill condition is: "Features visible but wins <=1/4, OR features still invisible." This is a disjunctive rule -- either branch independently triggers Kill. The "features still invisible" branch does not require evaluating behavior change at all. The V3.1 verdict used this branch, making the behavior change criterion moot.

**Impact on KILL verdict:** The double-counting concern is real in principle but does not affect the V3.1 verdict. The Kill was triggered by the "features still invisible" branch, which is independent of behavior change. Even if the behavior change criterion were removed entirely, the verdict would be the same.

---

## Summary Findings

| Question | Finding | Impact on KILL |
|----------|---------|----------------|
| A. Pre-registration | Criteria were pre-registered in handoff before evaluation | Supports KILL |
| B. Phase 5.5 contradiction | Tension with general standards, but pre-registration takes precedence | Weakens KILL -- the elevation of qualitative analysis to hard criterion is the decisive move |
| C. confidence_label dismissal | Reasonable but post-hoc resolution of ambiguous definition | Weakens KILL -- if confidence_label counts as "visible," feature visibility passes |
| D. Anonymization bias | 8/8 identification failure but no detectable score skew | Neutral -- procedural failure, no evidence of outcome impact |
| E. Test selection | Pre-registered in handoff, derived from V3.0 recommendations | Strengthens KILL -- best-case tests still showed feature invisibility |
| F. Double-counting | Partial overlap but criteria measure different causal stages | Neutral -- Kill triggered by visibility branch, behavior change is moot |

---

## Audit Verdict

**Methodology flawed -- KILL weakened.**

The KILL conclusion rests on two methodological decisions that are defensible but not airtight:

1. **Elevating Phase 5.5 to a hard verdict criterion** contradicts the general evaluation standards' explicit statement that post-hoc feature analysis "does NOT affect verdicts." The V3.1 handoff pre-registered this elevation, which satisfies the "pre-register everything" principle, but creates an internal conflict within the methodology documentation. A strict-constructionist reading of the standards would reject the feature visibility criterion entirely, leaving only the quantitative results (3/4 wins, 4.11 avg) -- which pass all Ship thresholds.

2. **Dismissing confidence_label visibility** resolved an ambiguity in the pre-registered visibility definition ("V3 features visible in >=3/4 tests") without specifying what counts as a "V3 feature" or what counts as "visible." The dismissal is substantively correct -- `confidence_label: "high"` in JSON that gets piped away is not functionally visible -- but the distinction between "present in tool output" and "perceived by agent" was not pre-registered.

The KILL is not invalidated because:
- The underlying empirical observation is real: agents do pipe away metadata, `suggestion` and `related_files` were genuinely absent/empty in almost all cases, and zero agents changed behavior.
- The pre-registration of feature visibility criteria in the handoff is a reasonable specialization for an evaluation whose explicit purpose was testing feature visibility.
- The focused test selection gave V3.1 its best chance, and it still failed on the qualitative criteria.

But the KILL is weakened because:
- A reader who follows only the general evaluation standards would reach a different conclusion (Ship/Iterate based on 3/4 wins and 4.11 avg).
- The confidence_label ambiguity could have been resolved either way, and the direction chosen determined the verdict.
- The anonymization failure (8/8 identified) was not properly escalated per the standards' own protocol, adding procedural uncertainty.

The evaluation would have been stronger if:
1. The general standards explicitly permitted version-specific handoffs to override Phase 5.5's default.
2. The handoff defined "visible" precisely (e.g., "the agent demonstrably processed the field, not merely that the field was present in tool output").
3. The verification failure triggered re-sanitization or was explicitly waived with documented justification.

Despite these flaws, the core empirical finding -- that agents systematically discard metadata fields by piping JSON through `head` or extracting only the `results` array -- is robust and directly observable in the raw transcripts. The strategic conclusion (V3's approach of embedding metadata in output is structurally flawed) follows from this observation regardless of the scoring methodology.
