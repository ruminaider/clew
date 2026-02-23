"""Tests for MCP server tools."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

from clew.mcp_server import (
    _error_response,
    _heuristic_explain,
    _result_to_dict,
    explain,
    get_context,
    index_status,
    search,
    trace,
)


def _mock_search_result(**overrides):
    """Create a mock SearchResult with defaults."""
    defaults = {
        "file_path": "src/main.py",
        "content": 'def hello():\n    """Say hello."""\n    print(\'hello\')\n    return True',
        "score": 0.95,
        "chunk_type": "function",
        "line_start": 1,
        "line_end": 4,
        "language": "python",
        "class_name": "",
        "function_name": "hello",
        "signature": "def hello():",
        "docstring": "Say hello.",
        "app_name": "",
        "layer": "",
        "chunk_id": "src/main.py::function::hello",
        "source": "semantic",
        "context": "",
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
    components.cache.resolve_entity.side_effect = lambda e, **kwargs: e
    components.cache.traverse_relationships.return_value = []
    return components


class TestResultToDict:
    def test_converts_all_fields(self):
        result = _mock_search_result()
        d = _result_to_dict(result, detail="full")
        assert d["file_path"] == "src/main.py"
        expected = 'def hello():\n    """Say hello."""\n    print(\'hello\')\n    return True'
        assert d["content"] == expected
        assert d["score"] == 0.95
        assert d["chunk_type"] == "function"
        assert d["line_start"] == 1
        assert d["line_end"] == 4
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
        d = _result_to_dict(result, detail="full")
        assert d["file_path"] == "lib/utils.ts"
        assert d["content"] == "export function parse() {}"
        assert d["score"] == 0.72
        assert d["chunk_type"] == "class"
        assert d["line_start"] == 10
        assert d["line_end"] == 25
        assert d["language"] == "typescript"
        assert d["class_name"] == "Parser"
        assert d["function_name"] == "parse"


class TestResultDictNewFields:
    """Test enriched and importance_score fields in result dicts."""

    def test_importance_score_included_when_nonzero(self):
        result = _mock_search_result(importance_score=0.75)
        d = _result_to_dict(result, detail="compact")
        assert d["importance_score"] == 0.75

    def test_importance_score_omitted_when_zero(self):
        result = _mock_search_result(importance_score=0.0)
        d = _result_to_dict(result, detail="compact")
        assert "importance_score" not in d

    def test_enriched_included_when_present(self):
        result = _mock_search_result(enriched=True)
        d = _result_to_dict(result, detail="compact")
        assert d["enriched"] is True

    def test_enriched_false_included(self):
        result = _mock_search_result(enriched=False)
        d = _result_to_dict(result, detail="compact")
        assert d["enriched"] is False

    def test_enriched_omitted_when_not_present(self):
        """When result has no enriched attribute, it is not in the dict."""
        result = _mock_search_result()
        # Mock objects return Mock for any attribute by default,
        # so we need spec to avoid that — instead, just delete the attr
        del result.enriched
        d = _result_to_dict(result, detail="compact")
        assert "enriched" not in d

    def test_full_detail_includes_new_fields(self):
        result = _mock_search_result(importance_score=0.5, enriched=True)
        d = _result_to_dict(result, detail="full")
        assert d["importance_score"] == 0.5
        assert d["enriched"] is True
        assert "content" in d


class TestErrorResponse:
    def test_qdrant_connection_error(self):
        from clew.exceptions import QdrantConnectionError

        err = QdrantConnectionError("http://localhost:6333")
        resp = _error_response(err)
        assert "error" in resp
        assert resp["fix"] == "Run: docker compose up -d qdrant"

    def test_voyage_auth_error(self):
        from clew.exceptions import VoyageAuthError

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

    def test_generic_clew_error(self):
        from clew.exceptions import ClewError

        err = ClewError("generic problem")
        resp = _error_response(err)
        assert "generic problem" in resp["error"]
        assert resp["fix"] == "Check logs for details"


def _mock_search_response(**overrides):
    """Create a mock SearchResponse with defaults."""
    from clew.search.models import QueryIntent, SuggestionType

    defaults = {
        "results": [],
        "query_enhanced": "test",
        "total_candidates": 0,
        "intent": QueryIntent.CODE,
        "confidence": 1.0,
        "confidence_label": "high",
        "suggestion_type": SuggestionType.NONE,
        "mode_used": "semantic",
        "auto_escalated": False,
    }
    defaults.update(overrides)
    return Mock(**defaults)


class TestSearchTool:
    @patch("clew.mcp_server._get_components")
    async def test_search_returns_results(self, mock_get):
        components = _mock_components()
        mock_get.return_value = components
        result = _mock_search_result()
        components.search_engine.search.return_value = _mock_search_response(
            results=[result], total_candidates=1
        )

        output = await search("hello")
        assert isinstance(output, dict)
        assert "results" in output
        assert len(output["results"]) == 1
        assert output["results"][0]["file_path"] == "src/main.py"
        assert output["results"][0]["score"] == 0.95
        assert "confidence" in output

    @patch("clew.mcp_server._get_components")
    async def test_search_with_custom_params(self, mock_get):
        components = _mock_components()
        mock_get.return_value = components
        components.search_engine.search.return_value = _mock_search_response()

        await search("hello", limit=5, collection="docs", active_file="src/app.py")

        call_args = components.search_engine.search.call_args[0][0]
        assert call_args.query == "hello"
        assert call_args.limit == 5
        assert call_args.collection == "docs"
        assert call_args.active_file == "src/app.py"

    @patch("clew.mcp_server._get_components")
    async def test_search_default_params(self, mock_get):
        components = _mock_components()
        mock_get.return_value = components
        components.search_engine.search.return_value = _mock_search_response()

        await search("test query")

        call_args = components.search_engine.search.call_args[0][0]
        assert call_args.query == "test query"
        assert call_args.limit == 5
        assert call_args.collection == "code"
        assert call_args.active_file is None

    @patch("clew.mcp_server._get_components")
    async def test_search_empty_results(self, mock_get):
        components = _mock_components()
        mock_get.return_value = components
        components.search_engine.search.return_value = _mock_search_response()

        output = await search("nonexistent")
        assert isinstance(output, dict)
        assert len(output["results"]) == 0

    @patch("clew.mcp_server._get_components")
    async def test_search_multiple_results(self, mock_get):
        components = _mock_components()
        mock_get.return_value = components
        results = [
            _mock_search_result(file_path="a.py", score=0.9),
            _mock_search_result(file_path="b.py", score=0.8),
            _mock_search_result(file_path="c.py", score=0.7),
        ]
        components.search_engine.search.return_value = _mock_search_response(
            results=results, total_candidates=3
        )

        output = await search("hello")
        assert len(output["results"]) == 3
        assert output["results"][0]["file_path"] == "a.py"
        assert output["results"][1]["file_path"] == "b.py"
        assert output["results"][2]["file_path"] == "c.py"

    @patch("clew.mcp_server._get_components")
    async def test_search_qdrant_error(self, mock_get):
        from clew.exceptions import QdrantConnectionError

        mock_get.return_value = _mock_components()
        mock_get.return_value.search_engine.search = AsyncMock(
            side_effect=QdrantConnectionError("http://localhost:6333")
        )

        output = await search("hello")
        assert isinstance(output, dict)
        assert "error" in output
        assert output["fix"] == "Run: docker compose up -d qdrant"

    @patch("clew.mcp_server._get_components")
    async def test_search_voyage_auth_error(self, mock_get):
        from clew.exceptions import VoyageAuthError

        mock_get.return_value = _mock_components()
        mock_get.return_value.search_engine.search = AsyncMock(side_effect=VoyageAuthError())

        output = await search("hello")
        assert isinstance(output, dict)
        assert "error" in output
        assert "VOYAGE_API_KEY" in output["fix"]

    @patch("clew.mcp_server._get_components")
    async def test_search_unexpected_error(self, mock_get):
        mock_get.return_value = _mock_components()
        mock_get.return_value.search_engine.search = AsyncMock(
            side_effect=RuntimeError("unexpected")
        )

        output = await search("hello")
        assert isinstance(output, dict)
        assert "error" in output
        assert output["fix"] == "Check logs for details"

    @patch("clew.mcp_server._get_components")
    async def test_search_with_intent(self, mock_get):
        components = _mock_components()
        mock_get.return_value = components
        components.search_engine.search.return_value = _mock_search_response()

        await search("hello", intent="debug")

        call_args = components.search_engine.search.call_args[0][0]
        from clew.search.models import QueryIntent

        assert call_args.intent == QueryIntent.DEBUG

    @patch("clew.mcp_server._get_components")
    async def test_search_with_enumeration_intent(self, mock_get):
        components = _mock_components()
        mock_get.return_value = components
        components.search_engine.search.return_value = _mock_search_response()

        await search("hello", intent="enumeration")

        call_args = components.search_engine.search.call_args[0][0]
        from clew.search.models import QueryIntent

        assert call_args.intent == QueryIntent.ENUMERATION

    @patch("clew.mcp_server._get_components")
    async def test_search_invalid_intent(self, mock_get):
        components = _mock_components()
        mock_get.return_value = components

        output = await search("hello", intent="invalid_intent")
        assert isinstance(output, dict)
        assert "error" in output
        assert "Invalid intent" in output["error"]

    @patch("clew.mcp_server._get_components")
    async def test_search_with_filters(self, mock_get):
        components = _mock_components()
        mock_get.return_value = components
        components.search_engine.search.return_value = _mock_search_response()

        await search("hello", filters={"language": "python"})

        call_args = components.search_engine.search.call_args[0][0]
        assert call_args.filters == {"language": "python"}

    @patch("clew.mcp_server._get_components")
    async def test_search_invalid_mode(self, mock_get):
        components = _mock_components()
        mock_get.return_value = components

        output = await search("hello", mode="invalid_mode")
        assert isinstance(output, dict)
        assert "error" in output
        assert "Invalid mode" in output["error"]

    @patch("clew.mcp_server._get_components")
    async def test_search_with_mode_keyword(self, mock_get):
        components = _mock_components()
        mock_get.return_value = components
        components.search_engine.search.return_value = _mock_search_response()

        await search("hello", mode="keyword")

        call_args = components.search_engine.search.call_args[0][0]
        assert call_args.mode == "keyword"

    @patch("clew.mcp_server._get_components")
    async def test_search_response_has_confidence(self, mock_get):
        components = _mock_components()
        mock_get.return_value = components
        components.search_engine.search.return_value = _mock_search_response(
            confidence=0.85, confidence_label="high"
        )

        output = await search("hello")
        assert output["confidence"] == 0.85

    @patch("clew.mcp_server._get_components")
    async def test_search_response_no_verbose_metadata_in_output(self, mock_get):
        """MCP output excludes response-level metadata (0% agent read rate)."""
        from clew.search.models import SuggestionType

        components = _mock_components()
        mock_get.return_value = components
        components.search_engine.search.return_value = _mock_search_response(
            suggestion_type=SuggestionType.TRY_EXHAUSTIVE,
            mode_used="exhaustive",
            auto_escalated=True,
        )

        output = await search("hello")
        assert "suggestion" not in output
        assert "confidence_label" not in output
        assert "mode_used" not in output
        assert "auto_escalated" not in output
        assert "related_files" not in output


class TestGetContextTool:
    @patch("clew.mcp_server._get_components")
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
        assert "related_chunks" not in output

    @patch("clew.mcp_server._get_components")
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

    @patch("clew.mcp_server._get_components")
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

    @patch("clew.mcp_server._get_components")
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

    @patch("clew.mcp_server._get_components")
    async def test_detects_typescript_language(self, mock_get, tmp_path):
        components = _mock_components()
        mock_get.return_value = components
        components.search_engine.search.return_value = Mock(results=[])

        test_file = tmp_path / "app.ts"
        test_file.write_text("const x = 1;")

        output = await get_context(str(test_file))
        assert output["language"] == "typescript"

    @patch("clew.mcp_server._get_components")
    async def test_detects_javascript_language(self, mock_get, tmp_path):
        components = _mock_components()
        mock_get.return_value = components
        components.search_engine.search.return_value = Mock(results=[])

        test_file = tmp_path / "app.js"
        test_file.write_text("const x = 1;")

        output = await get_context(str(test_file))
        assert output["language"] == "javascript"

    @patch("clew.mcp_server._get_components")
    async def test_detects_markdown_language(self, mock_get, tmp_path):
        components = _mock_components()
        mock_get.return_value = components
        components.search_engine.search.return_value = Mock(results=[])

        test_file = tmp_path / "readme.md"
        test_file.write_text("# Title")

        output = await get_context(str(test_file))
        assert output["language"] == "markdown"

    @patch("clew.mcp_server._get_components")
    async def test_unknown_extension_uses_raw(self, mock_get, tmp_path):
        components = _mock_components()
        mock_get.return_value = components
        components.search_engine.search.return_value = Mock(results=[])

        test_file = tmp_path / "data.toml"
        test_file.write_text("[section]\nkey = 'value'")

        output = await get_context(str(test_file))
        assert output["language"] == "toml"

    @patch("clew.mcp_server._get_components")
    async def test_includes_related_chunks(self, mock_get, tmp_path):
        components = _mock_components()
        mock_get.return_value = components
        result = _mock_search_result()
        components.search_engine.search.return_value = Mock(results=[result])

        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1")

        output = await get_context(str(test_file), include_related=True)
        assert len(output["related_chunks"]) == 1
        assert output["related_chunks"][0]["file_path"] == "src/main.py"

    @patch("clew.mcp_server._get_components")
    async def test_search_error_during_context(self, mock_get, tmp_path):
        from clew.exceptions import QdrantConnectionError

        components = _mock_components()
        mock_get.return_value = components
        components.search_engine.search = AsyncMock(
            side_effect=QdrantConnectionError("http://localhost:6333")
        )

        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1")

        output = await get_context(str(test_file), include_related=True)
        assert "error" in output
        assert output["fix"] == "Run: docker compose up -d qdrant"


class TestExplainTool:
    @patch("clew.mcp_server._get_components")
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

    @patch("clew.mcp_server._get_components")
    async def test_searches_question(self, mock_get):
        components = _mock_components()
        mock_get.return_value = components
        components.search_engine.search.return_value = Mock(results=[])

        output = await explain("src/main.py", question="How does auth work?")
        assert output["question"] == "How does auth work?"
        assert output["symbol"] is None

        call_args = components.search_engine.search.call_args[0][0]
        assert call_args.query == "How does auth work?"

    @patch("clew.mcp_server._get_components")
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

    @patch("clew.mcp_server._get_components")
    async def test_symbol_takes_priority_over_question(self, mock_get):
        components = _mock_components()
        mock_get.return_value = components
        components.search_engine.search.return_value = Mock(results=[])

        output = await explain("src/main.py", symbol="MyClass", question="What is this?")
        assert output["symbol"] == "MyClass"
        assert output["question"] == "What is this?"

        call_args = components.search_engine.search.call_args[0][0]
        assert call_args.query == "MyClass"

    @patch("clew.mcp_server._get_components")
    async def test_search_limit_is_ten(self, mock_get):
        """explain() fetches 10 results internally (filters down to 5)."""
        components = _mock_components()
        mock_get.return_value = components
        components.search_engine.search.return_value = Mock(results=[])

        await explain("src/main.py", symbol="Foo")

        call_args = components.search_engine.search.call_args[0][0]
        assert call_args.limit == 10

    @patch("clew.mcp_server._get_components")
    async def test_explain_filters_by_language(self, mock_get):
        """Low-score results from other languages are filtered out."""
        components = _mock_components()
        mock_get.return_value = components
        results = [
            _mock_search_result(file_path="src/auth.py", language="python", score=0.9),
            _mock_search_result(file_path="src/utils.py", language="python", score=0.5),
            _mock_search_result(file_path="tailwind.config.js", language="javascript", score=0.3),
            _mock_search_result(file_path="src/models.py", language="python", score=0.4),
        ]
        components.search_engine.search.return_value = Mock(results=results)

        output = await explain("src/main.py", symbol="EvvyJWTAuthentication")
        file_paths = [chunk["file_path"] for chunk in output["related_chunks"]]
        assert "tailwind.config.js" not in file_paths
        assert "src/auth.py" in file_paths
        assert "src/utils.py" in file_paths
        assert "src/models.py" in file_paths

    @patch("clew.mcp_server._get_components")
    async def test_explain_keeps_high_score_cross_language(self, mock_get):
        """Cross-language results with score >= 0.6 are kept."""
        components = _mock_components()
        mock_get.return_value = components
        results = [
            _mock_search_result(file_path="src/auth.py", language="python", score=0.9),
            _mock_search_result(file_path="src/auth.ts", language="typescript", score=0.75),
            _mock_search_result(file_path="tailwind.config.js", language="javascript", score=0.3),
        ]
        components.search_engine.search.return_value = Mock(results=results)

        output = await explain("src/main.py", symbol="AuthService")
        file_paths = [chunk["file_path"] for chunk in output["related_chunks"]]
        assert "src/auth.py" in file_paths
        assert "src/auth.ts" in file_paths  # high score, kept despite different language
        assert "tailwind.config.js" not in file_paths  # low score + different language, filtered

    @patch("clew.mcp_server._get_components")
    async def test_explain_no_filter_for_unknown_language(self, mock_get):
        """When language can't be detected from file_path, all results are kept."""
        components = _mock_components()
        mock_get.return_value = components
        results = [
            _mock_search_result(file_path="src/auth.py", language="python", score=0.9),
            _mock_search_result(file_path="config.js", language="javascript", score=0.3),
            _mock_search_result(file_path="readme.md", language="markdown", score=0.2),
        ]
        components.search_engine.search.return_value = Mock(results=results)

        output = await explain("Makefile", symbol="build")
        # All results should be kept since Makefile has unknown language
        assert len(output["related_chunks"]) == 3

    @patch("clew.mcp_server._get_components")
    async def test_explain_handles_error(self, mock_get):
        from clew.exceptions import VoyageAuthError

        mock_get.return_value = _mock_components()
        mock_get.return_value.search_engine.search = AsyncMock(side_effect=VoyageAuthError())

        output = await explain("src/main.py", symbol="MyClass")
        assert isinstance(output, dict)
        assert "error" in output
        assert "VOYAGE_API_KEY" in output["fix"]


class TestIndexStatusTool:
    @patch("clew.mcp_server._get_components")
    async def test_status_returns_info(self, mock_get):
        components = _mock_components()
        mock_get.return_value = components

        output = await index_status(action="status")
        assert output["indexed"] is True
        assert output["qdrant_healthy"] is True
        assert output["collections"]["code"] == 42
        assert output["collections"]["docs"] == 42
        assert output["last_commit"] == "abc123"

    @patch("clew.mcp_server._get_components")
    async def test_status_no_collections(self, mock_get):
        components = _mock_components()
        mock_get.return_value = components
        components.qdrant.collection_exists.return_value = False

        output = await index_status(action="status")
        assert output["indexed"] is False
        assert output["collections"] == {}

    @patch("clew.mcp_server._get_components")
    async def test_status_unhealthy_qdrant(self, mock_get):
        components = _mock_components()
        mock_get.return_value = components
        components.qdrant.health_check.return_value = False

        output = await index_status(action="status")
        assert output["qdrant_healthy"] is False

    @patch("clew.mcp_server._get_components")
    async def test_status_no_last_commit(self, mock_get):
        components = _mock_components()
        mock_get.return_value = components
        components.cache.get_last_indexed_commit.return_value = None

        output = await index_status(action="status")
        assert output["last_commit"] is None

    @patch("clew.discovery.discover_files")
    @patch("clew.mcp_server._get_components")
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

    @patch("clew.mcp_server._get_components")
    async def test_trigger_missing_project_root(self, mock_get):
        components = _mock_components()
        mock_get.return_value = components

        output = await index_status(action="trigger")
        assert "error" in output
        assert "project_root" in output["error"]

    @patch("clew.mcp_server._get_components")
    async def test_trigger_invalid_directory(self, mock_get):
        components = _mock_components()
        mock_get.return_value = components

        output = await index_status(action="trigger", project_root="/nonexistent/dir")
        assert "error" in output
        assert "Not a directory" in output["error"]

    @patch("clew.mcp_server._get_components")
    async def test_unknown_action(self, mock_get):
        components = _mock_components()
        mock_get.return_value = components

        output = await index_status(action="invalid")
        assert "error" in output
        assert "Unknown action" in output["error"]
        assert output["fix"] == "Use 'status' or 'trigger'"

    @patch("clew.mcp_server._get_components")
    async def test_voyage_auth_error(self, mock_get):
        from clew.exceptions import VoyageAuthError

        mock_get.side_effect = VoyageAuthError()

        output = await index_status(action="status")
        assert isinstance(output, dict)
        assert "error" in output
        assert "VOYAGE_API_KEY" in output["fix"]

    @patch("clew.mcp_server._get_components")
    async def test_qdrant_error_on_status(self, mock_get):
        from clew.exceptions import QdrantConnectionError

        mock_get.side_effect = QdrantConnectionError("http://localhost:6333")

        output = await index_status(action="status")
        assert isinstance(output, dict)
        assert "error" in output
        assert output["fix"] == "Run: docker compose up -d qdrant"

    @patch("clew.discovery.discover_files")
    @patch("clew.mcp_server._get_components")
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


class TestTraceTool:
    @patch("clew.mcp_server._get_components")
    async def test_trace_outbound(self, mock_get_components) -> None:
        mock_components = _mock_components()
        mock_components.cache.traverse_relationships.return_value = [
            {
                "source_entity": "app/main.py::Foo",
                "relationship": "calls",
                "target_entity": "app/utils.py::helper",
                "confidence": "inferred",
                "depth": 1,
            }
        ]
        mock_get_components.return_value = mock_components

        result = await trace(entity="app/main.py::Foo", direction="outbound")
        assert result["entity"] == "app/main.py::Foo"
        assert len(result["relationships"]) == 1
        assert result["relationships"][0]["target_entity"] == "app/utils.py::helper"

    @patch("clew.mcp_server._get_components")
    async def test_trace_with_max_depth(self, mock_get_components) -> None:
        mock_components = _mock_components()
        mock_components.cache.traverse_relationships.return_value = []
        mock_get_components.return_value = mock_components

        await trace(entity="a.py::Foo", max_depth=3)
        mock_components.cache.traverse_relationships.assert_called_once_with(
            "a.py::Foo", direction="both", max_depth=3, relationship_types=None
        )

    @patch("clew.mcp_server._get_components")
    async def test_trace_with_relationship_filter(self, mock_get_components) -> None:
        mock_components = _mock_components()
        mock_components.cache.traverse_relationships.return_value = []
        mock_get_components.return_value = mock_components

        await trace(
            entity="a.py::Foo",
            relationship_types=["imports", "calls"],
        )
        mock_components.cache.traverse_relationships.assert_called_once_with(
            "a.py::Foo",
            direction="both",
            max_depth=2,
            relationship_types=["imports", "calls"],
        )

    @patch("clew.mcp_server._get_components")
    async def test_trace_max_depth_clamped(self, mock_get_components) -> None:
        """max_depth is clamped to 5."""
        mock_components = _mock_components()
        mock_components.cache.traverse_relationships.return_value = []
        mock_get_components.return_value = mock_components

        await trace(entity="a.py::Foo", max_depth=10)
        mock_components.cache.traverse_relationships.assert_called_once_with(
            "a.py::Foo", direction="both", max_depth=5, relationship_types=None
        )

    @patch("clew.mcp_server._get_components")
    async def test_trace_error_handling(self, mock_get_components) -> None:
        mock_components = _mock_components()
        mock_components.cache.traverse_relationships.side_effect = Exception("DB error")
        mock_get_components.return_value = mock_components

        result = await trace(entity="a.py::Foo")
        assert "error" in result
        assert "fix" in result

    @patch("clew.mcp_server._get_components")
    async def test_trace_includes_resolved_entity(self, mock_get_components) -> None:
        """When entity is resolved to a different name, resolved_entity is in the response."""
        mock_components = _mock_components()
        mock_components.cache.resolve_entity.side_effect = None
        mock_components.cache.resolve_entity.return_value = (
            "/abs/path/backend/care/models.py::Prescription"
        )
        mock_components.cache.traverse_relationships.return_value = [
            {
                "source_entity": "/abs/path/backend/care/models.py::Prescription",
                "relationship": "inherits",
                "target_entity": "/abs/path/backend/utils/mixins.py::Base",
                "confidence": "static",
                "depth": 1,
            }
        ]
        mock_get_components.return_value = mock_components

        result = await trace(entity="Prescription")
        assert result["entity"] == "Prescription"
        assert result["resolved_entity"] == "/abs/path/backend/care/models.py::Prescription"
        assert len(result["relationships"]) == 1


class TestCompactResponse:
    """Test compact vs full response modes."""

    @patch("clew.mcp_server._get_components")
    async def test_search_compact_by_default(self, mock_get) -> None:
        """search() returns compact results (no content field) by default."""
        components = _mock_components()
        result = _mock_search_result()
        components.search_engine.search.return_value = _mock_search_response(
            results=[result], total_candidates=1
        )
        mock_get.return_value = components

        output = await search("test query")
        assert isinstance(output, dict)
        results = output["results"]
        assert len(results) == 1
        assert "snippet" in results[0]
        assert "content" not in results[0]
        assert "file_path" in results[0]
        assert "score" in results[0]

    @patch("clew.mcp_server._get_components")
    async def test_search_full_detail(self, mock_get) -> None:
        """search(detail='full') returns content field."""
        components = _mock_components()
        result = _mock_search_result()
        components.search_engine.search.return_value = _mock_search_response(
            results=[result], total_candidates=1
        )
        mock_get.return_value = components

        output = await search("test query", detail="full")
        assert isinstance(output, dict)
        results = output["results"]
        assert "content" in results[0]
        assert "snippet" in results[0]

    @patch("clew.mcp_server._get_components")
    async def test_search_default_limit_is_5(self, mock_get) -> None:
        """search() defaults to limit=5."""
        components = _mock_components()
        components.search_engine.search.return_value = _mock_search_response()
        mock_get.return_value = components

        await search("test query")
        call_args = components.search_engine.search.call_args
        request = call_args[0][0]
        assert request.limit == 5


class TestSnippetBuilding:
    """Test _build_snippet logic."""

    def test_snippet_with_signature_and_docstring(self) -> None:
        """Signature + docstring used when both available."""
        from clew.mcp_server import _build_snippet

        result = _mock_search_result(
            signature="def hello():",
            docstring="Say hello.\n\nGreets the user warmly.",
        )
        snippet = _build_snippet(result)
        assert snippet.startswith("def hello():")
        assert "Say hello." in snippet

    def test_snippet_with_signature_only(self) -> None:
        """Just signature when no docstring."""
        from clew.mcp_server import _build_snippet

        result = _mock_search_result(signature="def hello():", docstring="")
        snippet = _build_snippet(result)
        assert snippet == "def hello():"

    def test_snippet_fallback_to_content_lines(self) -> None:
        """First N lines of content when no signature."""
        from clew.mcp_server import _build_snippet

        result = _mock_search_result(
            signature="",
            docstring="",
            content="line1\nline2\nline3\nline4\nline5\nline6",
        )
        snippet = _build_snippet(result)
        lines = snippet.splitlines()
        assert len(lines) == 5
        assert lines[0] == "line1"


class TestGetContextIncludeRelated:
    """Test get_context include_related parameter."""

    @patch("clew.mcp_server._get_components")
    async def test_get_context_no_related_by_default(self, mock_get) -> None:
        """get_context() returns no related_chunks by default."""
        components = _mock_components()
        mock_get.return_value = components

        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("x = 1\n")
            f.flush()
            result = await get_context(f.name)

        assert "related_chunks" not in result

    @patch("clew.mcp_server._get_components")
    async def test_get_context_with_related(self, mock_get) -> None:
        """get_context(include_related=True) returns compact related_chunks."""
        components = _mock_components()
        sr = _mock_search_result()
        components.search_engine.search.return_value = Mock(results=[sr])
        mock_get.return_value = components

        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("x = 1\n")
            f.flush()
            result = await get_context(f.name, include_related=True)

        assert "related_chunks" in result
        assert len(result["related_chunks"]) == 1
        assert "content" not in result["related_chunks"][0]
        assert "snippet" in result["related_chunks"][0]


class TestExplainCompact:
    """Test explain tool compact response."""

    @patch("clew.mcp_server._get_components")
    async def test_explain_compact_by_default(self, mock_get) -> None:
        """explain() returns compact related_chunks by default."""
        components = _mock_components()
        sr = _mock_search_result()
        components.search_engine.search.return_value = Mock(results=[sr])
        mock_get.return_value = components

        result = await explain("src/main.py", symbol="hello")
        assert "related_chunks" in result
        assert "content" not in result["related_chunks"][0]
        assert "snippet" in result["related_chunks"][0]

    @patch("clew.mcp_server._get_components")
    async def test_explain_full_detail(self, mock_get) -> None:
        """explain(detail='full') returns content in related_chunks."""
        components = _mock_components()
        sr = _mock_search_result()
        components.search_engine.search.return_value = Mock(results=[sr])
        mock_get.return_value = components

        result = await explain("src/main.py", symbol="hello", detail="full")
        assert "content" in result["related_chunks"][0]

    @patch("clew.mcp_server._get_components")
    async def test_explain_limit_is_10(self, mock_get) -> None:
        """explain() fetches limit=10 internally (filters down to 5)."""
        components = _mock_components()
        components.search_engine.search.return_value = Mock(results=[])
        mock_get.return_value = components

        await explain("src/main.py", symbol="hello")
        call_args = components.search_engine.search.call_args
        request = call_args[0][0]
        assert request.limit == 10


class TestHeuristicExplainEnrichment:
    def test_includes_enrichment_when_cache_available(self):
        result = _mock_search_result(chunk_id="src/main.py::function::hello")
        mock_cache = Mock()
        mock_cache.get_enrichment.return_value = (
            "Greets the user and returns True",
            "hello,greeting",
        )

        explanation = _heuristic_explain("src/main.py", "hello", None, [result], cache=mock_cache)
        assert "Summary:" in explanation
        assert "Greets the user" in explanation

    def test_no_enrichment_without_cache(self):
        result = _mock_search_result(chunk_id="src/main.py::function::hello")

        explanation = _heuristic_explain("src/main.py", "hello", None, [result], cache=None)
        assert "Summary:" not in explanation

    def test_no_enrichment_when_cache_returns_none(self):
        result = _mock_search_result(chunk_id="src/main.py::function::hello")
        mock_cache = Mock()
        mock_cache.get_enrichment.return_value = None

        explanation = _heuristic_explain("src/main.py", "hello", None, [result], cache=mock_cache)
        assert "Summary:" not in explanation

    def test_enrichment_with_empty_description(self):
        result = _mock_search_result(chunk_id="src/main.py::function::hello")
        mock_cache = Mock()
        mock_cache.get_enrichment.return_value = ("", "hello")

        explanation = _heuristic_explain("src/main.py", "hello", None, [result], cache=mock_cache)
        assert "Summary:" not in explanation


class TestV4ResultFields:
    """Test V4 source and context fields in search result dicts."""

    @patch("clew.mcp_server._get_components")
    async def test_source_field_included_for_grep(self, mock_get):
        """Results with source='grep' include source in output dict."""
        components = _mock_components()
        result = _mock_search_result(source="grep")
        components.search_engine.search.return_value = _mock_search_response(
            results=[result], total_candidates=1
        )
        mock_get.return_value = components

        output = await search("hello")
        assert output["results"][0]["source"] == "grep"

    @patch("clew.mcp_server._get_components")
    async def test_source_field_omitted_for_semantic(self, mock_get):
        """Results with source='semantic' omit source from output dict."""
        components = _mock_components()
        result = _mock_search_result(source="semantic")
        components.search_engine.search.return_value = _mock_search_response(
            results=[result], total_candidates=1
        )
        mock_get.return_value = components

        output = await search("hello")
        assert "source" not in output["results"][0]

    @patch("clew.mcp_server._get_components")
    async def test_context_field_included_when_present(self, mock_get):
        """Results with non-empty context include context in output dict."""
        components = _mock_components()
        result = _mock_search_result(context="Called by: handler")
        components.search_engine.search.return_value = _mock_search_response(
            results=[result], total_candidates=1
        )
        mock_get.return_value = components

        output = await search("hello")
        assert output["results"][0]["context"] == "Called by: handler"

    @patch("clew.mcp_server._get_components")
    async def test_context_field_omitted_when_empty(self, mock_get):
        """Results with empty context omit context from output dict."""
        components = _mock_components()
        result = _mock_search_result(context="")
        components.search_engine.search.return_value = _mock_search_response(
            results=[result], total_candidates=1
        )
        mock_get.return_value = components

        output = await search("hello")
        assert "context" not in output["results"][0]

    @patch("clew.mcp_server._get_components")
    async def test_no_related_files_in_output(self, mock_get):
        """V4 search output does not include top-level related_files."""
        components = _mock_components()
        result = _mock_search_result(chunk_id="src/main.py::function::hello")
        components.search_engine.search.return_value = _mock_search_response(
            results=[result], total_candidates=1
        )
        mock_get.return_value = components

        output = await search("hello")
        assert "related_files" not in output
