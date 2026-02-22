#!/usr/bin/env python3
"""Batch enrichment script: populate enrichment_cache with LLM descriptions+keywords.

Reads chunk content from chunk_content_cache, calls Anthropic API to generate
descriptions and keywords, writes results to enrichment_cache. Supports resume
(skips already-enriched chunks).

Usage:
    CLEW_CACHE_DIR=/path/to/project/.clew python3 scripts/enrich.py [--batch-size 50] [--concurrency 10]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sqlite3
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from clew.clients.description import AnthropicDescriptionProvider, parse_enrichment_response
from clew.indexer.metadata import classify_layer, detect_app_name

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

LANGUAGE_MAP = {
    "py": "python", "js": "javascript", "ts": "typescript", "tsx": "typescript",
    "jsx": "javascript", "rb": "ruby", "rs": "rust", "go": "go", "java": "java",
    "kt": "kotlin", "swift": "swift", "c": "c", "cpp": "cpp", "h": "c",
    "hpp": "cpp", "cs": "csharp", "php": "php", "scala": "scala", "html": "html",
    "css": "css", "scss": "scss", "yaml": "yaml", "yml": "yaml", "json": "json",
    "md": "markdown", "sql": "sql", "sh": "bash", "bash": "bash",
}


def detect_language(file_path: str) -> str:
    ext = file_path.rsplit(".", 1)[-1].lower() if "." in file_path else ""
    return LANGUAGE_MAP.get(ext, "unknown")


def get_cache_dir() -> Path:
    env_val = os.environ.get("CLEW_CACHE_DIR")
    if env_val:
        return Path(env_val)
    # Try git root
    import subprocess
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip()) / ".clew"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return Path(".clew")


def load_unenriched_chunks(cache_dir: Path) -> list[dict]:
    """Load all chunks that need enrichment."""
    db_path = cache_dir / "cache.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # Get all chunk_ids from chunk_cache
    rows = conn.execute("SELECT file_path, chunk_ids FROM chunk_cache").fetchall()
    all_chunks = []
    for row in rows:
        file_path = row["file_path"]
        chunk_ids = json.loads(row["chunk_ids"])
        for cid in chunk_ids:
            all_chunks.append({"chunk_id": cid, "file_path": file_path})

    # Get already-enriched
    enriched = set(
        r[0] for r in conn.execute("SELECT chunk_id FROM enrichment_cache").fetchall()
    )

    # Get chunk content from cache
    unenriched = []
    skipped_types = 0
    skipped_no_content = 0
    for chunk in all_chunks:
        cid = chunk["chunk_id"]
        if cid in enriched:
            continue
        # Skip toplevel and file_summary chunks
        parts = cid.split("::")
        entity_type = parts[1] if len(parts) >= 2 else "unknown"
        if entity_type in ("toplevel", "file_summary"):
            skipped_types += 1
            continue

        # Get cached content
        row = conn.execute(
            "SELECT content, line_start, line_end FROM chunk_content_cache WHERE chunk_id = ?",
            (cid,),
        ).fetchone()
        if not row or not row["content"]:
            skipped_no_content += 1
            continue

        chunk["content"] = row["content"]
        chunk["line_start"] = row["line_start"]
        chunk["line_end"] = row["line_end"]
        chunk["entity_type"] = entity_type
        chunk["qualified_name"] = parts[2] if len(parts) >= 3 else ""
        unenriched.append(chunk)

    conn.close()

    logger.info(
        "Found %d chunks to enrich (%d already enriched, %d skipped types, %d no content)",
        len(unenriched), len(enriched), skipped_types, skipped_no_content,
    )
    return unenriched


def load_relationships(cache_dir: Path) -> dict[str, dict[str, list[str]]]:
    """Load relationship data for all entities."""
    state_path = cache_dir / "state.db"
    if not state_path.exists():
        return {}

    conn = sqlite3.connect(str(state_path))
    conn.row_factory = sqlite3.Row

    rels: dict[str, dict[str, list[str]]] = {}
    rows = conn.execute(
        "SELECT source_entity, relationship, target_entity FROM code_relationships"
    ).fetchall()

    for row in rows:
        src = row["source_entity"]
        rel_type = row["relationship"]
        tgt = row["target_entity"]
        tgt_short = tgt.split("::")[-1] if "::" in tgt else tgt
        src_short = src.split("::")[-1] if "::" in src else src

        # Source's outbound
        if src not in rels:
            rels[src] = {"callers": [], "callees": [], "imports": []}
        if rel_type == "calls":
            rels[src]["callees"].append(tgt_short)
        elif rel_type == "imports":
            rels[src]["imports"].append(tgt_short)

        # Target's inbound
        if tgt not in rels:
            rels[tgt] = {"callers": [], "callees": [], "imports": []}
        if rel_type == "calls":
            rels[tgt]["callers"].append(src_short)

    conn.close()
    return rels


def get_entity_rels(
    chunk: dict, all_rels: dict[str, dict[str, list[str]]]
) -> tuple[str, str, str]:
    """Get callers, callees, imports strings for a chunk."""
    file_path = chunk["file_path"]
    qualified_name = chunk["qualified_name"]
    entity_key = f"{file_path}::{qualified_name}" if qualified_name else file_path

    r = all_rels.get(entity_key, {"callers": [], "callees": [], "imports": []})
    callers = ", ".join(r["callers"][:5]) or "(none)"
    callees = ", ".join(r["callees"][:5]) or "(none)"
    imports = ", ".join(r["imports"][:5]) or "(none)"
    return callers, callees, imports


async def enrich_batch(
    provider: AnthropicDescriptionProvider,
    chunks: list[dict],
    all_rels: dict[str, dict[str, list[str]]],
) -> list[tuple[str, str, str]]:
    """Enrich a batch of chunks concurrently. Returns [(chunk_id, desc, keywords), ...]."""

    async def _enrich_one(chunk: dict) -> tuple[str, str, str] | None:
        callers, callees, imports = get_entity_rels(chunk, all_rels)
        content = chunk["content"]
        # Truncate very long content to save tokens
        if len(content) > 8000:
            content = content[:8000] + "\n... (truncated)"

        result = await provider.generate_enrichment(
            code=content,
            language=detect_language(chunk["file_path"]),
            entity_type=chunk["entity_type"],
            name=chunk["qualified_name"],
            file_path=chunk["file_path"],
            layer=classify_layer(chunk["file_path"]),
            app_name=detect_app_name(chunk["file_path"]),
            callers=callers,
            callees=callees,
            imports=imports,
        )
        if result:
            desc, kw = result
            return (chunk["chunk_id"], desc, kw)
        return None

    tasks = [_enrich_one(c) for c in chunks]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    enrichments = []
    for r in results:
        if isinstance(r, tuple):
            enrichments.append(r)
        elif isinstance(r, Exception):
            logger.warning("Enrichment failed: %s", r)
    return enrichments


def save_enrichments(cache_dir: Path, enrichments: list[tuple[str, str, str]]) -> None:
    """Write enrichment results to SQLite."""
    db_path = cache_dir / "cache.db"
    conn = sqlite3.connect(str(db_path))
    now = time.time()
    for chunk_id, desc, kw in enrichments:
        conn.execute(
            "INSERT OR REPLACE INTO enrichment_cache "
            "(chunk_id, description, keywords, enriched_at) VALUES (?, ?, ?, ?)",
            (chunk_id, desc, kw, now),
        )
    conn.commit()
    conn.close()


async def main() -> None:
    parser = argparse.ArgumentParser(description="Batch enrich code chunks")
    parser.add_argument("--batch-size", type=int, default=50, help="Chunks per batch")
    parser.add_argument("--concurrency", type=int, default=10, help="Concurrent API calls")
    parser.add_argument("--model", default="claude-haiku-4-5-20251001", help="Anthropic model")
    parser.add_argument("--dry-run", action="store_true", help="Count chunks without enriching")
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key and not args.dry_run:
        logger.error("ANTHROPIC_API_KEY not set")
        sys.exit(1)

    cache_dir = get_cache_dir()
    logger.info("Cache dir: %s", cache_dir)

    # Load chunks to enrich
    chunks = load_unenriched_chunks(cache_dir)
    if not chunks:
        logger.info("Nothing to enrich!")
        return

    if args.dry_run:
        logger.info("Dry run: would enrich %d chunks", len(chunks))
        return

    # Load relationship data
    logger.info("Loading relationship data...")
    all_rels = load_relationships(cache_dir)
    logger.info("Loaded relationships for %d entities", len(all_rels))

    # Create provider
    provider = AnthropicDescriptionProvider(
        api_key=api_key,
        model=args.model,
        max_tokens=300,
        max_concurrent=args.concurrency,
    )

    # Process in batches
    total_enriched = 0
    total_failed = 0
    start_time = time.time()
    num_batches = (len(chunks) + args.batch_size - 1) // args.batch_size

    for i in range(0, len(chunks), args.batch_size):
        batch = chunks[i : i + args.batch_size]
        batch_num = i // args.batch_size + 1

        enrichments = await enrich_batch(provider, batch, all_rels)
        if enrichments:
            save_enrichments(cache_dir, enrichments)

        total_enriched += len(enrichments)
        total_failed += len(batch) - len(enrichments)

        elapsed = time.time() - start_time
        rate = total_enriched / elapsed if elapsed > 0 else 0
        eta = (len(chunks) - i - len(batch)) / rate if rate > 0 else 0

        logger.info(
            "Batch %d/%d: %d enriched, %d failed | Total: %d/%d (%.1f/s, ETA: %.0fs)",
            batch_num, num_batches, len(enrichments), len(batch) - len(enrichments),
            total_enriched, len(chunks), rate, eta,
        )

    elapsed = time.time() - start_time
    logger.info(
        "Done! %d enriched, %d failed in %.0fs (%.1f chunks/s)",
        total_enriched, total_failed, elapsed, total_enriched / elapsed if elapsed > 0 else 0,
    )


if __name__ == "__main__":
    asyncio.run(main())
