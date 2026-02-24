# /clew:search

Semantic code search. The main discovery tool for finding code by concept, behavior, or intent.

## When to Use

- Finding code you don't know the name of ("where does the app handle pharmacy API errors?")
- Vocabulary bridging -- your words don't match the codebase's naming conventions
- Concept search ("authentication middleware", "rate limiting logic")
- Debugging -- finding error handlers, exception flows, logging related to a symptom
- Discovering how a feature is implemented when you only know the domain concept

## When NOT to Use

- Finding literal string patterns (use grep)
- Exhaustive enumeration ("find all usages of FooClass") (use grep)
- Searching file names or paths (use Glob)
- Reading a file you already know the path to (use Read)

## Usage

Call the `search` MCP tool:

```
search(query="pharmacy API error handling")
search(query="user authentication flow", limit=10)
search(query="database migration logic", filters={"language": "python"})
search(query="React form validation", intent="code")
search(query="why does checkout fail on expired tokens", intent="debug")
```

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `query` | required | Natural language search query |
| `limit` | 5 | Max results to return |
| `detail` | "compact" | "compact" for snippets, "full" for complete source |
| `intent` | auto-detected | "code", "docs", "debug", "location", "enumeration" |
| `filters` | none | Filter by "language", "chunk_type", "app_name", "layer", "is_test" |
| `active_file` | none | Currently open file path for proximity boosting |
| `mode` | "semantic" | "semantic", "keyword", or "exhaustive" |

## Reading Results

Results are compact by default -- each result contains:

- `file_path`, `line_start`, `line_end` -- location in the codebase
- `snippet` -- signature + docstring preview (first 5 lines)
- `score` -- relevance score (higher is better)
- `chunk_type` -- "function", "class", "module", etc.

To see full source for a promising result, use the Read tool:

```
Read file_path, offset=line_start, limit=(line_end - line_start + 1)
```

## Query Tips

- Use natural language: "how does the app send email notifications" works better than "email send"
- Describe behavior, not implementation: "validates user input before saving" over "if request.data"
- Include domain context: "pharmacy prescription refill" not just "refill"
- For debugging, describe the symptom: "timeout when calling external payment API"
