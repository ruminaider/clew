"""Tests for CLI interface."""

from typer.testing import CliRunner

from code_search.cli import app

runner = CliRunner()


class TestCLI:
    def test_help(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Semantic code search tool" in result.stdout

    def test_index_help(self) -> None:
        result = runner.invoke(app, ["index", "--help"])
        assert result.exit_code == 0
        assert "--config" in result.stdout
        assert "--full" in result.stdout

    def test_status_runs(self) -> None:
        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0

    def test_search_help(self) -> None:
        result = runner.invoke(app, ["search", "--help"])
        assert result.exit_code == 0
        assert "--raw" in result.stdout
