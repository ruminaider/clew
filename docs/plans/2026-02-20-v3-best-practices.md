# V3 Best Practices Research: Agent-Tool Communication Patterns

**Date:** 2026-02-19
**Purpose:** Determine whether "agents ignore tool metadata" is a known limitation with known solutions, or a clew-specific failure. This research informs the devil's advocate review of the V3 KILL decision.

---

## 1. Agent-Tool Communication Patterns in Production Code Search Tools

### Cursor: Separate Tools, No Metadata

Cursor provides **separate, specialized tools** for different retrieval modes rather than a single search tool with metadata guidance:

- **`codebase_search`**: Semantic search against pre-indexed embeddings. Described as "a semantic search tool, so the query should ask for something semantically matching what is needed."
- **`grep_search`**: Exact pattern matching via ripgrep. Described as "best for finding exact text matches or regex patterns. More precise than semantic search for finding specific strings or patterns."

Critically, **neither tool returns relevance scores, confidence metrics, or quality metadata** to the agent. The agent receives code snippets and file paths, nothing more. The agent decides which tool to use based on the task description, not based on feedback from previous tool calls.

Cursor also employs a **pre-filtering LLM** that re-ranks and filters results before they reach the main agent, ensuring "the main agent gets the 'perfect' results." This means quality signals are consumed by infrastructure, not surfaced to the agent.

**Sources:**
- [Cursor Agent System Prompt (March 2025)](https://gist.github.com/sshh12/25ad2e40529b269a88b80e7cf1c38084)
- [How Cursor AI IDE Works](https://blog.sshh.io/p/how-cursor-ai-ide-works)
- [Cursor Agent Prompt 2.0](https://github.com/x1xhlol/system-prompts-and-models-of-ai-tools/blob/main/Cursor%20Prompts/Agent%20Prompt%202.0.txt)

**Applicability to clew:** Cursor's architecture validates the V4 direction of autonomous mode switching. Cursor never asks the agent to interpret search quality metadata. The system handles mode selection transparently, and the agent operates on results directly. This is the exact opposite of V3's metadata-guidance approach.

### Sourcegraph Cody: Search-First RAG, No Agent-Visible Metadata

Sourcegraph made a deliberate architectural decision to move away from embeddings for code search. Their evaluation showed BM25F delivered "roughly 20% improvement across all key metrics compared to baseline ranking" and they explicitly note that "agentic search systems can produce high quality answers with only access to simple search tools based on lexical matches."

Sourcegraph's architecture uses a two-stage pipeline: Zoekt trigram-based search for first-stage retrieval, then BM25F scoring for ranking. The agent does not see ranking scores or confidence levels.

Their "Deep Search" MCP server exposes search as a tool but focuses on returning results, not metadata about result quality.

**Sources:**
- [Keeping it boring (and relevant) with BM25F](https://sourcegraph.com/blog/keeping-it-boring-and-relevant-with-bm25f)
- [Sourcegraph Cody vs Qodo comparison](https://www.augmentcode.com/tools/sourcegraph-cody-vs-qodo)

**Applicability to clew:** Sourcegraph's move away from embeddings at enterprise scale is informative but addresses a different problem (scalability, not agent communication). The relevant insight is that their search quality improvements happen entirely within the search infrastructure, not via agent-visible metadata.

### GitHub Copilot: Tool Consolidation, Not Metadata

GitHub streamlined Copilot's toolset from 40+ tools to 13 core tools using "embedding-guided selection and adaptive clustering." This resulted in 2-5 percentage point improvement in task success rate and 400ms latency reduction.

The key insight: GitHub's approach to improving tool use was to **reduce the number of tools** (less agent decision-making), not to add metadata to help agents make better decisions with more tools. The 94.5% coverage rate of the embedding-based selection indicates that pre-selecting the right tools for the agent is more effective than giving the agent more information to select tools itself.

**Sources:**
- [GitHub Copilot Enhances Efficiency by Streamlining Tool Usage](https://blockchain.news/news/github-copilot-enhances-efficiency-by-streamlining-tool-usage)
- [November 2025 Copilot Roundup](https://github.com/orgs/community/discussions/180828)

**Applicability to clew:** This strongly supports the pattern that production systems make decisions for agents rather than surfacing metadata to guide agent decisions. Copilot's tool consolidation is philosophically aligned with autonomous mode switching (V4): the system decides, not the agent.

### Continue.dev: MCP-Native, Tool Results as Context

Continue.dev's agent mode uses MCP tool results as direct context items: "Any data returned from a tool call is automatically fed back into the model as a context item." This is a pass-through model where all tool output becomes part of the agent's context without filtering or metadata separation.

**Sources:**
- [Continue.dev Agent Quick Start](https://docs.continue.dev/ide-extensions/agent/quick-start)
- [How to Make Agent mode Aware of Codebases](https://docs.continue.dev/guides/codebase-documentation-awareness)

**Applicability to clew:** Continue.dev's pass-through model suggests that in the MCP pathway, tool results do reach the agent intact. This partially contradicts the V3 observation that agents ignore metadata, since it's the CLI pathway where piping discards metadata, not the MCP pathway. V3.1 was only evaluated via CLI agents.

### Pattern Summary

| Tool | Search Architecture | Agent Sees Metadata? | Mode Selection |
|------|---------------------|---------------------|----------------|
| Cursor | Separate tools (semantic + grep) | No | Agent chooses tool |
| Sourcegraph | Two-stage (trigram + BM25F) | No | Infrastructure decides |
| GitHub Copilot | 13 consolidated tools | No | Embedding-guided routing |
| Continue.dev | MCP pass-through | All output passed | Agent chooses tool |
| **clew V3** | **Single tool + metadata** | **Yes, but ignored** | **Agent guided by metadata** |

**Conclusion:** No production code search tool surfaces quality metadata to guide agent behavior. The industry pattern is either separate tools (let the agent choose) or autonomous infrastructure (the system chooses). V3's metadata-guidance approach has no precedent in production systems.

---

## 2. LLM Tool Output Design Research

### Anthropic's "Writing Tools for Agents" (September 2025)

Anthropic's official engineering blog post on tool design provides the most authoritative guidance. Key principles directly relevant to V3:

**Return meaningful, human-readable context:**
> Natural language identifiers significantly outperform cryptic technical IDs. Converting arbitrary alphanumeric UUIDs into semantically meaningful language "significantly improves Claude's precision in retrieval tasks by reducing hallucinations."

**Implement `response_format` for verbosity control:**
> The example shows a detailed response consuming 206 tokens versus a concise version using only 72 tokens. A `response_format` enum parameter allows agents to request either "concise" or "detailed" responses.

**Token efficiency is paramount:**
> Claude Code restricts tool responses to 25,000 tokens by default. Every token in a tool response is a token not available for reasoning or additional tool calls.

**Steer agents through error messages:**
> Instead of returning `ERROR: TOO_MANY_RESULTS`, return: "Found 847 expenses. This is too large to return. Please narrow your date range or specify a category filter."

**Critically, the blog does NOT recommend:**
- Adding metadata fields that describe result quality
- Including confidence scores or suggestions in tool output
- Using top-level response fields to guide agent behavior

The guidance focuses on making the results themselves more useful, not on adding sidecar metadata about the results. This is the core design philosophy that V3 violated.

**Sources:**
- [Writing effective tools for AI agents](https://www.anthropic.com/engineering/writing-tools-for-agents)
- [Summary by Agentailor](https://blog.agentailor.com/posts/writing-tools-for-ai-agents)

**Applicability to clew:** Anthropic's own guidance aligns with result-level enrichment (V4 approach b) rather than response-level metadata (V3 approach). The recommendation to steer through error messages supports the V4 approach of using synthetic warning results, but not the V3 approach of adding top-level metadata fields.

### Tool Response Format Impact

Research confirms that response format significantly impacts LLM performance:
> "Tool response structure -- such as XML, JSON, or Markdown -- can impact evaluation performance significantly, as LLMs are trained on next-token prediction and tend to perform better with formats matching their training data."

The optimal format varies by task, but the consistent finding is that what's IN the results matters more than metadata ABOUT the results.

**Sources:**
- [LLM agents - Agent Development Kit](https://google.github.io/adk-docs/agents/llm-agents/)

### Programmatic Tool Calling: The Context Window Problem

Anthropic's programmatic tool calling feature (September 2025) reveals a fundamental architectural insight: **Claude processes tool results through code, not through direct attention.**

> "Instead of Claude requesting tools one at a time with each result being returned to its context, Claude writes code that calls multiple tools, processes their outputs, and controls what information actually enters its context window."

In programmatic tool calling:
- Tool results are processed by code in a sandbox
- Only the **final output** of the code enters Claude's context
- Intermediate tool results, including all metadata, are never seen by the model

This is architecturally identical to the agent piping pattern observed in V3.1 evaluations (`| python3 -c "data['results']"`, `| head -100`). Claude Code agents naturally adopt this filtering pattern because it's how the model is designed to work efficiently with tool output.

**Sources:**
- [Introducing advanced tool use](https://www.anthropic.com/engineering/advanced-tool-use)
- [Programmatic tool calling documentation](https://platform.claude.com/docs/en/agents-and-tools/tool-use/programmatic-tool-calling)

**Applicability to clew:** This is the most significant finding. Anthropic's own architecture validates that agents filter tool output through code, discarding metadata in the process. V3's assumption that agents would read top-level metadata fields conflicts with the direction Anthropic's own tooling is moving. Programmatic tool calling explicitly moves data processing OUT of the model's context, making metadata-guidance approaches structurally incompatible.

---

## 3. Claude Code MCP Tool Consumption

### How MCP Tool Results Reach the Model

When Claude Code receives an MCP tool response:

1. Tool results are structured as `tool_result` content items within the conversation
2. Text content from MCP tools is rendered directly into Claude's context
3. A warning is displayed when any MCP tool output exceeds 10,000 tokens
4. Maximum allowed output is 25,000 tokens (configurable via `MAX_MCP_OUTPUT_TOKENS`)

**Key distinction:** When Claude Code calls an MCP tool directly (not through Bash piping), the full text content of the tool response enters Claude's context window. This means MCP-based agents would see V3's metadata fields, unlike CLI-based agents that pipe output through shell commands.

However, Claude Code also implements **MCP Tool Search** which "activates automatically when MCP tool descriptions would consume more than 10% of the context window." This dynamically loads tools on-demand, suggesting Claude Code actively manages what enters the context to preserve reasoning capacity.

### MCP Content Annotations

The MCP specification (November 2025 revision) supports content annotations with `audience` and `priority` fields:

```json
{
  "type": "text",
  "text": "result data",
  "annotations": {
    "audience": ["user", "assistant"],
    "priority": 0.9
  }
}
```

These annotations provide hints about which content items are most relevant. However, the spec explicitly states: "annotations are hints provided by the MCP server and are informational only, and do not enforce any behavior or restrictions."

### Structured Content (June 2025 Update)

The MCP spec added `structuredContent` and `outputSchema` fields, enabling programmatic consumption of tool results. This means MCP clients can validate and parse tool output without relying on the LLM to interpret text. Combined with programmatic tool calling, this creates a path where tool metadata could be consumed by code rather than by the model.

**Sources:**
- [Claude Code MCP Documentation](https://code.claude.com/docs/en/mcp)
- [MCP Tools Specification (2025-11-25)](https://modelcontextprotocol.io/specification/2025-11-25/server/tools)
- [MCP Tool Annotations Introduction](https://blog.marcnuri.com/mcp-tool-annotations-introduction)

**Applicability to clew:** V3.1 was only evaluated with CLI agents, where piping discards metadata. The MCP pathway is a fundamentally different channel where all tool output reaches the model. V3's metadata-guidance approach was never tested in the environment where it had the best chance of working. This is a significant evaluation gap.

---

## 4. Known Agent Limitations

### "Lost in the Middle" Problem

Research on the "Lost in the Middle" phenomenon (published in TACL, cited extensively in 2024-2025) establishes that LLMs have inherent position bias in how they process context:

> "Performance is often highest when relevant information occurs at the beginning or end of the input context, and significantly degrades when models must access relevant information in the middle of long contexts."

This is caused by Rotary Position Embedding (RoPE) introducing a "long-term decay effect" and causal attention masks creating position-specific hidden states.

For tool output, this means metadata placed at the beginning or end of a response has a better chance of being attended to than metadata embedded in the middle. V3's `confidence_label` was a top-level field in JSON output, which in serialized form would appear near the beginning -- theoretically a favorable position. However, when agents pipe output through extraction scripts, position is irrelevant because the metadata is stripped entirely.

Claude specifically shows "more uniform attention across its context window" compared to other models, with "relatively stable performance up to 60k tokens." This suggests Claude would be better than average at attending to metadata, IF the metadata reaches the model.

**Sources:**
- [Lost in the Middle: How Language Models Use Long Contexts](https://arxiv.org/abs/2307.03172)
- [Lost in the Middle: How LLM architecture and training data shape position bias](https://techxplore.com/news/2025-06-lost-middle-llm-architecture-ai.html)

### Agent Output Processing Patterns

The Speakeasy MCP documentation describes a `jq_filter` pattern where the LLM agent explicitly filters tool responses:

> "By adding an optional jq_filter parameter to your tool, the LLM can provide jq syntax to filter the response before processing it... The LLM processes a fraction of the original response size."

This reveals that **agents actively choose to discard information** from tool responses. This is not a bug but a rational optimization: "Large API responses consume valuable LLM context. When an API returns hundreds of records, the LLM must process every field of every record, even when only a few specific details are needed."

When an agent calls `clew search --json | python3 -c "import json,sys; data=json.load(sys.stdin); [print(r['file_path']) for r in data['results']]"`, it is doing exactly what jq_filter does: extracting the actionable data (file paths) and discarding everything else (metadata, confidence scores, suggestions).

**Sources:**
- [Filtering large MCP tool responses with jq](https://www.speakeasy.com/mcp/tool-design/response-filtering-jq)

### MCP isError as Agent-Influencing Signal

The MCP specification distinguishes between protocol errors and tool execution errors. Tool execution errors (returned with `isError: true`) are specifically designed to influence agent behavior:

> "Tool Execution Errors contain actionable feedback that language models can use to self-correct and retry with adjusted parameters."

> "When input validation errors are treated as Tool Execution Errors rather than Protocol Errors, language models can receive validation error feedback in their context window, allowing them to self-correct and successfully complete tasks without human intervention."

This is significant: `isError: true` is a metadata signal that agents DO respond to. The difference between `isError` and V3's `confidence_label` is that `isError` changes the tool's return status (it's part of the protocol, not sidecar metadata) and triggers a well-established retry/correct behavior pattern.

**Sources:**
- [Error Handling in MCP Servers Best Practices](https://mcpcat.io/guides/error-handling-custom-mcp-servers/)
- [SEP-1303: Input Validation Errors as Tool Execution Errors](https://github.com/modelcontextprotocol/modelcontextprotocol/issues/1303)
- [Better MCP tool call error responses](https://alpic.ai/blog/better-mcp-tool-call-error-responses-ai-recover-gracefully)

**Applicability to clew:** This suggests that if V3 had returned low-confidence results as `isError: true` with a message like "Search results have low confidence. Try narrowing your query or using --mode exhaustive", the agent would have been more likely to react. Error signals follow a different processing path than metadata fields.

---

## 5. Result-Level vs Response-Level Metadata

### The Fundamental Problem

The V3 approach placed metadata at the **response level** (top-level JSON fields alongside the `results` array):

```json
{
  "confidence_label": "low",
  "suggestion": "Try refining your query...",
  "related_files": [...],
  "mode": "semantic",
  "results": [...]
}
```

Agents extract the `results` array and discard everything else. This is a documented, rational behavior pattern.

### What Per-Result Metadata Looks Like

An alternative approach embeds signals within each result:

```json
{
  "results": [
    {
      "file_path": "clew/search/engine.py",
      "snippet": "class SearchEngine:...",
      "confidence": 0.89,
      "related": "Called by: cli.py:search_command | Tests: test_engine.py"
    }
  ]
}
```

Since agents iterate over results to extract file paths and snippets, per-result metadata is processed in the same loop. The agent cannot discard it without also discarding the actionable data.

### Evidence from Production Systems

Cursor's `codebase_search` returns code snippets with file paths and line numbers -- all per-result data. No response-level metadata.

GitHub Copilot's code matching feature embeds license information, repository URLs, and match locations directly in each matched suggestion -- again, per-result metadata.

The GrepRAG paper found that grep-based retrieval identifies "code fragments more closely related to the completion site" by focusing on per-identifier relevance. The paper's optimized pipeline embeds structural signals (class names at 35.96%, method names at 41.47%) directly in the retrieval results, not as response-level metadata.

### The Attention Economy Argument

From the "Lost in the Middle" research and context engineering literature:

> "Unstructured data, such as long email threads or technical documents, often leads to hallucinations or errors because the model sees too much irrelevant information."

> "By filtering and reorganizing data into participant summaries, timelines, or decision lists, the model receives relevant context that improves reasoning and factual grounding."

Applied to tool output: structured, per-result enrichment that integrates signals into the data the agent is already reading will receive attention. Response-level metadata that requires the agent to explicitly look outside its extraction loop will not.

**Sources:**
- [GrepRAG paper](https://arxiv.org/html/2601.23254v1)
- [Context Engineering for LLMs](https://research.aimultiple.com/context-engineering/)

**Applicability to clew:** Per-result enrichment (embedding relationship context, confidence badges, and suggestions directly in each result's snippet or as a natural part of each result object) is the most likely approach to survive agent piping patterns. V4 approach (b) from the alternative tactics analysis aligns with this finding.

---

## 6. The Cursor/Sourcegraph Approach: Separate Tools

### Why Separate Tools?

Cursor provides `codebase_search` and `grep_search` as separate tools, not a single `search` tool with a `mode` parameter. This architectural choice has specific benefits:

1. **Tool selection is a well-understood agent capability.** LLMs are extensively trained on tool selection tasks. Choosing between two tools with clear descriptions is easier than interpreting a metadata field that suggests switching to a different mode.

2. **The system prompt guides tool selection.** Cursor's prompt explicitly states: "grep_search is more precise than semantic search for finding specific strings or patterns, and preferred over semantic search when the exact symbol/function name is known." This guidance is processed ONCE during system prompt ingestion, not on every tool call.

3. **Parallel execution.** Cursor's prompt instructs: "When running multiple read-only commands like read_file, grep_search or codebase_search, always run all of the commands in parallel." An agent can call both search types simultaneously rather than calling one, reading metadata, then deciding to call the other.

4. **No re-decision overhead.** With V3's approach, the agent would need to: (a) call search, (b) read metadata, (c) decide to call again differently. With separate tools, the agent makes one decision upfront. The GrepRAG paper found only "20-30% overlap" between grep and semantic results, confirming they are complementary and both should be used when thoroughness matters.

### The Deliberate Avoidance of Metadata

This pattern is not accidental. GitHub Copilot went further by reducing from 40+ tools to 13, using embedding-guided selection so the **system** routes queries to the right tool rather than the agent choosing. The trend across all major players is toward reducing agent decision-making about search quality, not increasing it.

The research paper "An Exploratory Study of Code Retrieval Techniques in Coding Agents" (October 2025) investigates whether "human-centric tooling like LSP translates to agent-centric performance, or whether simpler lexical tools like grep and ripgrep are more aligned with how models explore and synthesize context." The study examines multi-agent architectures where "a dedicated retrieval agent handles context gathering separately from the primary coding agent," further supporting the pattern of separation over metadata.

A benchmark comparing mgrep (semantic search) with grep-based workflows found that "mgrep+Claude Code used approximately 2x fewer tokens at similar or better quality, as mgrep finds relevant snippets in a few semantic queries first, allowing the model to spend capacity on reasoning instead of scanning." This confirms that the value of better search is in reducing agent workload, not in giving agents more information to process.

**Sources:**
- [An Exploratory Study of Code Retrieval Techniques in Coding Agents](https://www.preprints.org/manuscript/202510.0924)
- [Search and Indexing Strategies](https://developertoolkit.ai/en/shared-workflows/context-management/codebase-indexing/)
- [Cursor Semantic Search 12.5% Better Accuracy](https://www.digitalapplied.com/blog/cursor-semantic-search-coding-ai-guide)

**Applicability to clew:** If clew adopted the separate-tools pattern, it would offer `clew_semantic_search` and `clew_grep_search` (or `clew_exhaustive_search`) as separate MCP tools. The agent would choose based on task type. However, this requires agents to learn clew's tool taxonomy, which is a higher friction approach than autonomous mode switching where a single `clew search` internally decides.

---

## Assessment: Was V3's Metadata-Guidance Approach Doomed, Poorly Executed, or Ahead of Its Time?

### Doomed by Design

The evidence strongly supports that V3's core strategy -- embedding metadata in tool output to guide agent behavior -- was doomed by design. The reasons are structural, not implementation-specific:

1. **No precedent in production systems.** Cursor, Sourcegraph, GitHub Copilot, and Continue.dev all avoid surfacing quality metadata to agents. The industry has converged on either separate tools (Cursor) or autonomous infrastructure decisions (Copilot, Sourcegraph). Not a single production code search tool uses metadata to guide agent search behavior.

2. **Conflicts with how agents process tool output.** Anthropic's own programmatic tool calling feature explicitly moves data processing out of the model's context window. Claude writes code to filter and extract from tool output, discarding metadata in the process. This is the exact pattern V3.1 observed ("agents pipe away metadata"). It is not a clew-specific bug but a designed behavior that Anthropic actively encourages for token efficiency.

3. **Anthropic's tool design guidance recommends against it.** The "Writing Tools for Agents" blog post focuses on making results themselves more useful, not on adding sidecar metadata. The recommended patterns are: human-readable field names, `response_format` for verbosity control, and steering through error messages. None of these involve adding top-level quality metadata.

4. **The attention economy works against it.** Tool metadata competes with result data for attention. When agents have limited context windows and are optimized for token efficiency, they rationally discard non-actionable metadata. Research on position bias and context engineering confirms that information outside the primary data path receives less attention.

### Partial Execution Failure

While the design was fundamentally flawed, there were also execution problems that prevented a fair test:

1. **V3.1 was only tested via CLI agents.** The MCP pathway, where tool results reach the model intact without piping, was never evaluated. Continue.dev's architecture confirms that MCP tool results enter the model's context directly. V3's metadata might have been visible in MCP-based evaluations.

2. **Confidence calibration was wrong.** The confidence scorer returned "high" for 10/11 searches, meaning the `suggestion` field (which only fires on low confidence) appeared in only 1 out of 11 opportunities. The metadata-guidance strategy was barely tested because the triggering condition rarely fired.

3. **The suggestion text was too vague.** "Low confidence -- consider refining query or trying a different mode" is not actionable enough. Compare with MCP `isError` responses that provide specific correction instructions.

### Ahead of Its Time?

The MCP specification's evolution toward structured content, output schemas, and content annotations suggests that tool-to-agent metadata communication is a recognized need. However:

- MCP annotations are "informational only" (spec language) -- they do not enforce behavior
- Structured content is designed for programmatic consumption by code, not for model attention
- The trend is toward infrastructure processing metadata, not agents processing metadata

V3 was not ahead of its time. It was trying to solve a real problem (agents need better results, not more results) through a channel that the ecosystem is actively moving away from. The solution to "agents need better results" is to make the results better autonomously, not to tell agents the results are bad and hope they adjust.

### Verdict

**V3's metadata-guidance approach was doomed by design**, with execution failures making the evaluation incomplete but not changing the structural conclusion. The approach has no precedent, conflicts with documented agent behavior patterns, and contradicts Anthropic's own tool design guidance.

---

## Specific Patterns Clew Could Adopt

Based on this research, the following patterns have production precedent and could address clew's goals:

### Pattern 1: Autonomous Mode Switching (Highest Confidence)

Like Sourcegraph and GitHub Copilot, clew should internally decide search mode based on query analysis. The `classify_intent()` function and ENUMERATION detection already exist. When ENUMERATION intent is detected, clew should automatically fan out to grep without requiring agent involvement.

**Evidence:** All major tools make infrastructure-level decisions about search strategy. No production tool asks the agent to switch modes.

### Pattern 2: Per-Result Enrichment (High Confidence)

Embed relationship context, test file references, and structural information directly in each search result's snippet text. Since agents extract snippets as part of their normal workflow, this information enters their reasoning loop naturally.

Example: Instead of a top-level `related_files` field, each result includes:
```
"snippet": "class SearchEngine:\n    \"\"\"Orchestrates search pipeline.\"\"\"\n    # Related: called by cli.search_command | tested in test_engine.py"
```

**Evidence:** Cursor returns per-result file paths and line numbers. GrepRAG embeds structural signals per-identifier. Anthropic recommends human-readable, contextually relevant tool responses.

### Pattern 3: Synthetic Warning Results (Medium Confidence)

When confidence is low, insert a warning as the first element of the results array:
```json
{"type": "warning", "message": "Only 2 results above confidence threshold. Results may be incomplete for this query."}
```

Since agents iterate over results, they will encounter this entry. Unlike top-level metadata, it cannot be filtered out by `data['results']` extraction.

**Evidence:** MCP `isError` responses successfully influence agent behavior. Error/warning signals in the data stream (not sidecar metadata) trigger self-correction. No direct production precedent for this exact pattern in code search tools.

### Pattern 4: Separate MCP Tools (Medium Confidence)

Expose `clew_search` (semantic) and `clew_exhaustive_search` (semantic + grep) as separate MCP tools with clear descriptions. The agent chooses based on the task.

**Evidence:** Cursor uses this exact pattern with `codebase_search` and `grep_search`. Research confirms agents are good at tool selection when tool descriptions are clear. However, this increases agent decision-making overhead and requires system prompt integration.

### Pattern 5: MCP Error Responses for Low Confidence (Lower Confidence)

Return `isError: true` when confidence is below a threshold, with a message suggesting query refinement. This uses a protocol-level signal that agents are documented to respond to.

**Evidence:** MCP spec explicitly states that `isError` tool results provide "actionable feedback that language models can use to self-correct." Research confirms agents retry with corrected parameters after receiving `isError`. However, low confidence is not truly an "error" -- this would be an abuse of the error channel that could confuse agents or cause unnecessary retries.
