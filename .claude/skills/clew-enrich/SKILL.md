# /clew-enrich

Enrich indexed code chunks with LLM-generated descriptions and keywords to improve semantic search quality.

## Three Enrichment Paths

Clew supports three ways to enrich code chunks:

1. **Inline enrichment (CLI)** — Configure `enrichment_provider` in `.clew.yaml` and run `clew index .`. Enrichment happens automatically during indexing. Supports Anthropic API, any OpenAI-compatible API (OpenAI, OpenRouter, DeepSeek, Together, Groq), and local Ollama.

2. **This skill (`/clew-enrich`)** — Uses your Claude Code subscription as the LLM. No API keys needed. Best when you want the most capable model, human review of descriptions, or don't have external API keys.

3. **`clew reembed`** — Re-embeds chunks that already have enrichment data in cache. Used after skill-based enrichment or after changing enrichment models.

## When to Use This Skill

Use `/clew-enrich` when:
- You don't have API keys for Anthropic/OpenAI/Ollama
- You want human-in-the-loop review of generated descriptions
- You want to use the most capable model available (your Claude Code subscription model)
- You want to selectively enrich specific chunks

For automated enrichment during indexing, configure `enrichment_provider` in `.clew.yaml` instead.

## Prerequisites

- The project must already be indexed (`clew index [PROJECT_ROOT]`)
- The `.clew/` directory must exist in the project root (created by `clew index`)

## What It Does

1. Reads all chunk IDs from the SQLite cache (`cache.db`)
2. Identifies chunks that have NOT yet been enriched
3. For each unenriched chunk, reads the source code from disk
4. Generates a description (2-3 sentences) and keywords (8-15 terms) per chunk
5. Writes enrichment data back to the SQLite cache
6. Triggers `clew reembed` to re-embed all enriched chunks with the new content

## Step-by-Step Instructions

### Step 1: Locate the Cache Directory

The cache directory is at `{project_root}/.clew/`. The project root is typically the git root. If `CLEW_CACHE_DIR` is set, use that path instead.

```bash
# Find the git root
git rev-parse --show-toplevel
```

The cache database file is `{cache_dir}/cache.db`.

### Step 2: Read Unenriched Chunks

Run this Python script to get the list of unenriched chunk IDs and their file paths:

```python
import sqlite3
import json

cache_dir = "{PROJECT_ROOT}/.clew"  # Replace with actual path
conn = sqlite3.connect(f"{cache_dir}/cache.db")
conn.row_factory = sqlite3.Row

# Get all chunk_ids from chunk_cache
rows = conn.execute("SELECT file_path, chunk_ids FROM chunk_cache").fetchall()
all_chunks = []
for row in rows:
    file_path = row["file_path"]
    chunk_ids = json.loads(row["chunk_ids"])
    for cid in chunk_ids:
        all_chunks.append((cid, file_path))

# Get already-enriched chunk_ids
enriched = set(
    r[0] for r in conn.execute("SELECT chunk_id FROM enrichment_cache").fetchall()
)
conn.close()

# Filter to unenriched
unenriched = [(cid, fp) for cid, fp in all_chunks if cid not in enriched]
print(f"Total chunks: {len(all_chunks)}")
print(f"Already enriched: {len(enriched)}")
print(f"Unenriched: {len(unenriched)}")
```

### Step 3: Enrich Each Chunk

For each unenriched chunk, you need to:

1. **Parse the chunk_id** to extract entity info. The format is: `file_path::entity_type::qualified_name` (for named entities) or `file_path::toplevel::sha256hash` (for anonymous/toplevel chunks).

2. **Read the source file** from disk using the `file_path` from the chunk_id (the part before the first `::`).

3. **Generate description and keywords**. For each chunk, produce output in this exact format:
   ```
   Description: 2-3 sentences explaining what the code does, why it exists, and what domain concept it represents.
   Keywords: 8-15 space-separated terms a developer might search for when looking for this code.
   ```

   When generating descriptions and keywords, consider:
   - What does this code do at a high level?
   - What domain concepts does it relate to?
   - What would someone search for to find this code?
   - Include both technical terms and domain-specific vocabulary

4. **Write enrichment to cache** using this Python script (batch mode):

```python
import sqlite3
import time

cache_dir = "{PROJECT_ROOT}/.clew"  # Replace with actual path
conn = sqlite3.connect(f"{cache_dir}/cache.db")

enrichments = [
    # ("chunk_id", "description text", "keyword1 keyword2 keyword3 ..."),
]

for chunk_id, description, keywords in enrichments:
    conn.execute(
        "INSERT OR REPLACE INTO enrichment_cache "
        "(chunk_id, description, keywords, enriched_at) "
        "VALUES (?, ?, ?, ?)",
        (chunk_id, description, keywords, time.time()),
    )

conn.commit()
conn.close()
print(f"Wrote {len(enrichments)} enrichments to cache")
```

### Step 4: Process in Batches

Process chunks in batches of 20-50 to manage context window size:

1. Read a batch of source files using the Read tool
2. Generate descriptions and keywords for all chunks in the batch
3. Write the batch to SQLite
4. Repeat until all chunks are processed

Skip chunks where:
- The file no longer exists on disk
- The chunk_id contains `::file_summary::` (already synthetic)

Note: `::toplevel::` chunks (module-level code) SHOULD be enriched — they often contain important configuration, middleware, Django settings, and orchestration logic.

### Step 5: Re-embed

After all enrichments are written to the cache, run:

```bash
clew reembed {PROJECT_ROOT}
```

This reads the enrichment data from cache and re-embeds all enriched chunks with the full content (description + keywords + code) into Qdrant's named vectors.

## Enrichment Cache Schema

The enrichment data is stored in `{cache_dir}/cache.db` in the `enrichment_cache` table:

```sql
CREATE TABLE IF NOT EXISTS enrichment_cache (
    chunk_id TEXT PRIMARY KEY,
    description TEXT,
    keywords TEXT,
    enriched_at REAL
);
```

## Example Output

For a chunk with ID `backend/ecomm/utils.py::function::EcommUtils._process_shopify_order_impl`:

```
Description: Processes incoming Shopify orders by validating order data, creating internal Order records, and triggering fulfillment workflows. This is the core order ingestion handler called by the Shopify webhook receiver.
Keywords: shopify order processing webhook fulfillment ecommerce cart purchase payment order_ingestion
```

## Notes

- Enrichment is idempotent: running `/clew-enrich` again skips already-enriched chunks
- To re-enrich everything, delete the `enrichment_cache` table contents first: `DELETE FROM enrichment_cache` in `cache.db`
- The `clew reembed` step is required after skill-based enrichment; without it, the search index won't reflect the new descriptions
- If using inline CLI enrichment (`enrichment_provider` in `.clew.yaml`), re-embed is not needed — enrichment and embedding happen in a single pass during `clew index`
- The enrichment cache is shared between all paths — chunks enriched via this skill are reused by `clew index` (no redundant LLM calls)
