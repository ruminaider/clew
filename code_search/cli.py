"""Typer CLI for code-search."""

from pathlib import Path

import typer
from rich.console import Console

app = typer.Typer(help="Semantic code search tool")
console = Console()


@app.command()
def index(
    config: Path = typer.Option("config.yaml", "--config", "-c"),
    full: bool = typer.Option(False, "--full"),
    files: list[str] = typer.Option(None, "--files", "-f"),
) -> None:
    """Index the codebase."""
    console.print("[yellow]Indexing not yet implemented.[/yellow]")


@app.command()
def status() -> None:
    """Show system health and index statistics."""
    console.print("[bold]code-search status[/bold]")
    console.print("  Qdrant: [dim]not checked[/dim]")
    console.print("  Collections: [dim]none[/dim]")


@app.command()
def search(
    query: str = typer.Argument(...),
    raw: bool = typer.Option(False, "--raw"),
) -> None:
    """Search the codebase."""
    console.print("[yellow]Search not yet implemented.[/yellow]")
