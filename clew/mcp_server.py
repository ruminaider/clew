"""MCP server exposing clew tools for Claude Code."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

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
    return {
        "file_path": result.file_path,
        "line_start": result.line_start,
        "line_end": result.line_end,
        "score": result.score,
        "chunk_type": result.chunk_type,
        "language": result.language,
        "function_name": result.function_name,
        "class_name": result.class_name,
        "snippet": _build_snippet(result),
    }


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


@mcp.tool()
async def explain(
    file_path: str,
    symbol: str | None = None,
    question: str | None = None,
    detail: str = "compact",
) -> dict[str, Any]:
    """Search for context about a symbol or question in a file.

    Args:
        file_path: Path to the file for context
        symbol: Symbol name to look up (class, function, variable)
        question: Natural language question about the code
        detail: Response detail level — "compact" (default) or "full"
    """
    try:
        query = symbol or question or file_path

        components = _get_components()
        request = SearchRequest(query=query, limit=10, active_file=file_path)
        response = await components.search_engine.search(request)

        # Post-filter: prefer same language, keep high-confidence cross-language results
        source_lang = detect_language(file_path)
        if source_lang != "unknown":
            filtered = [r for r in response.results if r.language == source_lang or r.score >= 0.6]
        else:
            filtered = response.results

        # Limit back down to 5
        filtered = filtered[:5]

        return {
            "file_path": file_path,
            "symbol": symbol,
            "question": question,
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
) -> dict[str, object]:
    """Trace code relationships for an entity.

    Shows what imports, calls, inherits from, or depends on the given entity.
    Useful for understanding code dependencies and impact analysis.

    Args:
        entity: Entity identifier (e.g., "app/main.py::Foo")
        direction: "inbound" (dependents), "outbound" (dependencies), or "both"
        max_depth: How many hops to follow (1-5, default 2)
        relationship_types: Optional filter (e.g., ["imports", "calls", "inherits"])
    """
    try:
        components = _get_components()
        clamped_depth = max(1, min(5, max_depth))

        resolved = components.cache.resolve_entity(entity)

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

            return {
                "indexed": bool(collections),
                "qdrant_healthy": healthy,
                "collections": collections,
                "last_commit": last_commit,
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
