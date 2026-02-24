# /clew:index

Trigger reindexing of the codebase. Updates the search index to reflect code changes.

## When to Use

- After significant code changes (new files, refactors, renamed modules)
- When /clew:status shows the index is stale
- When search results seem outdated or missing recently added code
- On initial setup of a project

## When NOT to Use

- For routine searches -- the index updates incrementally
- To check index health (use /clew:status first)

## Usage

Call the `index_status` MCP tool with action "trigger":

```
index_status(action="trigger", project_root="/path/to/project")
```

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `action` | -- | Must be "trigger" |
| `project_root` | required | Absolute path to the project root directory |

## Reading Results

The response contains:

- `triggered` -- confirmation that indexing started
- `files_processed` -- number of files indexed
- `chunks_created` -- number of code chunks created
- `files_skipped` -- number of files skipped (binary, too large, etc.)
- `errors` -- list of any errors encountered

## Notes

- Indexing is incremental by default (only changed files are reprocessed)
- For a full reindex from scratch, use the CLI: `clew index --full`
- The MCP tool does not support `--full` mode -- use the CLI for that
- Large codebases may take a few minutes on first index
