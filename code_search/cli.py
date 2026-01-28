"""Typer CLI for code-search."""

from pathlib import Path

import typer

app = typer.Typer(help="Semantic code search tool")


@app.command()
def index(
    config: Path = typer.Option("config.yaml", "--config", "-c"),
    full: bool = typer.Option(False, "--full"),
    files: list[str] = typer.Option(None, "--files", "-f"),
) -> None:
    """Index the codebase."""
    typer.echo("Indexing not yet implemented.")


@app.command()
def status() -> None:
    """Show system health and index statistics."""
    typer.echo("Status not yet implemented.")


@app.command()
def search(
    query: str = typer.Argument(...),
    raw: bool = typer.Option(False, "--raw"),
) -> None:
    """Search the codebase."""
    typer.echo("Search not yet implemented.")
