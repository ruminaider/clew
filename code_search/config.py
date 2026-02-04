"""Config loading and validation."""

import os
from pathlib import Path


class Environment:
    """Load environment variables with defaults."""

    VOYAGE_API_KEY: str = os.environ.get("VOYAGE_API_KEY", "")
    QDRANT_URL: str = os.environ.get("QDRANT_URL", "http://localhost:6333")
    QDRANT_API_KEY: str | None = os.environ.get("QDRANT_API_KEY") or None
    CACHE_DIR: Path = Path(os.environ.get("CODE_SEARCH_CACHE_DIR", ".code-search"))
    LOG_LEVEL: str = os.environ.get("CODE_SEARCH_LOG_LEVEL", "INFO")
    ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")

    @classmethod
    def validate(cls) -> list[str]:
        """Return list of missing required env vars."""
        errors: list[str] = []
        if not cls.VOYAGE_API_KEY:
            errors.append("VOYAGE_API_KEY is required")
        return errors
