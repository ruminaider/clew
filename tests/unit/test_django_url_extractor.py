"""Tests for Django URL pattern extraction."""

from __future__ import annotations

import pytest

from code_search.chunker.parser import ASTParser
from code_search.indexer.extractors.django_urls import DjangoURLExtractor


@pytest.fixture
def parser() -> ASTParser:
    return ASTParser()


@pytest.fixture
def extractor() -> DjangoURLExtractor:
    return DjangoURLExtractor()


class TestURLPatternExtraction:
    def test_path_pattern(self, extractor: DjangoURLExtractor, parser: ASTParser) -> None:
        source = """from django.urls import path
from . import views

urlpatterns = [
    path("api/users/", views.user_list, name="user-list"),
    path("api/users/<int:pk>/", views.user_detail, name="user-detail"),
]
"""
        tree = parser.parse(source, "python")
        patterns = extractor.extract_url_patterns(tree, source, "app/urls.py")
        assert "/api/users/" in [p["pattern"] for p in patterns]
        assert "/api/users/<int:pk>/" in [p["pattern"] for p in patterns]

    def test_path_with_view_name(self, extractor: DjangoURLExtractor, parser: ASTParser) -> None:
        source = 'path("api/items/", views.item_list)\n'
        tree = parser.parse(source, "python")
        patterns = extractor.extract_url_patterns(tree, source, "app/urls.py")
        assert any(p["view"] == "views.item_list" for p in patterns)

    def test_non_urls_file_returns_empty(
        self, extractor: DjangoURLExtractor, parser: ASTParser
    ) -> None:
        """Only extract from files named urls.py."""
        source = 'path("api/items/", views.item_list)\n'
        tree = parser.parse(source, "python")
        patterns = extractor.extract_url_patterns(tree, source, "app/views.py")
        assert len(patterns) == 0

    def test_include_pattern(self, extractor: DjangoURLExtractor, parser: ASTParser) -> None:
        source = """from django.urls import include, path

urlpatterns = [
    path("api/", include("users.urls")),
]
"""
        tree = parser.parse(source, "python")
        patterns = extractor.extract_url_patterns(tree, source, "project/urls.py")
        assert any(p.get("include") == "users.urls" for p in patterns)
