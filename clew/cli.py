"""Typer CLI for clew."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

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
    nl_descriptions: bool = typer.Option(
        False,
        "--nl-descriptions",
        help="Generate NL descriptions for undocumented code (requires ANTHROPIC_API_KEY)",
    ),
) -> None:
    """Index the codebase for semantic search."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    from clew.exceptions import ClewError
    from clew.factory import create_components
    from clew.indexer.change_detector import ChangeDetector

    try:
        components = create_components(
            config_path=config if config.exists() else None,
            nl_descriptions=nl_descriptions,
            project_root=project_root,
        )
    except ClewError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from None

    # Full reindex: drop collection and clear cached state
    if full:
        console.print("[yellow]Full reindex: dropping collection and clearing cache...[/yellow]")
        components.qdrant.delete_collection("code")
        components.cache.clear_all_state("code")

    # Ensure collection exists
    components.qdrant.ensure_collection("code", dense_dim=1024)

    # Discover files
    root = project_root.resolve()
    if files:
        file_paths = [Path(f) for f in files]
    else:
        from clew.discovery import discover_files

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
    mode: str | None = typer.Option(
        None,
        "--mode",
        "-m",
        help=(
            "Search mode (default: semantic). "
            "semantic: best for questions and debugging. "
            "keyword: best for 'find all X' identifier matching. "
            "exhaustive: semantic + grep for completeness guarantees."
        ),
    ),
    exhaustive: bool = typer.Option(False, "--exhaustive", help="Shortcut for --mode exhaustive"),
    raw: bool = typer.Option(False, "--raw", help="Output raw JSON"),
    json_output: bool = typer.Option(False, "--json", help="Compact JSON to stdout"),
    full_content: bool = typer.Option(False, "--full", help="Include full content (with --json)"),
    project_root: Path | None = typer.Option(
        None, "--project-root", "-p", help="Project root directory (for cache dir resolution)"
    ),
) -> None:
    """Search the codebase."""
    from clew.exceptions import ClewError
    from clew.factory import create_components
    from clew.search.models import QueryIntent, SearchRequest

    try:
        components = create_components(project_root=project_root)
    except ClewError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from None

    parsed_intent = None
    if intent:
        try:
            parsed_intent = QueryIntent(intent)
        except ValueError:
            console.print(f"[red]Invalid intent: {intent}. Use: code, docs, debug, location[/red]")
            raise typer.Exit(1) from None

    # Mode resolution
    effective_mode = "exhaustive" if exhaustive else mode
    valid_modes = {"semantic", "keyword", "exhaustive"}
    if effective_mode and effective_mode not in valid_modes:
        console.print(
            f"[red]Invalid mode: {effective_mode}. Use: {', '.join(sorted(valid_modes))}[/red]"
        )
        raise typer.Exit(1)

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
        mode=effective_mode,
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
                "source": getattr(r, "source", "semantic"),
            }
            for r in response.results
        ]
        print(json.dumps(results, indent=2))
        return

    if json_output:
        from clew.mcp_server import _compact_result_to_dict

        results_list = []
        for r in response.results:
            d = _compact_result_to_dict(r)
            if full_content:
                d["content"] = r.content
            results_list.append(d)
        output: dict[str, Any] = {
            "query": query,
            "query_enhanced": response.query_enhanced,
            "intent": response.intent.value,
            "mode": getattr(response, "mode_used", effective_mode or "semantic"),
            "total_candidates": response.total_candidates,
            "confidence": round(response.confidence, 3),
            "results": results_list,
        }
        print(json.dumps(output, indent=2))
        return

    if not response.results:
        console.print("[yellow]No results found.[/yellow]")
        return

    mode_used = getattr(response, "mode_used", effective_mode or "semantic")
    console.print(
        f"[dim]Query: {response.query_enhanced} | Intent: {response.intent.value} | "
        f"Mode: {mode_used} | Candidates: {response.total_candidates}[/dim]"
    )
    if getattr(response, "auto_escalated", False):
        console.print("[cyan]Auto-escalated to exhaustive (low confidence)[/cyan]")
    console.print()

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

    # Show grep results if present (grep items are in results with source="grep")
    grep_items = [r for r in response.results if getattr(r, "source", "semantic") == "grep"]
    if grep_items:
        console.print(f"\n[bold]Grep results ({len(grep_items)} additional matches):[/bold]")
        grep_table = Table()
        grep_table.add_column("File", style="cyan")
        grep_table.add_column("Line", style="dim")
        grep_table.add_column("Content")
        for g in grep_items[:20]:
            grep_table.add_row(g.file_path, str(g.line_start), g.content[:100])
        console.print(grep_table)


@app.command()
def status(
    json_output: bool = typer.Option(False, "--json", help="Compact JSON to stdout"),
    project_root: Path | None = typer.Option(
        None, "--project-root", "-p", help="Project root directory (for cache dir resolution)"
    ),
) -> None:
    """Show system health and index statistics."""
    from clew.exceptions import ClewError
    from clew.factory import create_components

    try:
        components = create_components(project_root=project_root)
    except ClewError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from None

    # Qdrant health
    healthy = components.qdrant.health_check()

    # Collections
    collections: dict[str, int | None] = {}
    for name in ["code", "docs"]:
        if components.qdrant.collection_exists(name):
            collections[name] = components.qdrant.collection_count(name)
        else:
            collections[name] = None

    # Last indexed commit
    last_commit = components.cache.get_last_indexed_commit("code")

    # Staleness detection
    from clew.indexer.git_tracker import GitChangeTracker

    tracker = GitChangeTracker(Path(".").resolve())
    staleness = tracker.check_staleness(last_commit)

    if json_output:
        output: dict[str, Any] = {
            "qdrant_healthy": healthy,
            "collections": {
                name: {"chunks": count} if count is not None else None
                for name, count in collections.items()
            },
            "last_commit": last_commit,
            "is_stale": staleness.is_stale,
            "commits_behind": staleness.commits_behind,
            "has_uncommitted_changes": staleness.has_uncommitted_changes,
        }
        print(json.dumps(output, indent=2))
        return

    table = Table(title="clew status")
    table.add_column("Component", style="bold")
    table.add_column("Status")

    table.add_row("Qdrant", "[green]healthy[/green]" if healthy else "[red]unreachable[/red]")

    for name, count in collections.items():
        if count is not None:
            table.add_row(f"Collection: {name}", f"{count} chunks")
        else:
            table.add_row(f"Collection: {name}", "[dim]not created[/dim]")

    table.add_row("Last commit", last_commit or "[dim]none[/dim]")

    if staleness.is_stale:
        stale_msg = "[yellow]stale[/yellow]"
        if staleness.commits_behind > 0:
            stale_msg += f" ({staleness.commits_behind} commits behind)"
        elif staleness.commits_behind == -1:
            stale_msg += " (unknown distance)"
        if staleness.has_uncommitted_changes:
            stale_msg += " + uncommitted changes"
    else:
        stale_msg = "[green]up to date[/green]"
    table.add_row("Index freshness", stale_msg)

    console.print(table)


@app.command()
def trace(
    entity: str = typer.Argument(..., help="Entity to trace (e.g., 'app/main.py::Foo')"),
    direction: str = typer.Option("both", "--direction", "-d", help="inbound, outbound, or both"),
    max_depth: int = typer.Option(2, "--depth", help="Max hops (1-5)"),
    relationship_types: list[str] | None = typer.Option(
        None, "--type", "-t", help="Filter relationship types"
    ),
    language: str | None = typer.Option(
        None, "--language", "-l", help="Prefer entities in this language (python, typescript, etc.)"
    ),
    raw: bool = typer.Option(False, "--raw", help="Output raw JSON"),
    json_output: bool = typer.Option(False, "--json", help="Compact JSON to stdout"),
    project_root: Path | None = typer.Option(
        None, "--project-root", "-p", help="Project root directory (for cache dir resolution)"
    ),
) -> None:
    """Trace code relationships for an entity."""
    from clew.exceptions import ClewError
    from clew.factory import create_components

    try:
        components = create_components(project_root=project_root)
    except ClewError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from None

    clamped_depth = max(1, min(5, max_depth))
    resolved = components.cache.resolve_entity(entity, language=language)
    if resolved != entity:
        console.print(f"[dim]Resolved: {entity} → {resolved}[/dim]")
    relationships = components.cache.traverse_relationships(
        resolved,
        direction=direction,
        max_depth=clamped_depth,
        relationship_types=relationship_types,
    )

    if raw:
        print(json.dumps({"entity": entity, "relationships": relationships}, indent=2))
        return

    if json_output:
        output = {
            "entity": entity,
            "resolved_entity": resolved,
            "direction": direction,
            "max_depth": clamped_depth,
            "relationships": relationships,
        }
        print(json.dumps(output, indent=2))
        return

    if not relationships:
        console.print(f"[yellow]No relationships found for {entity}[/yellow]")
        return

    table = Table(title=f"Relationships for {entity}")
    table.add_column("Depth", style="dim")
    table.add_column("Source")
    table.add_column("Relationship", style="bold")
    table.add_column("Target")
    table.add_column("Confidence", style="dim")

    for rel in relationships:
        table.add_row(
            str(rel["depth"]),
            str(rel["source_entity"]),
            str(rel["relationship"]),
            str(rel["target_entity"]),
            str(rel["confidence"]),
        )

    console.print(table)


@app.command()
def reembed(
    project_root: Path = typer.Argument(".", help="Project root directory"),
    config: Path = typer.Option("config.yaml", "--config", "-c", help="Config file path"),
) -> None:
    """Re-embed enriched chunks into Qdrant.

    Reads enrichment data (description + keywords) from SQLite cache
    and re-embeds all 3 named vectors with full content.
    Run this after enrichment data has been written to the cache.
    """
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    from clew.exceptions import ClewError
    from clew.factory import create_components

    try:
        components = create_components(
            config_path=config if config.exists() else None,
            project_root=project_root,
        )
    except ClewError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from None

    # Ensure collection exists
    components.qdrant.ensure_collection("code", dense_dim=1024)

    console.print("[bold]Re-embedding enriched chunks...[/bold]")
    result = asyncio.run(components.indexing_pipeline.reembed(collection="code"))

    console.print(
        f"[green]Done![/green] {result.chunks_created} chunks re-embedded "
        f"from {result.files_processed} files"
    )
    if result.errors:
        for err in result.errors[:5]:
            console.print(f"[red]  {err}[/red]")


@app.command()
def serve() -> None:
    """Start the MCP server for Claude Code integration."""
    from clew.mcp_server import mcp as mcp_server

    mcp_server.run()
