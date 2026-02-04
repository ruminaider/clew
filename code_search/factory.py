"""Component factory -- centralized wiring for all code-search components."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from code_search.clients import create_embedding_provider
from code_search.clients.qdrant import QdrantManager
from code_search.config import Environment
from code_search.indexer.cache import CacheDB
from code_search.indexer.pipeline import IndexingPipeline
from code_search.models import ProjectConfig
from code_search.search.engine import SearchEngine
from code_search.search.enhance import QueryEnhancer
from code_search.search.hybrid import HybridSearchEngine
from code_search.search.rerank import RerankProvider

if TYPE_CHECKING:
    from code_search.clients.base import EmbeddingProvider
    from code_search.clients.description import DescriptionProvider


@dataclass
class Components:
    """Container for all wired components."""

    config: ProjectConfig
    qdrant: QdrantManager
    embedder: EmbeddingProvider
    cache: CacheDB
    search_engine: SearchEngine
    indexing_pipeline: IndexingPipeline
    enhancer: QueryEnhancer | None
    reranker: RerankProvider | None
    description_provider: DescriptionProvider | None = None


def create_components(config_path: Path | None = None) -> Components:
    """Create all components with proper configuration.

    Args:
        config_path: Path to YAML config file. Uses defaults if None or missing.

    Returns:
        Components dataclass with all wired components.
    """
    # Load config
    env = Environment()
    if config_path:
        config = ProjectConfig.from_yaml(config_path)
    else:
        config = ProjectConfig()

    # Infrastructure
    qdrant = QdrantManager(url=env.QDRANT_URL, api_key=env.QDRANT_API_KEY)
    embedder = create_embedding_provider(config.indexing, env)
    cache = CacheDB(env.CACHE_DIR)

    # Query enhancement (optional)
    enhancer: QueryEnhancer | None = None
    if config.terminology_file:
        terminology_path = Path(config.terminology_file)
        if terminology_path.exists():
            enhancer = QueryEnhancer(terminology_path)

    # Search components
    hybrid = HybridSearchEngine(qdrant=qdrant, embedder=embedder)

    # Reranker (optional -- only if API key available)
    reranker: RerankProvider | None = None
    if env.VOYAGE_API_KEY:
        reranker = RerankProvider(api_key=env.VOYAGE_API_KEY)

    search_engine = SearchEngine(
        hybrid_engine=hybrid,
        reranker=reranker,
        enhancer=enhancer,
        search_config=config.search,
    )

    # NL Description provider (optional)
    description_provider: DescriptionProvider | None = None
    if config.indexing.nl_description_enabled and env.ANTHROPIC_API_KEY:
        from code_search.clients.description import AnthropicDescriptionProvider

        description_provider = AnthropicDescriptionProvider(
            api_key=env.ANTHROPIC_API_KEY,
            model=config.indexing.nl_description_model,
            max_concurrent=config.indexing.nl_description_max_concurrent,
        )

    # Indexing
    indexing_pipeline = IndexingPipeline(
        qdrant=qdrant,
        embedder=embedder,
        description_provider=description_provider,
        cache=cache,
    )

    return Components(
        config=config,
        qdrant=qdrant,
        embedder=embedder,
        cache=cache,
        search_engine=search_engine,
        indexing_pipeline=indexing_pipeline,
        enhancer=enhancer,
        reranker=reranker,
        description_provider=description_provider,
    )
