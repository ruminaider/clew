"""Client wrappers for external services."""

from __future__ import annotations

from typing import TYPE_CHECKING

from clew.exceptions import ConfigError

if TYPE_CHECKING:
    from clew.config import Environment
    from clew.models import IndexingConfig

    from .base import EmbeddingProvider


def create_embedding_provider(config: IndexingConfig, env: Environment) -> EmbeddingProvider:
    """Create embedding provider from configuration."""
    if config.embedding_provider == "voyage":
        from .voyage import VoyageEmbeddingProvider

        return VoyageEmbeddingProvider(api_key=env.VOYAGE_API_KEY, model=config.embedding_model)
    raise ConfigError(f"Unknown embedding provider: {config.embedding_provider}")
