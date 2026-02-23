"""Integration tests for autonomous grep escalation pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from clew.models import SearchConfig
from clew.search.engine import SearchEngine
from clew.search.models import QueryIntent, SearchRequest, SearchResult


def _make_result(
    score: float = 0.8,
    file_path: str = "src/main.py",
    line_start: int = 1,
    line_end: int = 10,
    function_name: str = "foo",
    **kwargs: object,
) -> SearchResult:
    defaults = {
        "content": "def foo(): pass",
        "chunk_type": "function",
        "language": "python",
        "class_name": "",
    }
    defaults.update(kwargs)
    return SearchResult(
        score=score,
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


class TestAutoEscalationPipeline:
    """Integration tests for the full auto-escalation pipeline.

    Auto-escalation is purely post-hoc, triggered by low confidence
    (flat top / steep tail Z-score < 0.5) on CODE/DOCS queries.
    """

    @pytest.mark.asyncio
    async def test_full_pipeline_low_confidence_post_hoc_grep(self):
        """Low-confidence CODE query triggers post-hoc grep, auto_escalated=True."""
        # Flat top, steep tail: Z < 0.5 → LOW
        semantic_results = [
            _make_result(score=1.0, file_path="a.py", line_start=1, line_end=10),
            _make_result(score=0.98, file_path="b.py", line_start=1, line_end=10),
            _make_result(score=0.96, file_path="c.py", line_start=1, line_end=10),
            _make_result(score=0.94, file_path="d.py", line_start=1, line_end=10),
            _make_result(score=0.92, file_path="e.py", line_start=1, line_end=10),
            _make_result(score=0.85, file_path="f.py", line_start=1, line_end=10),
            _make_result(score=0.75, file_path="g.py", line_start=1, line_end=10),
            _make_result(score=0.65, file_path="h.py", line_start=1, line_end=10),
            _make_result(score=0.55, file_path="i.py", line_start=1, line_end=10),
            _make_result(score=0.45, file_path="j.py", line_start=1, line_end=10),
        ]
        hybrid = Mock()
        hybrid.search = AsyncMock(return_value=semantic_results)

        engine = SearchEngine(
            hybrid_engine=hybrid,
            search_config=SearchConfig(),
            project_root=Path("/project"),
        )

        # Mock grep subprocess to return additional results
        rg_output = "\n".join(
            [
                _make_rg_match("src/other.py", 20, "def bar(): pass", "bar"),
                _make_rg_match("src/routes.py", 5, "urlpatterns = [", "urlpatterns"),
            ]
        )
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(rg_output.encode(), b""))
        mock_process.returncode = 0

        with patch(
            "clew.search.grep.asyncio.create_subprocess_exec",
            return_value=mock_process,
        ):
            request = SearchRequest(query="webhook handler code")
            response = await engine.search(request)

        # Should have both semantic and grep results
        semantic_items = [r for r in response.results if r.source == "semantic"]
        grep_items = [r for r in response.results if r.source == "grep"]
        assert len(semantic_items) >= 1
        assert len(grep_items) >= 1
        assert response.auto_escalated is True
        assert response.mode_used == "exhaustive"

    @pytest.mark.asyncio
    async def test_full_pipeline_no_escalation(self):
        """High-confidence CODE query does not trigger subprocess."""
        # Front-loaded decay: big gaps at top, tiny in tail → Z=1.56 → HIGH
        semantic_results = [
            _make_result(score=1.0, file_path="a.py", line_start=1, line_end=10),
            _make_result(score=0.7, file_path="b.py", line_start=1, line_end=10),
            _make_result(score=0.50, file_path="c.py", line_start=1, line_end=10),
            _make_result(score=0.45, file_path="d.py", line_start=1, line_end=10),
            _make_result(score=0.40, file_path="e.py", line_start=1, line_end=10),
            _make_result(score=0.38, file_path="f.py", line_start=1, line_end=10),
            _make_result(score=0.37, file_path="g.py", line_start=1, line_end=10),
            _make_result(score=0.36, file_path="h.py", line_start=1, line_end=10),
            _make_result(score=0.35, file_path="i.py", line_start=1, line_end=10),
            _make_result(score=0.34, file_path="j.py", line_start=1, line_end=10),
        ]
        hybrid = Mock()
        hybrid.search = AsyncMock(return_value=semantic_results)

        engine = SearchEngine(
            hybrid_engine=hybrid,
            search_config=SearchConfig(),
            project_root=Path("/project"),
        )

        with patch(
            "clew.search.grep.asyncio.create_subprocess_exec",
        ) as mock_exec:
            request = SearchRequest(
                query="handle payment processing",
                intent=QueryIntent.CODE,
            )
            response = await engine.search(request)

        # Subprocess should NOT have been called (CODE intent, no escalation)
        mock_exec.assert_not_called()
        assert response.auto_escalated is False
        assert response.mode_used == "semantic"

    @pytest.mark.asyncio
    async def test_deduplication_in_merge(self):
        """Grep results overlapping semantic results are deduplicated in merge."""
        # Flat top, steep tail: Z < 0.5 → LOW
        semantic_results = [
            _make_result(
                score=1.0,
                file_path="src/main.py",
                line_start=5,
                line_end=15,
                function_name="process_order",
            ),
            _make_result(score=0.98, file_path="a.py", line_start=1, line_end=10),
            _make_result(score=0.96, file_path="b.py", line_start=1, line_end=10),
            _make_result(score=0.94, file_path="c.py", line_start=1, line_end=10),
            _make_result(score=0.92, file_path="d.py", line_start=1, line_end=10),
            _make_result(score=0.85, file_path="e.py", line_start=1, line_end=10),
            _make_result(score=0.75, file_path="f.py", line_start=1, line_end=10),
            _make_result(score=0.65, file_path="g.py", line_start=1, line_end=10),
            _make_result(score=0.55, file_path="h.py", line_start=1, line_end=10),
            _make_result(score=0.45, file_path="i.py", line_start=1, line_end=10),
        ]
        hybrid = Mock()
        hybrid.search = AsyncMock(return_value=semantic_results)

        engine = SearchEngine(
            hybrid_engine=hybrid,
            search_config=SearchConfig(),
            project_root=Path("/project"),
        )

        # One overlapping (line 10 is within 5-15) and one non-overlapping
        rg_output = "\n".join(
            [
                _make_rg_match("src/main.py", 10, "  x = 1", "process_order"),
                _make_rg_match("src/other.py", 20, "def other(): pass", "process_order"),
            ]
        )
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(rg_output.encode(), b""))
        mock_process.returncode = 0

        with patch(
            "clew.search.grep.asyncio.create_subprocess_exec",
            return_value=mock_process,
        ):
            request = SearchRequest(query="process_order usages")
            response = await engine.search(request)

        # Should have non-overlapping grep result (overlapping one deduped)
        grep_items = [r for r in response.results if r.source == "grep"]
        assert len(grep_items) == 1
        assert grep_items[0].file_path == "src/other.py"

    @pytest.mark.asyncio
    async def test_graceful_fallback_rg_not_available(self):
        """When rg is not installed, only semantic results are returned."""
        # Flat top, steep tail: Z < 0.5 → LOW
        semantic_results = [
            _make_result(score=1.0, file_path="a.py", line_start=1, line_end=10),
            _make_result(score=0.98, file_path="b.py", line_start=1, line_end=10),
            _make_result(score=0.96, file_path="c.py", line_start=1, line_end=10),
            _make_result(score=0.94, file_path="d.py", line_start=1, line_end=10),
            _make_result(score=0.92, file_path="e.py", line_start=1, line_end=10),
            _make_result(score=0.85, file_path="f.py", line_start=1, line_end=10),
            _make_result(score=0.75, file_path="g.py", line_start=1, line_end=10),
            _make_result(score=0.65, file_path="h.py", line_start=1, line_end=10),
            _make_result(score=0.55, file_path="i.py", line_start=1, line_end=10),
            _make_result(score=0.45, file_path="j.py", line_start=1, line_end=10),
        ]
        hybrid = Mock()
        hybrid.search = AsyncMock(return_value=semantic_results)

        engine = SearchEngine(
            hybrid_engine=hybrid,
            search_config=SearchConfig(),
            project_root=Path("/project"),
        )

        with patch(
            "clew.search.grep.asyncio.create_subprocess_exec",
            side_effect=FileNotFoundError,
        ):
            request = SearchRequest(query="webhook handler code")
            response = await engine.search(request)

        # Should fall back gracefully to semantic-only results
        assert len(response.results) >= 1
        assert all(r.source == "semantic" for r in response.results)
        assert response.auto_escalated is False
