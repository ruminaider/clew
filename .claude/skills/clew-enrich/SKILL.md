# /clew-enrich

Enrich indexed code chunks with LLM-generated descriptions and keywords to improve semantic search quality. Auto-detects codebase size and chooses single-agent or parallel worker orchestration.

## Three Enrichment Paths

Clew supports three ways to enrich code chunks:

1. **Inline enrichment (CLI)** — Configure `enrichment_provider` in `.clew.yaml` and run `clew index .`. Enrichment happens automatically during indexing. Supports Anthropic API, any OpenAI-compatible API, and local Ollama.

2. **This skill (`/clew-enrich`)** — Uses your Claude Code subscription as the LLM. No API keys needed. Best for the most capable model or when you lack external API keys. Auto-parallelizes for large codebases.

3. **`clew reembed`** — Re-embeds chunks that already have enrichment data in cache. Used after skill-based enrichment or after changing enrichment models.

## Step 1: Inventory

Always run this first. Save the script to `/tmp/clew-enrich-inventory.py` and run it.

```python
import sqlite3, json, os, subprocess

def get_cache_dir():
    env = os.environ.get("CLEW_CACHE_DIR")
    if env:
        return env
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return os.path.join(result.stdout.strip(), ".clew")
    except Exception:
        pass
    return ".clew"

cache_dir = get_cache_dir()
db_path = os.path.join(cache_dir, "cache.db")

if not os.path.exists(db_path):
    print(json.dumps({"error": "cache.db not found. Run 'clew index .' first.", "cache_dir": cache_dir}))
    raise SystemExit(1)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

# Count all chunk IDs from chunk_cache
rows = conn.execute("SELECT file_path, chunk_ids FROM chunk_cache").fetchall()
all_chunk_ids = []
for row in rows:
    for cid in json.loads(row["chunk_ids"]):
        all_chunk_ids.append(cid)

# Count already enriched
enriched_ids = set(
    r[0] for r in conn.execute("SELECT chunk_id FROM enrichment_cache").fetchall()
)

# Count chunks with cached content
content_ids = set(
    r[0] for r in conn.execute("SELECT chunk_id FROM chunk_content_cache").fetchall()
)

# Unenriched = has content + not enriched + not file_summary
unenriched = []
no_content_count = 0
for cid in all_chunk_ids:
    if cid in enriched_ids:
        continue
    parts = cid.split("::")
    entity_type = parts[1] if len(parts) >= 2 else "unknown"
    if entity_type == "file_summary":
        continue
    if cid not in content_ids:
        no_content_count += 1
        continue
    unenriched.append(cid)

n = len(unenriched)
if n == 0:
    strategy, worker_count = "done", 0
elif n < 200:
    strategy, worker_count = "single", 1
elif n < 1000:
    strategy, worker_count = "parallel", 3
elif n < 5000:
    strategy, worker_count = "parallel", 4
else:
    strategy, worker_count = "parallel", 5

conn.close()
print(json.dumps({
    "cache_dir": cache_dir,
    "total_chunks": len(all_chunk_ids),
    "enriched": len(enriched_ids),
    "unenriched": n,
    "no_content": no_content_count,
    "strategy": strategy,
    "worker_count": worker_count,
}))
```

Report inventory results to the user:
- Total chunks, already enriched, unenriched, recommended strategy
- If `no_content` is high, suggest `clew index . --full` to populate `chunk_content_cache`
- If `strategy` is `"done"`, ask if user wants `clew reembed .` or finish

## Step 2: Route

Based on inventory output:
- **`"done"`** — All chunks enriched. Offer `clew reembed .` or finish.
- **`"single"`** — Go to **Single-Agent Path** (< 200 unenriched chunks).
- **`"parallel"`** — Go to **Parallel Path** (>= 200 unenriched chunks).

---

## Single-Agent Path

For < 200 unenriched chunks. Process everything inline.

### Step 3a: Load a Batch

Save this script to `/tmp/clew-enrich-load.py` and run it with: `python3 /tmp/clew-enrich-load.py <cache_dir> <offset>`

The script loads 30 unenriched chunks starting at `offset`, including their source content from `chunk_content_cache` and relationship context from `state.db`.

```python
import sqlite3, json, os, sys

LANGUAGE_MAP = {
    "py": "python", "js": "javascript", "ts": "typescript", "tsx": "typescript",
    "jsx": "javascript", "rb": "ruby", "rs": "rust", "go": "go", "java": "java",
    "kt": "kotlin", "swift": "swift", "c": "c", "cpp": "cpp", "cs": "csharp",
    "php": "php", "scala": "scala", "sh": "bash", "sql": "sql",
}
LAYER_MAP = {
    "models.py": "model", "views.py": "view", "viewsets.py": "view",
    "serializers.py": "serializer", "tasks.py": "task", "service.py": "service",
    "services.py": "service", "admin.py": "admin", "forms.py": "form",
    "urls.py": "routing", "middleware.py": "middleware", "signals.py": "signal",
}
BATCH_SIZE = 30

cache_dir = sys.argv[1]
offset = int(sys.argv[2]) if len(sys.argv) > 2 else 0

conn = sqlite3.connect(os.path.join(cache_dir, "cache.db"))
conn.row_factory = sqlite3.Row

# Build unenriched list
rows = conn.execute("SELECT file_path, chunk_ids FROM chunk_cache").fetchall()
all_chunks = []
for row in rows:
    fp = row["file_path"]
    for cid in json.loads(row["chunk_ids"]):
        parts = cid.split("::")
        et = parts[1] if len(parts) >= 2 else "unknown"
        if et == "file_summary":
            continue
        all_chunks.append({
            "chunk_id": cid, "file_path": fp, "entity_type": et,
            "qualified_name": parts[2] if len(parts) >= 3 else "",
        })

enriched = set(r[0] for r in conn.execute("SELECT chunk_id FROM enrichment_cache").fetchall())
content_ids = set(r[0] for r in conn.execute("SELECT chunk_id FROM chunk_content_cache").fetchall())
unenriched = [c for c in all_chunks if c["chunk_id"] not in enriched and c["chunk_id"] in content_ids]

# Load relationships from state.db
state_path = os.path.join(cache_dir, "state.db")
rels = {}
if os.path.exists(state_path):
    sconn = sqlite3.connect(state_path)
    sconn.row_factory = sqlite3.Row
    for r in sconn.execute("SELECT source_entity, relationship, target_entity FROM code_relationships").fetchall():
        src, rel_type, tgt = r["source_entity"], r["relationship"], r["target_entity"]
        tgt_s = tgt.split("::")[-1] if "::" in tgt else tgt
        src_s = src.split("::")[-1] if "::" in src else src
        rels.setdefault(src, {"callers": [], "callees": [], "imports": []})
        rels.setdefault(tgt, {"callers": [], "callees": [], "imports": []})
        if rel_type == "calls":
            rels[src]["callees"].append(tgt_s)
            rels[tgt]["callers"].append(src_s)
        elif rel_type == "imports":
            rels[src]["imports"].append(tgt_s)
    sconn.close()

# Get batch
batch = unenriched[offset:offset + BATCH_SIZE]
results = []
for chunk in batch:
    cid = chunk["chunk_id"]
    row = conn.execute("SELECT content FROM chunk_content_cache WHERE chunk_id = ?", (cid,)).fetchone()
    if not row or not row["content"]:
        continue
    fp = chunk["file_path"]
    ext = fp.rsplit(".", 1)[-1].lower() if "." in fp else ""
    lang = LANGUAGE_MAP.get(ext, "unknown")
    fname = fp.rsplit("/", 1)[-1] if "/" in fp else fp
    layer = "test" if ("test" in fp.lower()) else LAYER_MAP.get(fname, "component" if ext in ("tsx", "jsx") else "other")
    app = fp.rsplit("/", 2)[-2] if fp.count("/") >= 1 else ""

    entity_key = f"{fp}::{chunk['qualified_name']}" if chunk["qualified_name"] else fp
    r = rels.get(entity_key, {"callers": [], "callees": [], "imports": []})

    content = row["content"]
    if len(content) > 8000:
        content = content[:8000] + "\n... (truncated)"

    results.append({
        "chunk_id": cid, "file_path": fp, "entity_type": chunk["entity_type"],
        "qualified_name": chunk["qualified_name"], "language": lang,
        "layer": layer, "app_name": app, "content": content,
        "callers": ", ".join(r["callers"][:5]) or "(none)",
        "callees": ", ".join(r["callees"][:5]) or "(none)",
        "imports": ", ".join(r["imports"][:5]) or "(none)",
    })

conn.close()
print(json.dumps({
    "total_unenriched": len(unenriched),
    "offset": offset,
    "batch_size": len(results),
    "has_more": offset + BATCH_SIZE < len(unenriched),
    "next_offset": offset + BATCH_SIZE,
    "chunks": results,
}))
```

### Step 4a: Generate and Save Enrichments

For each chunk in the batch output, generate a description and keywords (see **Enrichment Format** below for the exact format and quality guidelines).

After generating enrichments for the batch, save them to SQLite. Write a Python script that embeds the enrichments as data and runs it:

```python
import sqlite3, time

cache_dir = "CACHE_DIR_HERE"
enrichments = [
    # Fill in with generated enrichments:
    # ("chunk_id", "description text", "keyword1 keyword2 ..."),
]

conn = sqlite3.connect(f"{cache_dir}/cache.db")
now = time.time()
for chunk_id, description, keywords in enrichments:
    conn.execute(
        "INSERT OR REPLACE INTO enrichment_cache "
        "(chunk_id, description, keywords, enriched_at) VALUES (?, ?, ?, ?)",
        (chunk_id, description, keywords, now),
    )
conn.commit()
conn.close()
print(f"Saved {len(enrichments)} enrichments")
```

### Step 4a (loop): Repeat

Run the load script again with `next_offset` from the previous output. Continue until `has_more` is `false`.

### Step 5a: Re-embed

```bash
clew reembed .
```

Report completion: total chunks enriched.

---

## Parallel Path

For >= 200 unenriched chunks. Spawns a team of parallel workers.

### Step 3b: Partition Chunks

Save to `/tmp/clew-enrich-partition.py` and run: `python3 /tmp/clew-enrich-partition.py <cache_dir> <worker_count>`

Creates balanced partition files with directory locality. Large directories are split across workers to avoid imbalance.

```python
import sqlite3, json, os, sys
from collections import defaultdict

cache_dir = sys.argv[1]
worker_count = int(sys.argv[2])

conn = sqlite3.connect(os.path.join(cache_dir, "cache.db"))
conn.row_factory = sqlite3.Row

rows = conn.execute("SELECT file_path, chunk_ids FROM chunk_cache").fetchall()
all_chunks = []
for row in rows:
    fp = row["file_path"]
    for cid in json.loads(row["chunk_ids"]):
        parts = cid.split("::")
        et = parts[1] if len(parts) >= 2 else "unknown"
        if et == "file_summary":
            continue
        all_chunks.append({
            "chunk_id": cid, "file_path": fp, "entity_type": et,
            "qualified_name": parts[2] if len(parts) >= 3 else "",
        })

enriched = set(r[0] for r in conn.execute("SELECT chunk_id FROM enrichment_cache").fetchall())
content_ids = set(r[0] for r in conn.execute("SELECT chunk_id FROM chunk_content_cache").fetchall())
unenriched = [c for c in all_chunks if c["chunk_id"] not in enriched and c["chunk_id"] in content_ids]
conn.close()

# Group by directory
dir_groups = defaultdict(list)
for chunk in unenriched:
    d = os.path.dirname(chunk["file_path"]) or "."
    dir_groups[d].append(chunk)

# Split oversized directories into sub-groups for better balance
target_size = max(len(unenriched) // worker_count, 1)
units = []  # (label, chunk_list) tuples for bin-packing
for dir_name, chunks in dir_groups.items():
    if len(chunks) <= target_size:
        units.append((dir_name, chunks))
    else:
        # Split large directory into target_size sub-groups
        for j in range(0, len(chunks), target_size):
            units.append((f"{dir_name}[{j}]", chunks[j:j + target_size]))

# Sort units by chunk count descending (better bin-packing)
units.sort(key=lambda x: -len(x[1]))

# Greedy bin-packing: assign each unit to the smallest bin
bins = [[] for _ in range(worker_count)]
bin_sizes = [0] * worker_count
for label, chunks in units:
    smallest = min(range(worker_count), key=lambda i: bin_sizes[i])
    bins[smallest].extend(chunks)
    bin_sizes[smallest] += len(chunks)

# Write partition files
for i, bin_chunks in enumerate(bins):
    path = f"/tmp/clew-enrich-partition-{i}.json"
    with open(path, "w") as f:
        json.dump({"worker_id": i, "chunk_count": len(bin_chunks), "chunks": bin_chunks}, f)

print(json.dumps({
    "worker_count": worker_count,
    "sizes": bin_sizes,
    "partitions": [f"/tmp/clew-enrich-partition-{i}.json" for i in range(worker_count)],
}))
```

### Step 4b: Export Relationships

Save to `/tmp/clew-enrich-export-rels.py` and run: `python3 /tmp/clew-enrich-export-rels.py <cache_dir>`

Exports relationship data to a single JSON file that all workers read.

```python
import sqlite3, json, os, sys

cache_dir = sys.argv[1]
state_path = os.path.join(cache_dir, "state.db")
output_path = "/tmp/clew-enrich-relationships.json"

if not os.path.exists(state_path):
    with open(output_path, "w") as f:
        json.dump({}, f)
    print(f"No state.db, wrote empty relationships to {output_path}")
    sys.exit(0)

conn = sqlite3.connect(state_path)
conn.row_factory = sqlite3.Row
rels = {}
for r in conn.execute("SELECT source_entity, relationship, target_entity FROM code_relationships").fetchall():
    src, rel_type, tgt = r["source_entity"], r["relationship"], r["target_entity"]
    tgt_s = tgt.split("::")[-1] if "::" in tgt else tgt
    src_s = src.split("::")[-1] if "::" in src else src
    rels.setdefault(src, {"callers": [], "callees": [], "imports": []})
    rels.setdefault(tgt, {"callers": [], "callees": [], "imports": []})
    if rel_type == "calls":
        rels[src]["callees"].append(tgt_s)
        rels[tgt]["callers"].append(src_s)
    elif rel_type == "imports":
        rels[src]["imports"].append(tgt_s)
conn.close()

with open(output_path, "w") as f:
    json.dump(rels, f)
print(f"Exported relationships for {len(rels)} entities to {output_path}")
```

### Step 5b: Spawn Worker Team

1. **Create team:** Use `TeamCreate` with `team_name: "clew-enrich"`.

2. **Create tasks:** Use `TaskCreate` for each worker:
   - Subject: `"Enrich partition {i} ({chunk_count} chunks)"`
   - Description: brief summary of the worker's assignment

3. **Spawn workers:** Use the `Task` tool for each worker. Spawn **all workers in a single message** (parallel Task calls) for maximum concurrency:
   - `subagent_type: "general-purpose"`
   - `team_name: "clew-enrich"`
   - `name: "worker-{i}"`
   - `prompt:` Fill in the **Worker Instructions** template below, replacing these placeholders:
     - `{WORKER_ID}` → worker index (0, 1, 2, ...)
     - `{PARTITION_FILE}` → `/tmp/clew-enrich-partition-{i}.json`
     - `{OUTPUT_FILE}` → `/tmp/clew-enrich-output-{i}.json`
     - `{CHUNK_COUNT}` → number of chunks from the partition script's `sizes` array
     - `{CACHE_DIR}` → the `cache_dir` value from the inventory output
     - `{TASK_ID}` → the task ID from `TaskCreate` for this worker

### Step 6b: Monitor Workers

Workers mark their tasks complete via `TaskUpdate` when finished. The system automatically sends idle notifications.

Check `TaskList` to track progress. When all worker tasks show `completed`, proceed to merge.

If a worker encounters an error, note it and continue. Partial enrichment is fine — the skill is idempotent.

### Step 7b: Merge Worker Results

After all workers complete, run: `python3 /tmp/clew-enrich-merge.py <cache_dir> <worker_count>`

```python
import sqlite3, json, os, sys, time

cache_dir = sys.argv[1]
worker_count = int(sys.argv[2])

conn = sqlite3.connect(os.path.join(cache_dir, "cache.db"))
now = time.time()
total = 0
for i in range(worker_count):
    path = f"/tmp/clew-enrich-output-{i}.json"
    if not os.path.exists(path):
        print(f"Worker {i}: no output file (skipped or failed)")
        continue
    with open(path) as f:
        enrichments = json.load(f)
    for e in enrichments:
        conn.execute(
            "INSERT OR REPLACE INTO enrichment_cache "
            "(chunk_id, description, keywords, enriched_at) VALUES (?, ?, ?, ?)",
            (e["chunk_id"], e["description"], e["keywords"], now),
        )
    conn.commit()
    total += len(enrichments)
    print(f"Worker {i}: merged {len(enrichments)} enrichments")
conn.close()
print(f"Total merged: {total} enrichments")
```

### Step 8b: Re-embed + Cleanup

```bash
clew reembed .
```

Clean up temporary files:
```bash
rm -f /tmp/clew-enrich-partition-*.json /tmp/clew-enrich-output-*.json /tmp/clew-enrich-relationships.json /tmp/clew-enrich-inventory.py /tmp/clew-enrich-load.py /tmp/clew-enrich-partition.py /tmp/clew-enrich-export-rels.py /tmp/clew-enrich-merge.py
```

Shut down workers: Use `SendMessage` with `type: "shutdown_request"` for each worker. After all confirm shutdown, use `TeamDelete` to clean up.

Report completion: total enrichments merged, per-worker counts.

---

## Worker Instructions

Self-contained prompt template for parallel workers. Replace all `{PLACEHOLDERS}` before passing to the Task tool.

```
You are a clew enrichment worker. Generate descriptions and keywords for code chunks to improve semantic search quality.

## Assignment

- Worker ID: {WORKER_ID}
- Partition: {PARTITION_FILE} ({CHUNK_COUNT} chunks)
- Relationships: /tmp/clew-enrich-relationships.json
- Cache DB: {CACHE_DIR}/cache.db
- Output file: {OUTPUT_FILE}
- Task ID: {TASK_ID}

## Process

Repeat this loop until all chunks are processed:

### 1. Load sub-batch of 30 chunks

Write this script to /tmp/clew-enrich-worker-load.py and run:
python3 /tmp/clew-enrich-worker-load.py {PARTITION_FILE} OFFSET {CACHE_DIR}

(Replace OFFSET with current position — start at 0, increment by 30 each iteration)

```python
import sqlite3, json, os, sys

LANGUAGE_MAP = {
    "py": "python", "js": "javascript", "ts": "typescript", "tsx": "typescript",
    "jsx": "javascript", "rb": "ruby", "rs": "rust", "go": "go", "java": "java",
    "kt": "kotlin", "swift": "swift", "c": "c", "cpp": "cpp", "cs": "csharp",
    "php": "php", "sh": "bash", "sql": "sql",
}
LAYER_MAP = {
    "models.py": "model", "views.py": "view", "viewsets.py": "view",
    "serializers.py": "serializer", "tasks.py": "task", "service.py": "service",
    "services.py": "service", "admin.py": "admin", "forms.py": "form",
    "urls.py": "routing", "middleware.py": "middleware", "signals.py": "signal",
}

partition_file = sys.argv[1]
offset = int(sys.argv[2])
cache_dir = sys.argv[3]

with open(partition_file) as f:
    partition = json.load(f)

batch = partition["chunks"][offset:offset + 30]
if not batch:
    print(json.dumps({"done": True}))
    sys.exit(0)

with open("/tmp/clew-enrich-relationships.json") as f:
    rels = json.load(f)

conn = sqlite3.connect(os.path.join(cache_dir, "cache.db"))
results = []
for chunk in batch:
    cid = chunk["chunk_id"]
    row = conn.execute(
        "SELECT content FROM chunk_content_cache WHERE chunk_id = ?", (cid,)
    ).fetchone()
    if not row or not row[0]:
        continue
    fp = chunk["file_path"]
    ext = fp.rsplit(".", 1)[-1].lower() if "." in fp else ""
    lang = LANGUAGE_MAP.get(ext, "unknown")
    fname = fp.rsplit("/", 1)[-1] if "/" in fp else fp
    layer = "test" if "test" in fp.lower() else LAYER_MAP.get(
        fname, "component" if ext in ("tsx", "jsx") else "other"
    )
    app = fp.rsplit("/", 2)[-2] if fp.count("/") >= 1 else ""
    entity_key = (
        f"{fp}::{chunk['qualified_name']}" if chunk.get("qualified_name") else fp
    )
    r = rels.get(entity_key, {"callers": [], "callees": [], "imports": []})
    content = row[0]
    if len(content) > 8000:
        content = content[:8000] + "\n... (truncated)"
    results.append({
        "chunk_id": cid, "file_path": fp,
        "entity_type": chunk["entity_type"],
        "qualified_name": chunk.get("qualified_name", ""),
        "language": lang, "layer": layer, "app_name": app,
        "content": content,
        "callers": ", ".join(r["callers"][:5]) or "(none)",
        "callees": ", ".join(r["callees"][:5]) or "(none)",
        "imports": ", ".join(r["imports"][:5]) or "(none)",
    })
conn.close()
print(json.dumps({
    "done": False, "count": len(results),
    "next_offset": offset + 30, "chunks": results,
}))
```

### 2. Generate enrichments

For EACH chunk in the loaded batch, generate:

```
Description: <2-3 sentences: what the code does, why it exists, what domain concept it represents>
Keywords: <8-15 space-separated terms a developer might search for>
```

Use the chunk's metadata (entity_type, file_path, layer, app_name, callers, callees, imports) and its code content to produce high-quality enrichments.

Quality guidelines:
- Descriptions explain WHAT and WHY, not HOW
- Include domain-specific vocabulary, not just technical terms
- Keywords cover: name variations, domain concepts, related features, common search terms
- For tests, mention what is being tested and testing patterns
- For API endpoints, mention HTTP methods, URL patterns, purpose

### 3. Save enrichments to output file

Construct a Python script with the generated enrichments embedded as data and run it. The script reads the existing output file (if any), appends the new enrichments, and writes back:

```python
import json

enrichments = [
    # Fill with your generated enrichments:
    # {"chunk_id": "...", "description": "...", "keywords": "..."},
]
output_file = "{OUTPUT_FILE}"
try:
    with open(output_file) as f:
        existing = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    existing = []
existing.extend(enrichments)
with open(output_file, "w") as f:
    json.dump(existing, f)
print(f"Saved {len(enrichments)} enrichments (total: {len(existing)})")
```

### 4. Repeat

Increment offset by 30 and go back to step 1. Continue until the load script outputs `{"done": true}`.

### 5. Complete

After processing all chunks:

1. Mark your task complete: use TaskUpdate with taskId "{TASK_ID}" and status "completed"
2. Wait for shutdown signal from the team lead
```

---

## Enrichment Format

Output for each chunk must satisfy `parse_enrichment_response()` in `clew/clients/description.py`. Use exactly this format:

```
Description: <2-3 sentences>
Keywords: <8-15 space-separated terms>
```

**Description** — What the code does, why it exists, what domain concept it represents. Write as if for a search index. Be specific about the domain, not just technical mechanics.

**Keywords** — Space-separated terms a developer would search for. Include:
- Function/class name variations (camelCase, snake_case, abbreviations)
- Domain concepts (e.g., "authentication", "payment processing")
- Related features and patterns
- Common developer search terms

**Example:**

For `backend/ecomm/utils.py::function::EcommUtils._process_shopify_order_impl`:
```
Description: Processes incoming Shopify orders by validating order data, creating internal Order records, and triggering fulfillment workflows. This is the core order ingestion handler called by the Shopify webhook receiver.
Keywords: shopify order processing webhook fulfillment ecommerce cart purchase payment order_ingestion
```

## Notes

- **Idempotent:** Running `/clew-enrich` again skips already-enriched chunks. Safe to re-run after interruption.
- **Resume-friendly:** Partial enrichment is preserved. Re-running picks up where the previous run left off.
- **Shared cache:** The `enrichment_cache` is shared between all enrichment paths. Chunks enriched via this skill are reused by `clew index` (no redundant LLM calls).
- **Re-embed required:** After enrichment, `clew reembed .` updates the search index. The skill runs this automatically.
- **To re-enrich:** Clear the cache first: `sqlite3 {cache_dir}/cache.db "DELETE FROM enrichment_cache"`, then run `/clew-enrich`.
- **toplevel chunks:** Module-level code (`::toplevel::`) IS enriched — contains configuration, middleware, and orchestration logic.
- **file_summary chunks:** Skipped — these are synthetic summaries, not real code.
- **Content source:** All chunk content is read from `chunk_content_cache` (exact AST-extracted content), not from disk files. This avoids drift and chunk boundary issues.
