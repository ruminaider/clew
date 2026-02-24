# /clew:status

Index health check. Shows Qdrant connection status, collection sizes, and index freshness.

## When to Use

- Before searching, to verify the index is available and not stale
- Diagnosing why search returns no results or unexpected results
- Checking whether reindexing is needed after code changes

## When NOT to Use

- Searching for code (use /clew:search)
- Triggering a reindex (use /clew:index)

## Usage

Call the `index_status` MCP tool with action "status":

```
index_status(action="status")
index_status(action="status", project_root="/path/to/project")
```

Pass `project_root` to enable staleness detection (checks if the index is behind the current git HEAD).

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `action` | "status" | Use "status" for health check |
| `project_root` | none | Project root for staleness detection |

## Reading Results

The response contains:

- `qdrant_healthy` -- whether Qdrant is reachable
- `collections` -- map of collection names to chunk counts (e.g., `{"code": 1523}`)
- `indexed` -- whether any collections exist
- `last_commit` -- the git commit hash when the index was last updated
- `is_stale` -- whether the index is behind HEAD (only with project_root)
- `commits_behind` -- how many commits behind (only with project_root)
- `has_uncommitted_changes` -- whether there are uncommitted file changes

If `qdrant_healthy` is false, start Qdrant: `docker compose up -d qdrant`

If `is_stale` is true, reindex with /clew:index.
