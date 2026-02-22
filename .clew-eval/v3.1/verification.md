# V3.1 Anonymization Verification

## Summary
- Transcripts analyzed: 8
- Identified at >60% confidence: 8/8
- Pass/Fail: **FAIL** (threshold is <=3 identified at >60%)

### Identification Table

| Transcript | Identified As | Confidence | Key Signals |
|------------|--------------|------------|-------------|
| C1-A | grep | 70% | Regex patterns, file:line:content format, no JSON metadata |
| C1-B | clew | 75% | NL queries, JSON results with chunk_type/snippet/is_test fields |
| B1-A | grep | 65% | Regex alternation (`.*`/`|`), files_with_matches param, plain text results |
| B1-B | clew | 80% | `intent: "code"`, `mode: "semantic"`, trace graph output, NL queries |
| D1-A | clew | 70% | `chunk_type: "file_summary"`, `intent: "code"`, NL-first then regex fallback |
| D1-B | grep | 65% | All regex patterns, `type=py` param, plain text format, 80KB output file |
| D4-A | clew | 70% | NL queries, JSON with `chunk_type: "class"/"method"/"file_summary"` |
| D4-B | grep | 70% | `ls` navigation, regex alternation, `--` context separators, no JSON metadata |

## Per-Transcript Analysis

### C1-A
- **Identified as:** grep
- **Confidence:** 70%
- **Reasoning:** This transcript uses `find_files()` and `search()` with regex patterns and `output_mode="files_with_matches"` — these look like grep/ripgrep-style operations mapped to generic names. The search on line 239 uses a regex pattern `"refill|payment|checkout|billing"` which is characteristic of exact text matching. The agent never performs a natural language/semantic query. All searches are pattern-based. The approach is purely structural: find URL files, read them sequentially, confirm with pattern search. No results are returned as JSON with metadata like `chunk_type`, `function_name`, `snippet`, `is_test`, `line_start`, `line_end`, etc.
- **Leaks found:**
  - Search approach is entirely pattern-based regex, never natural language
  - No JSON result objects with semantic search metadata (chunk_type, snippet, scores)
  - Step 8 uses regex-style OR patterns: `"refill|payment|checkout|billing"` — this is a grep pattern, not a semantic query

### C1-B
- **Identified as:** clew
- **Confidence:** 75%
- **Reasoning:** The initial searches in Steps 1 and 2 use natural language queries: `search("ecommerce URL patterns views")` and `search("Django URL patterns cart orders shopify")`. These are semantic search queries, not regex patterns. The results come back as JSON objects with structured metadata including `file_path`, `line_start`, `chunk_type`, `function_name`, `class_name`, `snippet`, and `is_test` fields. This is the signature of clew's search response format. Line 79 contains the note `[search metadata]` which suggests additional metadata was present but redacted. Later searches like `search("consult checkout URL view")` and `search("refill prescription order view URL")` and `search("payment checkout view URL payment processing")` are all natural language queries, not regex patterns.
- **Leaks found:**
  - JSON result format with `chunk_type`, `function_name`, `class_name`, `snippet`, `is_test` fields — this is clew's output schema
  - Natural language queries (semantic search) vs pattern matching
  - `[search metadata]` note on line 79 suggests redacted clew metadata
  - Results are ranked by relevance, not by file position

### B1-A
- **Identified as:** grep
- **Confidence:** 65%
- **Reasoning:** The search patterns in this transcript are consistently regex-based. Step 2 uses `search("shopify.*order|order.*shopify|treatment.*refill|refill.*treatment", files_with_matches=True, case_insensitive=True)` — this is unmistakably a regex pattern with wildcards and alternation. Step 3 uses `search("def.*process.*shopify.*order|def.*shopify.*order.*process|def.*process.*order.*refill|def.*refill.*order", output_mode="content", case_insensitive=True)` — another regex. All subsequent searches follow the same pattern. Results come back as plain file:line:content format, not JSON with metadata. Step 15 uses `search("process_shopify_order_for_treatment_refill|_process_shopify_order_impl", output_mode="content", case_insensitive=True)` — pipe-separated alternation.
- **Leaks found:**
  - Regex patterns with `.*` wildcards and `|` alternation throughout
  - `files_with_matches=True` and `case_insensitive=True` parameters are grep/ripgrep flags
  - Results in plain `file:line:content` format, no JSON metadata

### B1-B
- **Identified as:** clew
- **Confidence:** 80%
- **Reasoning:** Multiple strong signals. Step 1 uses a natural language query: `search("shopify order processing treatment refill")`. The results come back as a JSON object with explicit metadata fields: `query`, `intent`, `mode`, `total_candidates`, and structured result objects with `file_path`, `line_start`, `line_end`, `chunk_type`, `language`, `function_name`, `class_name`, `snippet`, `is_test`. The `intent: "code"` and `mode: "semantic"` fields on lines 18-19 are direct leaks revealing clew's intent classification and search mode. `total_candidates: 30` reveals the internal candidate count. Step 4 shows a relationship graph output (lines 257-272) that maps call relationships — this is clew's `trace` feature. The results return structured relationship edges like `process_shopify_order_for_treatment_refill -> calls -> _parse_order_note_attributes` which is clew's relationship extraction format.
- **Leaks found:**
  - `"intent": "code"` and `"mode": "semantic"` on lines 18-19 — these are clew-specific fields
  - `"total_candidates": 30` — clew's internal candidate count
  - JSON results with `chunk_type`, `language`, `is_test`, `line_start`, `line_end` — clew schema
  - Relationship graph output (Step 4) with `-> calls ->` edges — clew's trace feature
  - Natural language queries vs regex patterns

### D1-A
- **Identified as:** clew
- **Confidence:** 70%
- **Reasoning:** Step 1 begins with a natural language query: `search("background task enqueue delay apply_async")`. The results come back as JSON with `query`, `intent`, `results` containing `file_path`, `chunk_type`, `snippet` fields. The `intent: "code"` field is visible. However, the agent quickly switches to pattern-based search in Step 2 (`search("\.delay\(|\.apply_async\(|send_task\(")`) which looks like grep. The initial semantic search returned configuration files and task definitions but "not the call sites" (line 38), which prompted switching to pattern search. This behavior — trying semantic first, then falling back to pattern — is consistent with clew's hybrid approach. The initial JSON result format with `chunk_type: "section"` and `chunk_type: "file_summary"` (lines 22, 27, 32) is clew-specific.
- **Leaks found:**
  - Initial results as JSON with `intent: "code"`, `chunk_type: "section"`, `chunk_type: "file_summary"` — clew metadata
  - Natural language first query followed by fallback to regex pattern
  - `chunk_type: "file_summary"` is a clew-specific chunk type

### D1-B
- **Identified as:** grep
- **Confidence:** 65%
- **Reasoning:** The exploration process is purely grep-based from the start. Step 2 searches with regex: `search("\.delay\(", path="backend/", type=py, files_with_matches)`. Step 3 uses `search("\.apply_async\(", ...)`. Step 4 uses `search("send_task\(", ...)`. All searches use regex patterns and grep-style parameters (`type=py`, `files_with_matches`, `context=3 lines`). Results come back as plain file:line:content format. Step 5 mentions the "full output (80KB) was persisted to a temporary file" — this is consistent with large grep output being saved. No JSON metadata, no semantic queries, no chunk_type or intent fields anywhere.
- **Leaks found:**
  - All searches are regex patterns with grep-style parameters (`type=py`, `context=3 lines`)
  - Results in plain file:line:content format
  - No semantic/natural language queries anywhere
  - Large output "persisted to a temporary file" — grep behavior

### D4-A
- **Identified as:** clew
- **Confidence:** 70%
- **Reasoning:** Step 1 begins with three parallel natural language searches: `search("authentication middleware permission classes")`, `search("login required decorator API endpoint auth")`, `search("token authentication API key session auth backend")`. All three return JSON results with `file_path`, `chunk_type`, `function_name`, `class_name`, `snippet` fields. The `chunk_type` values include "class", "method", "file_summary" — all clew-specific. Results are ranked by relevance. Step 7's search `search("permission_classes|authentication_classes|AllowAny|IsAuthenticated|csrf_exempt")` switches to pattern matching, but the initial approach and result format identify it as clew.
- **Leaks found:**
  - JSON results with `chunk_type: "class"`, `chunk_type: "method"`, `chunk_type: "file_summary"` — clew metadata
  - Natural language queries for initial discovery
  - Relevance-ranked results

### D4-B
- **Identified as:** grep
- **Confidence:** 70%
- **Reasoning:** The exploration starts with `ls` commands to understand directory structure, then uses pattern-based searches. Step 4 uses: `search("AUTHENTICATION_BACKENDS|REST_FRAMEWORK|DEFAULT_AUTHENTICATION_CLASSES|DEFAULT_PERMISSION_CLASSES", path="backend", context=3)`. This is clearly a grep search with regex alternation and context lines. Step 25 uses `search("permission_classes|authentication_classes|IsAuthenticated|AllowAny|IsAdminUser|login_required|IsStaff", path="backend/api/v1/views", context=2)`. All results come back in grep's standard `file:line:content` format with context markers (`--` between groups). The agent's approach is systematic file-by-file reading and grep searching — never using natural language queries. The "Output too large (23KB). Full output saved to: [tool-results-cache]" pattern is consistent with grep. Raw file content is read with line numbers visible (e.g., `1->`, `2->` prefix format).
- **Leaks found:**
  - Regex patterns with `|` alternation and `context=N` parameters
  - Results in grep's standard format with `--` context separators
  - `ls` commands for directory exploration (file-system navigation, not search)
  - No semantic queries, no JSON metadata, no chunk_type fields
  - Raw file reads with line number prefix format

## Overall Assessment

The sanitization has significant gaps. The primary leaks are:

1. **Result format divergence:** Clew transcripts consistently show JSON results with `chunk_type`, `function_name`, `class_name`, `snippet`, `is_test`, `line_start`, `line_end` fields. Grep transcripts show plain `file:line:content` format. This structural difference is immediately recognizable.

2. **Query style divergence:** Clew transcripts begin with natural language queries ("shopify order processing treatment refill"). Grep transcripts use regex patterns (`\.delay\(|\.apply_async\(`). While some clew transcripts also use regex-style searches, the initial approach differs.

3. **Explicit metadata leaks in B1-B:** The `"intent": "code"`, `"mode": "semantic"`, and `"total_candidates": 30` fields on lines 18-19 are direct clew metadata that were not sanitized. The relationship graph output in Step 4 is also a clew-specific feature.

4. **Chunk type vocabulary:** Terms like `chunk_type: "file_summary"`, `chunk_type: "section"`, `is_test: true/false` are clew-specific and appear nowhere in grep output.

### Recommendations

To improve anonymization:
- Normalize all search result formats to a common schema or strip metadata entirely
- Remove `intent`, `mode`, `total_candidates` fields from clew results
- Convert relationship graph outputs to generic format
- Normalize query styles (or explicitly note that both tools support both query types)
- Remove `[search metadata]` annotations
