# V3 Devil's Advocate Review

## Section 1: Mission Brief

You are a fresh investigator tasked with validating or invalidating the conclusion that V3's metadata-guidance strategy is unviable. You should assume nothing about the prior evaluators' objectivity — they may have confirmation bias, methodology gaps, or unstated assumptions. Your job is to find the truth.

**The user is available to brainstorm and answer questions.** This is an interactive investigation, not a solo assignment. Ask questions, propose hypotheses, and challenge assumptions in dialogue.

**The verdict to challenge:** "V3 tries to make agents smarter by embedding metadata (confidence labels, suggestions, related files, grep results) in search output. Agents ignore metadata. Therefore V3 is dead."

**What would change the verdict:**
- Evidence that the evaluation methodology was flawed enough to invalidate the KILL
- Evidence that the strategy could work with different implementation tactics
- Evidence that the approach is fundamentally sound but needs a different delivery mechanism
- Evidence that the evaluation criteria were shifted post-hoc to justify a predetermined conclusion

---

## Section 2: Evidence Summary

### V3.0 Results (2026-02-19)

12 tests across two tracks. Clew avg 3.84/5.0, grep avg 3.97/5.0.

**Track A (Regression):** 8 tests reused from V2.3. Clew avg 3.85, grep avg 4.14. Clew won 3/8 (A1, A4, C1). The pre-registered Iterate threshold required >= 4/8 Track A wins. Verdict: **KILL** (below Iterate).

**Track B (Mode-Specific):** 4 new tests. Clew avg 3.81, grep avg 3.62. Clew won 1/4 (D3 only — the mode-negative honesty check where both scored low).

**Root cause diagnosed by evaluators:** V3.0 features existed in code (719 tests passing) but were invisible in CLI/MCP output. 0/12 agents saw `confidence_label`, `suggestion`, `related_files`, or `grep_results`. 1/12 agents (D1 Track B) discovered `--exhaustive` via `--help`. The evaluators concluded Track A results "essentially measure V2.3-equivalent behavior" since V3 features had no observable effect.

**Sanitization:** PASSED cleanly (0/12 identifiable at >60% confidence).

**Scorer agreement:** 81.7% within 1 point. 4 tiebreakers needed (A2, C1, D1, D3). D1 flipped from clew to grep after tiebreaker (3.75 vs 3.80, 0.05 gap). D3 had 6 tiebreaker dimensions — the most contentious test.

**Cross-version instability:** 6/8 Track A tests flipped winner vs V2.3. The evaluators acknowledged "agent variance dominates" and "the evaluation framework is not robust enough to distinguish systematic improvement from noise at this sample size."

### V3.1 Results (2026-02-19)

4 focused tests selected from V3.0 failure patterns. Clew avg 4.11/5.0, grep avg 3.67/5.0.

| Test | Track | Clew | Grep | Winner | Margin |
|------|-------|------|------|--------|--------|
| B1 | A (Regression) | **4.75** | 3.95 | **CLEW** | +0.80 |
| C1 | A (Regression) | 3.60 | 3.60 | **CLEW** (tiebreaker) | 0.00 |
| D1 | B (Modes) | 3.85 | **3.92** | **GREP** | -0.07 |
| D4 | B (Modes) | **4.22** | 3.20 | **CLEW** | +1.02 |

**V3.1 code fix:** Added V3 fields (`confidence_label`, `suggestion`, `related_files`, `grep_results`, `mode`, `suggested_patterns`) to `--json` and rich CLI output.

**Feature visibility (from raw transcript analysis):**
- `confidence_label`: visible in 4/4 tests (always present in JSON)
- `suggestion`: visible in 1/4 tests (only D4; only fires on low confidence, and 10/11 searches returned "high")
- `related_files`: visible in 0/4 tests (empty — no graph data for these queries)
- `grep_results`: visible in 0/4 tests (requires `--exhaustive`, which no agent used)

**Agent behavior change:** 0/4 agents reacted to any V3 metadata. Even D4, which received `"suggestion": "Low confidence — consider refining query or trying a different mode"`, did not change behavior.

**Verdict criteria applied:**

| Criterion | Result | Threshold | Status |
|-----------|--------|-----------|--------|
| Win rate | 3/4 | >= 3/4 | PASS |
| No regression | 4.11 avg | >= 3.50 | PASS |
| Feature visibility | 1/4 actionable | >= 3/4 | **FAIL** |
| Agent behavior change | 0/4 | >= 2/4 | **FAIL** |

Verdict: **KILL** (despite passing score-based criteria).

**Sanitization:** FAILED (8/8 identifiable at >60% confidence). Evaluation proceeded per pre-registered escalation protocol.

**Scorer agreement:** 85% exact, 100% within 1 point, 0 tiebreakers needed.

### Key Claim to Challenge

> "Agents follow search → extract_paths → read_files pattern; metadata outside this loop is invisible."

This is the foundation of the KILL verdict. If this claim is wrong, incomplete, or only true under specific evaluation conditions, the verdict may not hold.

---

## Section 3: Identified Vulnerabilities

These are specific weaknesses in the evaluation that you should investigate. They are organized by severity — how much they could undermine the KILL verdict if confirmed.

### CRITICAL (could invalidate the verdict)

**1. Anonymization failure → biased scoring.**

V3.1 verification showed 8/8 transcripts identifiable at >60% confidence. The evaluation proceeded anyway under the pre-registered escalation protocol ("Second failure: Proceed with documented caveat"). But the verification report (`verification.md`) documents specific leaks: B1-B scored 80% confidence with explicit `"intent": "code"` and `"mode": "semantic"` fields visible, plus relationship graph output from clew's `trace` feature. If scorers could identify which tool was clew, their ratings may reflect tool preference rather than transcript quality.

Key question: Did the specific scorers for B1, D1, D4 (the close tests) show patterns consistent with identification bias? All 8 score files are available for analysis.

**2. Sample size inadequacy.**

4 tests cannot distinguish signal from noise. V3.0 demonstrated that 6/8 tests flip between versions due to agent variance alone. With n=4, a single test swing changes the verdict. The V3.0 pre-registered Iterate threshold required >= 4/8 Track A wins — a threshold that is arithmetically impossible with only 2 Track A tests in V3.1. V3.1 used different thresholds (>= 3/4 wins), but the fundamental problem remains: at n=4, the margin of error exceeds the margin of victory.

**3. Post-hoc test selection.**

The 4 V3.1 tests (C1, B1, D1, D4) were chosen based on V3.0 failure patterns — specifically "completeness-focused tests" where V3 features were expected to help most. This introduces selection bias: the tests were chosen because problems were most visible there, not because they represent a balanced sample of clew's use cases. The evaluation standards document does not pre-register a protocol for focused re-evaluations with subset test selection.

### HIGH (weakens the verdict significantly)

**4. Feature visibility criteria contradict the general evaluation standards.**

The general evaluation standards (Phase 5.5) state: post-hoc feature analysis "does NOT affect verdicts or scores — published alongside quantitative results as a separate section." However, the V3.1 evaluation handoff (Section 12) pre-registered feature visibility as a hard verdict criterion: "Ship V3.1 = wins >= 3/4 AND features visible in >= 3/4 AND avg >= 3.50." So the V3.1 handoff explicitly overrode the general standards by promoting Phase 5.5 analysis to verdict-determining status. The question is: was this a valid specialization of the methodology, or did it create internally contradictory rules? The quantitative criteria alone (3/4 wins, 4.11 avg, no regression) would support SHIP. The feature visibility criterion turned a SHIP into a KILL — and that criterion's legitimacy depends on whether the V3.1 handoff can override the general standards it claims to follow.

**5. Confidence scorer miscalibration.**

The confidence scoring system returned "high" for 10/11 searches across all 4 tests — including searches with scores as low as 0.034. The `suggestion` field only fires when confidence is "low." If the confidence threshold were properly calibrated (e.g., lowered so that marginal results trigger suggestions), suggestions would have appeared in more tests, giving agents more opportunities to react. The "agents ignore suggestions" conclusion is based on a sample of 1 search where a suggestion appeared.

**6. Goal-post shifting on "visibility."**

`confidence_label` was visible in 4/4 tests. The feature visibility criterion was "features visible in >= 3/4 tests." But `confidence_label` visibility was dismissed because agents "didn't react to it." The original criterion was then narrowed to mean "actionable features visible AND agents react" — but "agent behavior change" was a separate criterion (>= 2/4 threshold). This creates double-counting: the same observation (agents didn't react) fails two criteria instead of one.

### MEDIUM (alternative interpretations)

**7. Suggestion text was too vague to be actionable.**

D4 received: "Low confidence — consider refining query or trying a different mode." This is generic advice, not a specific instruction. Compare with a hypothetical: "Low confidence (0.034). Try `clew search --mode exhaustive 'authentication middleware'` for comprehensive file-level coverage." The failure may be a UX design problem (weak suggestion text), not evidence that the strategy is dead.

**8. Agent piping is rational behavior, not a bug.**

Agents use `| head -100` and `| python3 -c "data['results']"` because extracting file paths from results is exactly what agents need to do. Calling this a "structural flaw" of V3 conflates "agents filter output" with "agents can't receive guidance." Other delivery mechanisms (stderr warnings, MCP resource URIs, structured error fields) could reach agents through different channels.

**9. MCP server path was not tested.**

V3.1 evaluation used CLI agents (Bash + `clew search --json | ...`). The MCP server returns structured JSON responses directly — no piping, no truncation. MCP tool responses go through Claude Code's tool result handling, which may process metadata differently than raw CLI output. No MCP-based agent was evaluated.

**10. No implicit behavior change measurement.**

The evaluation checked for explicit agent reactions ("agent mentioned confidence label" or "agent switched to --exhaustive"). But agents might have implicitly improved their queries after seeing low confidence scores without stating "because of the suggestion." The evaluation only checked for explicit reactions in transcript text.

---

## Section 4: Research Assignments

Execute these three research tracks in parallel. Each track has a clear deliverable. After all three complete, synthesize findings into a final verdict.

### Track 1: Methodology Audit (1 agent)

**Goal:** Determine whether the evaluation followed its own pre-registered rules.

**Steps:**
1. Read the evaluation standards: `docs/VIABILITY-EVALUATION-STANDARDS.md`
2. Read the V3.1 results: `.clew-eval/v3.1/viability_results.md`
3. Read the V3.1 feature visibility analysis: `.clew-eval/v3.1/feature_visibility.md`
4. Read the V3.1 verification report: `.clew-eval/v3.1/verification.md`
5. Read ALL 8 scorer files in `.clew-eval/v3.1/scores/` (B1-scorer1.json, B1-scorer2.json, C1-scorer1.json, C1-scorer2.json, D1-scorer1.json, D1-scorer2.json, D4-scorer1.json, D4-scorer2.json)
6. Cross-reference V3.1 raw transcripts (`.clew-eval/v3.1/raw-transcripts/*.jsonl`) — search for `confidence_label`, `suggestion`, `related_files` to verify the feature visibility claims
7. Read the V3.0 results for comparison: `docs/plans/2026-02-19-v3.0-viability-results.md`
8. Read the V3.1 evaluation handoff (pre-registered protocol): `docs/plans/2026-02-19-v3.1-evaluation-handoff.md`

**Specific questions to answer:**
- Were the V3.1 verdict criteria (feature visibility >= 3/4, agent behavior change >= 2/4) pre-registered in the evaluation handoff, or added during/after computation?
- Did the Phase 5.5 analysis contaminate the verdict despite the standards saying it "does NOT affect verdicts"?
- Is counting `confidence_label` as "visible" but not as "feature visibility passes" consistent with pre-registered definitions?
- Did the anonymization failure (8/8 identified) introduce scorer bias? Check scorer files for patterns.
- Were the V3.1 focused test selection criteria (C1, B1, D1, D4) pre-registered or chosen post-hoc?

**Deliverable:** `methodology-audit.md` with pass/fail assessment on each evaluation standards requirement, plus a summary verdict on whether the methodology supports the KILL conclusion.

### Track 2: Best Practices Research (1 agent)

**Goal:** Determine whether "agents ignore tool metadata" is a known limitation with known solutions, or a clew-specific failure.

**Research topics:**
1. **Agent-tool communication patterns:** How do Cursor (codebase_search + grep_search), Sourcegraph Cody, GitHub Copilot, and Continue.dev surface search quality signals to LLM agents? Do any of them use metadata fields in tool output to guide agent behavior?
2. **LLM tool output design:** Search for academic papers or engineering blog posts on "tool output design for LLM agents," "how LLM agents process tool results," "structured tool responses for AI agents." Is there research on what parts of tool output LLMs attend to?
3. **Claude Code MCP tool consumption:** How does Claude Code (the CLI tool, not the API) process MCP tool responses? Does it render all fields to the LLM, or does it extract/summarize? Are there MCP response patterns that are more likely to influence agent behavior?
4. **Known agent limitations:** Is "agents ignore non-result metadata" documented as a limitation of Claude, GPT, or other LLM agents? Are there known workarounds?
5. **Result-level vs response-level metadata:** Research whether embedding signals per-result (e.g., confidence badge on each search hit) vs per-response (top-level metadata fields) affects agent attention.

**Deliverable:** `best-practices.md` with findings organized by topic, applicable patterns for clew, and an assessment of whether V3's approach was doomed by design or just poorly executed.

### Track 3: Alternative Tactics Analysis (1 agent)

**Goal:** Evaluate whether V3's core features could be delivered through a mechanism agents would actually use.

**Steps:**
1. Read V3 implementation code:
   - `clew/search/engine.py` (core search pipeline with confidence scoring)
   - `clew/cli.py` (CLI output serialization)
   - `clew/mcp_server.py` (MCP tool definitions and response format)
   - `clew/search/surfacing.py` (peripheral code surfacing module)
   - `clew/search/grep.py` (grep subprocess integration)
2. For each alternative approach below, assess: Is it implementable in V3's codebase? What would change? What's the estimated effort? Would it survive agent piping patterns?

**Five approaches to evaluate:**

**(a) Autonomous mode switching.** Clew internally decides when to use grep based on query analysis. No agent involvement — the agent just calls `clew search` and gets the best results automatically. Confidence scoring and ENUMERATION intent already exist; they just need to trigger internal behavior instead of outputting metadata.

**(b) Result-level enrichment.** Instead of top-level `related_files` field, embed relationship context directly in each search result's snippet. E.g., a method result includes "Called by: process_order(), handle_webhook() | Tests: test_payment.py" in the snippet text. Agents would see this because they already read result snippets.

**(c) Structured warnings in results array.** Insert synthetic "warning" results at the top of the results array when confidence is low. E.g., `{"type": "warning", "message": "Only 2 results above confidence threshold. Consider searching for 'authentication middleware' with broader terms."}`. Since agents extract the results array, they would see these.

**(d) Two-phase response.** First call returns a search plan ("I'll search semantically for X, then grep for pattern Y, and check related files Z"). Agent can approve/modify. Second call executes. This makes the metadata the primary response, not a sidecar.

**(e) MCP-native approach.** Use MCP tool description fields, input schema `description` annotations, and `isError` response flag to guide agent behavior. E.g., when confidence is low, return `isError: true` with a message suggesting a better query. Claude Code may handle `isError` responses differently than normal results.

**Deliverable:** `alternative-tactics.md` with feasibility matrix (approach vs. criteria: survives piping, implementable in current code, estimated effort, requires agent behavior change) and a recommended approach.

---

## Section 5: Artifact Map

Every file the review agent needs, verified to exist as of 2026-02-19:

| Artifact | Path | What It Contains |
|----------|------|-----------------|
| V3.1 final verdict | `.clew-eval/v3.1/viability_results.md` | Full results with per-test scores, verdict criteria, and chain-of-failure analysis |
| V3.1 feature visibility | `.clew-eval/v3.1/feature_visibility.md` | Post-hoc analysis of which V3 features agents saw/reacted to |
| V3.1 raw scores | `.clew-eval/v3.1/scores/*.json` | 8 scorer JSON files + consolidated_scores.json + viability_results.json |
| V3.1 sanitized transcripts | `.clew-eval/v3.1/sanitized-transcripts/*.md` | 8 scorer-facing anonymized transcripts (B1-A/B, C1-A/B, D1-A/B, D4-A/B) |
| V3.1 raw transcripts | `.clew-eval/v3.1/raw-transcripts/*.jsonl` | 8 pre-sanitization agent conversation logs |
| V3.1 A/B mapping | `.clew-eval/v3.1/mapping.json` | Tool A/B → clew/grep assignment per test |
| V3.1 anonymization verification | `.clew-eval/v3.1/verification.md` | Verification report (FAILED: 8/8 identifiable at >60%) |
| V3.0 results | `docs/plans/2026-02-19-v3.0-viability-results.md` | V3.0 verdict, full per-test analysis, feature analysis |
| V3.0 raw data | `.clew-eval/v3.0/` | 24 raw transcripts, sanitized transcripts, 37 score files, verification report |
| V2.3 results | `docs/plans/2026-02-17-v2.3-viability-results.md` | V2.3 SHIP baseline for comparison |
| Evaluation standards | `docs/VIABILITY-EVALUATION-STANDARDS.md` | Reusable blind A/B evaluation methodology |
| V3.1 evaluation handoff | `docs/plans/2026-02-19-v3.1-evaluation-handoff.md` | V3.1 pre-registered evaluation protocol |
| V3.1 investigation handoff | `docs/plans/2026-02-19-v3.1-investigation-handoff.md` | How V3.1 fixes were identified |
| V3 design plan | `docs/plans/2026-02-18-v3-hybrid-exhaustive-search.md` | Original V3 architecture and feature design |
| ADR-005 | `docs/adr/005-bm25-identifier-matching-vs-grep.md` | BM25 identifier matching vs grep design insight |
| V3 search engine | `clew/search/engine.py` | Core search pipeline with confidence scoring and mode selection |
| V3 CLI output | `clew/cli.py` | V3.1 output serialization changes |
| V3 MCP server | `clew/mcp_server.py` | MCP tool definitions and response format |
| V3 surfacing module | `clew/search/surfacing.py` | Peripheral code surfacing via graph traversal |
| V3 grep integration | `clew/search/grep.py` | Grep subprocess integration |

---

## Section 6: Verdict Framework

After completing all three research tracks, produce one of these verdicts:

**1. "Evaluation valid, V3 dead."** The methodology is sound, the conclusion holds. V3's metadata-guidance approach is fundamentally incompatible with how agents use tools. Recommend V4 pivot with autonomous mode switching.

**2. "Evaluation flawed, V3 inconclusive."** Methodological issues (anonymization failure, sample size, post-hoc criterion escalation) undermine the conclusion. Recommend re-evaluation with fixes: larger sample, proper anonymization, pre-registered feature visibility criteria, MCP-based agents.

**3. "V3 strategy viable, execution failed."** The approach is sound but the implementation and evaluation didn't give it a fair test. Specific issues to cite: confidence miscalibration (10/11 "high"), weak suggestion text, CLI-only testing (no MCP agents), post-hoc test selection. Recommend V3.2 with targeted fixes and re-evaluation.

**4. "V3 strategy viable via different tactics."** The core insight (agents need better search results, not more metadata) is correct, but embedding metadata in JSON output is the wrong delivery mechanism. Recommend specific alternative tactic(s) from Track 3 research, with implementation plan.

Present your verdict with supporting evidence from each track, confidence level (high/medium/low), and dissenting considerations.
