"""Indexing pipeline: file -> chunk -> metadata -> embed -> upsert to Qdrant.

Uses structured chunk IDs, full metadata payload, and BM25 sparse vectors
with raw term counts.

V2 architecture: Two-pass indexing with 3 named vectors.
  Pass 1 (basic index, no LLM): signature + semantic stub + body vectors
  Pass 2 (enrichment, LLM required): re-embed with description + keywords
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from qdrant_client import models

from clew.chunker.fallback import Chunk, split_file
from clew.chunker.parser import ASTParser
from clew.chunker.tokenizer import count_tokens
from clew.indexer.extractors.api_boundary import APIBoundaryMatcher
from clew.indexer.extractors.django_models import DjangoModelFieldExtractor
from clew.indexer.extractors.django_urls import DjangoURLExtractor
from clew.indexer.extractors.python import PythonRelationshipExtractor
from clew.indexer.extractors.tests import TestRelationshipExtractor
from clew.indexer.extractors.typescript import TypeScriptRelationshipExtractor
from clew.indexer.importance import compute_importance_scores
from clew.indexer.metadata import (
    build_chunk_id,
    classify_layer,
    detect_app_name,
    extract_signature,
    is_test_file,
)
from clew.search.tokenize import text_to_sparse_vector

if TYPE_CHECKING:
    from clew.clients.base import EmbeddingProvider
    from clew.clients.description import DescriptionProvider
    from clew.clients.qdrant import QdrantManager
    from clew.indexer.cache import CacheDB
    from clew.indexer.extractors.base import RelationshipExtractor

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


def detect_language(file_path: str) -> str:
    """Detect language from file extension."""
    ext = file_path.rsplit(".", 1)[-1].lower() if "." in file_path else ""
    return LANGUAGE_MAP.get(ext, "unknown")


def _build_signature_text(
    chunk_id: str,
    signature: str,
    class_name: str,
    app_name: str,
    layer: str,
) -> str:
    """Build signature text for the 'signature' vector."""
    parts = [chunk_id]
    if signature:
        parts.append(signature)
    if class_name:
        parts.append(f"class: {class_name}")
    if app_name:
        parts.append(f"app: {app_name}")
    if layer:
        parts.append(f"layer: {layer}")
    return "\n".join(parts)


def _build_semantic_stub(
    signature_text: str,
    *,
    callers: list[str] | None = None,
    callees: list[str] | None = None,
    imports: list[str] | None = None,
) -> str:
    """Build a semantic stub for Pass 1 (no description/keywords).

    Combines signature text with available relationship data.
    """
    parts = [signature_text]
    if callers:
        parts.append(f"[Callers]: {', '.join(callers)}")
    if callees:
        parts.append(f"[Calls]: {', '.join(callees)}")
    if imports:
        parts.append(f"[Imports]: {', '.join(imports)}")
    return "\n".join(parts)


def _build_enriched_semantic_text(
    file_path: str,
    layer: str,
    app_name: str,
    description: str,
    keywords: str,
    *,
    callers: list[str] | None = None,
    callees: list[str] | None = None,
    imports: list[str] | None = None,
) -> str:
    """Build enriched semantic text for Pass 2 (with LLM output)."""
    parts = [
        f"[File]: {file_path}",
        f"[Layer]: {layer}",
        f"[App]: {app_name}",
        f"[Description]: {description}",
        f"[Keywords]: {keywords}",
    ]
    if callers:
        parts.append(f"[Callers]: {', '.join(callers)}")
    if callees:
        parts.append(f"[Calls]: {', '.join(callees)}")
    if imports:
        parts.append(f"[Imports]: {', '.join(imports)}")
    return "\n".join(parts)


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
        description_provider: DescriptionProvider | None = None,
        cache: CacheDB | None = None,
        batch_size: int = 25,
        max_tokens: int = 3000,
    ) -> None:
        self._qdrant = qdrant
        self._embedder = embedder
        self._description_provider = description_provider
        self._cache = cache
        self._batch_size = batch_size
        self._max_tokens = max_tokens
        self._parser = ASTParser()

        # Language-specific relationship extractors
        _ts_extractor = TypeScriptRelationshipExtractor()
        self._extractors: dict[str, RelationshipExtractor] = {
            "python": PythonRelationshipExtractor(),
            "typescript": _ts_extractor,
            "tsx": _ts_extractor,
            "javascript": _ts_extractor,
        }
        self._test_extractor = TestRelationshipExtractor()
        self._django_url_extractor = DjangoURLExtractor()
        self._django_model_extractor = DjangoModelFieldExtractor()
        self._api_boundary_matcher = APIBoundaryMatcher()

    async def index_files(
        self,
        files: list[Path],
        collection: str = "code",
        delete_before_upsert: bool = False,
        resume: bool = True,
    ) -> IndexingResult:
        """Index a list of files into a Qdrant collection.

        Args:
            resume: If True and a checkpoint exists, skip already-completed batches.
        """
        result = IndexingResult()
        all_chunks: list[Chunk] = []
        all_url_patterns: list[dict[str, str]] = []

        for file_path in files:
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
            except (OSError, UnicodeDecodeError) as e:
                logger.warning("Cannot read %s: %s", file_path, e)
                result.files_skipped += 1
                result.errors.append(f"{file_path}: {e}")
                if self._cache:
                    self._cache.record_failed_file(str(file_path), type(e).__name__, str(e))
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

            # Generate file summary chunk
            file_summary = self._build_file_summary(str(file_path), content, chunks)
            if file_summary:
                chunks.append(file_summary)

            all_chunks.extend(chunks)
            result.files_processed += 1

            # Cache chunk IDs for this file (needed by reembed)
            if self._cache:
                import hashlib

                file_hash = hashlib.sha256(content.encode()).hexdigest()
                chunk_ids = [
                    build_chunk_id(
                        c.file_path,
                        c.metadata.get("entity_type", "section"),
                        c.metadata.get(
                            "qualified_name", c.metadata.get("name", "")
                        ),
                    )
                    for c in chunks
                ]
                self._cache.set_file_chunks(str(file_path), file_hash, chunk_ids)

            # Extract and store code relationships
            if self._cache:
                url_patterns = self._extract_relationships(str(file_path), content)
                all_url_patterns.extend(url_patterns)

        # Post-processing: match API boundaries across languages
        if self._cache and all_url_patterns:
            self._match_api_boundaries(all_url_patterns)

        # Post-extraction normalization: resolve remaining bare target_entity values
        if self._cache:
            self._normalize_relationship_targets()

        # Compute importance scores from relationship graph
        importance_scores: dict[str, float] = {}
        if self._cache:
            pairs = self._cache.get_all_relationship_pairs()
            importance_scores = compute_importance_scores(pairs)

        if not all_chunks:
            return result

        # Check for resume checkpoint
        last_checkpoint = -1
        if resume and self._cache:
            last_checkpoint = self._cache.get_last_checkpoint(collection)
            if last_checkpoint >= 0:
                logger.info("Resuming from checkpoint: batch %d", last_checkpoint + 1)

        # Batch embed and upsert
        total_batches = (len(all_chunks) + self._batch_size - 1) // self._batch_size
        had_errors = False
        for i in range(0, len(all_chunks), self._batch_size):
            batch_num = i // self._batch_size + 1
            batch = all_chunks[i : i + self._batch_size]

            # Skip already-completed batches
            if batch_num - 1 <= last_checkpoint:
                logger.debug("Skipping batch %d/%d (checkpointed)", batch_num, total_batches)
                result.chunks_created += len(batch)
                continue

            logger.info(
                "Embedding batch %d/%d (%d chunks)...",
                batch_num,
                total_batches,
                len(batch),
            )
            try:
                await self._embed_and_upsert(batch, collection, importance_scores=importance_scores)
                result.chunks_created += len(batch)
                # Save checkpoint on success
                if self._cache:
                    batch_files = list({c.file_path for c in batch})
                    self._cache.save_checkpoint(collection, batch_num - 1, batch_files)
            except Exception as e:
                logger.warning("Batch %d/%d failed: %s — skipping", batch_num, total_batches, e)
                result.errors.append(f"Batch {batch_num}: {e}")
                had_errors = True

        # Clear checkpoints on full success (no errors)
        if not had_errors and self._cache:
            self._cache.clear_checkpoints(collection)

        return result

    def _build_file_summary(
        self, file_path: str, content: str, chunks: list[Chunk]
    ) -> Chunk | None:
        """Build a synthetic file_summary chunk from a file's chunks."""
        # Collect signatures from all entity chunks
        signatures: list[str] = []
        for c in chunks:
            entity_type = c.metadata.get("entity_type", "section")
            if entity_type in ("function", "class", "method"):
                sig = extract_signature(entity_type, c.content)
                if sig:
                    signatures.append(sig)

        # Extract module docstring (first line starting with """ or ''')
        module_docstring = ""
        for line in content.split("\n"):
            stripped = line.strip()
            if stripped.startswith(('"""', "'''")):
                module_docstring = stripped.strip("\"'")
                break
            if stripped and not stripped.startswith("#"):
                break

        # Extract import list
        import_lines: list[str] = []
        for line in content.split("\n"):
            stripped = line.strip()
            if stripped.startswith("import ") or stripped.startswith("from "):
                import_lines.append(stripped)

        # Build summary content
        parts = [f"# File: {file_path}"]
        if module_docstring:
            parts.append(f"# {module_docstring}")
        if import_lines:
            parts.append("# Imports: " + ", ".join(import_lines[:20]))
        if signatures:
            parts.append("# Entities:")
            parts.extend(f"#   {s}" for s in signatures[:30])

        summary_content = "\n".join(parts)
        if not signatures and not import_lines:
            return None

        return Chunk(
            content=summary_content,
            source="synthetic",
            file_path=file_path,
            metadata={
                "entity_type": "file_summary",
                "chunk_type": "file_summary",
                "qualified_name": "__file_summary__",
                "name": "file_summary",
            },
        )

    def _get_chunk_relationships(self, chunk_id: str) -> tuple[list[str], list[str], list[str]]:
        """Get callers, callees, and imports for a chunk from the cache.

        Returns (callers, callees, imports) lists.
        """
        callers: list[str] = []
        callees: list[str] = []
        imports: list[str] = []

        if not self._cache:
            return callers, callees, imports

        # Extract entity name from chunk_id (format: file_path::entity_type::name)
        parts = chunk_id.split("::")
        if len(parts) < 3:
            return callers, callees, imports

        # Build entity key: file_path::qualified_name
        file_path = parts[0]
        qualified_name = parts[2] if len(parts) >= 3 else ""
        entity_key = f"{file_path}::{qualified_name}" if qualified_name else file_path

        rels = self._cache.get_relationships(entity_key, direction="both")
        for r in rels:
            if r.relationship == "imports" and r.source_entity == entity_key:
                target = r.target_entity
                imports.append(target.split("::")[-1] if "::" in target else target)
            elif r.relationship == "calls":
                if r.source_entity == entity_key:
                    target = r.target_entity
                    callees.append(target.split("::")[-1] if "::" in target else target)
                else:
                    source = r.source_entity
                    callers.append(source.split("::")[-1] if "::" in source else source)

        return callers, callees, imports

    def _extract_relationships(self, file_path: str, content: str) -> list[dict[str, str]]:
        """Extract code relationships from a file and store in cache.

        Returns any Django URL patterns found (for API boundary matching).
        """
        assert self._cache is not None  # caller checks

        language = detect_language(file_path)
        extractor = self._extractors.get(language)
        url_patterns: list[dict[str, str]] = []

        # Delete old relationships for this file before re-extracting
        self._cache.delete_relationships_by_file(file_path)

        from clew.indexer.relationships import Relationship as _Relationship

        all_rels: list[_Relationship] = []

        if extractor and language in ("python", "typescript", "tsx", "javascript"):
            try:
                tree = self._parser.parse(content, language)
                rels = extractor.extract(tree, content, file_path)
                all_rels.extend(rels)

                # Also run test relationship extractor
                test_rels = self._test_extractor.extract(tree, content, file_path)
                all_rels.extend(test_rels)

                # Extract Django URL patterns from urls.py files
                if language == "python":
                    url_patterns = self._django_url_extractor.extract_url_patterns(
                        tree, content, file_path
                    )
                    # Extract Django model field relationships
                    model_rels = self._django_model_extractor.extract(tree, content, file_path)
                    all_rels.extend(model_rels)
            except Exception:
                logger.debug("Relationship extraction failed for %s", file_path)

        if all_rels:
            self._cache.store_relationships(all_rels)

        return url_patterns

    def _match_api_boundaries(self, url_patterns: list[dict[str, str]]) -> None:
        """Match frontend API calls to backend URL patterns."""
        assert self._cache is not None

        from clew.indexer.relationships import Relationship as _Relationship

        api_calls: list[_Relationship] = []
        with self._cache._get_state_conn() as conn:
            rows = conn.execute(
                "SELECT source_entity, relationship, target_entity, file_path, confidence "
                "FROM code_relationships WHERE relationship = 'calls_api'"
            ).fetchall()
            for row in rows:
                api_calls.append(
                    _Relationship(
                        source_entity=row[0],
                        relationship=row[1],
                        target_entity=row[2],
                        file_path=row[3],
                        confidence=row[4],
                    )
                )

        if api_calls:
            matches = self._api_boundary_matcher.match(url_patterns, api_calls)
            if matches:
                self._cache.store_relationships(matches)

    def _normalize_relationship_targets(self) -> None:
        """Post-extraction normalization: resolve bare target_entity values.

        Builds a symbol index from source_entity values, then resolves
        remaining bare target_entity values where the match is unambiguous
        (exactly 1 source_entity matches the bare name).
        """
        assert self._cache is not None

        with self._cache._get_state_conn() as conn:
            # Build symbol index: bare_name → [fully_qualified_names]
            rows = conn.execute("SELECT DISTINCT source_entity FROM code_relationships").fetchall()

            symbol_index: dict[str, list[str]] = {}
            for (source_entity,) in rows:
                if "::" in source_entity:
                    # Extract the symbol part after last ::
                    symbol = source_entity.rsplit("::", 1)[1]
                    symbol_index.setdefault(symbol, []).append(source_entity)

            # Find bare target_entity values (no :: and no / — not file paths)
            bare_targets = conn.execute(
                "SELECT DISTINCT target_entity FROM code_relationships "
                "WHERE target_entity NOT LIKE '%::%' AND target_entity NOT LIKE '%/%'"
            ).fetchall()

            updates: list[tuple[str, str]] = []
            for (target,) in bare_targets:
                # Check if exactly 1 match exists in the symbol index
                # Also check dotted names: `Foo.bar` → try `Foo`
                base_name = target.split(".")[0]
                candidates = symbol_index.get(base_name, [])
                if len(candidates) == 1:
                    resolved = candidates[0]
                    if base_name != target:
                        # Preserve the dotted suffix: Foo.bar → resolved::Foo.bar
                        suffix = target[len(base_name) :]
                        resolved = f"{resolved}{suffix}"
                    updates.append((resolved, target))

            if updates:
                logger.info(
                    "Post-extraction normalization: resolved %d bare target entities",
                    len(updates),
                )
                conn.executemany(
                    "UPDATE OR IGNORE code_relationships SET target_entity = ? "
                    "WHERE target_entity = ?",
                    updates,
                )
                for resolved, original in updates:
                    conn.execute(
                        "DELETE FROM code_relationships WHERE target_entity = ?",
                        (original,),
                    )

            # Second pass: resolve module-qualified targets
            module_qualified = conn.execute(
                "SELECT DISTINCT target_entity FROM code_relationships "
                "WHERE target_entity LIKE '%::%' AND target_entity NOT LIKE '%/%'"
            ).fetchall()

            # Build file-path index: symbol → [file-qualified entities]
            file_entities_by_symbol: dict[str, list[str]] = {}
            for (source_entity,) in rows:
                if "::" in source_entity and "/" in source_entity:
                    symbol = source_entity.rsplit("::", 1)[1]
                    file_entities_by_symbol.setdefault(symbol, []).append(source_entity)

            module_updates: list[tuple[str, str]] = []
            for (target,) in module_qualified:
                module_part, symbol_part = target.split("::", 1)
                base_symbol = symbol_part.split(".")[0]
                candidates = file_entities_by_symbol.get(base_symbol, [])

                module_as_path = module_part.replace(".", "/")
                matching = [c for c in candidates if module_as_path in c.split("::")[0]]

                if len(matching) == 1:
                    resolved_file = matching[0].split("::")[0]
                    if base_symbol != symbol_part:
                        resolved = f"{resolved_file}::{symbol_part}"
                    else:
                        resolved = f"{resolved_file}::{base_symbol}"
                    module_updates.append((resolved, target))

            if module_updates:
                logger.info(
                    "Post-extraction normalization: resolved %d module-qualified targets",
                    len(module_updates),
                )
                conn.executemany(
                    "UPDATE OR IGNORE code_relationships SET target_entity = ? "
                    "WHERE target_entity = ?",
                    module_updates,
                )
                for resolved, original in module_updates:
                    conn.execute(
                        "DELETE FROM code_relationships WHERE target_entity = ?",
                        (original,),
                    )

    async def _generate_descriptions(self, chunks: list[Chunk]) -> list[str | None] | None:
        """Generate NL descriptions for chunks that lack docstrings.

        Returns None if no description provider is configured.
        Returns a list parallel to chunks with descriptions or None per chunk.
        """
        if not self._description_provider:
            return None

        import hashlib

        results: list[str | None] = [None] * len(chunks)
        to_generate: list[tuple[int, dict[str, str]]] = []

        for i, chunk in enumerate(chunks):
            docstring = chunk.metadata.get("docstring")
            if docstring:
                continue

            content_hash = hashlib.sha256(chunk.content.encode()).hexdigest()

            # Check cache first
            if self._cache:
                cached = self._cache.get_description(
                    content_hash, self._description_provider.model_name
                )
                if cached:
                    results[i] = cached
                    continue

            to_generate.append(
                (
                    i,
                    {
                        "code": chunk.content,
                        "language": detect_language(chunk.file_path),
                        "entity_type": chunk.metadata.get("entity_type", "section"),
                        "name": chunk.metadata.get(
                            "qualified_name", chunk.metadata.get("name", "")
                        ),
                        "_content_hash": content_hash,
                    },
                )
            )

        if not to_generate:
            return results

        items = [item for _, item in to_generate]
        descriptions = await self._description_provider.generate_batch(items)

        for (idx, item), desc in zip(to_generate, descriptions):
            results[idx] = desc
            if desc and self._cache:
                self._cache.set_description(
                    item["_content_hash"],
                    self._description_provider.model_name,
                    desc,
                )

        return results

    async def _embed_with_token_limit(
        self, texts: list[str], max_batch_tokens: int = 100_000
    ) -> list[list[float]]:
        """Embed texts in sub-batches that respect the API token limit."""
        all_embeddings: list[list[float]] = []
        sub_batch: list[str] = []
        sub_batch_tokens = 0

        async def _embed_with_retry(batch: list[str], max_retries: int = 3) -> list[list[float]]:
            for attempt in range(max_retries):
                try:
                    return await self._embedder.embed(batch, input_type="document")
                except Exception as e:
                    if attempt < max_retries - 1:
                        wait = 2 ** (attempt + 1)
                        logger.warning(
                            "Embedding API error (attempt %d/%d), retrying in %ds: %s",
                            attempt + 1, max_retries, wait, e,
                        )
                        await asyncio.sleep(wait)
                    else:
                        raise

        for text in texts:
            tokens = count_tokens(text)
            if sub_batch and sub_batch_tokens + tokens > max_batch_tokens:
                embs = await _embed_with_retry(sub_batch)
                all_embeddings.extend(embs)
                sub_batch = []
                sub_batch_tokens = 0
            sub_batch.append(text)
            sub_batch_tokens += tokens

        if sub_batch:
            embs = await _embed_with_retry(sub_batch)
            all_embeddings.extend(embs)

        return all_embeddings

    async def _embed_and_upsert(
        self,
        chunks: list[Chunk],
        collection: str,
        *,
        importance_scores: dict[str, float] | None = None,
    ) -> None:
        """Embed a batch of chunks and upsert to Qdrant (Pass 1).

        Uses 3 named vectors: signature, semantic (stub), body.
        """
        # Generate NL descriptions (if provider configured — backward compat with --nl-descriptions)
        descriptions = await self._generate_descriptions(chunks)

        # Build per-chunk metadata and texts for each vector
        sig_texts: list[str] = []
        sem_texts: list[str] = []
        body_texts: list[str] = []
        chunk_metas: list[dict[str, object]] = []

        for i, chunk in enumerate(chunks):
            file_path_str = chunk.file_path
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

            # Build signature text
            sig_text = _build_signature_text(
                chunk_id,
                signature,
                chunk.metadata.get("parent_class", ""),
                app_name,
                layer,
            )

            # Get relationship context for semantic stub
            callers, callees, imports = self._get_chunk_relationships(chunk_id)

            # Check if we have enrichment data in cache
            enriched = False
            enrichment_desc = ""
            enrichment_kw = ""
            if self._cache:
                enrichment = self._cache.get_enrichment(chunk_id)
                if enrichment:
                    enrichment_desc, enrichment_kw = enrichment
                    enriched = True

            # Build semantic text
            desc = descriptions[i] if descriptions else None
            if enriched:
                # Use cached enrichment for semantic vector
                sem_text = _build_enriched_semantic_text(
                    file_path_str,
                    layer,
                    app_name,
                    enrichment_desc,
                    enrichment_kw,
                    callers=callers,
                    callees=callees,
                    imports=imports,
                )
            elif desc:
                # Backward compat: use NL description from --nl-descriptions
                sem_text = _build_enriched_semantic_text(
                    file_path_str,
                    layer,
                    app_name,
                    desc,
                    "",
                    callers=callers,
                    callees=callees,
                    imports=imports,
                )
                enriched = True
            else:
                # Pass 1 stub: signature + relationships
                sem_text = _build_semantic_stub(
                    sig_text,
                    callers=callers,
                    callees=callees,
                    imports=imports,
                )

            sig_texts.append(sig_text)
            sem_texts.append(sem_text)
            body_texts.append(chunk.content)

            # Compute importance score for this chunk's file
            importance_score = 0.0
            if importance_scores:
                importance_score = importance_scores.get(file_path_str, 0.0)

            chunk_metas.append(
                {
                    "chunk": chunk,
                    "chunk_id": chunk_id,
                    "entity_type": entity_type,
                    "qualified_name": qualified_name,
                    "app_name": app_name,
                    "layer": layer,
                    "signature": signature,
                    "enriched": enriched,
                    "importance_score": importance_score,
                    "description": enrichment_desc or (desc or ""),
                    "keywords": enrichment_kw,
                }
            )

        # Embed all three vectors
        sig_embeddings = await self._embed_with_token_limit(sig_texts)
        sem_embeddings = await self._embed_with_token_limit(sem_texts)
        body_embeddings = await self._embed_with_token_limit(body_texts)

        points: list[models.PointStruct] = []
        for i, meta in enumerate(chunk_metas):
            pt_chunk = meta["chunk"]
            assert isinstance(pt_chunk, Chunk)
            pt_chunk_id = str(meta["chunk_id"])
            pt_enriched = bool(meta["enriched"])

            # BM25 sparse vector
            if pt_enriched:
                # Pass 2: semantic text + raw code
                sparse_text = sem_texts[i] + "\n" + pt_chunk.content
            else:
                # Pass 1: raw code only
                sparse_text = pt_chunk.content
            sparse = text_to_sparse_vector(sparse_text)

            file_path_str = pt_chunk.file_path

            payload: dict[str, object] = {
                "content": pt_chunk.content,
                "chunk_id": pt_chunk_id,
                "file_path": file_path_str,
                "language": detect_language(file_path_str),
                "chunk_type": meta["entity_type"],
                "class_name": pt_chunk.metadata.get("parent_class", ""),
                "function_name": pt_chunk.metadata.get("name", ""),
                "signature": meta["signature"],
                "app_name": meta["app_name"],
                "layer": meta["layer"],
                "line_start": pt_chunk.metadata.get("line_start", 0),
                "line_end": pt_chunk.metadata.get("line_end", 0),
                "is_test": is_test_file(file_path_str),
                "source_type": collection,
                "embedding_model": self._embedder.model_name,
                "indexed_at": datetime.now(tz=timezone.utc).isoformat(),
                "enriched": pt_enriched,
                "importance_score": meta["importance_score"],
            }

            # Add description/keywords if available
            if meta["description"]:
                payload["description"] = meta["description"]
                payload["nl_description"] = meta["description"]  # backward compat
            if meta["keywords"]:
                payload["keywords"] = meta["keywords"]

            # Add docstring from chunk metadata if present
            docstring = pt_chunk.metadata.get("docstring")
            if docstring:
                payload["docstring"] = docstring

            point_id = str(uuid.uuid5(CHUNK_UUID_NAMESPACE, pt_chunk_id))

            points.append(
                models.PointStruct(
                    id=point_id,
                    vector={
                        "signature": sig_embeddings[i],
                        "semantic": sem_embeddings[i],
                        "body": body_embeddings[i],
                        "bm25": models.SparseVector(
                            indices=sparse.indices,
                            values=sparse.values,
                        ),
                    },
                    payload=payload,
                )
            )

        self._qdrant.upsert_points(collection, points)

    async def reembed(self, collection: str = "code") -> IndexingResult:
        """Re-embed all chunks using cached enrichment data (Pass 2).

        Reads chunks from SQLite chunk cache, enrichment from enrichment_cache,
        and re-embeds with full content into all 3 named vectors.
        """
        result = IndexingResult()
        if not self._cache:
            result.errors.append("No cache configured")
            return result

        # Compute importance scores
        pairs = self._cache.get_all_relationship_pairs()
        importance_scores = compute_importance_scores(pairs)

        # Get all files from chunk cache
        with self._cache._get_cache_conn() as conn:
            rows = conn.execute("SELECT file_path, chunk_ids FROM chunk_cache").fetchall()

        if not rows:
            logger.info("No chunks in cache to re-embed")
            return result

        # Collect chunks that have enrichment data
        chunks_to_embed: list[tuple[str, str, str, str]] = []  # (chunk_id, file_path, desc, kw)
        for row in rows:
            file_path = row["file_path"]
            import json

            chunk_ids = json.loads(row["chunk_ids"])
            for chunk_id in chunk_ids:
                enrichment = self._cache.get_enrichment(chunk_id)
                if enrichment:
                    desc, kw = enrichment
                    chunks_to_embed.append((chunk_id, file_path, desc, kw))

        if not chunks_to_embed:
            logger.info("No enriched chunks to re-embed")
            return result

        # Skip chunks already enriched in Qdrant (resume support)
        already_enriched: set[str] = set()
        try:
            offset_id = None
            while True:
                scroll_result = self._qdrant._client.scroll(
                    collection_name=collection,
                    scroll_filter=models.Filter(
                        must=[models.FieldCondition(
                            key="enriched",
                            match=models.MatchValue(value=True),
                        )]
                    ),
                    limit=1000,
                    with_payload=["chunk_id"],
                    with_vectors=False,
                    offset=offset_id,
                )
                points, next_offset = scroll_result
                for p in points:
                    cid = p.payload.get("chunk_id", "") if p.payload else ""
                    if cid:
                        already_enriched.add(cid)
                if next_offset is None:
                    break
                offset_id = next_offset
            if already_enriched:
                before = len(chunks_to_embed)
                chunks_to_embed = [
                    c for c in chunks_to_embed if c[0] not in already_enriched
                ]
                logger.info(
                    "Skipping %d already-enriched chunks (%d remaining)",
                    before - len(chunks_to_embed),
                    len(chunks_to_embed),
                )
        except Exception as exc:
            logger.warning("Could not check existing enriched chunks, re-embedding all: %s", exc)

        if not chunks_to_embed:
            logger.info("All chunks already enriched")
            return result

        logger.info("Re-embedding %d enriched chunks", len(chunks_to_embed))

        # Process in batches
        for i in range(0, len(chunks_to_embed), self._batch_size):
            batch = chunks_to_embed[i : i + self._batch_size]

            sig_texts: list[str] = []
            sem_texts: list[str] = []
            body_texts: list[str] = []
            point_data: list[dict[str, object]] = []

            for chunk_id, file_path, desc, kw in batch:
                # Read the source file to get raw content
                try:
                    content = Path(file_path).read_text(encoding="utf-8", errors="replace")
                except (OSError, UnicodeDecodeError):
                    logger.debug("Cannot read %s for re-embed, skipping", file_path)
                    continue

                # Parse chunk_id to extract metadata
                parts = chunk_id.split("::")
                entity_type = parts[1] if len(parts) >= 2 else "section"
                qualified_name = parts[2] if len(parts) >= 3 else ""

                app_name = detect_app_name(file_path)
                layer = classify_layer(file_path)
                signature = extract_signature(entity_type, content)
                class_name = ""
                if "." in qualified_name:
                    class_name = qualified_name.split(".")[0]

                # Build signature text
                sig_text = _build_signature_text(chunk_id, signature, class_name, app_name, layer)

                # Get relationship context
                callers, callees, imports = self._get_chunk_relationships(chunk_id)

                # Build enriched semantic text
                sem_text = _build_enriched_semantic_text(
                    file_path,
                    layer,
                    app_name,
                    desc,
                    kw,
                    callers=callers,
                    callees=callees,
                    imports=imports,
                )

                # For body, use the content we can find
                # The actual chunk content may be a subset of the file
                # Use the full file for now as a reasonable approximation
                body_text = content

                sig_texts.append(sig_text)
                sem_texts.append(sem_text)
                body_texts.append(body_text)

                importance = importance_scores.get(file_path, 0.0)
                point_data.append(
                    {
                        "chunk_id": chunk_id,
                        "file_path": file_path,
                        "entity_type": entity_type,
                        "app_name": app_name,
                        "layer": layer,
                        "signature": signature,
                        "class_name": class_name,
                        "importance_score": importance,
                        "description": desc,
                        "keywords": kw,
                        "body_text": body_text,
                        "sem_text": sem_text,
                    }
                )

            if not sig_texts:
                continue

            # Embed all three vectors
            sig_embeddings = await self._embed_with_token_limit(sig_texts)
            sem_embeddings = await self._embed_with_token_limit(sem_texts)
            body_embeddings = await self._embed_with_token_limit(body_texts)

            points: list[models.PointStruct] = []
            for j, data in enumerate(point_data):
                c_id = str(data["chunk_id"])
                fp = str(data["file_path"])

                # BM25: semantic text + raw code
                sparse_text = str(data["sem_text"]) + "\n" + str(data["body_text"])
                sparse = text_to_sparse_vector(sparse_text)

                payload: dict[str, object] = {
                    "content": data["body_text"],
                    "chunk_id": c_id,
                    "file_path": fp,
                    "language": detect_language(fp),
                    "chunk_type": data["entity_type"],
                    "class_name": data["class_name"],
                    "signature": data["signature"],
                    "app_name": data["app_name"],
                    "layer": data["layer"],
                    "is_test": is_test_file(fp),
                    "source_type": collection,
                    "embedding_model": self._embedder.model_name,
                    "indexed_at": datetime.now(tz=timezone.utc).isoformat(),
                    "enriched": True,
                    "importance_score": data["importance_score"],
                    "description": data["description"],
                    "nl_description": data["description"],
                    "keywords": data["keywords"],
                }

                point_id = str(uuid.uuid5(CHUNK_UUID_NAMESPACE, c_id))
                points.append(
                    models.PointStruct(
                        id=point_id,
                        vector={
                            "signature": sig_embeddings[j],
                            "semantic": sem_embeddings[j],
                            "body": body_embeddings[j],
                            "bm25": models.SparseVector(
                                indices=sparse.indices,
                                values=sparse.values,
                            ),
                        },
                        payload=payload,
                    )
                )

            self._qdrant.upsert_points(collection, points)
            result.chunks_created += len(points)
            result.files_processed += len({str(d["file_path"]) for d in point_data})

        return result
