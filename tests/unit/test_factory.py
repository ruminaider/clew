"""Tests for the component factory."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from code_search.exceptions import QdrantConnectionError
from code_search.factory import Components, create_components


@pytest.fixture
def mock_env() -> MagicMock:
    """Mock Environment with sensible defaults."""
    env = MagicMock()
    env.VOYAGE_API_KEY = "test-voyage-key"
    env.QDRANT_URL = "http://localhost:6333"
    env.QDRANT_API_KEY = None
    env.CACHE_DIR = Path("/tmp/test-cache")
    env.ANTHROPIC_API_KEY = ""
    return env


@pytest.fixture
def _patch_all(mock_env: MagicMock) -> dict[str, MagicMock]:
    """Patch all external dependencies and return dict of mocks."""
    with (
        patch("code_search.factory.Environment", return_value=mock_env) as m_env,
        patch("code_search.factory.QdrantManager") as m_qdrant,
        patch("code_search.factory.create_embedding_provider") as m_embedder,
        patch("code_search.factory.CacheDB") as m_cache,
        patch("code_search.factory.HybridSearchEngine") as m_hybrid,
        patch("code_search.factory.RerankProvider") as m_rerank,
        patch("code_search.factory.IndexingPipeline") as m_pipeline,
        patch("code_search.factory.SearchEngine") as m_search_engine,
    ):
        yield {
            "Environment": m_env,
            "QdrantManager": m_qdrant,
            "create_embedding_provider": m_embedder,
            "CacheDB": m_cache,
            "HybridSearchEngine": m_hybrid,
            "RerankProvider": m_rerank,
            "IndexingPipeline": m_pipeline,
            "SearchEngine": m_search_engine,
            "env": mock_env,
        }


class TestCreateComponentsDefaultConfig:
    """Test create_components with no config_path (defaults)."""

    def test_returns_components_dataclass(self, _patch_all: dict[str, MagicMock]) -> None:
        result = create_components()
        assert isinstance(result, Components)

    def test_creates_qdrant_manager(self, _patch_all: dict[str, MagicMock]) -> None:
        create_components()
        _patch_all["QdrantManager"].assert_called_once_with(
            url="http://localhost:6333", api_key=None
        )

    def test_creates_embedding_provider(self, _patch_all: dict[str, MagicMock]) -> None:
        create_components()
        _patch_all["create_embedding_provider"].assert_called_once()

    def test_creates_cache_db(self, _patch_all: dict[str, MagicMock]) -> None:
        create_components()
        _patch_all["CacheDB"].assert_called_once_with(Path("/tmp/test-cache"))

    def test_creates_hybrid_search_engine(self, _patch_all: dict[str, MagicMock]) -> None:
        create_components()
        _patch_all["HybridSearchEngine"].assert_called_once_with(
            qdrant=_patch_all["QdrantManager"].return_value,
            embedder=_patch_all["create_embedding_provider"].return_value,
        )

    def test_creates_search_engine(self, _patch_all: dict[str, MagicMock]) -> None:
        create_components()
        _patch_all["SearchEngine"].assert_called_once()

    def test_creates_indexing_pipeline(self, _patch_all: dict[str, MagicMock]) -> None:
        create_components()
        _patch_all["IndexingPipeline"].assert_called_once_with(
            qdrant=_patch_all["QdrantManager"].return_value,
            embedder=_patch_all["create_embedding_provider"].return_value,
            description_provider=None,
            cache=_patch_all["CacheDB"].return_value,
        )


class TestCreateComponentsFromYaml:
    """Test create_components with a config_path."""

    def test_loads_config_from_yaml(self, _patch_all: dict[str, MagicMock]) -> None:
        with patch("code_search.factory.ProjectConfig") as mock_config_cls:
            mock_config = MagicMock()
            mock_config.terminology_file = None
            mock_config.indexing = MagicMock()
            mock_config.search = MagicMock()
            mock_config_cls.from_yaml.return_value = mock_config

            result = create_components(config_path=Path("/some/config.yaml"))

            mock_config_cls.from_yaml.assert_called_once_with(Path("/some/config.yaml"))
            assert result.config is mock_config


class TestNoVoyageKeyNoReranker:
    """When VOYAGE_API_KEY is empty, reranker should be None."""

    def test_reranker_is_none(self, _patch_all: dict[str, MagicMock]) -> None:
        _patch_all["env"].VOYAGE_API_KEY = ""
        result = create_components()
        assert result.reranker is None
        _patch_all["RerankProvider"].assert_not_called()


class TestNoTerminologyFileNoEnhancer:
    """When no terminology_file is set, enhancer should be None."""

    def test_enhancer_is_none(self, _patch_all: dict[str, MagicMock]) -> None:
        result = create_components()
        assert result.enhancer is None


class TestTerminologyFileExistsCreatesEnhancer:
    """When terminology_file exists on disk, enhancer should be created."""

    def test_enhancer_created(self, _patch_all: dict[str, MagicMock], tmp_path: Path) -> None:
        # Create a real terminology file so Path.exists() returns True
        terminology_file = tmp_path / "terms.yaml"
        terminology_file.write_text("abbreviations: {}")

        with (
            patch("code_search.factory.ProjectConfig") as mock_config_cls,
            patch("code_search.factory.QueryEnhancer") as mock_enhancer_cls,
        ):
            mock_config = MagicMock()
            mock_config.terminology_file = str(terminology_file)
            mock_config.indexing = MagicMock()
            mock_config.search = MagicMock()
            mock_config_cls.return_value = mock_config

            result = create_components()

            mock_enhancer_cls.assert_called_once_with(terminology_file)
            assert result.enhancer is mock_enhancer_cls.return_value


class TestQdrantConnectionErrorPropagates:
    """QdrantConnectionError from QdrantManager should propagate."""

    def test_raises_qdrant_connection_error(self, _patch_all: dict[str, MagicMock]) -> None:
        _patch_all["QdrantManager"].side_effect = QdrantConnectionError("http://localhost:6333")
        with pytest.raises(QdrantConnectionError):
            create_components()


class TestRerankerCreatedWithApiKey:
    """When VOYAGE_API_KEY is set, reranker should be created."""

    def test_reranker_created(self, _patch_all: dict[str, MagicMock]) -> None:
        result = create_components()
        _patch_all["RerankProvider"].assert_called_once_with(api_key="test-voyage-key")
        assert result.reranker is _patch_all["RerankProvider"].return_value


class TestDescriptionProviderNoneByDefault:
    """When nl_description_enabled is False (default), description_provider should be None."""

    def test_description_provider_none(self, _patch_all: dict[str, MagicMock]) -> None:
        result = create_components()
        assert result.description_provider is None


class TestNLDescriptionsOverride:
    """nl_descriptions=True overrides config to enable descriptions."""

    def test_create_components_nl_descriptions_override(
        self, _patch_all: dict[str, MagicMock]
    ) -> None:
        """nl_descriptions=True overrides config to enable descriptions."""
        _patch_all["env"].ANTHROPIC_API_KEY = "test-key"

        with patch(
            "code_search.clients.description.AnthropicDescriptionProvider"
        ) as mock_provider_cls:
            result = create_components(nl_descriptions=True)

            assert result.config.indexing.nl_description_enabled is True
            mock_provider_cls.assert_called_once()
            assert result.description_provider is mock_provider_cls.return_value


class TestDescriptionProviderCreatedWhenEnabled:
    """When nl_description_enabled is True and ANTHROPIC_API_KEY is set."""

    def test_description_provider_created(self, _patch_all: dict[str, MagicMock]) -> None:
        _patch_all["env"].ANTHROPIC_API_KEY = "test-anthropic-key"

        with (
            patch("code_search.factory.ProjectConfig") as mock_config_cls,
            patch(
                "code_search.clients.description.AnthropicDescriptionProvider"
            ) as mock_provider_cls,
        ):
            mock_config = MagicMock()
            mock_config.terminology_file = None
            mock_config.search = MagicMock()
            mock_indexing = MagicMock()
            mock_indexing.nl_description_enabled = True
            mock_indexing.nl_description_model = "claude-sonnet-4-5-20250929"
            mock_indexing.nl_description_max_concurrent = 5
            mock_config.indexing = mock_indexing
            mock_config_cls.return_value = mock_config

            result = create_components()

            mock_provider_cls.assert_called_once_with(
                api_key="test-anthropic-key",
                model="claude-sonnet-4-5-20250929",
                max_concurrent=5,
            )
            assert result.description_provider is mock_provider_cls.return_value

    def test_description_provider_none_without_api_key(
        self, _patch_all: dict[str, MagicMock]
    ) -> None:
        """Even with nl_description_enabled=True, None if no ANTHROPIC_API_KEY."""
        _patch_all["env"].ANTHROPIC_API_KEY = ""

        with patch("code_search.factory.ProjectConfig") as mock_config_cls:
            mock_config = MagicMock()
            mock_config.terminology_file = None
            mock_config.search = MagicMock()
            mock_indexing = MagicMock()
            mock_indexing.nl_description_enabled = True
            mock_config.indexing = mock_indexing
            mock_config_cls.return_value = mock_config

            result = create_components()
            assert result.description_provider is None


class TestIndexingPipelineReceivesDescriptionProvider:
    """IndexingPipeline should receive description_provider and cache."""

    def test_pipeline_receives_provider_and_cache(self, _patch_all: dict[str, MagicMock]) -> None:
        _patch_all["env"].ANTHROPIC_API_KEY = "test-key"

        with (
            patch("code_search.factory.ProjectConfig") as mock_config_cls,
            patch(
                "code_search.clients.description.AnthropicDescriptionProvider"
            ) as mock_provider_cls,
        ):
            mock_config = MagicMock()
            mock_config.terminology_file = None
            mock_config.search = MagicMock()
            mock_indexing = MagicMock()
            mock_indexing.nl_description_enabled = True
            mock_indexing.nl_description_model = "claude-sonnet-4-5-20250929"
            mock_indexing.nl_description_max_concurrent = 5
            mock_config.indexing = mock_indexing
            mock_config_cls.return_value = mock_config

            create_components()

            _patch_all["IndexingPipeline"].assert_called_once_with(
                qdrant=_patch_all["QdrantManager"].return_value,
                embedder=_patch_all["create_embedding_provider"].return_value,
                description_provider=mock_provider_cls.return_value,
                cache=_patch_all["CacheDB"].return_value,
            )
