"""SQLite caching for embeddings and chunk state."""

from __future__ import annotations

import json
import logging
import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from clew.indexer.relationships import Relationship

logger = logging.getLogger(__name__)

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

CREATE TABLE IF NOT EXISTS enrichment_cache (
    chunk_id TEXT PRIMARY KEY,
    description TEXT,
    keywords TEXT,
    enriched_at REAL
);
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

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);
"""

# Current schema version — increment when adding migrations
CURRENT_SCHEMA_VERSION = 3


def _migration_v1_to_v2(conn: sqlite3.Connection) -> None:
    """Add target_entity index for faster inbound lookups."""
    # idx_rel_target already exists in the CREATE TABLE schema, but this
    # migration ensures it exists for databases created before it was added.
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_rel_target_entity ON code_relationships(target_entity)"
    )


def _migration_v2_to_v3(conn: sqlite3.Connection) -> None:
    """Add enrichment_cache table for LLM-generated descriptions + keywords."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS enrichment_cache ("
        "    chunk_id TEXT PRIMARY KEY,"
        "    description TEXT,"
        "    keywords TEXT,"
        "    enriched_at REAL"
        ")"
    )


# Ordered list of migration functions: index = from_version
_MIGRATIONS: list[Callable[[sqlite3.Connection], None]] = [
    lambda _conn: None,  # v0→v1: initial schema (no-op, tables already created)
    _migration_v1_to_v2,  # v1→v2: add target_entity index
    _migration_v2_to_v3,  # v2→v3: add enrichment_cache table
]


class CacheDB:
    """SQLite-based cache for embeddings and indexing state."""

    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._init_databases()

    def _init_databases(self) -> None:
        """Create tables if they don't exist, then run pending migrations."""
        with self._get_cache_conn() as conn:
            conn.executescript(CACHE_SCHEMA)
        with self._get_state_conn() as conn:
            conn.executescript(STATE_SCHEMA)
            self._run_migrations(conn)

    @staticmethod
    def _run_migrations(conn: sqlite3.Connection) -> None:
        """Run any pending schema migrations."""
        row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
        current = row[0] if row[0] is not None else 0

        if current >= CURRENT_SCHEMA_VERSION:
            return

        for version in range(current, CURRENT_SCHEMA_VERSION):
            try:
                if version < len(_MIGRATIONS):
                    logger.info("Running schema migration v%d → v%d", version, version + 1)
                    _MIGRATIONS[version](conn)
                conn.execute(
                    "INSERT OR REPLACE INTO schema_version (version) VALUES (?)",
                    (version + 1,),
                )
            except Exception as e:
                from clew.exceptions import SchemaMigrationError

                raise SchemaMigrationError(version, version + 1, e) from e

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

    def clear_all_state(self, collection: str) -> None:
        """Clear all indexing state for a collection (for --full reindex).

        Clears: code_relationships, failed_files, checkpoints (filtered),
        index_state (filtered), safety_state (filtered), and chunk_cache.
        Preserves: embedding_cache, description_cache (content-addressed, reusable).
        """
        with self._get_state_conn() as conn:
            conn.execute("DELETE FROM code_relationships")
            conn.execute("DELETE FROM failed_files")
            conn.execute("DELETE FROM checkpoints WHERE collection_name = ?", (collection,))
            conn.execute("DELETE FROM index_state WHERE collection_name = ?", (collection,))
            conn.execute("DELETE FROM safety_state WHERE collection_name = ?", (collection,))
        with self._get_cache_conn() as conn:
            conn.execute("DELETE FROM chunk_cache")
            conn.execute("DELETE FROM enrichment_cache")
        logger.info("Cleared all indexing state for collection '%s'", collection)

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

    def get_all_relationship_pairs(self) -> list[tuple[str, str]]:
        """Return all (source_entity, target_entity) pairs from code_relationships."""
        with self._get_state_conn() as conn:
            rows = conn.execute(
                "SELECT source_entity, target_entity FROM code_relationships"
            ).fetchall()
            return [(row[0], row[1]) for row in rows]

    def get_enrichment(self, chunk_id: str) -> tuple[str, str] | None:
        """Return (description, keywords) for a chunk, or None."""
        with self._get_cache_conn() as conn:
            row = conn.execute(
                "SELECT description, keywords FROM enrichment_cache WHERE chunk_id = ?",
                (chunk_id,),
            ).fetchone()
            return (row["description"], row["keywords"]) if row else None

    def set_enrichment(self, chunk_id: str, description: str, keywords: str) -> None:
        """Store enrichment data for a chunk."""
        import time

        with self._get_cache_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO enrichment_cache "
                "(chunk_id, description, keywords, enriched_at) "
                "VALUES (?, ?, ?, ?)",
                (chunk_id, description, keywords, time.time()),
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
        from clew.indexer.relationships import Relationship as _Relationship

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

    # --- Checkpoint methods for indexing recovery ---

    def save_checkpoint(self, collection: str, batch_index: int, file_paths: list[str]) -> None:
        """Record a successfully completed batch for resume support."""
        with self._get_state_conn() as conn:
            conn.execute(
                "INSERT INTO checkpoints (collection_name, batch_index, files_processed) "
                "VALUES (?, ?, ?)",
                (collection, batch_index, json.dumps(file_paths)),
            )
        logger.info("Saved checkpoint: collection=%s batch=%d", collection, batch_index)

    def get_last_checkpoint(self, collection: str) -> int:
        """Get the last completed batch index for a collection, or -1 if none."""
        with self._get_state_conn() as conn:
            row = conn.execute(
                "SELECT MAX(batch_index) FROM checkpoints WHERE collection_name = ?",
                (collection,),
            ).fetchone()
            return row[0] if row[0] is not None else -1

    def clear_checkpoints(self, collection: str) -> None:
        """Clear all checkpoints for a collection (called on full success)."""
        with self._get_state_conn() as conn:
            conn.execute(
                "DELETE FROM checkpoints WHERE collection_name = ?",
                (collection,),
            )
        logger.info("Cleared checkpoints for collection=%s", collection)

    def record_failed_file(self, file_path: str, error_type: str, error_message: str) -> None:
        """Record a file that failed during indexing."""
        with self._get_state_conn() as conn:
            conn.execute(
                """INSERT INTO failed_files (file_path, error_type, error_message, retry_count)
                VALUES (?, ?, ?, 1)
                ON CONFLICT(file_path) DO UPDATE SET
                    error_type = excluded.error_type,
                    error_message = excluded.error_message,
                    retry_count = retry_count + 1,
                    last_attempt = datetime('now')""",
                (file_path, error_type, error_message),
            )

    def get_failed_files(self) -> list[dict[str, object]]:
        """Get all files that failed during indexing."""
        with self._get_state_conn() as conn:
            rows = conn.execute(
                "SELECT file_path, error_type, error_message, retry_count, last_attempt "
                "FROM failed_files ORDER BY last_attempt DESC"
            ).fetchall()
            return [
                {
                    "file_path": row[0],
                    "error_type": row[1],
                    "error_message": row[2],
                    "retry_count": row[3],
                    "last_attempt": row[4],
                }
                for row in rows
            ]

    @staticmethod
    def _escape_like(value: str) -> str:
        """Escape LIKE metacharacters so ``_`` and ``%`` match literally."""
        return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    def resolve_entity(self, entity: str, *, context_file: str | None = None) -> str:
        """Resolve a user-provided entity identifier to a stored entity.

        Supports exact match, suffix match (for relative paths), and
        symbol-only match (just class/function name without file path).

        Resolution strategy:
          1. Exact match against source_entity or target_entity.
          2. Suffix match — entities whose source_entity or target_entity
             ends with the provided string.
          3. Symbol-only match — when the entity has no ``::`` separator,
             match against the symbol portion after the last ``::`` in
             stored entities.

        When multiple candidates exist at any tier, rank by proximity:
          - Same directory as context_file (if provided)
          - Import relationship from context_file (if provided)
          - Alphabetical (deterministic fallback)

        Returns the resolved entity string, or the original if no match is found.
        """
        safe = self._escape_like(entity)

        with self._get_state_conn() as conn:
            # 1. Exact match on source_entity
            row = conn.execute(
                "SELECT source_entity FROM code_relationships WHERE source_entity = ? LIMIT 1",
                (entity,),
            ).fetchone()
            if row:
                return str(row[0])

            # Exact match on target_entity
            row = conn.execute(
                "SELECT target_entity FROM code_relationships WHERE target_entity = ? LIMIT 1",
                (entity,),
            ).fetchone()
            if row:
                return str(row[0])

            # 2. Suffix match — collect all candidates
            suffix_pattern = f"%{safe}"
            candidates: list[str] = []

            rows = conn.execute(
                "SELECT DISTINCT source_entity FROM code_relationships "
                "WHERE source_entity LIKE ? ESCAPE '\\'",
                (suffix_pattern,),
            ).fetchall()
            candidates.extend(row[0] for row in rows)

            rows = conn.execute(
                "SELECT DISTINCT target_entity FROM code_relationships "
                "WHERE target_entity LIKE ? ESCAPE '\\'",
                (suffix_pattern,),
            ).fetchall()
            candidates.extend(row[0] for row in rows if row[0] not in candidates)

            if candidates:
                return self._rank_candidates(candidates, context_file, conn)

            # 3. Symbol-only match (no :: in the query)
            if "::" not in entity:
                symbol_pattern = f"%::{safe}"
                candidates = []

                rows = conn.execute(
                    "SELECT DISTINCT source_entity FROM code_relationships "
                    "WHERE source_entity LIKE ? ESCAPE '\\'",
                    (symbol_pattern,),
                ).fetchall()
                candidates.extend(row[0] for row in rows)

                rows = conn.execute(
                    "SELECT DISTINCT target_entity FROM code_relationships "
                    "WHERE target_entity LIKE ? ESCAPE '\\'",
                    (symbol_pattern,),
                ).fetchall()
                candidates.extend(row[0] for row in rows if row[0] not in candidates)

                if candidates:
                    return self._rank_candidates(candidates, context_file, conn)

        logger.debug("Entity resolution fallback: '%s' has no matches", entity)
        return entity

    def _rank_candidates(
        self,
        candidates: list[str],
        context_file: str | None,
        conn: sqlite3.Connection,
    ) -> str:
        """Rank entity candidates by proximity to context_file."""
        if len(candidates) == 1:
            return candidates[0]

        if not context_file:
            # No context — return first alphabetically for determinism
            return sorted(candidates)[0]

        # Extract directory from context file for proximity
        context_dir = context_file.rsplit("/", 1)[0] if "/" in context_file else ""

        def score(candidate: str) -> tuple[int, str]:
            # Lower score = better match
            # Tier 0: same directory
            cand_file = candidate.split("::")[0] if "::" in candidate else candidate
            cand_dir = cand_file.rsplit("/", 1)[0] if "/" in cand_file else ""
            if context_dir and cand_dir == context_dir:
                return (0, candidate)
            # Tier 1: import relationship exists
            row = conn.execute(
                "SELECT 1 FROM code_relationships "
                "WHERE source_entity = ? AND target_entity = ? LIMIT 1",
                (context_file, candidate),
            ).fetchone()
            if row:
                return (1, candidate)
            # Tier 2: any other match
            return (2, candidate)

        candidates.sort(key=score)
        logger.debug(
            "Entity resolution: '%s' resolved to '%s' (of %d candidates)",
            candidates[0],
            candidates[0],
            len(candidates),
        )
        return candidates[0]

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
        resolution_cache: dict[str, str] = {}  # avoid repeated LIKE queries

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
                    next_raw = rel.target_entity
                elif direction != "outbound" and rel.target_entity == current:
                    next_raw = rel.source_entity
                else:
                    continue

                # Resolve module-qualified names to file-qualified (cached)
                if next_raw not in resolution_cache:
                    resolved = self.resolve_entity(next_raw)
                    resolution_cache[next_raw] = resolved
                next_entity = resolution_cache[next_raw]

                if next_entity not in visited:
                    visited.add(next_entity)
                    queue.append((next_entity, depth + 1))
                else:
                    # Mark edge as part of a cycle
                    results[-1]["cycle_detected"] = True

        return results
