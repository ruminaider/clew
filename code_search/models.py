"""Pydantic models for data structures."""

from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field, field_validator


class ChunkStrategy(str, Enum):
    CLASS_WITH_METHODS = "class_with_methods"
    FUNCTION = "function"
    FILE = "file"
    SECTION = "section"


class CollectionConfig(BaseModel):
    include: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)


class ChunkOverride(BaseModel):
    strategy: ChunkStrategy = ChunkStrategy.CLASS_WITH_METHODS
    max_tokens: int = Field(default=3000, ge=100, le=8000)


class DjangoConfig(BaseModel):
    app_detection: bool = True
    related_files: dict[str, list[str]] = Field(default_factory=dict)


class SecurityConfig(BaseModel):
    exclude_patterns: list[str] = Field(
        default_factory=lambda: [
            "**/.env*",
            "**/secrets/**",
            "**/*credential*",
            "**/*secret*",
            "**/*.pem",
            "**/*.key",
        ]
    )


class SafetyConfig(BaseModel):
    """Safety limits to prevent runaway indexing. See ADR-003."""

    max_total_chunks: int = Field(default=500_000, ge=1000)
    max_file_size_bytes: int = Field(default=1_048_576, ge=1024)  # 1 MB
    batch_size: int = Field(default=25, ge=1, le=1000)
    collection_limits: dict[str, int] = Field(default_factory=dict)


class IndexingConfig(BaseModel):
    """Indexing pipeline configuration."""

    overlap_tokens: int = Field(default=200, ge=0, le=1000)
    fallback_max_tokens: int = Field(default=3000, ge=500, le=8000)
    embedding_provider: str = Field(default="voyage")
    embedding_model: str = Field(default="voyage-code-3")
    nl_description_enabled: bool = Field(default=False)
    nl_description_model: str = Field(default="claude-sonnet-4-5-20250929")
    nl_description_max_concurrent: int = Field(default=5, ge=1, le=20)


class SearchConfig(BaseModel):
    """Search pipeline configuration. See Tradeoff B resolution."""

    rerank_candidates: int = Field(default=30, ge=10, le=100)
    rerank_top_k: int = Field(default=10, ge=1, le=50)
    no_rerank_threshold: int = Field(default=10, ge=1)
    rerank_model: str = "rerank-2.5"
    high_confidence_threshold: float = Field(default=0.92, ge=0.0, le=1.0)
    low_variance_threshold: float = Field(default=0.1, ge=0.0, le=1.0)


class ProjectConfig(BaseModel):
    """Root configuration model."""

    project: dict[str, str] = Field(default_factory=lambda: {"name": "default", "root": "."})
    collections: dict[str, CollectionConfig] = Field(default_factory=dict)
    chunking: dict[str, int] = Field(default_factory=lambda: {"default_max_tokens": 3000})
    django: DjangoConfig = Field(default_factory=DjangoConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)
    indexing: IndexingConfig = Field(default_factory=IndexingConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)
    terminology_file: str | None = None

    @field_validator("collections", mode="before")
    @classmethod
    def validate_collections(
        cls, v: dict[str, CollectionConfig | dict[str, list[str]]]
    ) -> dict[str, CollectionConfig]:
        if not v:
            return {
                "code": CollectionConfig(
                    include=["**/*.py", "**/*.ts", "**/*.tsx"],
                    exclude=["**/migrations/**", "**/node_modules/**"],
                ),
                "docs": CollectionConfig(include=["**/*.md"], exclude=[]),
            }
        return {k: CollectionConfig(**v_) if isinstance(v_, dict) else v_ for k, v_ in v.items()}

    @classmethod
    def from_yaml(cls, path: Path) -> "ProjectConfig":
        """Load config from YAML file."""
        import yaml

        if not path.exists():
            return cls()

        with open(path) as f:
            data = yaml.safe_load(f) or {}

        return cls(**data)

    @classmethod
    def from_yaml_with_errors(cls, path: Path) -> tuple["ProjectConfig", list[str]]:
        """Load config and return any validation errors."""
        import yaml
        from pydantic import ValidationError

        errors: list[str] = []

        if not path.exists():
            return cls(), [f"Config file not found: {path}"]

        try:
            with open(path) as f:
                data = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            return cls(), [f"Invalid YAML: {e}"]

        try:
            config = cls(**data)
            return config, []
        except ValidationError as e:
            for error in e.errors():
                loc = ".".join(str(x) for x in error["loc"])
                errors.append(f"{loc}: {error['msg']}")
            return cls(), errors
