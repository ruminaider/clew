# Codebase Onboarding

Learn an unfamiliar codebase by mapping its structure, entry points, domain model, and key subsystems.

## When to Use

- First time working with a codebase
- Switching to a project you haven't touched in a while
- Need to understand the high-level architecture before making changes

## When NOT to Use

- You already know the codebase and just need to find specific code (use /clew:search)
- You need to debug a specific issue (use the debug skill)

## Workflow

### Step 1: Check Index Health

Verify the index is available and current before starting.

```
index_status(action="status", project_root="/path/to/project")
```

If `is_stale` is true or `indexed` is false, trigger reindexing first:

```
index_status(action="trigger", project_root="/path/to/project")
```

### Step 2: Find Entry Points

Search for the main entry points -- where the application starts, where requests come in.

```
search(query="application entry point main startup", limit=10)
search(query="API route definitions endpoints", limit=10)
search(query="CLI command definitions", limit=10)
```

Read the top results to understand the application's public interface.

### Step 3: Map the Domain Model

Search for the core data models and business logic.

```
search(query="core data models and entities", limit=10)
search(query="business logic validation rules", limit=10)
```

For key models, trace their relationships outbound to see what they depend on:

```
trace(entity="app/models.py::User", direction="outbound", max_depth=2)
trace(entity="app/models.py::Order", direction="both")
```

### Step 4: Identify Key Subsystems

Search for cross-cutting concerns and infrastructure.

```
search(query="database connection and query execution")
search(query="authentication and authorization")
search(query="error handling and logging")
search(query="external API integrations")
```

### Step 5: Understand Testing Structure

```
search(query="test fixtures and setup", filters={"is_test": "true"})
```

Trace from a model to see its test coverage:

```
trace(entity="app/models.py::Order", relationship_types=["tests"])
```

## Example: Onboarding to a Django Project

1. `index_status(action="status")` -- verify index is ready
2. `search(query="URL routing and view configuration")` -- find urls.py and views
3. `search(query="database models")` -- find models.py files
4. `trace(entity="orders/models.py::Order", direction="both", max_depth=2)` -- map Order relationships
5. `search(query="middleware pipeline request processing")` -- understand the request lifecycle
6. `search(query="celery tasks background jobs")` -- find async processing
7. Read the key files identified in steps 2-6

## Tips

- Start broad, then narrow. The first pass is about mapping, not understanding every line.
- Pay attention to the `layer` metadata in results (api, model, service, util) to understand architecture.
- Use trace with `max_depth=2` to see immediate dependencies without information overload.
- After onboarding, make notes about key files and entities for future reference.
