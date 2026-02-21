"""Integration tests for exhaustive search pipeline (semantic + grep).

V4 removed the standalone search_with_grep() function. Exhaustive behavior
is now handled internally by SearchEngine via auto-escalation. These tests
verify the engine-integrated exhaustive mode.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from clew.models import SearchConfig
from clew.search.engine import SearchEngine
from clew.search.models import (
    QueryIntent,
    SearchRequest,
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


def _make_engine(
    semantic_results: list[SearchResult] | None = None,
    project_root: Path | None = Path("/project"),
) -> SearchEngine:
    """Create a SearchEngine with mock hybrid and project_root for grep."""
    hybrid = Mock()
    hybrid.search = AsyncMock(return_value=semantic_results or [_make_result()])
    return SearchEngine(
        hybrid_engine=hybrid,
        search_config=SearchConfig(),
        project_root=project_root,
    )


class TestExhaustiveMode:
    """Test exhaustive mode via SearchEngine (replaces search_with_grep tests)."""

    @pytest.mark.asyncio
    async def test_exhaustive_returns_combined_results(self):
        """Exhaustive mode returns both semantic and grep results."""
        engine = _make_engine()

        rg_output = "\n".join(
            [
                _make_rg_match("src/other.py", 20, "def bar(): pass", "process_order"),
                _make_rg_match("src/another.py", 30, "class Baz:", "process_order"),
            ]
        )
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(rg_output.encode(), b""))
        mock_process.returncode = 0

        with patch(
            "clew.search.grep.asyncio.create_subprocess_exec",
            return_value=mock_process,
        ):
            request = SearchRequest(
                query="find all process_order usages",
                mode="exhaustive",
                intent=QueryIntent.ENUMERATION,
            )
            response = await engine.search(request)

        semantic_items = [r for r in response.results if r.source == "semantic"]
        grep_items = [r for r in response.results if r.source == "grep"]
        assert len(semantic_items) >= 1
        assert len(grep_items) >= 1

    @pytest.mark.asyncio
    async def test_deduplication(self):
        """Grep results overlapping semantic results are deduplicated."""
        semantic_result = _make_result(
            file_path="src/main.py", line_start=5, line_end=15, function_name="process_order"
        )
        engine = _make_engine(semantic_results=[semantic_result])

        rg_output = "\n".join(
            [
                # Overlaps with semantic (line 10 is within 5-15)
                _make_rg_match("src/main.py", 10, "  x = 1", "process_order"),
                # Does NOT overlap
                _make_rg_match("src/other.py", 10, "  y = 2", "process_order"),
            ]
        )
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(rg_output.encode(), b""))
        mock_process.returncode = 0

        with patch(
            "clew.search.grep.asyncio.create_subprocess_exec",
            return_value=mock_process,
        ):
            request = SearchRequest(
                query="find all process_order usages",
                mode="exhaustive",
                intent=QueryIntent.ENUMERATION,
            )
            response = await engine.search(request)

        grep_items = [r for r in response.results if r.source == "grep"]
        assert len(grep_items) == 1
        assert grep_items[0].file_path == "src/other.py"

    @pytest.mark.asyncio
    async def test_graceful_fallback_rg_not_available(self):
        """When rg is not installed, only semantic results are returned."""
        engine = _make_engine()

        with patch(
            "clew.search.grep.asyncio.create_subprocess_exec",
            side_effect=FileNotFoundError,
        ):
            request = SearchRequest(
                query="find all process_order usages",
                mode="exhaustive",
                intent=QueryIntent.ENUMERATION,
            )
            response = await engine.search(request)

        assert len(response.results) >= 1
        assert all(r.source == "semantic" for r in response.results)

    @pytest.mark.asyncio
    async def test_engine_search_called_once(self):
        """Hybrid search is called exactly once (not duplicated)."""
        hybrid = Mock()
        hybrid.search = AsyncMock(return_value=[_make_result()])
        engine = SearchEngine(
            hybrid_engine=hybrid,
            search_config=SearchConfig(),
            project_root=Path("/project"),
        )

        with patch(
            "clew.search.grep.asyncio.create_subprocess_exec",
            side_effect=FileNotFoundError,
        ):
            request = SearchRequest(
                query="find all process_order usages",
                mode="exhaustive",
                intent=QueryIntent.ENUMERATION,
            )
            await engine.search(request)

        hybrid.search.assert_awaited_once()
