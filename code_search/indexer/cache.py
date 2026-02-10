"""SQLite caching for embeddings and chunk state."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from code_search.indexer.relationships import Relationship

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

CREATE TABLE IF NOT EXISTS description_cache (
    content_hash TEXT NOT NULL,
    provider_model TEXT NOT NULL,
    description TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (content_hash, provider_model)
);

CREATE INDEX IF NOT EXISTS idx_description_cache_model
ON description_cache(provider_model);
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

CREATE TABLE IF NOT EXISTS code_relationships (
    source_entity TEXT NOT NULL,
    relationship TEXT NOT NULL,
    target_entity TEXT NOT NULL,
    file_path TEXT NOT NULL,
    confidence TEXT DEFAULT 'static',
    PRIMARY KEY (source_entity, relationship, target_entity)
);

CREATE INDEX IF NOT EXISTS idx_rel_source ON code_relationships(source_entity);
CREATE INDEX IF NOT EXISTS idx_rel_target ON code_relationships(target_entity);
CREATE INDEX IF NOT EXISTS idx_rel_file ON code_relationships(file_path);
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

    def get_description(self, content_hash: str, model: str) -> str | None:
        """Get cached NL description or None if not found."""
        with self._get_cache_conn() as conn:
            row = conn.execute(
                "SELECT description FROM description_cache "
                "WHERE content_hash = ? AND provider_model = ?",
                (content_hash, model),
            ).fetchone()
            return row["description"] if row else None

    def set_description(
        self,
        content_hash: str,
        model: str,
        description: str,
    ) -> None:
        """Cache an NL description."""
        with self._get_cache_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO description_cache "
                "(content_hash, provider_model, description) "
                "VALUES (?, ?, ?)",
                (content_hash, model, description),
            )

    def get_last_indexed_commit(self, collection_name: str) -> str | None:
        """Get the last indexed commit hash for a collection."""
        with self._get_state_conn() as conn:
            row = conn.execute(
                "SELECT last_commit FROM index_state WHERE collection_name = ?",
                (collection_name,),
            ).fetchone()
            return row[0] if row else None

    def set_last_indexed_commit(self, collection_name: str, commit_hash: str) -> None:
        """Set the last indexed commit hash for a collection."""
        with self._get_state_conn() as conn:
            conn.execute(
                """INSERT INTO index_state (collection_name, last_commit, last_indexed_at)
                VALUES (?, ?, datetime('now'))
                ON CONFLICT(collection_name) DO UPDATE SET
                    last_commit = excluded.last_commit,
                    last_indexed_at = excluded.last_indexed_at""",
                (collection_name, commit_hash),
            )

    def store_relationships(self, relationships: list[Relationship]) -> None:
        """Store relationships, upserting on conflict."""
        with self._get_state_conn() as conn:
            conn.executemany(
                """INSERT OR REPLACE INTO code_relationships
                   (source_entity, relationship, target_entity, file_path, confidence)
                   VALUES (?, ?, ?, ?, ?)""",
                [
                    (r.source_entity, r.relationship, r.target_entity, r.file_path, r.confidence)
                    for r in relationships
                ],
            )

    def get_relationships(
        self,
        entity: str,
        *,
        direction: str = "both",
        relationship_types: list[str] | None = None,
    ) -> list[Relationship]:
        """Get relationships for an entity.

        Args:
            entity: Entity identifier (e.g., "app/main.py::Foo")
            direction: "inbound", "outbound", or "both"
            relationship_types: Optional filter by relationship type
        """
        from code_search.indexer.relationships import Relationship as _Relationship

        results: list[_Relationship] = []
        with self._get_state_conn() as conn:
            if direction in ("outbound", "both"):
                query = (
                    "SELECT source_entity, relationship, target_entity, file_path, confidence "
                    "FROM code_relationships WHERE source_entity = ?"
                )
                params: list[str] = [entity]
                if relationship_types:
                    placeholders = ",".join("?" * len(relationship_types))
                    query += f" AND relationship IN ({placeholders})"
                    params.extend(relationship_types)
                for row in conn.execute(query, params):
                    results.append(
                        _Relationship(
                            source_entity=row[0],
                            relationship=row[1],
                            target_entity=row[2],
                            file_path=row[3],
                            confidence=row[4],
                        )
                    )

            if direction in ("inbound", "both"):
                query = (
                    "SELECT source_entity, relationship, target_entity, file_path, confidence "
                    "FROM code_relationships WHERE target_entity = ?"
                )
                params = [entity]
                if relationship_types:
                    placeholders = ",".join("?" * len(relationship_types))
                    query += f" AND relationship IN ({placeholders})"
                    params.extend(relationship_types)
                for row in conn.execute(query, params):
                    results.append(
                        _Relationship(
                            source_entity=row[0],
                            relationship=row[1],
                            target_entity=row[2],
                            file_path=row[3],
                            confidence=row[4],
                        )
                    )

        return results

    def delete_relationships_by_file(self, file_path: str) -> None:
        """Delete all relationships originating from a file."""
        with self._get_state_conn() as conn:
            conn.execute(
                "DELETE FROM code_relationships WHERE file_path = ?",
                (file_path,),
            )

    @staticmethod
    def _escape_like(value: str) -> str:
        """Escape LIKE metacharacters so ``_`` and ``%`` match literally."""
        return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    def resolve_entity(self, entity: str) -> str:
        """Resolve a user-provided entity identifier to a stored entity.

        Supports exact match, suffix match (for relative paths), and
        symbol-only match (just class/function name without file path).

        Resolution strategy:
          1. Exact match against source_entity or target_entity.
          2. Suffix match — entities whose source_entity or target_entity
             ends with the provided string (e.g., relative path like
             ``backend/care/models.py::Prescription``).
          3. Symbol-only match — when the entity has no ``::`` separator,
             match against the symbol portion after the last ``::`` in
             stored entities.

        When multiple candidates exist, source_entity matches are preferred.

        Returns the resolved entity string, or the original if no match is found.
        """
        safe = self._escape_like(entity)

        with self._get_state_conn() as conn:
            # 1. Exact match on source_entity
            row = conn.execute(
                "SELECT source_entity FROM code_relationships "
                "WHERE source_entity = ? LIMIT 1",
                (entity,),
            ).fetchone()
            if row:
                return row[0]

            # Exact match on target_entity
            row = conn.execute(
                "SELECT target_entity FROM code_relationships "
                "WHERE target_entity = ? LIMIT 1",
                (entity,),
            ).fetchone()
            if row:
                return row[0]

            # 2. Suffix match — source_entity first, then target_entity
            suffix_pattern = f"%{safe}"
            row = conn.execute(
                "SELECT source_entity FROM code_relationships "
                "WHERE source_entity LIKE ? ESCAPE '\\' LIMIT 1",
                (suffix_pattern,),
            ).fetchone()
            if row:
                return row[0]

            row = conn.execute(
                "SELECT target_entity FROM code_relationships "
                "WHERE target_entity LIKE ? ESCAPE '\\' LIMIT 1",
                (suffix_pattern,),
            ).fetchone()
            if row:
                return row[0]

            # 3. Symbol-only match (no :: in the query) — match the trailing
            #    ``::symbol`` portion of stored entities.
            if "::" not in entity:
                symbol_pattern = f"%::{safe}"
                row = conn.execute(
                    "SELECT source_entity FROM code_relationships "
                    "WHERE source_entity LIKE ? ESCAPE '\\' LIMIT 1",
                    (symbol_pattern,),
                ).fetchone()
                if row:
                    return row[0]

                row = conn.execute(
                    "SELECT target_entity FROM code_relationships "
                    "WHERE target_entity LIKE ? ESCAPE '\\' LIMIT 1",
                    (symbol_pattern,),
                ).fetchone()
                if row:
                    return row[0]

        return entity

    def traverse_relationships(
        self,
        entity: str,
        *,
        direction: str = "both",
        max_depth: int = 2,
        relationship_types: list[str] | None = None,
    ) -> list[dict[str, object]]:
        """BFS traversal of the relationship graph.

        Returns list of dicts with: source_entity, relationship, target_entity,
        confidence, depth.
        """
        from collections import deque

        visited: set[str] = {entity}
        queue: deque[tuple[str, int]] = deque([(entity, 0)])
        results: list[dict[str, object]] = []
        seen_edges: set[tuple[str, str, str]] = set()

        while queue:
            current, depth = queue.popleft()
            if depth >= max_depth:
                continue

            neighbors = self.get_relationships(
                current, direction=direction, relationship_types=relationship_types
            )

            for rel in neighbors:
                edge_key = (rel.source_entity, rel.relationship, rel.target_entity)
                if edge_key in seen_edges:
                    continue
                seen_edges.add(edge_key)

                results.append(
                    {
                        "source_entity": rel.source_entity,
                        "relationship": rel.relationship,
                        "target_entity": rel.target_entity,
                        "confidence": rel.confidence,
                        "depth": depth + 1,
                    }
                )

                # Determine the next entity to follow
                if direction != "inbound" and rel.source_entity == current:
                    next_entity = rel.target_entity
                elif direction != "outbound" and rel.target_entity == current:
                    next_entity = rel.source_entity
                else:
                    continue

                if next_entity not in visited:
                    visited.add(next_entity)
                    queue.append((next_entity, depth + 1))

        return results
