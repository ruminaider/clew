"""Custom exception hierarchy for code-search."""


class CodeSearchError(Exception):
    """Base exception for code-search."""


# Configuration errors
class ConfigError(CodeSearchError):
    """Configuration-related errors."""


class ConfigNotFoundError(ConfigError):
    """Config file not found."""


class ConfigValidationError(ConfigError):
    """Config validation failed."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(f"Config validation failed: {', '.join(errors)}")


# Infrastructure errors
class InfrastructureError(CodeSearchError):
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
class IndexingError(CodeSearchError):
    """Indexing-related errors."""


class ParseError(IndexingError):
    """Failed to parse source file."""

    def __init__(self, file_path: str, errors: list[str]):
        self.file_path = file_path
        self.errors = errors
        super().__init__(f"Failed to parse {file_path}: {errors}")


# Search errors
class SearchError(CodeSearchError):
    """Search-related errors."""


class SearchUnavailableError(SearchError):
    """Search service is unavailable."""


class InvalidFilterError(SearchError):
    """Invalid search filter."""

    def __init__(self, filter_name: str, value: str, valid_values: list[str]):
        super().__init__(f"Invalid filter '{filter_name}': '{value}'. Valid values: {valid_values}")
