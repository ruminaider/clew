# /clew:explain

Understand a symbol with context from semantic search, the relationship graph, and optional LLM synthesis.

## When to Use

- Getting a quick summary of what a class or function does
- Understanding a symbol in context without reading all the source
- Answering a specific question about a piece of code
- Getting an overview of a file's purpose

## When NOT to Use

- Searching for code across the codebase (use /clew:search)
- Reading full source code (use Read)
- Tracing dependencies (use /clew:trace)

## Usage

Call the `explain` MCP tool:

```
explain(file_path="src/auth.py", symbol="JWTAuthentication")
explain(file_path="app/models.py", symbol="Prescription.get_refills")
explain(file_path="app/views.py", question="How does this file handle authorization?")
explain(file_path="lib/cache.py")
```

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `file_path` | required | Path to the file for context |
| `symbol` | none | Symbol name to explain (class, function, variable) |
| `question` | none | Natural language question about the code |
| `detail` | "compact" | "compact" for snippets in related_chunks, "full" for complete source |

Provide either `symbol` or `question` (or neither, for a file-level overview).

## Reading Results

The response contains:

- `explanation` -- synthesized explanation (from LLM if available, otherwise heuristic)
- `explanation_source` -- "llm" or "heuristic" (indicates quality level)
- `related_chunks` -- search results used to build the explanation (compact by default)

The heuristic explanation includes signatures, docstrings, and relationship data (callers/callees). The LLM explanation provides a 2-4 sentence natural language summary.

Use Read to inspect specific related chunks that need deeper investigation.
