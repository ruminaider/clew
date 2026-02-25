"""Custom exception hierarchy for clew."""


class ClewError(Exception):
    """Base exception for clew."""


# Configuration errors
class ConfigError(ClewError):
    """Configuration-related errors."""


class ConfigNotFoundError(ConfigError):
    """Config file not found."""


class ConfigValidationError(ConfigError):
    """Config validation failed."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(f"Config validation failed: {', '.join(errors)}")


# Infrastructure errors
class InfrastructureError(ClewError):
    """Infrastructure-related errors."""


class QdrantError(InfrastructureError):
    """Qdrant-related errors."""


class QdrantConnectionError(QdrantError):
    """Cannot connect to Qdrant."""

    def __init__(self, url: str, original: Exception | None = None):
        self.url = url
        self.original = original
        super().__init__(
            f"Cannot connect to Qdrant at {url}. "
            "Ensure Qdrant is running: docker compose up -d qdrant"
        )


class OllamaError(InfrastructureError):
    """Ollama-related errors."""


class OllamaConnectionError(OllamaError):
    """Cannot connect to Ollama."""

    def __init__(self, url: str, original: Exception | None = None):
        self.url = url
        self.original = original
        super().__init__(
            f"Cannot connect to Ollama at {url}. "
            "Ensure Ollama is running: ollama serve"
        )


class OllamaModelError(OllamaError):
    """Ollama model not available."""

    def __init__(self, model: str, url: str):
        self.model = model
        self.url = url
        super().__init__(
            f"Ollama model '{model}' not available. "
            f"Pull it with: ollama pull {model}"
        )


class DimensionMismatchError(QdrantError):
    """Collection exists with different vector dimensions."""

    def __init__(self, collection: str, expected: int, actual: int):
        self.collection = collection
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"Collection '{collection}' has {actual}-dim vectors "
            f"but embedder produces {expected}-dim. "
            f"Reindex with: clew index --full"
        )


class VoyageError(InfrastructureError):
    """Voyage API errors."""


class VoyageAuthError(VoyageError):
    """Voyage API authentication failed."""

    def __init__(self) -> None:
        super().__init__(
            "Voyage API authentication failed. Check VOYAGE_API_KEY environment variable."
        )


class VoyageRateLimitError(VoyageError):
    """Voyage API rate limit exceeded."""

    def __init__(self, retry_after: int | None = None):
        self.retry_after = retry_after
        msg = "Voyage API rate limit exceeded."
        if retry_after:
            msg += f" Retry after {retry_after} seconds."
        super().__init__(msg)


# Indexing errors
class IndexingError(ClewError):
    """Indexing-related errors."""


class ParseError(IndexingError):
    """Failed to parse source file."""

    def __init__(self, file_path: str, errors: list[str]):
        self.file_path = file_path
        self.errors = errors
        super().__init__(f"Failed to parse {file_path}: {errors}")


# Search errors
class SearchError(ClewError):
    """Search-related errors."""


class SearchUnavailableError(SearchError):
    """Search service is unavailable (e.g., circuit breaker open)."""


class InvalidFilterError(SearchError):
    """Invalid search filter."""

    def __init__(self, filter_name: str, value: str, valid_values: list[str]):
        super().__init__(f"Invalid filter '{filter_name}': '{value}'. Valid values: {valid_values}")


class SchemaMigrationError(IndexingError):
    """Schema migration failed."""

    def __init__(self, from_version: int, to_version: int, original: Exception | None = None):
        self.from_version = from_version
        self.to_version = to_version
        self.original = original
        super().__init__(f"Schema migration v{from_version} → v{to_version} failed: {original}")
