"""SQLite caching for embeddings and chunk state."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

CACHE_SCHEMA = """
CREATE TABLE IF NOT EXISTS embedding_cache (
    content_hash TEXT NOT NULL,
    embedding_model TEXT NOT NULL,
    embedding BLOB NOT NULL,
    token_count INTEGER NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (content_hash, embedding_model)
);

CREATE INDEX IF NOT EXISTS idx_embedding_cache_model
ON embedding_cache(embedding_model);

CREATE TABLE IF NOT EXISTS chunk_cache (
    file_path TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    chunk_count INTEGER NOT NULL,
    chunk_ids TEXT NOT NULL,
    updated_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (file_path)
);

CREATE INDEX IF NOT EXISTS idx_chunk_cache_hash
ON chunk_cache(file_hash);
"""

STATE_SCHEMA = """
CREATE TABLE IF NOT EXISTS index_state (
    collection_name TEXT PRIMARY KEY,
    last_commit TEXT,
    last_indexed_at TEXT,
    total_chunks INTEGER DEFAULT 0,
    total_files INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS failed_files (
    file_path TEXT PRIMARY KEY,
    error_type TEXT NOT NULL,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    last_attempt TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS checkpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    collection_name TEXT NOT NULL,
    batch_index INTEGER NOT NULL,
    files_processed TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS safety_state (
    collection_name TEXT PRIMARY KEY,
    chunk_count INTEGER DEFAULT 0,
    last_checked_at TEXT DEFAULT (datetime('now')),
    limit_breached BOOLEAN DEFAULT FALSE
);
"""


class CacheDB:
    """SQLite-based cache for embeddings and indexing state."""

    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._init_databases()

    def _init_databases(self) -> None:
        """Create tables if they don't exist."""
        with self._get_cache_conn() as conn:
            conn.executescript(CACHE_SCHEMA)
        with self._get_state_conn() as conn:
            conn.executescript(STATE_SCHEMA)

    @contextmanager
    def _get_cache_conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.cache_dir / "cache.db")
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    @contextmanager
    def _get_state_conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.cache_dir / "state.db")
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def get_embedding(self, content_hash: str, model: str) -> bytes | None:
        """Get cached embedding or None if not found."""
        with self._get_cache_conn() as conn:
            row = conn.execute(
                "SELECT embedding FROM embedding_cache "
                "WHERE content_hash = ? AND embedding_model = ?",
                (content_hash, model),
            ).fetchone()
            return row["embedding"] if row else None

    def set_embedding(
        self,
        content_hash: str,
        model: str,
        embedding: bytes,
        token_count: int,
    ) -> None:
        """Cache an embedding."""
        with self._get_cache_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO embedding_cache "
                "(content_hash, embedding_model, embedding, token_count) "
                "VALUES (?, ?, ?, ?)",
                (content_hash, model, embedding, token_count),
            )

    def get_file_hash(self, file_path: str) -> str | None:
        """Get cached file hash for change detection."""
        with self._get_cache_conn() as conn:
            row = conn.execute(
                "SELECT file_hash FROM chunk_cache WHERE file_path = ?",
                (file_path,),
            ).fetchone()
            return row["file_hash"] if row else None

    def get_file_chunk_ids(self, file_path: str) -> list[str]:
        """Get cached chunk IDs for a file."""
        with self._get_cache_conn() as conn:
            row = conn.execute(
                "SELECT chunk_ids FROM chunk_cache WHERE file_path = ?",
                (file_path,),
            ).fetchone()
            if row:
                return json.loads(row["chunk_ids"])  # type: ignore[no-any-return]
            return []

    def set_file_chunks(self, file_path: str, file_hash: str, chunk_ids: list[str]) -> None:
        """Cache file hash and chunk IDs."""
        with self._get_cache_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO chunk_cache "
                "(file_path, file_hash, chunk_count, chunk_ids) "
                "VALUES (?, ?, ?, ?)",
                (file_path, file_hash, len(chunk_ids), json.dumps(chunk_ids)),
            )
