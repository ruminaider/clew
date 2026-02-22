# V3 Alternative Tactics Analysis

**Date:** 2026-02-20
**Context:** Devil's Advocate Review, Track 3 — Alternative Delivery Mechanisms
**Scope:** Evaluate whether V3's core features could be delivered through mechanisms that agents actually use

---

## 1. Existing V3 Code Inventory

V3 added substantial infrastructure that is production-ready and well-tested (719 tests). The following table maps each V3 feature to its implementation location and current status.

| Feature | Module | Status | Agent-Visible (V3.1) |
|---------|--------|--------|---------------------|
| Confidence scoring | `engine.py:194-237` (`_compute_confidence`) | Working | Yes (in JSON), but agents don't react |
| Suggestion generation | `engine.py:119-141`, `mcp_server.py:160-170` | Working | 1/11 searches triggered (threshold too high) |
| Intent classification | `intent.py:70-131` (`classify_intent`) | Working | Yes, drives internal routing |
| ENUMERATION intent | `intent.py:15-26`, `hybrid.py:175-188` | Working | Drives BM25-heavy prefetches internally |
| Mode selection (semantic/keyword/exhaustive) | `engine.py:62-71`, `cli.py:130-141` | Working | Requires explicit `--mode` flag |
| Grep integration | `grep.py` (310 lines) | Working | Requires `--exhaustive` or `mode="exhaustive"` |
| Pattern generation | `grep.py:120-170` (`generate_grep_patterns`) | Working | Patterns generated but only used when exhaustive |
| Peripheral surfacing | `surfacing.py` (93 lines) | Working | Top-level `related_files` field (agents pipe away) |
| Confidence labels | `engine.py:227-236`, `models.py:71` | Working | In JSON output, agents ignore |
| Suggested patterns | `models.py:74`, `engine.py:124-130` | Working | In JSON output, agents ignore |

**Key insight:** The *computation* infrastructure is solid. The problem is exclusively in the *delivery* layer -- how computed results reach agents.

---

## 2. Feasibility Matrix

| Approach | Survives Piping | Implementable Now | Effort | Requires Agent Cooperation | Recommended |
|----------|----------------|-------------------|--------|---------------------------|-------------|
| **(a) Autonomous mode switching** | Yes | Yes (most code exists) | ~50 lines | No | **Yes** |
| **(b) Result-level enrichment** | Yes | Partially (graph data sparse) | ~80 lines | No | **Yes (conditional)** |
| **(c) Structured warnings in results** | Partially | Yes | ~30 lines | No (but risky) | No |
| **(d) Two-phase response** | N/A | Partially (MCP supports it) | ~200 lines | **Yes** | No |
| **(e) MCP-native `isError`** | MCP only | Yes | ~40 lines | Partially | No |

---

## 3. Detailed Analysis

### (a) Autonomous Mode Switching

**Concept:** Clew internally decides when to augment semantic search with grep, without requiring the agent to pass `--mode exhaustive` or `--exhaustive`. The agent calls `clew search "query"` and gets the best possible results automatically.

**What V3 code already supports this:**

1. **Intent classification** (`intent.py:70-131`): `classify_intent()` already detects ENUMERATION queries ("find all", "list all", "every instance", etc.). This is the primary trigger for needing grep-augmented results.

2. **Confidence scoring** (`engine.py:194-237`): `_compute_confidence()` already computes a confidence label (high/medium/low) and a `SuggestionType` that distinguishes `TRY_KEYWORD`, `TRY_EXHAUSTIVE`, and `LOW_CONFIDENCE`. The suggestion type `TRY_EXHAUSTIVE` is the exact signal needed to trigger autonomous grep.

3. **Pattern generation** (`grep.py:120-170`): `generate_grep_patterns()` already derives ripgrep patterns from query text and semantic search results. This does not require agent input.

4. **Grep execution** (`grep.py:173-255`): `run_grep()` and `search_with_grep()` are fully operational and handle timeout, error recovery, and deduplication.

5. **Mode routing** (`engine.py:62-71`): The mode routing logic already handles `mode="exhaustive"` by calling `search_with_grep()`.

**What would need to change in `engine.py`:**

The core change is in the `search()` method. Instead of the current flow:

```
agent passes mode="exhaustive" --> engine runs grep
```

The new flow would be:

```
engine runs semantic search --> computes confidence --> if low/medium, internally runs grep --> merges results
```

Concretely, this means:

1. Move the grep invocation from the CLI/MCP layer (`cli.py:194-207`, `mcp_server.py:240-241`) into `engine.py`'s `search()` method.
2. After Step 7 (confidence computation), add a conditional: if `suggestion_type == SuggestionType.TRY_EXHAUSTIVE` and `intent == QueryIntent.ENUMERATION`, run `search_with_grep()` automatically.
3. Merge grep results into the `SearchResponse` (the `grep_results` field on `SearchResponse` would need to be added, or grep results could be converted to `SearchResult` objects and interleaved).
4. For ENUMERATION intent specifically, always run grep regardless of confidence (this is the "completeness guarantee" use case).

**Estimated changes:**

- `engine.py`: ~30 lines (add grep trigger logic after confidence computation, accept `project_root` parameter)
- `models.py`: ~5 lines (add `grep_results` field to `SearchResponse`)
- `cli.py`: ~-15 lines (remove manual exhaustive handling, let engine handle it)
- `mcp_server.py`: ~-10 lines (same simplification)
- Total: ~50 lines net, mostly reorganization

**Does this survive agent piping?** Yes. This is the critical advantage. The agent never needs to know about modes, confidence, or grep. It calls `clew search "find all error handlers"` and the results array contains both semantic and grep-derived matches. Agents extract `results` -- they get better results. The improvement is invisible and automatic.

**Risks:**

- **Latency:** Grep adds 1-5 seconds. For queries where grep is unnecessary (most semantic queries), this would be wasted. The intent classifier and confidence scoring provide adequate gating -- grep should only trigger for ENUMERATION queries or low-confidence results.
- **False positive triggers:** If confidence thresholds are miscalibrated (as V3.1 showed -- 10/11 "high"), grep never triggers. This is a tuning problem, not an architectural one. The fix is to lower `confidence_high_threshold_reranked` from 0.7 to ~0.5 and test.
- **Project root detection:** `engine.py` currently does not know the project root (needed for grep). The MCP server already has `_get_project_root()` which detects from git. This function would need to be accessible to the engine, either passed as a parameter or via config.

**Assessment:** This is the highest-leverage change. The entire grep integration pipeline exists; it just needs to be triggered automatically instead of waiting for an explicit flag that agents never use.

---

### (b) Result-Level Enrichment

**Concept:** Instead of surfacing relationship data as a top-level `related_files` field (which agents pipe away), embed relationship context directly into each search result's snippet or as additional fields within the result object.

For example, a search result for `process_payment()` would include:

```json
{
  "file_path": "billing/processor.py",
  "snippet": "def process_payment(order, amount):\n    \"\"\"Process payment...\"\"\"",
  "related": "Called by: handle_checkout() [billing/views.py], process_order() [orders/pipeline.py] | Tests: test_processor.py",
  "score": 0.85
}
```

**Where in the pipeline would this happen:**

The enrichment would occur in `mcp_server.py:_compact_result_to_dict()` (line 63) or a new function called from it. The data source is `cache.traverse_relationships_batch()` (`cache.py:779`), which already supports batch traversal.

The flow:

1. After search results are returned by `engine.search()`, collect entity identifiers from results (same logic as `surfacing.py:28-41`).
2. Call `cache.traverse_relationships_batch()` once for all result entities.
3. Group relationships by source/target entity to map them back to individual results.
4. Append a `related` string to each result's snippet or as a separate `context` field.

**How much data is available from the relationship store:**

This depends heavily on what has been indexed. The relationship store (`cache.py`) tracks: `imports`, `inherits`, `calls`, `decorates`, `renders`, `tests`, `calls_api`, `contains`. For a well-indexed Django project with `clew index --full`, a typical function has 2-5 relationships. For projects without full relationship extraction, this could be empty.

The V3.1 evaluation showed `related_files` was empty for all 4 tests. This is a data availability problem, not an architectural one. If the target project has been fully indexed with relationship extraction, the data would be present.

**Does this survive agent piping?** Yes. Agents read the `snippet` field (it's within the results array). If relationship context is embedded in the snippet text, agents will see it. If it's a separate field within each result object (like `"related": "..."`), agents will also see it because their extraction patterns pull entire result objects, not cherry-picked fields.

**Would it bloat results?** Mildly. A typical `related` string would add 50-100 characters per result. For 5 results, that's 250-500 extra characters -- negligible compared to the snippet content itself. The enrichment should be capped (e.g., top 3 callers, 1 test file) to prevent unbounded growth.

**Estimated changes:**

- `mcp_server.py`: ~50 lines (add relationship lookup to `_compact_result_to_dict()` or a wrapper)
- `cli.py`: ~20 lines (same enrichment for `--json` output)
- `surfacing.py`: ~10 lines (refactor batch traversal into a reusable function that returns per-entity data)
- Total: ~80 lines

**Risks:**

- **Empty data:** If relationships haven't been extracted, the `related` field is empty and adds no value. This is the same problem `related_files` had in V3.1.
- **Performance:** `traverse_relationships_batch()` is a single SQL query. For 5 results, this adds <10ms.
- **Noise:** Low-confidence relationships (e.g., generic `imports` edges) could clutter results. Filtering to `calls`, `tests`, `inherits` relationships would be more valuable.

**Assessment:** Good supplementary approach, but conditional on relationship data being available. Should be implemented alongside (a), not as a standalone fix.

---

### (c) Structured Warnings in Results Array

**Concept:** Insert synthetic "warning" result objects at position 0 of the results array when confidence is low.

```json
{
  "results": [
    {
      "type": "warning",
      "message": "Low confidence results. Only 2 of 5 results scored above 0.4. Consider using more specific terms.",
      "suggested_query": "find all authentication middleware classes"
    },
    {
      "file_path": "auth/middleware.py",
      "snippet": "...",
      "score": 0.45
    }
  ]
}
```

**Implementation complexity:** Low (~30 lines). In `mcp_server.py:search()`, after computing the response, insert a warning dict at `result_dict["results"][0]` when `confidence_label != "high"`.

**Would agents process these or skip them?** This is the critical question, and the answer is "unpredictable." Agents extract results to get file paths and line numbers. A warning object without `file_path` and `line_start` would break agents that assume uniform result format. Some agents might:

- Skip it silently (extracting `file_path` returns `None`, agent moves on)
- Error out (trying to read a file at path `None`)
- Process the message text (least likely based on observed behavior)

**Risk of confusing agents:** High. The V3.1 evaluation showed agents use patterns like `python3 -c "for r in data['results']: print(r['file_path'])"`. A warning result without `file_path` would either produce an error or print `None`, both of which degrade the experience. Even if the warning includes a dummy `file_path`, agents would try to open it.

**Assessment:** Not recommended. This approach trades one problem (agents ignore top-level metadata) for a worse one (agents crash or get confused by malformed results). The benefit of being "inside the results array" is negated by the format inconsistency.

---

### (d) Two-Phase Response

**Concept:** First call returns a search plan; second call executes it.

```
Agent: clew search "find all error handlers"
Clew (phase 1): {"plan": "I'll search semantically for error handlers, then grep for 'except|catch|@error_handler'. Estimated: 15 semantic + 30 grep results. Proceed?"}
Agent: clew search --execute-plan <plan_id>
Clew (phase 2): {"results": [...]}
```

**MCP protocol support:** MCP supports multi-step tool interactions. A tool can return a response that suggests calling another tool. However, there is no native "continuation" mechanism -- the agent would need to explicitly call the second tool.

**Does this require agent cooperation?** Yes, fundamentally. The agent must:

1. Read the plan response
2. Decide to call the execute step
3. Pass the plan ID

This is the same "agent must react to metadata" problem that killed V3. The agent would need to understand that the first call was a plan, not results, and take a specific follow-up action. Based on V3.1 evidence, agents do not do this.

**Compatibility with CLI usage:** Poor. CLI users would need to run two commands, which is worse UX than the current single command with `--exhaustive`.

**Assessment:** Not recommended. This reintroduces the agent cooperation problem in a more fragile form. If the agent ignores the plan and treats the first response as the final answer, the user gets no results at all (worse than V3's current behavior where they at least get semantic results).

---

### (e) MCP-Native Approach

**Concept:** Use MCP protocol features -- `isError` response flag, tool description annotations, `_meta` field -- to guide agent behavior.

**What MCP protocol features are available:**

1. **`isError` flag:** `CallToolResult(content=[...], isError=True)` marks the response as an error. The MCP Python SDK supports this natively. FastMCP tools can return `CallToolResult` directly for full control.

2. **`_meta` field:** `CallToolResult(_meta={...})` passes metadata to the client application (Claude Code) but is NOT exposed to the model. This is explicitly for client-level processing, not agent-level.

3. **`structuredContent`:** Alongside `content` (text shown to model), tools can return `structuredContent` (machine-readable data). However, this is primarily for client applications, not for influencing model behavior.

4. **Tool descriptions:** The `@mcp.tool()` decorator's docstring becomes the tool description in the MCP schema. Agents see this when deciding which tool to call. Descriptive annotations ("when confidence is low, try mode='exhaustive'") could theoretically influence behavior -- but V3.1 proved that system prompt hints about `--mode` and `--exhaustive` were ignored.

**How does Claude Code handle `isError` responses?**

Claude Code treats `isError: true` responses differently from normal responses. The agent sees the error and typically:
- Reports the error to the user
- May retry with different parameters
- May try a different approach

This is interesting because it creates an interrupt in the agent's pipeline. Instead of piping results through extraction patterns, the agent would need to handle the error.

However, abusing `isError` for "low confidence results" is semantically wrong. The search *succeeded* -- it just returned uncertain results. Marking a successful-but-uncertain search as an error could:
- Cause the agent to report "search failed" to the user
- Trigger unnecessary retries with the same query
- Undermine trust in the tool (agents may stop using it if it "errors" frequently)

**Would this work for CLI agents?** No. `isError` is an MCP protocol concept. CLI agents using `clew search --json | ...` would not see it. This creates a split between MCP and CLI behavior.

**Assessment:** Not recommended as the primary approach. `isError` could be useful for genuine errors (Qdrant down, API key missing) but should not be overloaded for search quality signals. The `_meta` field is explicitly not visible to the model. Tool descriptions have already been shown to be ignored.

---

## 4. Recommended Approach

### Primary: (a) Autonomous Mode Switching

**Justification:** This is the only approach that satisfies all criteria simultaneously:

- **Survives piping:** Yes -- results are just better, no metadata to ignore.
- **Implementable now:** Yes -- all computational components exist.
- **Low effort:** ~50 lines of reorganization.
- **No agent cooperation required:** The agent calls `clew search` and gets results. Period.

**Implementation plan:**

1. Add `project_root: Path | None = None` parameter to `SearchEngine.__init__()`.
2. In `SearchEngine.search()`, after Step 7 (confidence computation):
   ```python
   # Step 8: Autonomous grep augmentation
   if self._should_augment_with_grep(intent, suggestion_type):
       grep_results = await self._run_grep(request, response.results)
       response = self._merge_grep_results(response, grep_results)
   ```
3. Define `_should_augment_with_grep()`:
   - Return `True` if `intent == ENUMERATION`
   - Return `True` if `suggestion_type == TRY_EXHAUSTIVE` and `project_root` is available
   - Return `False` otherwise
4. Move `search_with_grep()` logic from `grep.py` into engine or call it internally.
5. Simplify `cli.py` and `mcp_server.py` by removing manual exhaustive handling -- the engine does it automatically.
6. **Recalibrate confidence thresholds.** Lower `confidence_high_threshold_reranked` from 0.7 to 0.5 so that marginal results actually trigger grep augmentation instead of always reading "high."

### Supplementary: (b) Result-Level Enrichment (when data is available)

After implementing (a), add relationship context to individual result objects. This is low-risk, low-effort, and survives piping. But it should be conditional -- only include `related` field when relationship data exists for the entity, to avoid empty noise.

### Explicit non-recommendations: (c), (d), (e)

- **(c) Structured warnings:** Too risky. Breaks agent extraction patterns.
- **(d) Two-phase:** Reintroduces agent cooperation problem.
- **(e) MCP isError:** Semantically incorrect. Split behavior between MCP and CLI.

---

## 5. Assessment: Was V3 "Viable but Poorly Delivered" or "Fundamentally Dead"?

### The V3 strategy was viable but poorly delivered.

The KILL verdict was based on the observation that "agents ignore metadata." But this conflates two distinct claims:

1. **"Agents ignore top-level JSON fields that aren't in the results array"** -- TRUE, and well-evidenced by V3.0 and V3.1 transcripts.

2. **"Agents cannot benefit from V3's computational improvements"** -- FALSE. The computation (confidence scoring, intent classification, grep integration, pattern generation) is sound. The delivery mechanism (top-level JSON metadata requiring agent interpretation) was the wrong choice.

**The fundamental error was treating agents as collaborators rather than consumers.** V3 asked agents to:
- Read confidence labels and decide to switch modes
- Read suggested patterns and decide to run grep
- Read related_files and decide to explore them

None of these require agent cooperation if the system acts autonomously. Autonomous mode switching (approach a) delivers the same outcome -- better results for hard queries -- without requiring agents to process metadata or change their behavior.

**The proof is in V3's own code:** The confidence scoring, ENUMERATION detection, and grep integration already work. The only missing piece is a conditional that says "if confidence is low, run grep automatically" instead of "if confidence is low, tell the agent to run grep." This is approximately 20 lines of logic change.

### However, two caveats:

1. **The metadata-guidance strategy IS fundamentally dead.** Even with perfect implementation, agents will not read and react to sidecar metadata. This is not a clew-specific failure -- it appears to be a general property of how LLM agents interact with tool output. The V3.1 evidence (0/4 agent behavior changes despite metadata being visible in JSON) is dispositive. Any future version that relies on agents interpreting metadata fields should be avoided.

2. **Autonomous mode switching has not been evaluated.** The claim that "approach (a) would work" is based on architectural analysis, not empirical evidence. The improvement is plausible (better results = higher scores regardless of agent behavior), but the actual impact on viability scores is unknown. ENUMERATION queries were clew's weakest category (C1: 3.13/5.0 in V2.3); autonomous grep for these queries should help, but by how much is uncertain.

### Recommendation:

Implement autonomous mode switching as a V4 feature (or V3.2, if the V3 line is resurrected). It is the natural evolution of V3's code: keep the computation, discard the metadata-guidance delivery mechanism. Estimated effort is 1-2 hours of implementation plus threshold recalibration, leveraging the ~2,200 lines of V3 code that already exist.
