"""Indexing pipeline: file -> chunk -> metadata -> embed -> upsert to Qdrant.

Uses structured chunk IDs, full metadata payload, and BM25 sparse vectors
with raw term counts.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from qdrant_client import models

from code_search.chunker.fallback import Chunk, split_file
from code_search.chunker.parser import ASTParser
from code_search.indexer.metadata import (
    build_chunk_id,
    classify_layer,
    detect_app_name,
    extract_signature,
)
from code_search.search.tokenize import text_to_sparse_vector

if TYPE_CHECKING:
    from code_search.clients.base import EmbeddingProvider
    from code_search.clients.qdrant import QdrantManager

logger = logging.getLogger(__name__)

# Namespace for deterministic UUID generation from chunk IDs
CHUNK_UUID_NAMESPACE = uuid.UUID("a3c0e7d2-b1f4-4c8a-9e6d-5f2a1b3c4d5e")

LANGUAGE_MAP: dict[str, str] = {
    "py": "python",
    "ts": "typescript",
    "tsx": "tsx",
    "js": "javascript",
    "jsx": "jsx",
    "md": "markdown",
    "yaml": "yaml",
    "yml": "yaml",
    "json": "json",
    "toml": "toml",
}


def _detect_language(file_path: str) -> str:
    """Detect language from file extension."""
    ext = file_path.rsplit(".", 1)[-1].lower() if "." in file_path else ""
    return LANGUAGE_MAP.get(ext, "unknown")


def _is_test_file(file_path: str) -> bool:
    """Check if a file is a test file."""
    parts = file_path.replace("\\", "/").split("/")
    name = parts[-1] if parts else ""
    return (
        name.startswith("test_")
        or name.endswith("_test.py")
        or name.endswith(".spec.ts")
        or name.endswith(".spec.js")
        or name.endswith(".test.ts")
        or name.endswith(".test.js")
        or "tests/" in file_path
        or "test/" in file_path
    )


@dataclass
class IndexingResult:
    """Result of an indexing run."""

    files_processed: int = 0
    chunks_created: int = 0
    files_skipped: int = 0
    errors: list[str] = field(default_factory=list)


class IndexingPipeline:
    """Orchestrate file indexing: chunk -> metadata -> embed -> upsert."""

    def __init__(
        self,
        qdrant: QdrantManager,
        embedder: EmbeddingProvider,
        batch_size: int = 100,
        max_tokens: int = 3000,
    ) -> None:
        self._qdrant = qdrant
        self._embedder = embedder
        self._batch_size = batch_size
        self._max_tokens = max_tokens
        self._parser = ASTParser()

    async def index_files(
        self,
        files: list[Path],
        collection: str = "code",
        delete_before_upsert: bool = False,
    ) -> IndexingResult:
        """Index a list of files into a Qdrant collection."""
        result = IndexingResult()
        all_chunks: list[Chunk] = []

        for file_path in files:
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
            except (OSError, UnicodeDecodeError) as e:
                logger.warning("Cannot read %s: %s", file_path, e)
                result.files_skipped += 1
                result.errors.append(f"{file_path}: {e}")
                continue

            if not content.strip():
                result.files_skipped += 1
                continue

            # Delete old chunks for this file if requested (for modified files)
            if delete_before_upsert:
                self._qdrant.delete_by_file_path(collection, str(file_path))

            chunks = split_file(
                str(file_path),
                content,
                self._max_tokens,
                self._parser,
            )
            all_chunks.extend(chunks)
            result.files_processed += 1

        if not all_chunks:
            return result

        # Batch embed and upsert
        for i in range(0, len(all_chunks), self._batch_size):
            batch = all_chunks[i : i + self._batch_size]
            await self._embed_and_upsert(batch, collection)
            result.chunks_created += len(batch)

        return result

    async def _embed_and_upsert(self, chunks: list[Chunk], collection: str) -> None:
        """Embed a batch of chunks and upsert to Qdrant."""
        texts = [c.content for c in chunks]
        embeddings = await self._embedder.embed(texts, input_type="document")

        points: list[models.PointStruct] = []
        for chunk, embedding in zip(chunks, embeddings):
            sparse = text_to_sparse_vector(chunk.content)
            file_path_str = chunk.file_path

            # Extract metadata
            entity_type = chunk.metadata.get("entity_type", "section")
            qualified_name = chunk.metadata.get("qualified_name", "")
            app_name = detect_app_name(file_path_str)
            layer = classify_layer(file_path_str)
            signature = extract_signature(entity_type, chunk.content)
            chunk_id = build_chunk_id(
                file_path_str,
                entity_type,
                qualified_name,
                content=chunk.content,
            )

            payload = {
                "content": chunk.content,
                "chunk_id": chunk_id,
                "file_path": file_path_str,
                "language": _detect_language(file_path_str),
                "chunk_type": entity_type,
                "class_name": chunk.metadata.get("parent_class", ""),
                "function_name": chunk.metadata.get("name", ""),
                "signature": signature,
                "app_name": app_name,
                "layer": layer,
                "line_start": chunk.metadata.get("line_start", 0),
                "line_end": chunk.metadata.get("line_end", 0),
                "is_test": _is_test_file(file_path_str),
                "source_type": collection,
                "embedding_model": self._embedder.model_name,
                "indexed_at": datetime.now(tz=timezone.utc).isoformat(),
            }

            # Qdrant requires UUID or int IDs -- generate deterministic UUID from chunk_id
            point_id = str(uuid.uuid5(CHUNK_UUID_NAMESPACE, chunk_id))

            points.append(
                models.PointStruct(
                    id=point_id,
                    vector={
                        "dense": embedding,
                        "bm25": models.SparseVector(
                            indices=sparse.indices,
                            values=sparse.values,
                        ),
                    },
                    payload=payload,
                )
            )

        self._qdrant.upsert_points(collection, points)
