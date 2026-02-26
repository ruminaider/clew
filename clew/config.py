"""Config loading and validation."""

import os
import subprocess
from pathlib import Path
from subprocess import TimeoutExpired


def _resolve_cache_dir(project_root: Path | None = None) -> Path:
    """Resolve cache directory: env var > project root > git root > CWD fallback.

    Resolution order:
    1. CLEW_CACHE_DIR env var (absolute path)
    2. {project_root}/.clew/ (if project_root provided)
    3. {git_root}/.clew/ (auto-detected from CWD)
    4. .clew/ relative to CWD (fallback)
    """
    env_val = os.environ.get("CLEW_CACHE_DIR")
    if env_val:
        return Path(env_val)

    if project_root is not None:
        candidate = Path(project_root).resolve() / ".clew"
        if candidate.exists():
            return candidate
        # Also try git root from project_root
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                timeout=5,
                cwd=str(project_root),
            )
            if result.returncode == 0:
                return Path(result.stdout.strip()) / ".clew"
        except (FileNotFoundError, TimeoutExpired):
            pass

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip()) / ".clew"
    except (FileNotFoundError, TimeoutExpired):
        pass

    return Path(".clew")


class Environment:
    """Load environment variables with defaults."""

    VOYAGE_API_KEY: str = os.environ.get("VOYAGE_API_KEY", "")
    QDRANT_URL: str = os.environ.get("QDRANT_URL", "http://localhost:6333")
    QDRANT_API_KEY: str | None = os.environ.get("QDRANT_API_KEY") or None
    CACHE_DIR: Path = _resolve_cache_dir()
    LOG_LEVEL: str = os.environ.get("CLEW_LOG_LEVEL", "INFO")
    ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")
    CLEW_DESCRIPTION_MODEL: str = os.environ.get(
        "CLEW_DESCRIPTION_MODEL", "claude-sonnet-4-5-20250929"
    )
    CLEW_FULL_INDEX_MODEL: str = os.environ.get("CLEW_FULL_INDEX_MODEL", "claude-opus-4-6")
    OLLAMA_URL: str = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    CLEW_CONFIDENCE_THRESHOLD: float = float(os.environ.get("CLEW_CONFIDENCE_THRESHOLD", "0.65"))
    ENRICHMENT_API_KEY: str = os.environ.get("ENRICHMENT_API_KEY", "")
    ENRICHMENT_BASE_URL: str = os.environ.get("ENRICHMENT_BASE_URL", "https://api.openai.com/v1")

    def __init__(self, project_root: Path | None = None) -> None:
        """Initialize with optional project_root for cache dir resolution."""
        if project_root is not None:
            self.CACHE_DIR = _resolve_cache_dir(project_root)

    @classmethod
    def validate(cls, embedding_provider: str = "voyage") -> list[str]:
        """Return list of missing required env vars.

        Args:
            embedding_provider: Which embedding provider is configured.
                VOYAGE_API_KEY only required when provider is "voyage".
        """
        errors: list[str] = []
        if embedding_provider == "voyage" and not cls.VOYAGE_API_KEY:
            errors.append("VOYAGE_API_KEY is required")
        return errors
