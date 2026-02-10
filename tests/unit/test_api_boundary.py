"""Tests for cross-language API boundary matching."""

from __future__ import annotations

from code_search.indexer.extractors.api_boundary import APIBoundaryMatcher
from code_search.indexer.relationships import Relationship


class TestAPIBoundaryMatching:
    def test_exact_match(self) -> None:
        matcher = APIBoundaryMatcher()
        url_patterns = [
            {"pattern": "/api/users/", "view": "views.user_list", "file_path": "users/urls.py"},
        ]
        api_calls = [
            Relationship(
                source_entity="src/api.ts::getUsers",
                relationship="calls_api",
                target_entity="/api/users/",
                file_path="src/api.ts",
                confidence="inferred",
            ),
        ]
        matches = matcher.match(url_patterns, api_calls)
        assert len(matches) == 1
        assert matches[0].source_entity == "src/api.ts::getUsers"
        assert matches[0].target_entity == "users/urls.py::views.user_list"
        assert matches[0].relationship == "calls_api"

    def test_no_match(self) -> None:
        matcher = APIBoundaryMatcher()
        url_patterns = [
            {"pattern": "/api/users/", "view": "views.user_list", "file_path": "users/urls.py"},
        ]
        api_calls = [
            Relationship(
                source_entity="src/api.ts::getItems",
                relationship="calls_api",
                target_entity="/api/items/",
                file_path="src/api.ts",
                confidence="inferred",
            ),
        ]
        matches = matcher.match(url_patterns, api_calls)
        assert len(matches) == 0

    def test_prefix_match(self) -> None:
        """Frontend call to /api/users matches backend /api/users/."""
        matcher = APIBoundaryMatcher()
        url_patterns = [
            {"pattern": "/api/users/", "view": "views.user_list", "file_path": "users/urls.py"},
        ]
        api_calls = [
            Relationship(
                source_entity="src/api.ts::getUsers",
                relationship="calls_api",
                target_entity="/api/users",
                file_path="src/api.ts",
                confidence="inferred",
            ),
        ]
        matches = matcher.match(url_patterns, api_calls)
        assert len(matches) == 1

    def test_parameterized_match(self) -> None:
        """Frontend /api/users/123 matches backend /api/users/<int:pk>/."""
        matcher = APIBoundaryMatcher()
        url_patterns = [
            {
                "pattern": "/api/users/<int:pk>/",
                "view": "views.user_detail",
                "file_path": "users/urls.py",
            },
        ]
        api_calls = [
            Relationship(
                source_entity="src/api.ts::getUser",
                relationship="calls_api",
                target_entity="/api/users/123",
                file_path="src/api.ts",
                confidence="inferred",
            ),
        ]
        matches = matcher.match(url_patterns, api_calls)
        assert len(matches) >= 1

    def test_empty_url_patterns(self) -> None:
        matcher = APIBoundaryMatcher()
        api_calls = [
            Relationship("src/api.ts::get", "calls_api", "/api/x/", "src/api.ts"),
        ]
        matches = matcher.match([], api_calls)
        assert len(matches) == 0

    def test_empty_api_calls(self) -> None:
        matcher = APIBoundaryMatcher()
        url_patterns = [
            {"pattern": "/api/users/", "view": "views.user_list", "file_path": "users/urls.py"},
        ]
        matches = matcher.match(url_patterns, [])
        assert len(matches) == 0

    def test_pattern_without_view(self) -> None:
        """URL pattern without view falls back to file_path as target."""
        matcher = APIBoundaryMatcher()
        url_patterns = [
            {"pattern": "/api/users/", "file_path": "users/urls.py"},
        ]
        api_calls = [
            Relationship("src/api.ts::get", "calls_api", "/api/users/", "src/api.ts"),
        ]
        matches = matcher.match(url_patterns, api_calls)
        assert len(matches) == 1
        assert matches[0].target_entity == "users/urls.py"
