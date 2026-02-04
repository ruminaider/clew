"""Tests for SearchConfig and IndexingConfig in models.py."""

from code_search.models import IndexingConfig, SearchConfig


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


class TestIndexingConfigNlDescription:
    def test_indexing_config_nl_description_defaults(self) -> None:
        config = IndexingConfig()
        assert config.nl_description_enabled is False
        assert config.nl_description_model == "claude-sonnet-4-5-20250929"
        assert config.nl_description_max_concurrent == 5

    def test_indexing_config_nl_description_custom(self) -> None:
        config = IndexingConfig(
            nl_description_enabled=True,
            nl_description_model="claude-haiku-4-5-20251001",
            nl_description_max_concurrent=10,
        )
        assert config.nl_description_enabled is True
        assert config.nl_description_model == "claude-haiku-4-5-20251001"
        assert config.nl_description_max_concurrent == 10

    def test_indexing_config_nl_description_max_concurrent_bounds(self) -> None:
        import pytest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            IndexingConfig(nl_description_max_concurrent=0)  # below 1
        with pytest.raises(ValidationError):
            IndexingConfig(nl_description_max_concurrent=21)  # above 20
