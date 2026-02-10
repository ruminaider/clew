"""MCP server exposing code-search tools for Claude Code."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from code_search.exceptions import (
    CodeSearchError,
    InvalidFilterError,
    QdrantConnectionError,
    VoyageAuthError,
)
from code_search.factory import Components, create_components
from code_search.search.models import SearchRequest

logger = logging.getLogger(__name__)

mcp = FastMCP("code-search")

# Lazy singleton for components
_components: Components | None = None


def _get_components() -> Components:
    """Get or create components singleton."""
    global _components  # noqa: PLW0603
    if _components is None:
        _components = create_components()
    return _components


def _result_to_dict(result: Any) -> dict[str, Any]:
    """Convert a SearchResult to a dict for MCP output."""
    return {
        "file_path": result.file_path,
        "content": result.content,
        "score": result.score,
        "chunk_type": result.chunk_type,
        "line_start": result.line_start,
        "line_end": result.line_end,
        "language": result.language,
        "class_name": result.class_name,
        "function_name": result.function_name,
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
    limit: int = 10,
    collection: str = "code",
    active_file: str | None = None,
    intent: str | None = None,
    filters: dict[str, str] | None = None,
) -> list[dict[str, Any]] | dict[str, str]:
    """Search the codebase for relevant code snippets.

    Args:
        query: Natural language search query
        limit: Maximum number of results (default 10)
        collection: Collection to search (default "code")
        active_file: Currently open file path for context boosting
        intent: Search intent hint (code, docs, debug, location)
        filters: Metadata filters (language, chunk_type, app_name, layer, is_test)
    """
    try:
        from code_search.search.models import QueryIntent

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
        return [_result_to_dict(r) for r in response.results]
    except InvalidFilterError as e:
        return {
            "error": str(e),
            "fix": "Valid filters: language, chunk_type, app_name, layer, is_test",
        }
    except CodeSearchError as e:
        return _error_response(e)
    except Exception as e:
        logger.exception("Unexpected error in search")
        return _error_response(e)


@mcp.tool()
async def get_context(
    file_path: str,
    line_start: int | None = None,
    line_end: int | None = None,
) -> dict[str, Any]:
    """Get file content with related code chunks.

    Args:
        file_path: Path to the file
        line_start: Optional start line (1-indexed)
        line_end: Optional end line (1-indexed)
    """
    try:
        path = Path(file_path)
        if not path.exists():
            return {"error": f"File not found: {file_path}", "fix": "Check the file path"}

        content = path.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()

        # Apply line range if specified
        if line_start is not None or line_end is not None:
            start = (line_start or 1) - 1  # convert to 0-indexed
            end = line_end or len(lines)
            lines = lines[start:end]
            content = "\n".join(lines)

        # Search for related chunks
        components = _get_components()
        request = SearchRequest(query=file_path, limit=5, active_file=file_path)
        response = await components.search_engine.search(request)

        # Detect language from extension
        ext = path.suffix.lstrip(".")
        lang_map = {
            "py": "python",
            "ts": "typescript",
            "tsx": "tsx",
            "js": "javascript",
            "md": "markdown",
        }
        language = lang_map.get(ext, ext)

        return {
            "file_path": file_path,
            "content": content,
            "language": language,
            "related_chunks": [_result_to_dict(r) for r in response.results],
        }
    except CodeSearchError as e:
        return _error_response(e)
    except Exception as e:
        logger.exception("Unexpected error in get_context")
        return _error_response(e)


@mcp.tool()
async def explain(
    file_path: str,
    symbol: str | None = None,
    question: str | None = None,
) -> dict[str, Any]:
    """Search for context about a symbol or question in a file.

    Args:
        file_path: Path to the file for context
        symbol: Symbol name to look up (class, function, variable)
        question: Natural language question about the code
    """
    try:
        query = symbol or question or file_path

        components = _get_components()
        request = SearchRequest(query=query, limit=10, active_file=file_path)
        response = await components.search_engine.search(request)

        return {
            "file_path": file_path,
            "symbol": symbol,
            "question": question,
            "related_chunks": [_result_to_dict(r) for r in response.results],
        }
    except CodeSearchError as e:
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

        relationships = components.cache.traverse_relationships(
            entity,
            direction=direction,
            max_depth=clamped_depth,
            relationship_types=relationship_types,
        )

        return {
            "entity": entity,
            "relationships": relationships,
        }
    except Exception as e:
        logger.exception("Unexpected error in trace")
        return {
            "error": f"Failed to trace relationships: {e}",
            "fix": "Ensure the codebase has been indexed. Run: code-search index --full",
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
            from code_search.discovery import discover_files

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

    except CodeSearchError as e:
        return _error_response(e)
    except Exception as e:
        logger.exception("Unexpected error in index_status")
        return _error_response(e)
