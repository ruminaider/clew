"""MCP server exposing clew tools for Claude Code."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from clew.clients.circuit_breaker import CircuitBreaker
from clew.exceptions import (
    ClewError,
    InvalidFilterError,
    QdrantConnectionError,
    VoyageAuthError,
)
from clew.factory import Components, create_components
from clew.indexer.pipeline import detect_language
from clew.search.models import SearchRequest

logger = logging.getLogger(__name__)

_EXPLAIN_PROMPT_VERSION = "v1"
_explain_breaker = CircuitBreaker("explain_llm", failure_threshold=3, cooldown_seconds=60.0)

mcp = FastMCP("clew")

# Lazy singleton for components
_components: Components | None = None


def _get_components() -> Components:
    """Get or create components singleton."""
    global _components  # noqa: PLW0603
    if _components is None:
        _components = create_components()
    return _components


SNIPPET_MAX_LINES = 5


def _build_snippet(result: Any) -> str:
    """Build a compact preview: signature + docstring if available, else first lines."""
    sig = getattr(result, "signature", "")
    doc = getattr(result, "docstring", "")
    if sig and doc:
        doc_lines = doc.splitlines()
        remaining = SNIPPET_MAX_LINES - 1
        doc_preview = "\n".join(doc_lines[:remaining])
        return f"{sig}\n{doc_preview}"
    if sig:
        return sig
    content = getattr(result, "content", "")
    lines = content.splitlines()
    return "\n".join(lines[:SNIPPET_MAX_LINES])


def _compact_result_to_dict(result: Any) -> dict[str, Any]:
    """Convert a SearchResult to a compact dict (no full content)."""
    d: dict[str, Any] = {
        "file_path": result.file_path,
        "line_start": result.line_start,
        "line_end": result.line_end,
        "score": result.score,
        "chunk_type": result.chunk_type,
        "language": result.language,
        "function_name": result.function_name,
        "class_name": result.class_name,
        "snippet": _build_snippet(result),
        "is_test": getattr(result, "is_test", False),
    }
    importance = getattr(result, "importance_score", 0.0)
    if importance:
        d["importance_score"] = importance
    enriched = getattr(result, "enriched", None)
    if enriched is not None:
        d["enriched"] = enriched
    return d


def _result_to_dict(result: Any, detail: str = "compact") -> dict[str, Any]:
    """Convert a SearchResult to a dict, respecting detail level."""
    if detail == "compact":
        return _compact_result_to_dict(result)
    return {
        **_compact_result_to_dict(result),
        "content": result.content,
    }


def _error_response(error: Exception) -> dict[str, str]:
    """Create a structured error response with fix hints."""
    if isinstance(error, QdrantConnectionError):
        return {"error": str(error), "fix": "Run: docker compose up -d qdrant"}
    if isinstance(error, VoyageAuthError):
        return {"error": str(error), "fix": "Set VOYAGE_API_KEY environment variable"}
    return {"error": str(error), "fix": "Check logs for details"}


@mcp.tool()
async def search(
    query: str,
    limit: int = 5,
    collection: str = "code",
    active_file: str | None = None,
    intent: str | None = None,
    filters: dict[str, str] | None = None,
    detail: str = "compact",
) -> list[dict[str, Any]] | dict[str, str]:
    """Search the codebase for relevant code snippets.

    Args:
        query: Natural language search query
        limit: Maximum number of results (default 5)
        collection: Collection to search (default "code")
        active_file: Currently open file path for context boosting
        intent: Search intent hint (code, docs, debug, location)
        filters: Metadata filters (language, chunk_type, app_name, layer, is_test)
        detail: Response detail level — "compact" (default) or "full"
    """
    try:
        from clew.search.models import QueryIntent

        parsed_intent = None
        if intent:
            try:
                parsed_intent = QueryIntent(intent)
            except ValueError:
                return {
                    "error": f"Invalid intent: {intent}",
                    "fix": "Use: code, docs, debug, location",
                }

        components = _get_components()
        request = SearchRequest(
            query=query,
            limit=limit,
            collection=collection,
            active_file=active_file,
            intent=parsed_intent,
            filters=filters or {},
        )
        response = await components.search_engine.search(request)
        return [_result_to_dict(r, detail) for r in response.results]
    except InvalidFilterError as e:
        return {
            "error": str(e),
            "fix": "Valid filters: language, chunk_type, app_name, layer, is_test",
        }
    except ClewError as e:
        return _error_response(e)
    except Exception as e:
        logger.exception("Unexpected error in search")
        return _error_response(e)


@mcp.tool()
async def get_context(
    file_path: str,
    line_start: int | None = None,
    line_end: int | None = None,
    include_related: bool = False,
) -> dict[str, Any]:
    """Get file content with optional related code chunks.

    Args:
        file_path: Path to the file
        line_start: Optional start line (1-indexed)
        line_end: Optional end line (1-indexed)
        include_related: If True, search for related code chunks (compact format)
    """
    try:
        path = Path(file_path)
        if not path.exists():
            return {"error": f"File not found: {file_path}", "fix": "Check the file path"}

        content = path.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()

        if line_start is not None or line_end is not None:
            start = (line_start or 1) - 1
            end = line_end or len(lines)
            lines = lines[start:end]
            content = "\n".join(lines)

        ext = path.suffix.lstrip(".")
        lang_map = {
            "py": "python",
            "ts": "typescript",
            "tsx": "tsx",
            "js": "javascript",
            "md": "markdown",
        }
        language = lang_map.get(ext, ext)

        result_dict: dict[str, Any] = {
            "file_path": file_path,
            "content": content,
            "language": language,
        }

        if include_related:
            components = _get_components()
            request = SearchRequest(query=file_path, limit=5, active_file=file_path)
            response = await components.search_engine.search(request)
            result_dict["related_chunks"] = [_compact_result_to_dict(r) for r in response.results]

        return result_dict
    except ClewError as e:
        return _error_response(e)
    except Exception as e:
        logger.exception("Unexpected error in get_context")
        return _error_response(e)


def _heuristic_explain(
    file_path: str,
    symbol: str | None,
    question: str | None,
    search_results: list[Any],
    trace_data: list[dict[str, object]] | None = None,
    cache: Any = None,
) -> str:
    """Build a structured explanation from search results and trace data.

    Always returns a non-empty string — this is the final fallback.
    """
    parts: list[str] = []
    subject = symbol or question or file_path
    parts.append(f"## {subject}\n")

    for result in search_results[:3]:
        loc = result.file_path
        if result.line_start:
            loc += f":{result.line_start}"
            if result.line_end:
                loc += f"-{result.line_end}"

        sig = getattr(result, "signature", "")
        doc = getattr(result, "docstring", "")

        parts.append(f"**{loc}** ({result.chunk_type or 'code'})")
        if sig:
            parts.append(f"```\n{sig}\n```")
        if doc:
            doc_truncated = doc[:300] + ("..." if len(doc) > 300 else "")
            parts.append(doc_truncated)

        # Add enrichment description if available
        if cache:
            chunk_id = getattr(result, "chunk_id", "")
            if chunk_id:
                enrichment = cache.get_enrichment(chunk_id)
                if enrichment:
                    desc, _keywords = enrichment
                    if desc:
                        parts.append(f"**Summary:** {desc}")

        parts.append("")

    if trace_data and symbol:
        inbound = [r for r in trace_data if str(r.get("target_entity", "")).endswith(symbol)]
        outbound = [r for r in trace_data if str(r.get("source_entity", "")).endswith(symbol)]

        if inbound:
            parts.append("### Used by")
            for r in inbound[:5]:
                parts.append(f"- `{r['source_entity']}` ({r['relationship']})")

        if outbound:
            parts.append("### Depends on")
            for r in outbound[:5]:
                parts.append(f"- `{r['target_entity']}` ({r['relationship']})")

    return "\n".join(parts) if parts else f"No additional context found for {subject}."


async def _llm_explain(
    file_path: str,
    symbol: str | None,
    question: str | None,
    search_results: list[Any],
    cache: Any,
) -> str | None:
    """Generate an LLM explanation with content-hash caching and circuit breaker.

    Returns None if LLM is unavailable or fails — caller should fall back to heuristic.
    """
    # Build cache key from inputs
    content_parts = [file_path, symbol or "", question or "", _EXPLAIN_PROMPT_VERSION]
    for r in search_results[:3]:
        content_parts.append(f"{r.file_path}:{r.line_start}")
    cache_key = hashlib.sha256("|".join(content_parts).encode()).hexdigest()

    # 1. Check cache (0ms fast path)
    cached = cache.get_description(cache_key, "explain")
    if cached:
        logger.debug("Explain cache hit: %s", cache_key[:12])
        return str(cached)

    # 2. Check circuit breaker
    if _explain_breaker.is_open:
        logger.debug("Explain LLM circuit breaker is open")
        return None

    # 3. Check API key availability
    from clew.config import Environment

    env = Environment()
    if not env.ANTHROPIC_API_KEY:
        return None

    # 4. Build prompt
    snippets: list[str] = []
    for r in search_results[:3]:
        content = getattr(r, "content", "")[:500]
        lang = r.language or ""
        desc_prefix = ""
        if cache:
            chunk_id = getattr(r, "chunk_id", "")
            if chunk_id:
                enrichment = cache.get_enrichment(chunk_id)
                if enrichment and enrichment[0]:
                    desc_prefix = f"# Description: {enrichment[0]}\n"
        header = f"{desc_prefix}# {r.file_path}:{r.line_start or ''}"
        snippets.append(f"```{lang}\n{header}\n{content}\n```")

    context = "\n\n".join(snippets)
    query = question or (f"What does `{symbol}` do?" if symbol else f"Explain {file_path}")

    prompt = (
        f"{query}\n\n"
        f"Context file: {file_path}\n\n"
        f"Relevant code:\n{context}\n\n"
        "Provide a concise explanation (2-4 sentences). "
        "Focus on what the code does and why, not implementation details."
    )

    # 5. Call LLM with timeout
    try:
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=env.ANTHROPIC_API_KEY)
        response = await asyncio.wait_for(
            client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            ),
            timeout=8.0,
        )

        block = response.content[0]
        if not hasattr(block, "text"):
            _explain_breaker.record_failure()
            return None

        text: str = block.text.strip()
        if not text:
            _explain_breaker.record_failure()
            return None

        _explain_breaker.record_success()
        cache.set_description(cache_key, "explain", text)
        logger.debug("Explain LLM response cached: %s", cache_key[:12])
        return text

    except asyncio.TimeoutError:
        logger.warning("Explain LLM timed out (8s)")
        _explain_breaker.record_failure()
        return None
    except Exception:
        logger.warning("Explain LLM call failed", exc_info=True)
        _explain_breaker.record_failure()
        return None


@mcp.tool()
async def explain(
    file_path: str,
    symbol: str | None = None,
    question: str | None = None,
    detail: str = "compact",
) -> dict[str, Any]:
    """Explain a symbol or answer a question about code in a file.

    Uses a fallback cascade: cached LLM response → live LLM call → heuristic
    explanation from search results and relationship graph. Always returns
    an explanation.

    Args:
        file_path: Path to the file for context
        symbol: Symbol name to look up (class, function, variable)
        question: Natural language question about the code
        detail: Response detail level — "compact" (default) or "full"
    """
    try:
        query = symbol or question or file_path
        components = _get_components()

        # Search for relevant chunks
        request = SearchRequest(query=query, limit=10, active_file=file_path)
        response = await components.search_engine.search(request)

        # Post-filter: prefer same language, keep high-confidence cross-language
        source_lang = detect_language(file_path)
        if source_lang != "unknown":
            filtered = [r for r in response.results if r.language == source_lang or r.score >= 0.6]
        else:
            filtered = response.results
        filtered = filtered[:5]

        # Get trace data for richer heuristic explanations
        trace_data: list[dict[str, object]] | None = None
        if symbol:
            entity = f"{file_path}::{symbol}"
            resolved = components.cache.resolve_entity(entity, context_file=file_path)
            trace_rels = components.cache.traverse_relationships(resolved, max_depth=1)
            if trace_rels:
                trace_data = trace_rels

        # Fallback cascade: LLM → heuristic
        explanation: str | None = None
        explanation_source = "heuristic"

        if components.config.search.explain_llm_enabled:
            explanation = await _llm_explain(
                file_path, symbol, question, filtered, components.cache
            )
            if explanation:
                explanation_source = "llm"

        if not explanation:
            explanation = _heuristic_explain(
                file_path, symbol, question, filtered, trace_data, cache=components.cache
            )

        return {
            "file_path": file_path,
            "symbol": symbol,
            "question": question,
            "explanation": explanation,
            "explanation_source": explanation_source,
            "related_chunks": [_result_to_dict(r, detail) for r in filtered],
        }
    except ClewError as e:
        return _error_response(e)
    except Exception as e:
        logger.exception("Unexpected error in explain")
        return _error_response(e)


@mcp.tool()
async def trace(
    entity: str,
    direction: str = "both",
    max_depth: int = 2,
    relationship_types: list[str] | None = None,
    language: str | None = None,
) -> dict[str, object]:
    """Trace code relationships for an entity.

    Shows what imports, calls, inherits from, or depends on the given entity.
    Useful for understanding code dependencies and impact analysis.

    Args:
        entity: Entity identifier (e.g., "app/main.py::Foo")
        direction: "inbound" (dependents), "outbound" (dependencies), or "both"
        max_depth: How many hops to follow (1-5, default 2)
        relationship_types: Optional filter (e.g., ["imports", "calls", "inherits"])
        language: Prefer entities in this language (e.g., "python", "typescript")
    """
    try:
        components = _get_components()
        clamped_depth = max(1, min(5, max_depth))

        resolved = components.cache.resolve_entity(entity, language=language)

        relationships = components.cache.traverse_relationships(
            resolved,
            direction=direction,
            max_depth=clamped_depth,
            relationship_types=relationship_types,
        )

        result: dict[str, object] = {
            "entity": entity,
            "relationships": relationships,
        }
        if resolved != entity:
            result["resolved_entity"] = resolved

        return result
    except Exception as e:
        logger.exception("Unexpected error in trace")
        return {
            "error": f"Failed to trace relationships: {e}",
            "fix": "Ensure the codebase has been indexed. Run: clew index --full",
        }


@mcp.tool()
async def index_status(
    action: str = "status",
    project_root: str | None = None,
) -> dict[str, Any]:
    """Check index status or trigger re-indexing.

    Args:
        action: "status" to check index state, "trigger" to start indexing
        project_root: Project root directory (for trigger action)
    """
    try:
        components = _get_components()

        if action == "status":
            healthy = components.qdrant.health_check()
            collections: dict[str, int] = {}
            for name in ["code", "docs"]:
                if components.qdrant.collection_exists(name):
                    collections[name] = components.qdrant.collection_count(name)

            last_commit = components.cache.get_last_indexed_commit("code")

            # Staleness detection
            staleness_info: dict[str, object] = {}
            if project_root:
                from clew.indexer.git_tracker import GitChangeTracker

                tracker = GitChangeTracker(Path(project_root))
                staleness = tracker.check_staleness(last_commit)
                staleness_info = {
                    "is_stale": staleness.is_stale,
                    "commits_behind": staleness.commits_behind,
                    "has_uncommitted_changes": staleness.has_uncommitted_changes,
                    "current_commit": staleness.current_commit,
                }

            return {
                "indexed": bool(collections),
                "qdrant_healthy": healthy,
                "collections": collections,
                "last_commit": last_commit,
                **staleness_info,
            }

        if action == "trigger":
            if not project_root:
                return {
                    "error": "project_root is required for trigger action",
                    "fix": "Provide project_root parameter",
                }

            root = Path(project_root)
            if not root.is_dir():
                return {
                    "error": f"Not a directory: {project_root}",
                    "fix": "Check the project_root path",
                }

            # Discover files
            from clew.discovery import discover_files

            files = discover_files(root, components.config)

            components.qdrant.ensure_collection("code", dense_dim=1024)
            result = await components.indexing_pipeline.index_files(files, collection="code")

            # Save commit hash after successful indexing
            from clew.indexer.git_tracker import GitChangeTracker

            tracker = GitChangeTracker(root)
            commit = tracker.get_current_commit()
            if commit:
                components.cache.set_last_indexed_commit("code", commit)

            return {
                "triggered": True,
                "files_processed": result.files_processed,
                "chunks_created": result.chunks_created,
                "files_skipped": result.files_skipped,
                "errors": result.errors,
            }

        return {"error": f"Unknown action: {action}", "fix": "Use 'status' or 'trigger'"}

    except ClewError as e:
        return _error_response(e)
    except Exception as e:
        logger.exception("Unexpected error in index_status")
        return _error_response(e)
