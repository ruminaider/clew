"""Tests for search pipeline data models."""

from clew.search.models import QueryIntent, SearchRequest, SearchResponse, SearchResult


class TestQueryIntent:
    def test_code_value(self) -> None:
        assert QueryIntent.CODE.value == "code"

    def test_debug_value(self) -> None:
        assert QueryIntent.DEBUG.value == "debug"

    def test_docs_value(self) -> None:
        assert QueryIntent.DOCS.value == "docs"

    def test_location_value(self) -> None:
        assert QueryIntent.LOCATION.value == "location"


class TestSearchResult:
    def test_create_with_required_fields(self) -> None:
        result = SearchResult(content="def foo():", file_path="main.py", score=0.95)
        assert result.content == "def foo():"
        assert result.file_path == "main.py"
        assert result.score == 0.95

    def test_default_optional_fields(self) -> None:
        result = SearchResult(content="x", file_path="f.py", score=0.5)
        assert result.chunk_type == ""
        assert result.line_start == 0
        assert result.language == ""
        assert result.signature == ""
        assert result.app_name == ""
        assert result.layer == ""
        assert result.chunk_id == ""
        assert result.importance_score == 0.0

    def test_importance_score_field(self) -> None:
        result = SearchResult(
            content="def foo():", file_path="main.py", score=0.95, importance_score=0.75
        )
        assert result.importance_score == 0.75

    def test_all_metadata_fields(self) -> None:
        result = SearchResult(
            content="def foo():",
            file_path="backend/care/models.py",
            score=0.9,
            chunk_type="method",
            class_name="Prescription",
            function_name="is_expired",
            signature="def is_expired(self) -> bool",
            app_name="care",
            layer="model",
            chunk_id="backend/care/models.py::method::Prescription.is_expired",
        )
        assert result.signature == "def is_expired(self) -> bool"
        assert result.app_name == "care"
        assert result.layer == "model"
        assert result.chunk_id == "backend/care/models.py::method::Prescription.is_expired"


class TestSearchRequest:
    def test_defaults(self) -> None:
        req = SearchRequest(query="find auth")
        assert req.collection == "code"
        assert req.limit == 10
        assert req.intent is None
        assert req.active_file is None

    def test_custom_values(self) -> None:
        req = SearchRequest(
            query="q",
            collection="docs",
            limit=5,
            intent=QueryIntent.DEBUG,
            active_file="src/auth.py",
        )
        assert req.collection == "docs"
        assert req.intent == QueryIntent.DEBUG
        assert req.active_file == "src/auth.py"


class TestSearchResponse:
    def test_create(self) -> None:
        result = SearchResult(content="x", file_path="f.py", score=0.5)
        resp = SearchResponse(
            results=[result],
            query_enhanced="expanded query",
            total_candidates=30,
            intent=QueryIntent.CODE,
        )
        assert resp.query_enhanced == "expanded query"
        assert resp.total_candidates == 30
        assert resp.intent == QueryIntent.CODE
        assert len(resp.results) == 1

    def test_empty_response(self) -> None:
        resp = SearchResponse(
            results=[],
            query_enhanced="q",
            total_candidates=0,
            intent=QueryIntent.CODE,
        )
        assert resp.results == []
