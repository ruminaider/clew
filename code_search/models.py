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
    batch_size: int = Field(default=100, ge=1, le=1000)
    collection_limits: dict[str, int] = Field(default_factory=dict)


class IndexingConfig(BaseModel):
    """Indexing pipeline configuration."""

    overlap_tokens: int = Field(default=200, ge=0, le=1000)
    fallback_max_tokens: int = Field(default=3000, ge=500, le=8000)
    embedding_provider: str = Field(default="voyage")
    embedding_model: str = Field(default="voyage-code-3")


class ProjectConfig(BaseModel):
    """Root configuration model."""

    project: dict[str, str] = Field(default_factory=lambda: {"name": "default", "root": "."})
    collections: dict[str, CollectionConfig] = Field(default_factory=dict)
    chunking: dict[str, int] = Field(default_factory=lambda: {"default_max_tokens": 3000})
    django: DjangoConfig = Field(default_factory=DjangoConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)
    indexing: IndexingConfig = Field(default_factory=IndexingConfig)
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
