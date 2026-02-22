"""Tests for grep integration module."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, Mock, patch

import pytest

from clew.search.grep import (
    GrepResult,
    _deduplicate_grep,
    generate_grep_patterns,
    grep_results_to_search_results,
    run_grep,
)
from clew.search.models import SearchResult


def _make_result(
    file_path: str = "src/main.py",
    line_start: int = 1,
    line_end: int = 10,
    function_name: str = "",
    class_name: str = "",
    **kwargs: object,
) -> SearchResult:
    """Create a SearchResult with defaults."""
    defaults = {
        "content": "def foo(): pass",
        "score": 0.9,
        "chunk_type": "function",
        "language": "python",
    }
    defaults.update(kwargs)
    return SearchResult(
        file_path=file_path,
        line_start=line_start,
        line_end=line_end,
        function_name=function_name,
        class_name=class_name,
        **defaults,  # type: ignore[arg-type]
    )


class TestGenerateGrepPatterns:
    """Test pattern generation from queries and results."""

    def test_query_derived_identifier(self):
        """Specific identifiers from query are included as patterns."""
        patterns = generate_grep_patterns("find process_order function", [], None)
        assert any("process_order" in p for p in patterns)

    def test_query_derived_camel_case(self):
        """CamelCase identifiers from query are included."""
        patterns = generate_grep_patterns("where is ProcessOrder used", [], None)
        assert any("ProcessOrder" in p for p in patterns)

    def test_framework_pattern_url(self):
        """URL keyword triggers framework patterns."""
        patterns = generate_grep_patterns("find all URL routes", [], None)
        assert any("urlpatterns" in p for p in patterns)
        assert any("path" in p for p in patterns)

    def test_framework_pattern_api(self):
        """API keyword triggers framework patterns."""
        patterns = generate_grep_patterns("api endpoints", [], None)
        assert any("api_view" in p for p in patterns)

    def test_result_derived_function_name(self):
        """Function names from results are included."""
        results = [_make_result(function_name="handle_payment")]
        patterns = generate_grep_patterns("payment", results, None)
        assert any("handle_payment" in p for p in patterns)

    def test_result_derived_class_name(self):
        """Class names from results are included."""
        results = [_make_result(class_name="PaymentProcessor")]
        patterns = generate_grep_patterns("payment", results, None)
        assert any("PaymentProcessor" in p for p in patterns)

    def test_stop_words_excluded(self):
        """Common stop words are not included as patterns."""
        patterns = generate_grep_patterns("find the function for import", [], None)
        # None of these should appear as standalone patterns
        for p in patterns:
            assert p not in {"find", "the", "for", "import"}

    def test_short_terms_excluded(self):
        """Terms shorter than 3 chars are excluded."""
        patterns = generate_grep_patterns("go to db", [], None)
        for p in patterns:
            assert p not in {"go", "to", "db"}

    def test_pattern_cap(self):
        """Pattern list is capped at 10."""
        # Create a query with many identifiers + results with many names
        results = [
            _make_result(function_name=f"func_{i}", class_name=f"Class{i}") for i in range(10)
        ]
        patterns = generate_grep_patterns(
            "handle process create update delete build check validate run execute",
            results,
            None,
        )
        assert len(patterns) <= 10

    def test_deduplication(self):
        """Duplicate patterns are removed."""
        results = [
            _make_result(function_name="process_order"),
            _make_result(function_name="process_order"),
        ]
        patterns = generate_grep_patterns("process_order", results, None)
        # Count occurrences of process_order pattern
        matches = [p for p in patterns if "process_order" in p]
        assert len(matches) == 1

    def test_empty_query_and_results(self):
        """Empty inputs produce empty patterns."""
        patterns = generate_grep_patterns("", [], None)
        assert patterns == []


class TestDeduplicateGrep:
    """Test deduplication of grep results against semantic results."""

    def test_removes_overlapping_results(self):
        """Grep results within semantic result line ranges are removed."""
        semantic = [_make_result(file_path="src/main.py", line_start=5, line_end=15)]
        grep = [
            GrepResult("src/main.py", 10, "  x = 1", "x"),
            GrepResult("src/other.py", 10, "  y = 2", "y"),
        ]
        result = _deduplicate_grep(grep, semantic)
        assert len(result) == 1
        assert result[0].file_path == "src/other.py"

    def test_keeps_non_overlapping(self):
        """Grep results outside semantic ranges are kept."""
        semantic = [_make_result(file_path="src/main.py", line_start=5, line_end=10)]
        grep = [
            GrepResult("src/main.py", 20, "  z = 3", "z"),
        ]
        result = _deduplicate_grep(grep, semantic)
        assert len(result) == 1

    def test_empty_semantic_keeps_all(self):
        """When no semantic results, all grep results are kept."""
        grep = [
            GrepResult("src/a.py", 1, "line", "pat"),
            GrepResult("src/b.py", 2, "line", "pat"),
        ]
        result = _deduplicate_grep(grep, [])
        assert len(result) == 2


class TestRunGrep:
    """Test ripgrep execution with all 5 failure modes."""

    @pytest.mark.asyncio
    async def test_rg_not_installed(self):
        """FileNotFoundError returns empty list."""
        with patch(
            "clew.search.grep.asyncio.create_subprocess_exec",
            side_effect=FileNotFoundError,
        ):
            result = await run_grep(["test"], project_root=__import__("pathlib").Path("."))
            assert result == []

    @pytest.mark.asyncio
    async def test_rg_timeout(self):
        """TimeoutError returns empty list."""
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(side_effect=asyncio.TimeoutError)
        mock_process.kill = Mock()

        with patch("clew.search.grep.asyncio.create_subprocess_exec", return_value=mock_process):
            result = await run_grep(
                ["test"],
                project_root=__import__("pathlib").Path("."),
                timeout=0.1,
            )
            assert result == []

    @pytest.mark.asyncio
    async def test_rg_no_matches(self):
        """Exit code 1 (no matches) returns empty list."""
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"", b""))
        mock_process.returncode = 1

        with patch("clew.search.grep.asyncio.create_subprocess_exec", return_value=mock_process):
            result = await run_grep(["test"], project_root=__import__("pathlib").Path("."))
            assert result == []

    @pytest.mark.asyncio
    async def test_rg_error_exit_code(self):
        """Exit code 2 (rg error) returns empty list."""
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"", b"bad pattern"))
        mock_process.returncode = 2

        with patch("clew.search.grep.asyncio.create_subprocess_exec", return_value=mock_process):
            result = await run_grep(["test"], project_root=__import__("pathlib").Path("."))
            assert result == []

    @pytest.mark.asyncio
    async def test_rg_malformed_json(self):
        """Malformed JSON lines are skipped."""
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"not valid json\n{bad\n", b""))
        mock_process.returncode = 0

        with patch("clew.search.grep.asyncio.create_subprocess_exec", return_value=mock_process):
            result = await run_grep(["test"], project_root=__import__("pathlib").Path("."))
            assert result == []

    @pytest.mark.asyncio
    async def test_rg_successful_parse(self):
        """Valid rg JSON output is parsed correctly."""
        match_line = json.dumps(
            {
                "type": "match",
                "data": {
                    "path": {"text": "src/main.py"},
                    "line_number": 42,
                    "lines": {"text": "def process_order():\n"},
                    "submatches": [{"match": {"text": "process_order"}, "start": 4, "end": 17}],
                },
            }
        )
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(match_line.encode(), b""))
        mock_process.returncode = 0

        with patch("clew.search.grep.asyncio.create_subprocess_exec", return_value=mock_process):
            result = await run_grep(
                ["process_order"],
                project_root=__import__("pathlib").Path("."),
            )
            assert len(result) == 1
            assert result[0].file_path == "src/main.py"
            assert result[0].line_number == 42
            assert result[0].line_content == "def process_order():"
            assert result[0].pattern_matched == "process_order"

    @pytest.mark.asyncio
    async def test_rg_max_count_in_command(self):
        """Verify --max-count is passed to rg command."""
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"", b""))
        mock_process.returncode = 1

        with patch(
            "clew.search.grep.asyncio.create_subprocess_exec", return_value=mock_process
        ) as mock_exec:
            await run_grep(
                ["test"],
                project_root=__import__("pathlib").Path("/project"),
                max_count=250,
            )
            cmd_args = mock_exec.call_args[0]
            # Find --max-count and the value after it
            idx = list(cmd_args).index("--max-count")
            assert cmd_args[idx + 1] == "250"

    @pytest.mark.asyncio
    async def test_rg_file_globs(self):
        """Verify --glob flags are passed when file_globs specified."""
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"", b""))
        mock_process.returncode = 1

        with patch(
            "clew.search.grep.asyncio.create_subprocess_exec", return_value=mock_process
        ) as mock_exec:
            await run_grep(
                ["test"],
                project_root=__import__("pathlib").Path("/project"),
                file_globs=["*.py", "*.ts"],
            )
            cmd_args = list(mock_exec.call_args[0])
            assert "--glob" in cmd_args
            assert "*.py" in cmd_args
            assert "*.ts" in cmd_args

    @pytest.mark.asyncio
    async def test_rg_empty_patterns(self):
        """Empty pattern list returns empty results."""
        result = await run_grep([], project_root=__import__("pathlib").Path("."))
        assert result == []

    @pytest.mark.asyncio
    async def test_rg_combined_pattern(self):
        """Multiple patterns are combined with | (OR)."""
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"", b""))
        mock_process.returncode = 1

        with patch(
            "clew.search.grep.asyncio.create_subprocess_exec", return_value=mock_process
        ) as mock_exec:
            await run_grep(
                ["foo", "bar", "baz"],
                project_root=__import__("pathlib").Path("/project"),
            )
            cmd_args = list(mock_exec.call_args[0])
            # Find the pattern argument (after -e)
            idx = cmd_args.index("-e")
            pattern = cmd_args[idx + 1]
            assert "(foo)|(bar)|(baz)" == pattern


class TestGrepResultsToSearchResults:
    """Test GrepResult -> SearchResult conversion."""

    def test_basic_conversion(self):
        grep_results = [
            GrepResult("src/main.py", 42, "def process_order():", "process_order"),
        ]
        search_results = grep_results_to_search_results(grep_results)
        assert len(search_results) == 1
        r = search_results[0]
        assert r.file_path == "src/main.py"
        assert r.line_start == 42
        assert r.line_end == 42
        assert r.score == 0.0
        assert r.source == "grep"
        assert r.chunk_type == "grep_match"
        assert r.content == "def process_order():"

    def test_multiple_results(self):
        grep_results = [
            GrepResult("a.py", 1, "line1", "pat"),
            GrepResult("b.py", 2, "line2", "pat"),
            GrepResult("c.py", 3, "line3", "pat"),
        ]
        search_results = grep_results_to_search_results(grep_results)
        assert len(search_results) == 3
        assert all(r.source == "grep" for r in search_results)
        assert all(r.score == 0.0 for r in search_results)

    def test_empty_input(self):
        assert grep_results_to_search_results([]) == []

    def test_preserves_content(self):
        """Line content is preserved including special characters."""
        grep_results = [
            GrepResult("main.py", 1, '    raise ValueError("bad input")', "ValueError"),
        ]
        search_results = grep_results_to_search_results(grep_results)
        assert search_results[0].content == '    raise ValueError("bad input")'

    @pytest.mark.asyncio
    async def test_rg_skips_non_match_types(self):
        """Non-match JSON lines (begin, end, summary) are skipped."""
        lines = "\n".join(
            [
                json.dumps({"type": "begin", "data": {"path": {"text": "f.py"}}}),
                json.dumps(
                    {
                        "type": "match",
                        "data": {
                            "path": {"text": "f.py"},
                            "line_number": 1,
                            "lines": {"text": "x\n"},
                            "submatches": [{"match": {"text": "x"}, "start": 0, "end": 1}],
                        },
                    }
                ),
                json.dumps({"type": "end", "data": {"path": {"text": "f.py"}}}),
                json.dumps({"type": "summary", "data": {}}),
            ]
        )
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(lines.encode(), b""))
        mock_process.returncode = 0

        with patch("clew.search.grep.asyncio.create_subprocess_exec", return_value=mock_process):
            result = await run_grep(["x"], project_root=__import__("pathlib").Path("."))
            assert len(result) == 1
