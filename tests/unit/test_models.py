"""Tests for SearchConfig in models.py."""

from code_search.models import SearchConfig


class TestSearchConfig:
    def test_defaults(self) -> None:
        config = SearchConfig()
        assert config.rerank_candidates == 30
        assert config.rerank_top_k == 10
        assert config.rerank_model == "rerank-2.5"

    def test_custom_candidates(self) -> None:
        config = SearchConfig(rerank_candidates=50)
        assert config.rerank_candidates == 50

    def test_bounds_enforced(self) -> None:
        import pytest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            SearchConfig(rerank_candidates=5)  # below 10
        with pytest.raises(ValidationError):
            SearchConfig(rerank_candidates=200)  # above 100
