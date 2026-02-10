# Compact MCP Responses & CACHE_DIR Fix — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce MCP tool response sizes by ~20x via compact-by-default mode, and fix trace returning empty by resolving CACHE_DIR from git root.

**Architecture:** Two independent changes: (1) Two-tier response format (compact/full) in mcp_server.py, pulling docstring through the SearchResult pipeline for richer snippets. (2) Git-root-aware CACHE_DIR resolution in config.py so CLI, MCP server, and indexer all find the same state.db.

**Tech Stack:** Python, pytest, unittest.mock, subprocess (for git root detection)

---

### Task 1: CACHE_DIR Resolution — Tests

**Files:**
- Modify: `tests/unit/test_config.py`

**Step 1: Write failing tests for cache dir resolution**

Add these tests to `tests/unit/test_config.py`:

```python
import importlib
import os
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestResolveCacheDir:
    """Test _resolve_cache_dir() resolution order."""

    def test_env_var_takes_priority(self) -> None:
        """CLEW_CACHE_DIR env var overrides all other resolution."""
        with patch.dict(os.environ, {"CLEW_CACHE_DIR": "/tmp/custom-cache"}):
            from clew.config import _resolve_cache_dir

            result = _resolve_cache_dir()
            assert result == Path("/tmp/custom-cache")

    def test_git_root_used_when_no_env_var(self) -> None:
        """Falls back to {git_root}/.clew/ when no env var set."""
        env_copy = {k: v for k, v in os.environ.items() if k != "CLEW_CACHE_DIR"}
        with patch.dict(os.environ, env_copy, clear=True):
            with patch("clew.config.subprocess") as mock_subprocess:
                mock_result = MagicMock()
                mock_result.returncode = 0
                mock_result.stdout = "/Users/me/myproject\n"
                mock_subprocess.run.return_value = mock_result

                from clew.config import _resolve_cache_dir

                result = _resolve_cache_dir()
                assert result == Path("/Users/me/myproject/.clew")

    def test_cwd_fallback_when_not_in_git_repo(self) -> None:
        """Falls back to CWD-relative .clew/ when not in a git repo."""
        env_copy = {k: v for k, v in os.environ.items() if k != "CLEW_CACHE_DIR"}
        with patch.dict(os.environ, env_copy, clear=True):
            with patch("clew.config.subprocess") as mock_subprocess:
                mock_result = MagicMock()
                mock_result.returncode = 128  # git error: not a repo
                mock_result.stdout = ""
                mock_subprocess.run.return_value = mock_result

                from clew.config import _resolve_cache_dir

                result = _resolve_cache_dir()
                assert result == Path(".clew")

    def test_cwd_fallback_when_git_not_installed(self) -> None:
        """Falls back to CWD-relative .clew/ when git is not installed."""
        env_copy = {k: v for k, v in os.environ.items() if k != "CLEW_CACHE_DIR"}
        with patch.dict(os.environ, env_copy, clear=True):
            with patch("clew.config.subprocess") as mock_subprocess:
                mock_subprocess.run.side_effect = FileNotFoundError("git not found")

                from clew.config import _resolve_cache_dir

                result = _resolve_cache_dir()
                assert result == Path(".clew")

    def test_cwd_fallback_when_git_times_out(self) -> None:
        """Falls back to CWD-relative .clew/ when git times out."""
        import subprocess as real_subprocess

        env_copy = {k: v for k, v in os.environ.items() if k != "CLEW_CACHE_DIR"}
        with patch.dict(os.environ, env_copy, clear=True):
            with patch("clew.config.subprocess") as mock_subprocess:
                mock_subprocess.run.side_effect = real_subprocess.TimeoutExpired(
                    cmd="git", timeout=5
                )
                mock_subprocess.TimeoutExpired = real_subprocess.TimeoutExpired

                from clew.config import _resolve_cache_dir

                result = _resolve_cache_dir()
                assert result == Path(".clew")
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_config.py::TestResolveCacheDir -v`
Expected: FAIL — `ImportError: cannot import name '_resolve_cache_dir'`

**Step 3: Commit**

```bash
git add tests/unit/test_config.py
git commit -m "test: add failing tests for cache dir resolution"
```

---

### Task 2: CACHE_DIR Resolution — Implementation

**Files:**
- Modify: `clew/config.py`

**Step 1: Implement `_resolve_cache_dir()` and update Environment**

Replace `clew/config.py` contents with:

```python
"""Config loading and validation."""

import os
import subprocess
from pathlib import Path


def _resolve_cache_dir() -> Path:
    """Resolve cache directory: env var > git root > CWD fallback.

    Resolution order:
    1. CLEW_CACHE_DIR env var (absolute path)
    2. {git_root}/.clew/ (auto-detected)
    3. .clew/ relative to CWD (fallback)
    """
    env_val = os.environ.get("CLEW_CACHE_DIR")
    if env_val:
        return Path(env_val)

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip()) / ".clew"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return Path(".clew")


class Environment:
    """Load environment variables with defaults."""

    VOYAGE_API_KEY: str = os.environ.get("VOYAGE_API_KEY", "")
    QDRANT_URL: str = os.environ.get("QDRANT_URL", "http://localhost:6333")
    QDRANT_API_KEY: str | None = os.environ.get("QDRANT_API_KEY") or None
    CACHE_DIR: Path = _resolve_cache_dir()
    LOG_LEVEL: str = os.environ.get("CLEW_LOG_LEVEL", "INFO")
    ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")

    @classmethod
    def validate(cls) -> list[str]:
        """Return list of missing required env vars."""
        errors: list[str] = []
        if not cls.VOYAGE_API_KEY:
            errors.append("VOYAGE_API_KEY is required")
        return errors
```

**Step 2: Run tests to verify they pass**

Run: `pytest tests/unit/test_config.py -v`
Expected: All PASS

**Step 3: Run full suite to check nothing broke**

Run: `pytest --tb=short -q`
Expected: All existing tests still pass

**Step 4: Commit**

```bash
git add clew/config.py
git commit -m "fix: resolve CACHE_DIR from git root so MCP server finds state.db"
```

---

### Task 3: Add `docstring` to SearchResult Pipeline — Tests

**Files:**
- Modify: `tests/unit/test_search_engine.py` (or create `tests/unit/test_hybrid.py` if hybrid tests exist there)

**Step 1: Write failing test for docstring extraction**

Find the existing test file for hybrid search. Add a test that verifies `docstring` is extracted from Qdrant payload:

```python
# Add to the test file that tests HybridSearchEngine._point_to_result
def test_point_to_result_extracts_docstring(self) -> None:
    """Verify docstring is pulled from Qdrant payload into SearchResult."""
    from unittest.mock import Mock
    from clew.search.hybrid import HybridSearchEngine

    point = Mock()
    point.score = 0.9
    point.payload = {
        "content": "def foo(): pass",
        "file_path": "src/main.py",
        "docstring": "Do the foo thing.",
        "signature": "def foo():",
    }

    result = HybridSearchEngine._point_to_result(point)
    assert result.docstring == "Do the foo thing."


def test_point_to_result_docstring_defaults_empty(self) -> None:
    """Verify docstring defaults to empty string when not in payload."""
    from unittest.mock import Mock
    from clew.search.hybrid import HybridSearchEngine

    point = Mock()
    point.score = 0.9
    point.payload = {
        "content": "def foo(): pass",
        "file_path": "src/main.py",
    }

    result = HybridSearchEngine._point_to_result(point)
    assert result.docstring == ""
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_search_engine.py -k "docstring" -v`
Expected: FAIL — `AttributeError: SearchResult has no attribute 'docstring'`

**Step 3: Commit**

```bash
git add tests/unit/test_search_engine.py
git commit -m "test: add failing tests for docstring in SearchResult"
```

---

### Task 4: Add `docstring` to SearchResult Pipeline — Implementation

**Files:**
- Modify: `clew/search/models.py`
- Modify: `clew/search/hybrid.py`

**Step 1: Add `docstring` field to SearchResult**

In `clew/search/models.py`, add after the `chunk_id` field:

```python
    docstring: str = ""
```

**Step 2: Extract `docstring` from Qdrant payload**

In `clew/search/hybrid.py`, in `_point_to_result()`, add after the `chunk_id` line:

```python
            docstring=payload.get("docstring", ""),
```

**Step 3: Run tests to verify they pass**

Run: `pytest tests/unit/test_search_engine.py -k "docstring" -v`
Expected: PASS

**Step 4: Run full suite**

Run: `pytest --tb=short -q`
Expected: All pass

**Step 5: Commit**

```bash
git add clew/search/models.py clew/search/hybrid.py
git commit -m "feat: pull docstring from Qdrant payload into SearchResult"
```

---

### Task 5: Compact Response Mode — Tests

**Files:**
- Modify: `tests/unit/test_mcp_server.py`

**Step 1: Update mock helper and write failing tests**

First, update `_mock_search_result` to include new fields:

```python
def _mock_search_result(**overrides):
    """Create a mock SearchResult with defaults."""
    defaults = {
        "file_path": "src/main.py",
        "content": "def hello():\n    \"\"\"Say hello.\"\"\"\n    print('hello')\n    return True",
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
    }
    defaults.update(overrides)
    return Mock(**defaults)
```

Then add these test classes:

```python
class TestCompactResponse:
    """Test compact vs full response modes."""

    @patch("clew.mcp_server._get_components")
    async def test_search_compact_by_default(self, mock_get) -> None:
        """search() returns compact results (no content field) by default."""
        components = _mock_components()
        result = _mock_search_result()
        components.search_engine.search.return_value = Mock(results=[result])
        mock_get.return_value = components

        results = await search("test query")
        assert isinstance(results, list)
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
        components.search_engine.search.return_value = Mock(results=[result])
        mock_get.return_value = components

        results = await search("test query", detail="full")
        assert isinstance(results, list)
        assert "content" in results[0]
        assert "snippet" in results[0]

    @patch("clew.mcp_server._get_components")
    async def test_search_default_limit_is_5(self, mock_get) -> None:
        """search() defaults to limit=5."""
        components = _mock_components()
        components.search_engine.search.return_value = Mock(results=[])
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
    async def test_explain_limit_is_5(self, mock_get) -> None:
        """explain() uses limit=5 internally."""
        components = _mock_components()
        components.search_engine.search.return_value = Mock(results=[])
        mock_get.return_value = components

        await explain("src/main.py", symbol="hello")
        call_args = components.search_engine.search.call_args
        request = call_args[0][0]
        assert request.limit == 5
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_mcp_server.py -k "Compact or Snippet or IncludeRelated or ExplainCompact" -v`
Expected: FAIL — functions don't accept `detail` param yet, `_build_snippet` doesn't exist

**Step 3: Commit**

```bash
git add tests/unit/test_mcp_server.py
git commit -m "test: add failing tests for compact response mode"
```

---

### Task 6: Compact Response Mode — Implementation

**Files:**
- Modify: `clew/mcp_server.py`

**Step 1: Add snippet builder and compact result formatter**

Add after the existing `_result_to_dict` function (replacing it):

```python
SNIPPET_MAX_LINES = 5


def _build_snippet(result: Any) -> str:
    """Build a compact preview: signature + docstring if available, else first lines."""
    sig = getattr(result, "signature", "")
    doc = getattr(result, "docstring", "")
    if sig and doc:
        doc_lines = doc.splitlines()
        remaining = SNIPPET_MAX_LINES - 1
        doc_preview = "\n".join(doc_lines[:remaining])
        return f"{sig}\n{doc_preview}"
    if sig:
        return sig
    content = getattr(result, "content", "")
    lines = content.splitlines()
    return "\n".join(lines[:SNIPPET_MAX_LINES])


def _compact_result_to_dict(result: Any) -> dict[str, Any]:
    """Convert a SearchResult to a compact dict (no full content)."""
    return {
        "file_path": result.file_path,
        "line_start": result.line_start,
        "line_end": result.line_end,
        "score": result.score,
        "chunk_type": result.chunk_type,
        "language": result.language,
        "function_name": result.function_name,
        "class_name": result.class_name,
        "snippet": _build_snippet(result),
    }


def _result_to_dict(result: Any, detail: str = "compact") -> dict[str, Any]:
    """Convert a SearchResult to a dict, respecting detail level."""
    if detail == "compact":
        return _compact_result_to_dict(result)
    return {
        **_compact_result_to_dict(result),
        "content": result.content,
    }
```

**Step 2: Update `search` tool**

Change the `search` function signature and body:
- Add `detail: str = "compact"` parameter
- Change default `limit` from `10` to `5`
- Update the return to use `_result_to_dict(r, detail)` instead of `_result_to_dict(r)`

```python
@mcp.tool()
async def search(
    query: str,
    limit: int = 5,
    collection: str = "code",
    active_file: str | None = None,
    intent: str | None = None,
    filters: dict[str, str] | None = None,
    detail: str = "compact",
) -> list[dict[str, Any]] | dict[str, str]:
    """Search the codebase for relevant code snippets.

    Args:
        query: Natural language search query
        limit: Maximum number of results (default 5)
        collection: Collection to search (default "code")
        active_file: Currently open file path for context boosting
        intent: Search intent hint (code, docs, debug, location)
        filters: Metadata filters (language, chunk_type, app_name, layer, is_test)
        detail: Response detail level — "compact" (default) returns snippets, "full" returns complete source
    """
    # ... existing try/except body, but change the return line:
    #   return [_result_to_dict(r, detail) for r in response.results]
```

**Step 3: Update `get_context` tool**

Add `include_related: bool = False` parameter. Only run related search when requested:

```python
@mcp.tool()
async def get_context(
    file_path: str,
    line_start: int | None = None,
    line_end: int | None = None,
    include_related: bool = False,
) -> dict[str, Any]:
    """Get file content with optional related code chunks.

    Args:
        file_path: Path to the file
        line_start: Optional start line (1-indexed)
        line_end: Optional end line (1-indexed)
        include_related: If True, search for related code chunks (compact format)
    """
    # ... existing file-reading logic ...

    result_dict: dict[str, Any] = {
        "file_path": file_path,
        "content": content,
        "language": language,
    }

    if include_related:
        components = _get_components()
        request = SearchRequest(query=file_path, limit=5, active_file=file_path)
        response = await components.search_engine.search(request)
        result_dict["related_chunks"] = [_compact_result_to_dict(r) for r in response.results]

    return result_dict
```

**Step 4: Update `explain` tool**

Add `detail` parameter, lower limit to 5:

```python
@mcp.tool()
async def explain(
    file_path: str,
    symbol: str | None = None,
    question: str | None = None,
    detail: str = "compact",
) -> dict[str, Any]:
    """Search for context about a symbol or question in a file.

    Args:
        file_path: Path to the file for context
        symbol: Symbol name to look up (class, function, variable)
        question: Natural language question about the code
        detail: Response detail level — "compact" (default) or "full"
    """
    # ... existing logic but change limit from 10 to 5:
    #   request = SearchRequest(query=query, limit=5, active_file=file_path)
    # ... and change the return:
    #   "related_chunks": [_result_to_dict(r, detail) for r in response.results],
```

**Step 5: Run tests to verify they pass**

Run: `pytest tests/unit/test_mcp_server.py -v`
Expected: All PASS

**Step 6: Run full test suite**

Run: `pytest --tb=short -q`
Expected: All pass

**Step 7: Lint and type check**

Run: `ruff check . && ruff format --check . && mypy clew/`
Expected: Clean

**Step 8: Commit**

```bash
git add clew/mcp_server.py
git commit -m "feat: compact MCP responses by default, opt-in full detail"
```

---

### Task 7: Update Existing Tests for New Defaults

**Files:**
- Modify: `tests/unit/test_mcp_server.py`

Existing tests that assert on `_result_to_dict` output (e.g., checking for `"content"` key in search results) will break because compact mode is now default. Update them:

**Step 1: Find and fix broken assertions**

Any test that does `assert results[0]["content"] == ...` on `search()` output needs updating:
- If the test is verifying the search pipeline works, change it to check `results[0]["snippet"]` instead
- If the test specifically needs full content, add `detail="full"` to the call

Similarly, `get_context` tests that expect `related_chunks` by default need `include_related=True` added.

**Step 2: Run full suite and iterate**

Run: `pytest tests/unit/test_mcp_server.py -v`
Fix any remaining failures.

**Step 3: Final full suite run**

Run: `pytest --tb=short -q && ruff check . && ruff format --check . && mypy clew/`
Expected: All green

**Step 4: Commit**

```bash
git add tests/unit/test_mcp_server.py
git commit -m "test: update existing tests for compact-by-default responses"
```
