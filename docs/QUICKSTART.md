# Quickstart

## 30-Second Setup

```bash
pip3 install clewdex
docker run -d --name clew-qdrant -p 6333:6333 -v clew_qdrant_data:/qdrant/storage qdrant/qdrant:v1.16.1
export VOYAGE_API_KEY="your-key-here"   # Free at https://dash.voyageai.com/
clew index . --full
clew doctor                              # Verify everything works
```

Or run the setup script which handles all of the above interactively:

```bash
bash scripts/setup.sh
```

## Detailed Walkthrough

### 1. Install clew

```bash
pip3 install clewdex
```

Requires Python 3.10+. Verify with `python3 --version`.

### 2. Start Qdrant

clew uses Qdrant as its vector database. Start it with Docker:

```bash
docker run -d --name clew-qdrant -p 6333:6333 \
  -v clew_qdrant_data:/qdrant/storage qdrant/qdrant:v1.16.1
```

Verify it's running: `curl http://localhost:6333/` should return JSON with version info.

### 3. Get a Voyage AI API Key

clew uses Voyage AI's `voyage-code-3` model for code embeddings.

1. Go to https://dash.voyageai.com/
2. Sign up (free tier available)
3. Create an API key
4. Export it:

```bash
export VOYAGE_API_KEY="your-key-here"
```

### 4. Index Your Codebase

From your project root:

```bash
clew index . --full
```

This discovers source files, parses them into semantic chunks, generates embeddings, and stores them in Qdrant. A typical 10K-line project takes 30-60 seconds.

Subsequent runs use incremental indexing (only changed files):

```bash
clew index .
```

### 5. Verify Setup

```bash
clew doctor
```

Expected output:

```
 ✓ Qdrant ......... connected (localhost:6333)
 ✓ Voyage API ..... authenticated (voyage-code-3)
 ✓ Cache dir ...... writable (/path/to/.clew/)
 ✓ Index .......... current (0 commits behind, 1,247 chunks)
 ✓ MCP server ..... ready
```

## First Search

### Concept Discovery

Find code by describing what it does, not what it's named:

```bash
clew search "retry logic with exponential backoff"
```

### Debugging

Find where errors originate:

```bash
clew search "where database connection timeouts are handled"
```

### Structural Trace

Follow code relationships (imports, calls, inheritance):

```bash
clew trace "MyService" --direction outbound --depth 2
```

## MCP Integration with Claude Code

Add to your project's `.mcp.json`:

```json
{
  "mcpServers": {
    "clew": {
      "command": "clew",
      "args": ["serve"],
      "env": {
        "VOYAGE_API_KEY": "your-key-here",
        "QDRANT_URL": "http://localhost:6333"
      }
    }
  }
}
```

### Optional Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VOYAGE_API_KEY` | (required) | Voyage AI API key |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant server URL |
| `QDRANT_API_KEY` | (none) | Qdrant authentication key |
| `CLEW_CACHE_DIR` | `{git_root}/.clew/` | Override cache directory location |
| `ANTHROPIC_API_KEY` | (none) | For NL description generation |

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `Cannot connect to Qdrant at http://localhost:6333` | Qdrant not running | `docker start clew-qdrant` or re-run the docker command from step 2 |
| `Voyage API authentication failed` | Invalid or expired API key | Check `VOYAGE_API_KEY` at https://dash.voyageai.com/ |
| `No files found to index` | Wrong directory or all files ignored | Run from project root; check `.clewignore` |
| `Collection 'code' does not exist` | Index not built | Run `clew index . --full` |
| `Index is stale (N commits behind)` | Code changed since last index | Run `clew index .` for incremental update |
| `MCP server import error` | Missing dependencies | `pip3 install clewdex` to reinstall |
| `docker: command not found` | Docker not installed | Install Docker Desktop from https://docker.com |

Run `clew doctor` at any time to diagnose issues.
