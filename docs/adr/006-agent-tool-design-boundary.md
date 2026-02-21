# ADR-006: Agent-Tool Design Boundary — Tools Should Be Smarter So Agents Can Be Simpler

**Status:** Accepted
**Date:** 2026-02-20
**Deciders:** Engineering team
**Related:** [ADR-005](./005-bm25-identifier-matching-vs-grep.md), ADR-007, [V3.0 Viability Results](../plans/2026-02-19-v3.0-viability-results.md), [V3.1 Evaluation Handoff](../plans/2026-02-19-v3.1-evaluation-handoff.md)

---

## Context

V3 introduced metadata fields at the response level to guide agent search behavior:

```json
{
  "confidence_label": "low",
  "suggestion": "Try refining your query or using --mode exhaustive",
  "related_files": [...],
  "mode": "semantic",
  "results": [...]
}
```

The hypothesis was that agents would read these fields and adjust their search strategy accordingly — switching to `--mode exhaustive`, refining queries, or following related file suggestions.

### V3 Evaluation Evidence

V3.1 viability results (2026-02-19) directly falsified this hypothesis:

- `confidence_label`: present in 4/4 JSON outputs, agents read it in 0/4 cases
- `suggestion`: fired in 1/11 searches (10 returned high confidence), agents acted on it in 0/1 cases
- `related_files`: populated in 0/11 searches (no graph data for the queried patterns)
- `grep_results`: never populated — no agent used `--exhaustive` despite system prompt hints
- **Agent behavior change: 0/4** — no agent modified its search strategy in response to metadata

The root cause was observed directly in agent transcripts: agents systematically extracted the `results` array and discarded all other top-level fields through shell piping patterns:

```bash
clew search "query" --json | python3 -c "import json,sys; data=json.load(sys.stdin); [print(r['file_path']) for r in data['results']]"
clew search "query" --json | head -100
```

These patterns are not bugs — they are rational optimizations to reduce token consumption and focus on actionable data.

### Industry Convergence

No production code search tool surfaces quality metadata to guide agent search behavior. The industry has converged on two alternative patterns:

| Tool | Pattern | Agent Sees Metadata? |
|------|---------|---------------------|
| Cursor | Separate tools (`codebase_search` + `grep_search`) | No — agent chooses tool |
| Sourcegraph | Two-stage infrastructure (Zoekt + BM25F) | No — infrastructure decides |
| GitHub Copilot | 13 consolidated tools, embedding-guided routing | No — system decides |
| Continue.dev | MCP pass-through | All output passed (no metadata added) |
| **clew V3** | **Single tool + response-level metadata** | **Yes, but agents ignored it** |

### Anthropic's Tool Design Guidance

Anthropic's "Writing Tools for Agents" (September 2025) explicitly focuses on making results themselves more useful, not on adding sidecar metadata about results. The recommended patterns are:

- Human-readable field names (not cryptic IDs)
- `response_format` parameter for verbosity control
- Steer agents through error messages, not metadata fields

The guidance does not recommend confidence scores, quality labels, or top-level suggestion fields.

### Programmatic Tool Calling: The Architectural Signal

Anthropic's programmatic tool calling feature (September 2025) reveals the architectural direction:

> "Instead of Claude requesting tools one at a time with each result being returned to its context, Claude writes code that calls multiple tools, processes their outputs, and controls what information actually enters its context window."

In this model, tool results are processed by code in a sandbox. Only the final output of the code enters Claude's context — intermediate results and all metadata are never seen by the model. This is architecturally identical to the shell piping patterns observed in V3.1. Claude Code agents naturally adopt filtering patterns because that is how the model is designed to work efficiently with tool output.

### The MCP Signal: `isError` vs Sidecar Metadata

The MCP specification distinguishes between protocol-level signals and sidecar metadata. `isError: true` is explicitly designed to influence agent behavior:

> "Tool Execution Errors contain actionable feedback that language models can use to self-correct and retry with adjusted parameters."

V3's `confidence_label` field is sidecar metadata — it is informational, not a protocol-level signal, and it follows a different processing path. Agents respond to `isError` because it triggers well-established retry/correction behavior. Agents do not respond to `confidence_label` because nothing in their training or tool-use protocol requires them to.

---

## Decision

**Tools should be smarter so agents can be simpler.**

Features that improve search quality must operate autonomously inside the search engine, not as metadata for agents to interpret. Specifically:

### 1. Response-level metadata is invisible to agents — remove it

Fields placed at the top level of a JSON response alongside the `results` array will be systematically discarded by agents extracting results through code. Do not add quality signals, confidence labels, mode suggestions, or related-file hints at the response level. If agents don't see it, it doesn't help.

### 2. Result-level enrichment survives piping — use it

Agents iterate over individual results to extract file paths and snippets. Data embedded within each result object is processed in the same loop as the actionable data and cannot be discarded without also discarding the result itself.

Per-result enrichment model:
```json
{
  "results": [
    {
      "file_path": "clew/search/engine.py",
      "snippet": "class SearchEngine:\n    \"\"\"Orchestrates search pipeline.\"\"\"\n    # Called by: cli.search_command | Tested by: test_engine.py",
      "confidence": 0.89
    }
  ]
}
```

Relationship context, test file references, and structural signals belong inside each result, not at the response level.

### 3. Protocol signals influence agent behavior; sidecar metadata does not

`isError: true` is a protocol-level signal that triggers documented agent self-correction behavior. Response-level metadata fields are informational only. When the tool needs to steer agent behavior (e.g., low confidence, incomplete results), use protocol-level mechanisms or inject signals into the results stream — not top-level metadata fields.

Example: A synthetic warning result injected at position 0 of the results array will be seen by agents iterating over results; a top-level `suggestion` field will not.

### 4. Autonomous mode switching: the engine decides, not the agent

The intent classifier (`classify_intent()`) and mode selection logic should operate inside the search engine and make decisions automatically. When ENUMERATION intent is detected, the engine fans out to grep internally. The agent calls `clew search "query"` and receives complete results — it does not need to know that grep was involved.

The `--mode` parameter is preserved as a hard-floor override for cases where the agent has domain-specific knowledge about the query type. But autonomous mode switching is the default, not the exception.

---

## Rationale

### Why autonomous decisions over agent-guided decisions?

Sourcegraph's evaluation found that "agentic search systems can produce high quality answers with only access to simple search tools based on lexical matches." Agents do not need to understand search infrastructure to use it effectively. When GitHub Copilot reduced from 40+ tools to 13 using embedding-guided selection, task success improved by 2-5 percentage points. The value is in reducing agent decision-making overhead, not in giving agents more information to decide with.

### Why result-level over response-level metadata?

The GrepRAG paper (arxiv:2601.23254) found that per-identifier structural signals (class names at 35.96%, method names at 41.47%) embedded directly in retrieval results improved completion quality. Cursor returns per-result file paths and line numbers with no response-level metadata. GitHub Copilot embeds license information and repository context in each suggestion. The production pattern is consistent: signals belong with the data they describe.

### Why does `--mode` survive as an override?

V3.0 Track B demonstrated that when agents chose `--mode exhaustive` explicitly, it worked correctly — the agent benefited from understanding the mode semantics. The `--mode` parameter preserves agent agency when the agent has task-specific knowledge. Autonomous switching handles the common case; `--mode` handles the expert case. This is a lower-friction interface than requiring all agents to read quality metadata and decide to switch.

---

## Consequences

### Positive

- **Results improve regardless of agent behavior.** Autonomous mode switching, result-level enrichment, and internal quality improvements benefit all agents without requiring any change to how agents call clew.
- **Survives all piping patterns.** `| head -100`, `data['results']`, jq filters — result-level data survives all of these. Response-level metadata survives none of them.
- **Aligned with industry direction.** Cursor, Sourcegraph, GitHub Copilot, and Anthropic's own tool design guidance all point toward infrastructure-level intelligence, not agent-visible metadata.
- **Reduces agent context consumption.** Removing response-level metadata fields reduces output size, freeing context for reasoning.

### Negative

- **Reduces user/agent control over search strategy.** Autonomous mode switching means the agent cannot easily observe what mode was selected or override it per-query. Mitigated by: `--mode` is preserved as an explicit override; mode selection is logged in status output.
- **Debugging is harder.** When autonomous mode switching produces unexpected results, it is less transparent than when the agent chose a mode explicitly. Mitigated by: `--mode` override allows manual reproduction.
- **V3 work is not salvageable as-is.** The V3.0/V3.1 implementation built response-level metadata infrastructure that must be removed or replaced with result-level equivalents in V4. This is engineering cost, not just design cost.

---

## References

- V3.0 viability evaluation: Internal, 2026-02-19
- V3.1 viability evaluation: Internal, 2026-02-19
- Best practices research: `docs/plans/2026-02-20-v3-best-practices.md`
- [Cursor Agent System Prompt (March 2025)](https://gist.github.com/sshh12/25ad2e40529b269a88b80e7cf1c38084)
- [How Cursor AI IDE Works](https://blog.sshh.io/p/how-cursor-ai-ide-works)
- [Keeping it boring (and relevant) with BM25F — Sourcegraph](https://sourcegraph.com/blog/keeping-it-boring-and-relevant-with-bm25f)
- [GitHub Copilot Enhances Efficiency by Streamlining Tool Usage](https://blockchain.news/news/github-copilot-enhances-efficiency-by-streamlining-tool-usage)
- [Writing effective tools for AI agents — Anthropic Engineering](https://www.anthropic.com/engineering/writing-tools-for-agents)
- [Introducing advanced tool use — Anthropic Engineering](https://www.anthropic.com/engineering/advanced-tool-use)
- [Programmatic tool calling — Anthropic Platform Docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/programmatic-tool-calling)
- [MCP Tools Specification (2025-11-25)](https://modelcontextprotocol.io/specification/2025-11-25/server/tools)
- [Error Handling in MCP Servers Best Practices](https://mcpcat.io/guides/error-handling-custom-mcp-servers/)
- [Filtering large MCP tool responses with jq — Speakeasy](https://www.speakeasy.com/mcp/tool-design/response-filtering-jq)
- [GrepRAG paper](https://arxiv.org/abs/2601.23254)
- [Lost in the Middle: How Language Models Use Long Contexts](https://arxiv.org/abs/2307.03172)
- [An Exploratory Study of Code Retrieval Techniques in Coding Agents](https://www.preprints.org/manuscript/202510.0924)
