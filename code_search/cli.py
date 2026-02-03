"""Typer CLI for code-search."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

app = typer.Typer(help="Semantic code search tool")
console = Console(stderr=True)


@app.command()
def index(
    project_root: Path = typer.Argument(".", help="Project root directory"),
    config: Path = typer.Option("config.yaml", "--config", "-c", help="Config file path"),
    full: bool = typer.Option(False, "--full", help="Full reindex (ignore change detection)"),
    files: list[str] | None = typer.Option(None, "--files", "-f", help="Specific files to index"),
) -> None:
    """Index the codebase for semantic search."""
    from code_search.exceptions import CodeSearchError
    from code_search.factory import create_components
    from code_search.indexer.change_detector import ChangeDetector

    try:
        components = create_components(config_path=config if config.exists() else None)
    except CodeSearchError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from None

    # Ensure collection exists
    components.qdrant.ensure_collection("code", dense_dim=1024)

    # Discover files
    root = project_root.resolve()
    if files:
        file_paths = [Path(f) for f in files]
    else:
        from code_search.discovery import discover_files

        file_paths = discover_files(root, components.config)

    if not file_paths:
        console.print("[yellow]No files found to index.[/yellow]")
        return

    # Change detection (unless --full)
    if full or files:
        to_index = file_paths
        console.print(f"[bold]Indexing {len(to_index)} files (full)...[/bold]")
    else:
        detector = ChangeDetector(root, components.cache)
        changes = detector.detect_changes([str(p) for p in file_paths])
        to_index = [Path(f) for f in changes.added + changes.modified]

        if not to_index:
            console.print("[green]No changes detected. Index is up to date.[/green]")
            return

        console.print(
            f"[bold]Detected changes ({changes.source}):[/bold] "
            f"{len(changes.added)} added, {len(changes.modified)} modified, "
            f"{len(changes.deleted)} deleted, {len(changes.unchanged)} unchanged"
        )

    # Run indexing
    result = asyncio.run(
        components.indexing_pipeline.index_files(
            to_index,
            collection="code",
            delete_before_upsert=not full,
        )
    )

    # Save commit hash
    if not files:
        detector_for_commit = ChangeDetector(root, components.cache)
        commit = detector_for_commit.get_current_commit()
        if commit:
            components.cache.set_last_indexed_commit("code", commit)

    # Print summary
    console.print(
        f"[green]Done![/green] {result.files_processed} files, {result.chunks_created} chunks"
    )
    if result.files_skipped:
        console.print(f"[yellow]Skipped: {result.files_skipped} files[/yellow]")
    if result.errors:
        for err in result.errors[:5]:
            console.print(f"[red]  {err}[/red]")


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
    limit: int = typer.Option(10, "--limit", "-n", help="Maximum results"),
    collection: str = typer.Option("code", "--collection", "-c", help="Collection to search"),
    active_file: str | None = typer.Option(
        None, "--active-file", "-a", help="Current file for context"
    ),
    intent: str | None = typer.Option(
        None, "--intent", "-i", help="Search intent (code/docs/debug/location)"
    ),
    language: str | None = typer.Option(None, "--language", "-l", help="Filter by language"),
    chunk_type: str | None = typer.Option(None, "--chunk-type", help="Filter by chunk type"),
    raw: bool = typer.Option(False, "--raw", help="Output raw JSON"),
) -> None:
    """Search the codebase."""
    from code_search.exceptions import CodeSearchError
    from code_search.factory import create_components
    from code_search.search.models import QueryIntent, SearchRequest

    try:
        components = create_components()
    except CodeSearchError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from None

    parsed_intent = None
    if intent:
        try:
            parsed_intent = QueryIntent(intent)
        except ValueError:
            console.print(f"[red]Invalid intent: {intent}. Use: code, docs, debug, location[/red]")
            raise typer.Exit(1) from None

    filters: dict[str, str] = {}
    if language:
        filters["language"] = language
    if chunk_type:
        filters["chunk_type"] = chunk_type

    request = SearchRequest(
        query=query,
        limit=limit,
        collection=collection,
        active_file=active_file,
        intent=parsed_intent,
        filters=filters,
    )

    response = asyncio.run(components.search_engine.search(request))

    if raw:
        results = [
            {
                "file_path": r.file_path,
                "content": r.content,
                "score": r.score,
                "chunk_type": r.chunk_type,
                "line_start": r.line_start,
                "line_end": r.line_end,
                "language": r.language,
                "class_name": r.class_name,
                "function_name": r.function_name,
            }
            for r in response.results
        ]
        # Print JSON to stdout (not stderr console)
        print(json.dumps(results, indent=2))
        return

    if not response.results:
        console.print("[yellow]No results found.[/yellow]")
        return

    console.print(
        f"[dim]Query: {response.query_enhanced} | Intent: {response.intent.value} | "
        f"Candidates: {response.total_candidates}[/dim]\n"
    )

    for _i, result in enumerate(response.results, 1):
        title = f"{result.file_path}"
        if result.line_start:
            title += f":{result.line_start}"
            if result.line_end:
                title += f"-{result.line_end}"
        title += f"  [dim](score: {result.score:.3f})[/dim]"

        # Truncate content for display
        content = result.content
        if len(content) > 500:
            content = content[:500] + "\n..."

        console.print(Panel(content, title=title, title_align="left", border_style="blue"))


@app.command()
def status() -> None:
    """Show system health and index statistics."""
    from code_search.exceptions import CodeSearchError
    from code_search.factory import create_components

    try:
        components = create_components()
    except CodeSearchError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from None

    table = Table(title="code-search status")
    table.add_column("Component", style="bold")
    table.add_column("Status")

    # Qdrant health
    healthy = components.qdrant.health_check()
    table.add_row("Qdrant", "[green]healthy[/green]" if healthy else "[red]unreachable[/red]")

    # Collections
    for name in ["code", "docs"]:
        if components.qdrant.collection_exists(name):
            count = components.qdrant.collection_count(name)
            table.add_row(f"Collection: {name}", f"{count} chunks")
        else:
            table.add_row(f"Collection: {name}", "[dim]not created[/dim]")

    # Last indexed commit
    last_commit = components.cache.get_last_indexed_commit("code")
    table.add_row("Last commit", last_commit or "[dim]none[/dim]")

    console.print(table)


@app.command()
def serve() -> None:
    """Start the MCP server for Claude Code integration."""
    from code_search.mcp_server import mcp as mcp_server

    mcp_server.run()
