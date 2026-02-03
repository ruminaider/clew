"""Tests for MCP server tools."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

from code_search.mcp_server import (
    _error_response,
    _result_to_dict,
    explain,
    get_context,
    index_status,
    search,
)


def _mock_search_result(**overrides):
    """Create a mock SearchResult with defaults."""
    defaults = {
        "file_path": "src/main.py",
        "content": "def hello(): pass",
        "score": 0.95,
        "chunk_type": "function",
        "line_start": 1,
        "line_end": 1,
        "language": "python",
        "class_name": "",
        "function_name": "hello",
    }
    defaults.update(overrides)
    return Mock(**defaults)


def _mock_components():
    """Create mock Components with common defaults."""
    components = Mock()
    components.search_engine.search = AsyncMock()
    components.indexing_pipeline.index_files = AsyncMock()
    components.qdrant.health_check.return_value = True
    components.qdrant.collection_exists.return_value = True
    components.qdrant.collection_count.return_value = 42
    components.qdrant.ensure_collection = Mock()
    components.cache.get_last_indexed_commit.return_value = "abc123"
    return components


class TestResultToDict:
    def test_converts_all_fields(self):
        result = _mock_search_result()
        d = _result_to_dict(result)
        assert d["file_path"] == "src/main.py"
        assert d["content"] == "def hello(): pass"
        assert d["score"] == 0.95
        assert d["chunk_type"] == "function"
        assert d["line_start"] == 1
        assert d["line_end"] == 1
        assert d["language"] == "python"
        assert d["class_name"] == ""
        assert d["function_name"] == "hello"

    def test_preserves_custom_values(self):
        result = _mock_search_result(
            file_path="lib/utils.ts",
            content="export function parse() {}",
            score=0.72,
            chunk_type="class",
            line_start=10,
            line_end=25,
            language="typescript",
            class_name="Parser",
            function_name="parse",
        )
        d = _result_to_dict(result)
        assert d["file_path"] == "lib/utils.ts"
        assert d["content"] == "export function parse() {}"
        assert d["score"] == 0.72
        assert d["chunk_type"] == "class"
        assert d["line_start"] == 10
        assert d["line_end"] == 25
        assert d["language"] == "typescript"
        assert d["class_name"] == "Parser"
        assert d["function_name"] == "parse"


class TestErrorResponse:
    def test_qdrant_connection_error(self):
        from code_search.exceptions import QdrantConnectionError

        err = QdrantConnectionError("http://localhost:6333")
        resp = _error_response(err)
        assert "error" in resp
        assert resp["fix"] == "Run: docker compose up -d qdrant"

    def test_voyage_auth_error(self):
        from code_search.exceptions import VoyageAuthError

        err = VoyageAuthError()
        resp = _error_response(err)
        assert "error" in resp
        assert resp["fix"] == "Set VOYAGE_API_KEY environment variable"

    def test_generic_error(self):
        err = RuntimeError("something broke")
        resp = _error_response(err)
        assert "error" in resp
        assert "something broke" in resp["error"]
        assert resp["fix"] == "Check logs for details"

    def test_generic_code_search_error(self):
        from code_search.exceptions import CodeSearchError

        err = CodeSearchError("generic problem")
        resp = _error_response(err)
        assert "generic problem" in resp["error"]
        assert resp["fix"] == "Check logs for details"


class TestSearchTool:
    @patch("code_search.mcp_server._get_components")
    async def test_search_returns_results(self, mock_get):
        components = _mock_components()
        mock_get.return_value = components
        result = _mock_search_result()
        components.search_engine.search.return_value = Mock(results=[result])

        output = await search("hello")
        assert isinstance(output, list)
        assert len(output) == 1
        assert output[0]["file_path"] == "src/main.py"
        assert output[0]["score"] == 0.95

    @patch("code_search.mcp_server._get_components")
    async def test_search_with_custom_params(self, mock_get):
        components = _mock_components()
        mock_get.return_value = components
        components.search_engine.search.return_value = Mock(results=[])

        await search("hello", limit=5, collection="docs", active_file="src/app.py")

        call_args = components.search_engine.search.call_args[0][0]
        assert call_args.query == "hello"
        assert call_args.limit == 5
        assert call_args.collection == "docs"
        assert call_args.active_file == "src/app.py"

    @patch("code_search.mcp_server._get_components")
    async def test_search_default_params(self, mock_get):
        components = _mock_components()
        mock_get.return_value = components
        components.search_engine.search.return_value = Mock(results=[])

        await search("test query")

        call_args = components.search_engine.search.call_args[0][0]
        assert call_args.query == "test query"
        assert call_args.limit == 10
        assert call_args.collection == "code"
        assert call_args.active_file is None

    @patch("code_search.mcp_server._get_components")
    async def test_search_empty_results(self, mock_get):
        components = _mock_components()
        mock_get.return_value = components
        components.search_engine.search.return_value = Mock(results=[])

        output = await search("nonexistent")
        assert isinstance(output, list)
        assert len(output) == 0

    @patch("code_search.mcp_server._get_components")
    async def test_search_multiple_results(self, mock_get):
        components = _mock_components()
        mock_get.return_value = components
        results = [
            _mock_search_result(file_path="a.py", score=0.9),
            _mock_search_result(file_path="b.py", score=0.8),
            _mock_search_result(file_path="c.py", score=0.7),
        ]
        components.search_engine.search.return_value = Mock(results=results)

        output = await search("hello")
        assert len(output) == 3
        assert output[0]["file_path"] == "a.py"
        assert output[1]["file_path"] == "b.py"
        assert output[2]["file_path"] == "c.py"

    @patch("code_search.mcp_server._get_components")
    async def test_search_qdrant_error(self, mock_get):
        from code_search.exceptions import QdrantConnectionError

        mock_get.return_value = _mock_components()
        mock_get.return_value.search_engine.search = AsyncMock(
            side_effect=QdrantConnectionError("http://localhost:6333")
        )

        output = await search("hello")
        assert isinstance(output, dict)
        assert "error" in output
        assert output["fix"] == "Run: docker compose up -d qdrant"

    @patch("code_search.mcp_server._get_components")
    async def test_search_voyage_auth_error(self, mock_get):
        from code_search.exceptions import VoyageAuthError

        mock_get.return_value = _mock_components()
        mock_get.return_value.search_engine.search = AsyncMock(side_effect=VoyageAuthError())

        output = await search("hello")
        assert isinstance(output, dict)
        assert "error" in output
        assert "VOYAGE_API_KEY" in output["fix"]

    @patch("code_search.mcp_server._get_components")
    async def test_search_unexpected_error(self, mock_get):
        mock_get.return_value = _mock_components()
        mock_get.return_value.search_engine.search = AsyncMock(
            side_effect=RuntimeError("unexpected")
        )

        output = await search("hello")
        assert isinstance(output, dict)
        assert "error" in output
        assert output["fix"] == "Check logs for details"

    @patch("code_search.mcp_server._get_components")
    async def test_search_with_intent(self, mock_get):
        components = _mock_components()
        mock_get.return_value = components
        components.search_engine.search.return_value = Mock(results=[])

        await search("hello", intent="debug")

        call_args = components.search_engine.search.call_args[0][0]
        from code_search.search.models import QueryIntent

        assert call_args.intent == QueryIntent.DEBUG

    @patch("code_search.mcp_server._get_components")
    async def test_search_invalid_intent(self, mock_get):
        components = _mock_components()
        mock_get.return_value = components

        output = await search("hello", intent="invalid_intent")
        assert isinstance(output, dict)
        assert "error" in output
        assert "Invalid intent" in output["error"]

    @patch("code_search.mcp_server._get_components")
    async def test_search_with_filters(self, mock_get):
        components = _mock_components()
        mock_get.return_value = components
        components.search_engine.search.return_value = Mock(results=[])

        await search("hello", filters={"language": "python"})

        call_args = components.search_engine.search.call_args[0][0]
        assert call_args.filters == {"language": "python"}


class TestGetContextTool:
    @patch("code_search.mcp_server._get_components")
    async def test_reads_full_file(self, mock_get, tmp_path):
        components = _mock_components()
        mock_get.return_value = components
        components.search_engine.search.return_value = Mock(results=[])

        test_file = tmp_path / "test.py"
        test_file.write_text("line1\nline2\nline3\n")

        output = await get_context(str(test_file))
        assert output["file_path"] == str(test_file)
        assert "line1" in output["content"]
        assert "line2" in output["content"]
        assert "line3" in output["content"]
        assert output["language"] == "python"
        assert output["related_chunks"] == []

    @patch("code_search.mcp_server._get_components")
    async def test_with_line_range(self, mock_get, tmp_path):
        components = _mock_components()
        mock_get.return_value = components
        components.search_engine.search.return_value = Mock(results=[])

        test_file = tmp_path / "test.py"
        test_file.write_text("line1\nline2\nline3\nline4\n")

        output = await get_context(str(test_file), line_start=2, line_end=3)
        assert "line2" in output["content"]
        assert "line3" in output["content"]
        assert "line1" not in output["content"]
        assert "line4" not in output["content"]

    @patch("code_search.mcp_server._get_components")
    async def test_with_only_line_start(self, mock_get, tmp_path):
        components = _mock_components()
        mock_get.return_value = components
        components.search_engine.search.return_value = Mock(results=[])

        test_file = tmp_path / "test.py"
        test_file.write_text("line1\nline2\nline3\n")

        output = await get_context(str(test_file), line_start=2)
        assert "line1" not in output["content"]
        assert "line2" in output["content"]
        assert "line3" in output["content"]

    @patch("code_search.mcp_server._get_components")
    async def test_with_only_line_end(self, mock_get, tmp_path):
        components = _mock_components()
        mock_get.return_value = components
        components.search_engine.search.return_value = Mock(results=[])

        test_file = tmp_path / "test.py"
        test_file.write_text("line1\nline2\nline3\n")

        output = await get_context(str(test_file), line_end=2)
        assert "line1" in output["content"]
        assert "line2" in output["content"]
        assert "line3" not in output["content"]

    async def test_file_not_found(self):
        output = await get_context("/nonexistent/path.py")
        assert "error" in output
        assert "fix" in output
        assert "File not found" in output["error"]

    @patch("code_search.mcp_server._get_components")
    async def test_detects_typescript_language(self, mock_get, tmp_path):
        components = _mock_components()
        mock_get.return_value = components
        components.search_engine.search.return_value = Mock(results=[])

        test_file = tmp_path / "app.ts"
        test_file.write_text("const x = 1;")

        output = await get_context(str(test_file))
        assert output["language"] == "typescript"

    @patch("code_search.mcp_server._get_components")
    async def test_detects_javascript_language(self, mock_get, tmp_path):
        components = _mock_components()
        mock_get.return_value = components
        components.search_engine.search.return_value = Mock(results=[])

        test_file = tmp_path / "app.js"
        test_file.write_text("const x = 1;")

        output = await get_context(str(test_file))
        assert output["language"] == "javascript"

    @patch("code_search.mcp_server._get_components")
    async def test_detects_markdown_language(self, mock_get, tmp_path):
        components = _mock_components()
        mock_get.return_value = components
        components.search_engine.search.return_value = Mock(results=[])

        test_file = tmp_path / "readme.md"
        test_file.write_text("# Title")

        output = await get_context(str(test_file))
        assert output["language"] == "markdown"

    @patch("code_search.mcp_server._get_components")
    async def test_unknown_extension_uses_raw(self, mock_get, tmp_path):
        components = _mock_components()
        mock_get.return_value = components
        components.search_engine.search.return_value = Mock(results=[])

        test_file = tmp_path / "data.toml"
        test_file.write_text("[section]\nkey = 'value'")

        output = await get_context(str(test_file))
        assert output["language"] == "toml"

    @patch("code_search.mcp_server._get_components")
    async def test_includes_related_chunks(self, mock_get, tmp_path):
        components = _mock_components()
        mock_get.return_value = components
        result = _mock_search_result()
        components.search_engine.search.return_value = Mock(results=[result])

        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1")

        output = await get_context(str(test_file))
        assert len(output["related_chunks"]) == 1
        assert output["related_chunks"][0]["file_path"] == "src/main.py"

    @patch("code_search.mcp_server._get_components")
    async def test_search_error_during_context(self, mock_get, tmp_path):
        from code_search.exceptions import QdrantConnectionError

        components = _mock_components()
        mock_get.return_value = components
        components.search_engine.search = AsyncMock(
            side_effect=QdrantConnectionError("http://localhost:6333")
        )

        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1")

        output = await get_context(str(test_file))
        assert "error" in output
        assert output["fix"] == "Run: docker compose up -d qdrant"


class TestExplainTool:
    @patch("code_search.mcp_server._get_components")
    async def test_searches_symbol(self, mock_get):
        components = _mock_components()
        mock_get.return_value = components
        result = _mock_search_result()
        components.search_engine.search.return_value = Mock(results=[result])

        output = await explain("src/main.py", symbol="MyClass")
        assert output["file_path"] == "src/main.py"
        assert output["symbol"] == "MyClass"
        assert output["question"] is None
        assert len(output["related_chunks"]) == 1

        # Verify search was called with symbol as query
        call_args = components.search_engine.search.call_args[0][0]
        assert call_args.query == "MyClass"
        assert call_args.active_file == "src/main.py"

    @patch("code_search.mcp_server._get_components")
    async def test_searches_question(self, mock_get):
        components = _mock_components()
        mock_get.return_value = components
        components.search_engine.search.return_value = Mock(results=[])

        output = await explain("src/main.py", question="How does auth work?")
        assert output["question"] == "How does auth work?"
        assert output["symbol"] is None

        call_args = components.search_engine.search.call_args[0][0]
        assert call_args.query == "How does auth work?"

    @patch("code_search.mcp_server._get_components")
    async def test_falls_back_to_file_path(self, mock_get):
        components = _mock_components()
        mock_get.return_value = components
        components.search_engine.search.return_value = Mock(results=[])

        output = await explain("src/main.py")
        assert output["symbol"] is None
        assert output["question"] is None

        call_args = components.search_engine.search.call_args[0][0]
        assert call_args.query == "src/main.py"
        assert call_args.active_file == "src/main.py"

    @patch("code_search.mcp_server._get_components")
    async def test_symbol_takes_priority_over_question(self, mock_get):
        components = _mock_components()
        mock_get.return_value = components
        components.search_engine.search.return_value = Mock(results=[])

        output = await explain("src/main.py", symbol="MyClass", question="What is this?")
        assert output["symbol"] == "MyClass"
        assert output["question"] == "What is this?"

        call_args = components.search_engine.search.call_args[0][0]
        assert call_args.query == "MyClass"

    @patch("code_search.mcp_server._get_components")
    async def test_search_limit_is_ten(self, mock_get):
        components = _mock_components()
        mock_get.return_value = components
        components.search_engine.search.return_value = Mock(results=[])

        await explain("src/main.py", symbol="Foo")

        call_args = components.search_engine.search.call_args[0][0]
        assert call_args.limit == 10

    @patch("code_search.mcp_server._get_components")
    async def test_explain_handles_error(self, mock_get):
        from code_search.exceptions import VoyageAuthError

        mock_get.return_value = _mock_components()
        mock_get.return_value.search_engine.search = AsyncMock(side_effect=VoyageAuthError())

        output = await explain("src/main.py", symbol="MyClass")
        assert isinstance(output, dict)
        assert "error" in output
        assert "VOYAGE_API_KEY" in output["fix"]


class TestIndexStatusTool:
    @patch("code_search.mcp_server._get_components")
    async def test_status_returns_info(self, mock_get):
        components = _mock_components()
        mock_get.return_value = components

        output = await index_status(action="status")
        assert output["indexed"] is True
        assert output["qdrant_healthy"] is True
        assert output["collections"]["code"] == 42
        assert output["collections"]["docs"] == 42
        assert output["last_commit"] == "abc123"

    @patch("code_search.mcp_server._get_components")
    async def test_status_no_collections(self, mock_get):
        components = _mock_components()
        mock_get.return_value = components
        components.qdrant.collection_exists.return_value = False

        output = await index_status(action="status")
        assert output["indexed"] is False
        assert output["collections"] == {}

    @patch("code_search.mcp_server._get_components")
    async def test_status_unhealthy_qdrant(self, mock_get):
        components = _mock_components()
        mock_get.return_value = components
        components.qdrant.health_check.return_value = False

        output = await index_status(action="status")
        assert output["qdrant_healthy"] is False

    @patch("code_search.mcp_server._get_components")
    async def test_status_no_last_commit(self, mock_get):
        components = _mock_components()
        mock_get.return_value = components
        components.cache.get_last_indexed_commit.return_value = None

        output = await index_status(action="status")
        assert output["last_commit"] is None

    @patch("code_search.discovery.discover_files")
    @patch("code_search.mcp_server._get_components")
    async def test_trigger_runs_pipeline(self, mock_get, mock_discover, tmp_path):
        components = _mock_components()
        mock_get.return_value = components
        components.indexing_pipeline.index_files.return_value = Mock(
            files_processed=3, chunks_created=10, files_skipped=0, errors=[]
        )

        # Create test files
        test_py = tmp_path / "test.py"
        app_ts = tmp_path / "app.ts"
        test_py.write_text("x = 1")
        app_ts.write_text("const y = 2")
        mock_discover.return_value = [app_ts, test_py]

        output = await index_status(action="trigger", project_root=str(tmp_path))
        assert output["triggered"] is True
        assert output["files_processed"] == 3
        assert output["chunks_created"] == 10
        assert output["files_skipped"] == 0
        assert output["errors"] == []
        components.indexing_pipeline.index_files.assert_called_once()
        components.qdrant.ensure_collection.assert_called_once_with("code", dense_dim=1024)

    @patch("code_search.mcp_server._get_components")
    async def test_trigger_missing_project_root(self, mock_get):
        components = _mock_components()
        mock_get.return_value = components

        output = await index_status(action="trigger")
        assert "error" in output
        assert "project_root" in output["error"]

    @patch("code_search.mcp_server._get_components")
    async def test_trigger_invalid_directory(self, mock_get):
        components = _mock_components()
        mock_get.return_value = components

        output = await index_status(action="trigger", project_root="/nonexistent/dir")
        assert "error" in output
        assert "Not a directory" in output["error"]

    @patch("code_search.mcp_server._get_components")
    async def test_unknown_action(self, mock_get):
        components = _mock_components()
        mock_get.return_value = components

        output = await index_status(action="invalid")
        assert "error" in output
        assert "Unknown action" in output["error"]
        assert output["fix"] == "Use 'status' or 'trigger'"

    @patch("code_search.mcp_server._get_components")
    async def test_voyage_auth_error(self, mock_get):
        from code_search.exceptions import VoyageAuthError

        mock_get.side_effect = VoyageAuthError()

        output = await index_status(action="status")
        assert isinstance(output, dict)
        assert "error" in output
        assert "VOYAGE_API_KEY" in output["fix"]

    @patch("code_search.mcp_server._get_components")
    async def test_qdrant_error_on_status(self, mock_get):
        from code_search.exceptions import QdrantConnectionError

        mock_get.side_effect = QdrantConnectionError("http://localhost:6333")

        output = await index_status(action="status")
        assert isinstance(output, dict)
        assert "error" in output
        assert output["fix"] == "Run: docker compose up -d qdrant"

    @patch("code_search.discovery.discover_files")
    @patch("code_search.mcp_server._get_components")
    async def test_trigger_discovers_supported_extensions(self, mock_get, mock_discover, tmp_path):
        components = _mock_components()
        mock_get.return_value = components
        components.indexing_pipeline.index_files.return_value = Mock(
            files_processed=2, chunks_created=5, files_skipped=0, errors=[]
        )

        # discover_files filters extensions — mock it returning only supported files
        code_py = tmp_path / "code.py"
        app_tsx = tmp_path / "app.tsx"
        code_py.write_text("x = 1")
        app_tsx.write_text("export default () => <div/>")
        (tmp_path / "data.json").write_text("{}")
        (tmp_path / "notes.txt").write_text("hello")
        mock_discover.return_value = [app_tsx, code_py]

        output = await index_status(action="trigger", project_root=str(tmp_path))
        assert output["triggered"] is True

        # Verify only supported extensions were passed
        call_args = components.indexing_pipeline.index_files.call_args
        files_passed = call_args[0][0]
        extensions = {f.suffix for f in files_passed}
        assert ".json" not in extensions
        assert ".txt" not in extensions
        assert ".py" in extensions
        assert ".tsx" in extensions
