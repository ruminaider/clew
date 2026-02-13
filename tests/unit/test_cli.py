"""Tests for CLI commands."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from typer.testing import CliRunner

from clew.cli import app

runner = CliRunner()


class TestHelpCommands:
    def test_help(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Semantic code search tool" in result.stdout

    def test_index_help(self) -> None:
        result = runner.invoke(app, ["index", "--help"])
        assert result.exit_code == 0
        assert "--config" in result.stdout
        assert "--full" in result.stdout

    def test_search_help(self) -> None:
        result = runner.invoke(app, ["search", "--help"])
        assert result.exit_code == 0
        assert "--raw" in result.stdout


class TestSearchCommand:
    @patch("clew.factory.create_components")
    def test_search_returns_results(self, mock_factory: Mock) -> None:
        """Search command displays results."""
        mock_result = Mock(
            file_path="src/main.py",
            content="def hello(): pass",
            score=0.95,
            chunk_type="function",
            line_start=1,
            line_end=1,
            language="python",
            class_name="",
            function_name="hello",
        )
        mock_response = Mock(
            results=[mock_result],
            query_enhanced="hello world",
            total_candidates=5,
            intent=Mock(value="code"),
        )
        mock_factory.return_value.search_engine.search = AsyncMock(return_value=mock_response)

        result = runner.invoke(app, ["search", "hello"])
        assert result.exit_code == 0

    @patch("clew.factory.create_components")
    def test_search_raw_json(self, mock_factory: Mock) -> None:
        """Search --raw outputs valid JSON."""
        mock_result = Mock(
            file_path="src/main.py",
            content="def hello(): pass",
            score=0.95,
            chunk_type="function",
            line_start=1,
            line_end=1,
            language="python",
            class_name="",
            function_name="hello",
        )
        mock_response = Mock(
            results=[mock_result],
            query_enhanced="hello",
            total_candidates=1,
            intent=Mock(value="code"),
        )
        mock_factory.return_value.search_engine.search = AsyncMock(return_value=mock_response)

        result = runner.invoke(app, ["search", "hello", "--raw"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert data[0]["file_path"] == "src/main.py"

    @patch("clew.factory.create_components")
    def test_search_no_results(self, mock_factory: Mock) -> None:
        """Search with no results shows message."""
        mock_response = Mock(
            results=[],
            query_enhanced="xyz",
            total_candidates=0,
            intent=Mock(value="code"),
        )
        mock_factory.return_value.search_engine.search = AsyncMock(return_value=mock_response)

        result = runner.invoke(app, ["search", "xyz"])
        assert result.exit_code == 0

    @patch("clew.factory.create_components")
    def test_search_connection_error(self, mock_factory: Mock) -> None:
        """Search shows error on connection failure."""
        from clew.exceptions import QdrantConnectionError

        mock_factory.side_effect = QdrantConnectionError("http://localhost:6333")

        result = runner.invoke(app, ["search", "hello"])
        assert result.exit_code == 1

    @patch("clew.factory.create_components")
    def test_search_with_intent_flag(self, mock_factory: Mock) -> None:
        mock_response = Mock(
            results=[],
            query_enhanced="test",
            total_candidates=0,
            intent=Mock(value="debug"),
        )
        mock_factory.return_value.search_engine.search = AsyncMock(return_value=mock_response)

        result = runner.invoke(app, ["search", "test", "--intent", "debug"])
        assert result.exit_code == 0

        call_args = mock_factory.return_value.search_engine.search.call_args[0][0]
        from clew.search.models import QueryIntent

        assert call_args.intent == QueryIntent.DEBUG

    @patch("clew.factory.create_components")
    def test_search_invalid_intent_exits(self, mock_factory: Mock) -> None:
        result = runner.invoke(app, ["search", "test", "--intent", "invalid"])
        assert result.exit_code == 1


class TestStatusCommand:
    @patch("clew.factory.create_components")
    def test_status_shows_info(self, mock_factory: Mock) -> None:
        """Status command displays component info."""
        mock_components = mock_factory.return_value
        mock_components.qdrant.health_check.return_value = True
        mock_components.qdrant.collection_exists.return_value = True
        mock_components.qdrant.collection_count.return_value = 42
        mock_components.cache.get_last_indexed_commit.return_value = "abc123"

        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0


class TestIndexCommand:
    @patch("clew.discovery.discover_files")
    @patch("clew.indexer.change_detector.ChangeDetector")
    @patch("clew.factory.create_components")
    def test_index_with_full_flag(
        self, mock_factory: Mock, mock_detector_cls: Mock, mock_discover: Mock, tmp_path: Path
    ) -> None:
        """Index --full skips change detection."""
        # Create a temp file to index
        test_py = tmp_path / "test.py"
        test_py.write_text("x = 1")
        mock_discover.return_value = [test_py]
        mock_components = mock_factory.return_value
        mock_components.indexing_pipeline.index_files = AsyncMock(
            return_value=Mock(files_processed=1, chunks_created=3, files_skipped=0, errors=[])
        )

        result = runner.invoke(app, ["index", str(tmp_path), "--full"])
        assert result.exit_code == 0
        # With --full, detect_changes should NOT be called (change detection skipped)
        mock_detector_cls.return_value.detect_changes.assert_not_called()

    @patch("clew.discovery.discover_files")
    @patch("clew.factory.create_components")
    def test_full_flag_drops_collection_and_clears_cache(
        self, mock_factory: Mock, mock_discover: Mock, tmp_path: Path
    ) -> None:
        """--full calls delete_collection and clear_all_state before indexing."""
        test_py = tmp_path / "test.py"
        test_py.write_text("x = 1")
        mock_discover.return_value = [test_py]
        mock_components = mock_factory.return_value
        mock_components.indexing_pipeline.index_files = AsyncMock(
            return_value=Mock(files_processed=1, chunks_created=3, files_skipped=0, errors=[])
        )

        result = runner.invoke(app, ["index", str(tmp_path), "--full"])
        assert result.exit_code == 0
        mock_components.qdrant.delete_collection.assert_called_once_with("code")
        mock_components.cache.clear_all_state.assert_called_once_with("code")

    @patch("clew.discovery.discover_files")
    @patch("clew.factory.create_components")
    def test_incremental_does_not_drop_collection(
        self, mock_factory: Mock, mock_discover: Mock, tmp_path: Path
    ) -> None:
        """Without --full, delete_collection and clear_all_state are NOT called."""
        test_py = tmp_path / "test.py"
        test_py.write_text("x = 1")
        mock_discover.return_value = [test_py]
        mock_components = mock_factory.return_value
        mock_components.indexing_pipeline.index_files = AsyncMock(
            return_value=Mock(files_processed=1, chunks_created=3, files_skipped=0, errors=[])
        )
        # Simulate change detector returning changes
        from clew.indexer.change_detector import ChangeDetector

        mock_changes = Mock(
            added=[str(test_py)], modified=[], deleted=[], unchanged=[], source="git"
        )
        with (
            patch.object(ChangeDetector, "__init__", return_value=None),
            patch.object(ChangeDetector, "detect_changes", return_value=mock_changes),
            patch.object(ChangeDetector, "get_current_commit", return_value="abc123"),
        ):
            result = runner.invoke(app, ["index", str(tmp_path)])

        assert result.exit_code == 0
        mock_components.qdrant.delete_collection.assert_not_called()
        mock_components.cache.clear_all_state.assert_not_called()

    @patch("clew.factory.create_components")
    def test_index_connection_error(self, mock_factory: Mock) -> None:
        """Index shows error on connection failure."""
        from clew.exceptions import QdrantConnectionError

        mock_factory.side_effect = QdrantConnectionError("http://localhost:6333")

        result = runner.invoke(app, ["index", "."])
        assert result.exit_code == 1


class TestIndexNLDescriptions:
    @patch("clew.discovery.discover_files")
    @patch("clew.factory.create_components")
    def test_index_with_nl_descriptions_flag(
        self, mock_factory: Mock, mock_discover: Mock, tmp_path: Path
    ) -> None:
        """--nl-descriptions flag passes nl_descriptions=True to factory."""
        test_py = tmp_path / "test.py"
        test_py.write_text("x = 1")
        mock_discover.return_value = [test_py]
        mock_components = mock_factory.return_value
        mock_components.indexing_pipeline.index_files = AsyncMock(
            return_value=Mock(files_processed=1, chunks_created=3, files_skipped=0, errors=[])
        )

        result = runner.invoke(app, ["index", str(tmp_path), "--full", "--nl-descriptions"])
        assert result.exit_code == 0
        # Verify nl_descriptions=True was passed to create_components
        mock_factory.assert_called_once_with(config_path=None, nl_descriptions=True)

    @patch("clew.discovery.discover_files")
    @patch("clew.factory.create_components")
    def test_index_without_nl_descriptions_flag(
        self, mock_factory: Mock, mock_discover: Mock, tmp_path: Path
    ) -> None:
        """Without --nl-descriptions, nl_descriptions=False is passed."""
        test_py = tmp_path / "test.py"
        test_py.write_text("x = 1")
        mock_discover.return_value = [test_py]
        mock_components = mock_factory.return_value
        mock_components.indexing_pipeline.index_files = AsyncMock(
            return_value=Mock(files_processed=1, chunks_created=3, files_skipped=0, errors=[])
        )

        result = runner.invoke(app, ["index", str(tmp_path), "--full"])
        assert result.exit_code == 0
        mock_factory.assert_called_once_with(config_path=None, nl_descriptions=False)

    def test_nl_descriptions_in_help(self) -> None:
        """--nl-descriptions appears in help text."""
        result = runner.invoke(app, ["index", "--help"])
        assert result.exit_code == 0
        assert "--nl-descriptions" in result.stdout


class TestTraceCommand:
    @patch("clew.factory.create_components")
    def test_trace_displays_relationships(self, mock_factory: Mock) -> None:
        mock_components = mock_factory.return_value
        mock_components.cache.resolve_entity.side_effect = lambda x: x
        mock_components.cache.traverse_relationships.return_value = [
            {
                "source_entity": "app/main.py::Foo",
                "relationship": "calls",
                "target_entity": "app/utils.py::helper",
                "confidence": "inferred",
                "depth": 1,
            }
        ]
        result = runner.invoke(app, ["trace", "app/main.py::Foo"])
        assert result.exit_code == 0

    @patch("clew.factory.create_components")
    def test_trace_no_relationships(self, mock_factory: Mock) -> None:
        mock_components = mock_factory.return_value
        mock_components.cache.resolve_entity.side_effect = lambda x: x
        mock_components.cache.traverse_relationships.return_value = []
        result = runner.invoke(app, ["trace", "app/main.py::Foo"])
        assert result.exit_code == 0

    @patch("clew.factory.create_components")
    def test_trace_with_direction_flag(self, mock_factory: Mock) -> None:
        mock_components = mock_factory.return_value
        mock_components.cache.resolve_entity.side_effect = lambda x: x
        mock_components.cache.traverse_relationships.return_value = []
        result = runner.invoke(app, ["trace", "app/main.py::Foo", "--direction", "inbound"])
        assert result.exit_code == 0
        mock_components.cache.traverse_relationships.assert_called_once()

    @patch("clew.factory.create_components")
    def test_trace_raw_json(self, mock_factory: Mock) -> None:
        mock_components = mock_factory.return_value
        mock_components.cache.resolve_entity.side_effect = lambda x: x
        mock_components.cache.traverse_relationships.return_value = [
            {
                "source_entity": "a.py::Foo",
                "relationship": "imports",
                "target_entity": "b.py::Bar",
                "confidence": "static",
                "depth": 1,
            }
        ]
        result = runner.invoke(app, ["trace", "a.py::Foo", "--raw"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, dict)
        assert "relationships" in data

    @patch("clew.factory.create_components")
    def test_trace_connection_error(self, mock_factory: Mock) -> None:
        from clew.exceptions import QdrantConnectionError

        mock_factory.side_effect = QdrantConnectionError("http://localhost:6333")
        result = runner.invoke(app, ["trace", "a.py::Foo"])
        assert result.exit_code == 1


class TestServeCommand:
    @patch("clew.mcp_server.mcp")
    def test_serve_calls_mcp_run(self, mock_mcp: Mock) -> None:
        """Serve command starts MCP server."""
        result = runner.invoke(app, ["serve"])
        assert result.exit_code == 0
        mock_mcp.run.assert_called_once()
