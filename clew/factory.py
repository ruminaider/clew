"""Component factory -- centralized wiring for all clew components."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from clew.clients import create_embedding_provider
from clew.clients.qdrant import QdrantManager
from clew.config import Environment
from clew.indexer.cache import CacheDB
from clew.indexer.pipeline import IndexingPipeline
from clew.models import ProjectConfig
from clew.search.engine import SearchEngine
from clew.search.enhance import QueryEnhancer
from clew.search.enrichment import CacheResultEnricher
from clew.search.hybrid import HybridSearchEngine
from clew.search.rerank import RerankProvider
from clew.search.telemetry import QueryTelemetry

if TYPE_CHECKING:
    from clew.clients.base import EmbeddingProvider
    from clew.clients.description import DescriptionProvider


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
    project_root: Path | None = None


def _get_project_root() -> Path | None:
    """Detect project root from git root or CWD."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip())
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return Path.cwd()


def create_components(
    config_path: Path | None = None,
    *,
    nl_descriptions: bool = False,
    project_root: Path | None = None,
) -> Components:
    """Create all components with proper configuration.

    Args:
        config_path: Path to YAML config file. Uses defaults if None or missing.
        nl_descriptions: If True, override config to enable NL description generation.
        project_root: Project root directory for cache dir resolution.

    Returns:
        Components dataclass with all wired components.
    """
    # Load config
    env = Environment(project_root=project_root)
    if config_path:
        config = ProjectConfig.from_yaml(config_path)
    else:
        config = ProjectConfig()

    if nl_descriptions:
        config.indexing.nl_description_enabled = True

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
    hybrid = HybridSearchEngine(
        qdrant=qdrant,
        embedder=embedder,
        enumeration_limit=config.search.enumeration_limit,
    )

    # Reranker (optional -- only if API key available)
    reranker: RerankProvider | None = None
    if env.VOYAGE_API_KEY:
        reranker = RerankProvider(api_key=env.VOYAGE_API_KEY)

    # Detect project root for grep integration
    resolved_root = project_root or _get_project_root()

    # Result enricher (needs project_root to relativize paths)
    enricher = CacheResultEnricher(cache, project_root=resolved_root)

    # Telemetry (optional, respects config)
    telemetry: QueryTelemetry | None = None
    if config.search.telemetry_enabled:
        telemetry = QueryTelemetry(cache_dir=env.CACHE_DIR, enabled=True)

    search_engine = SearchEngine(
        hybrid_engine=hybrid,
        reranker=reranker,
        enhancer=enhancer,
        search_config=config.search,
        project_root=resolved_root,
        enricher=enricher,
        telemetry=telemetry,
    )

    # NL Description provider (optional)
    description_provider: DescriptionProvider | None = None
    if config.indexing.nl_description_enabled and env.ANTHROPIC_API_KEY:
        from clew.clients.description import AnthropicDescriptionProvider

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
        project_root=resolved_root,
    )
