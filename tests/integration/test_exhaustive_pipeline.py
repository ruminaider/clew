"""Integration tests for exhaustive search pipeline (semantic + grep)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from clew.search.grep import search_with_grep
from clew.search.models import (
    QueryIntent,
    SearchRequest,
    SearchResponse,
    SearchResult,
)


def _make_result(
    file_path: str = "src/main.py",
    line_start: int = 1,
    line_end: int = 10,
    function_name: str = "foo",
    **kwargs: object,
) -> SearchResult:
    defaults = {
        "content": "def foo(): pass",
        "score": 0.9,
        "chunk_type": "function",
        "language": "python",
        "class_name": "",
    }
    defaults.update(kwargs)
    return SearchResult(
        file_path=file_path,
        line_start=line_start,
        line_end=line_end,
        function_name=function_name,
        **defaults,  # type: ignore[arg-type]
    )


def _make_response(results: list[SearchResult] | None = None) -> SearchResponse:
    return SearchResponse(
        results=results or [_make_result()],
        query_enhanced="test query",
        total_candidates=10,
        intent=QueryIntent.CODE,
        confidence=0.8,
        confidence_label="high",
    )


def _mock_engine(response: SearchResponse | None = None) -> Mock:
    engine = Mock()
    engine.search = AsyncMock(return_value=response or _make_response())
    return engine


def _make_rg_match(file_path: str, line_number: int, text: str, matched: str) -> str:
    return json.dumps(
        {
            "type": "match",
            "data": {
                "path": {"text": file_path},
                "line_number": line_number,
                "lines": {"text": text + "\n"},
                "submatches": [{"match": {"text": matched}, "start": 0, "end": len(matched)}],
            },
        }
    )


class TestSearchWithGrep:
    """Integration tests for the search_with_grep orchestration function."""

    @pytest.mark.asyncio
    async def test_returns_both_semantic_and_grep_results(self):
        """search_with_grep returns semantic response and grep results."""
        rg_output = "\n".join(
            [
                _make_rg_match("src/other.py", 20, "def bar(): pass", "bar"),
                _make_rg_match("src/another.py", 30, "class Baz:", "Baz"),
            ]
        )
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(rg_output.encode(), b""))
        mock_process.returncode = 0

        engine = _mock_engine()

        with patch(
            "clew.search.grep.asyncio.create_subprocess_exec",
            return_value=mock_process,
        ):
            request = SearchRequest(query="foo bar", mode="exhaustive")
            response, grep_results = await search_with_grep(engine, request, Path("/project"))

        assert len(response.results) == 1  # semantic result
        assert response.results[0].function_name == "foo"
        assert len(grep_results) >= 1  # grep found additional results

    @pytest.mark.asyncio
    async def test_deduplication_works(self):
        """Grep results overlapping with semantic results are removed."""
        semantic_result = _make_result(
            file_path="src/main.py", line_start=5, line_end=15, function_name="foo"
        )
        engine = _mock_engine(_make_response([semantic_result]))

        rg_output = "\n".join(
            [
                # This overlaps with semantic result (line 10 is within 5-15)
                _make_rg_match("src/main.py", 10, "  x = 1", "foo"),
                # This does NOT overlap
                _make_rg_match("src/other.py", 10, "  y = 2", "foo"),
            ]
        )
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(rg_output.encode(), b""))
        mock_process.returncode = 0

        with patch(
            "clew.search.grep.asyncio.create_subprocess_exec",
            return_value=mock_process,
        ):
            request = SearchRequest(query="foo", mode="exhaustive")
            response, grep_results = await search_with_grep(engine, request, Path("/project"))

        assert len(grep_results) == 1
        assert grep_results[0].file_path == "src/other.py"

    @pytest.mark.asyncio
    async def test_grep_capping(self):
        """Grep results are capped at grep_response_cap."""
        rg_lines = [_make_rg_match(f"src/file_{i}.py", i, f"line {i}", "foo") for i in range(50)]
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=("\n".join(rg_lines).encode(), b""))
        mock_process.returncode = 0

        engine = _mock_engine()

        with patch(
            "clew.search.grep.asyncio.create_subprocess_exec",
            return_value=mock_process,
        ):
            request = SearchRequest(query="foo", mode="exhaustive")
            response, grep_results = await search_with_grep(
                engine, request, Path("/project"), grep_response_cap=10
            )

        assert len(grep_results) <= 10

    @pytest.mark.asyncio
    async def test_graceful_fallback_rg_not_available(self):
        """When rg is not installed, only semantic results are returned."""
        engine = _mock_engine()

        with patch(
            "clew.search.grep.asyncio.create_subprocess_exec",
            side_effect=FileNotFoundError,
        ):
            request = SearchRequest(query="foo bar", mode="exhaustive")
            response, grep_results = await search_with_grep(engine, request, Path("/project"))

        assert len(response.results) == 1
        assert grep_results == []

    @pytest.mark.asyncio
    async def test_no_patterns_generated(self):
        """When no patterns can be generated, only semantic results returned."""
        # Empty query with no result names
        result = _make_result(function_name="", class_name="")
        engine = _mock_engine(_make_response([result]))

        request = SearchRequest(query="", mode="exhaustive")
        response, grep_results = await search_with_grep(engine, request, Path("/project"))

        assert len(response.results) == 1
        assert grep_results == []

    @pytest.mark.asyncio
    async def test_engine_search_called_once(self):
        """Engine.search is called exactly once (not duplicated)."""
        engine = _mock_engine()

        with patch(
            "clew.search.grep.asyncio.create_subprocess_exec",
            side_effect=FileNotFoundError,
        ):
            request = SearchRequest(query="foo bar", mode="exhaustive")
            await search_with_grep(engine, request, Path("/project"))

        engine.search.assert_awaited_once_with(request)
