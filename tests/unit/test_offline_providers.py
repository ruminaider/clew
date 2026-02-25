"""Tests for offline/local provider integration.

Covers: reranker dispatch, Ollama factory wiring, dimension mismatch,
conditional API key validation, and doctor checks.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from clew.config import Environment
from clew.exceptions import DimensionMismatchError
from clew.factory import _create_reranker
from clew.search.rerank_local import NoopRerankProvider

# --- Reranker dispatch tests ---


class TestCreateRerankerAutoWithVoyageKey:
    """auto + VOYAGE_API_KEY → VoyageRerankProvider."""

    def test_auto_with_key_creates_voyage(self) -> None:
        env = MagicMock()
        env.VOYAGE_API_KEY = "test-key"
        with patch("clew.search.rerank.voyageai"):
            reranker = _create_reranker("auto", env)
        assert reranker is not None
        assert reranker.model_name == "rerank-2.5"


class TestCreateRerankerAutoWithoutVoyageKey:
    """auto + no VOYAGE_API_KEY → FlashRank if installed, else Noop."""

    def test_auto_no_key_falls_to_noop(self) -> None:
        env = MagicMock()
        env.VOYAGE_API_KEY = ""
        # FlashRank not installed → ImportError → Noop fallback
        with patch(
            "clew.search.rerank_local.FlashRankRerankProvider",
            side_effect=ImportError("No flashrank"),
        ):
            reranker = _create_reranker("auto", env)
        assert isinstance(reranker, NoopRerankProvider)


class TestCreateRerankerExplicitNoop:
    """rerank_provider="noop" → NoopRerankProvider."""

    def test_explicit_noop(self) -> None:
        env = MagicMock()
        env.VOYAGE_API_KEY = "test-key"
        reranker = _create_reranker("noop", env)
        assert isinstance(reranker, NoopRerankProvider)


class TestCreateRerankerExplicitNone:
    """rerank_provider="none" → None."""

    def test_explicit_none(self) -> None:
        env = MagicMock()
        reranker = _create_reranker("none", env)
        assert reranker is None


class TestCreateRerankerExplicitVoyageNoKey:
    """rerank_provider="voyage" but no key → None."""

    def test_voyage_no_key_returns_none(self) -> None:
        env = MagicMock()
        env.VOYAGE_API_KEY = ""
        reranker = _create_reranker("voyage", env)
        assert reranker is None


class TestCreateRerankerExplicitFlashRankMissing:
    """rerank_provider="flashrank" but not installed → ImportError."""

    def test_flashrank_missing_raises(self) -> None:
        env = MagicMock()
        env.VOYAGE_API_KEY = ""
        with (
            patch.dict("sys.modules", {"flashrank": None}),
            pytest.raises(ImportError),
        ):
            _create_reranker("flashrank", env)


# --- Dimension mismatch tests ---


class TestDimensionMismatchError:
    def test_error_message(self) -> None:
        err = DimensionMismatchError("code", 1024, 768)
        assert "code" in str(err)
        assert "1024" in str(err)
        assert "768" in str(err)
        assert "clew index --full" in str(err)

    def test_attributes(self) -> None:
        err = DimensionMismatchError("code", 1024, 768)
        assert err.collection == "code"
        assert err.expected == 1024
        assert err.actual == 768


# --- Config validation tests ---


class TestConditionalValidation:
    def test_voyage_provider_requires_key(self) -> None:
        with patch.object(Environment, "VOYAGE_API_KEY", ""):
            errors = Environment.validate(embedding_provider="voyage")
        assert any("VOYAGE_API_KEY" in e for e in errors)

    def test_ollama_provider_skips_voyage_key(self) -> None:
        with patch.object(Environment, "VOYAGE_API_KEY", ""):
            errors = Environment.validate(embedding_provider="ollama")
        assert not any("VOYAGE_API_KEY" in e for e in errors)

    def test_voyage_provider_passes_with_key(self) -> None:
        with patch.object(Environment, "VOYAGE_API_KEY", "real-key"):
            errors = Environment.validate(embedding_provider="voyage")
        assert errors == []


# --- Ollama URL in Environment ---


class TestOllamaUrlConfig:
    def test_default_ollama_url(self) -> None:
        env = Environment()
        assert hasattr(env, "OLLAMA_URL")
        # Default should be localhost
        assert "11434" in env.OLLAMA_URL


# --- Embedding provider factory with Ollama ---


class TestEmbeddingProviderFactoryOllama:
    def test_ollama_branch(self) -> None:
        from clew.clients import create_embedding_provider
        from clew.models import IndexingConfig

        config = IndexingConfig(
            embedding_provider="ollama",
            embedding_model="test-model",
        )
        env = MagicMock()
        env.OLLAMA_URL = "http://localhost:11434"

        provider = create_embedding_provider(config, env)

        from clew.clients.ollama import OllamaEmbeddingProvider

        assert isinstance(provider, OllamaEmbeddingProvider)
        assert provider.model_name == "test-model"

    def test_unknown_provider_raises(self) -> None:
        from clew.clients import create_embedding_provider
        from clew.exceptions import ConfigError
        from clew.models import IndexingConfig

        config = IndexingConfig(embedding_provider="unknown")
        env = MagicMock()

        with pytest.raises(ConfigError, match="Unknown embedding provider"):
            create_embedding_provider(config, env)


# --- Doctor Ollama check ---


class TestDoctorOllamaCheck:
    def test_ollama_check_connected(self) -> None:
        from clew.doctor import check_ollama

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [{"name": "qwen3-embedding"}]
        }

        with patch("httpx.get", return_value=mock_response):
            result = check_ollama("http://localhost:11434")
            assert result.passed is True
            assert "qwen3-embedding" in result.detail

    def test_ollama_check_unreachable(self) -> None:
        from clew.doctor import check_ollama

        with patch("httpx.get", side_effect=Exception("Connection refused")):
            result = check_ollama("http://localhost:11434")
            assert result.passed is False
            assert "unreachable" in result.detail


# --- SearchConfig rerank_provider field ---


class TestSearchConfigRerankProvider:
    def test_default_is_auto(self) -> None:
        from clew.models import SearchConfig

        config = SearchConfig()
        assert config.rerank_provider == "auto"

    def test_accepts_explicit_values(self) -> None:
        from clew.models import SearchConfig

        for val in ("auto", "voyage", "flashrank", "noop", "none"):
            config = SearchConfig(rerank_provider=val)
            assert config.rerank_provider == val
