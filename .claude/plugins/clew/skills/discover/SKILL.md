# Guided Discovery

Find code related to a concept, feature, or behavior using a structured search-read-trace-explain workflow.

## When to Use

- You need to find code related to a concept but don't know where it lives
- You're exploring how a feature is implemented across multiple files
- You want to understand a subsystem and its dependencies

## When NOT to Use

- You know the exact file and line (just use Read)
- You need to find a literal string pattern (use grep)
- You need exhaustive enumeration of all usages (use grep)

## Workflow

### Step 1: Search

Start with a natural language query describing what you're looking for.

```
search(query="prescription refill validation logic")
```

Review the results. Each result has `file_path`, `line_start`, `line_end`, and a `snippet` preview.

### Step 2: Read

For the most relevant results, read the full source to understand the implementation.

```
Read file_path=result.file_path, offset=result.line_start, limit=(result.line_end - result.line_start + 20)
```

Read a bit beyond `line_end` to capture surrounding context (error handling, related functions).

### Step 3: Trace

For key entities found in Step 2, trace their relationships to understand the broader context.

```
trace(entity="app/models.py::Prescription.validate_refill", direction="inbound")
```

This reveals who calls this code, what depends on it, and where it fits in the architecture.

### Step 4: Explain (optional)

If the code is complex or unfamiliar, get a synthesized explanation.

```
explain(file_path="app/models.py", symbol="Prescription.validate_refill")
```

## Example: Finding Authentication Logic

1. `search(query="user authentication and session management")` -- find entry points
2. Read the top 2-3 results to identify the auth middleware and session handler
3. `trace(entity="auth/middleware.py::AuthMiddleware", direction="outbound")` -- see what auth depends on
4. `trace(entity="auth/middleware.py::AuthMiddleware", direction="inbound")` -- see what uses auth
5. Read the key dependencies (token validator, session store, user model)

## Tips

- If the first search doesn't find what you need, rephrase using different vocabulary
- Use `intent="debug"` when searching for error handling or failure modes
- Use filters to narrow results: `filters={"language": "python"}` or `filters={"layer": "api"}`
- After tracing, follow up with Read on the most interesting related entities
