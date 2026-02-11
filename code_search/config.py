"""Config loading and validation."""

import os
import subprocess
from pathlib import Path
from subprocess import TimeoutExpired


def _resolve_cache_dir() -> Path:
    """Resolve cache directory: env var > git root > CWD fallback.

    Resolution order:
    1. CODE_SEARCH_CACHE_DIR env var (absolute path)
    2. {git_root}/.code-search/ (auto-detected)
    3. .code-search/ relative to CWD (fallback)
    """
    env_val = os.environ.get("CODE_SEARCH_CACHE_DIR")
    if env_val:
        return Path(env_val)

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip()) / ".code-search"
    except (FileNotFoundError, TimeoutExpired):
        pass

    return Path(".code-search")


class Environment:
    """Load environment variables with defaults."""

    VOYAGE_API_KEY: str = os.environ.get("VOYAGE_API_KEY", "")
    QDRANT_URL: str = os.environ.get("QDRANT_URL", "http://localhost:6333")
    QDRANT_API_KEY: str | None = os.environ.get("QDRANT_API_KEY") or None
    CACHE_DIR: Path = _resolve_cache_dir()
    LOG_LEVEL: str = os.environ.get("CODE_SEARCH_LOG_LEVEL", "INFO")
    ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")

    @classmethod
    def validate(cls) -> list[str]:
        """Return list of missing required env vars."""
        errors: list[str] = []
        if not cls.VOYAGE_API_KEY:
            errors.append("VOYAGE_API_KEY is required")
        return errors
