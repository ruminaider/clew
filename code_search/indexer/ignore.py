"""Ignore pattern loading from 5-source hierarchy."""

from __future__ import annotations

import os
from pathlib import Path

from pathspec import PathSpec

DEFAULT_IGNORE_PATTERNS = [
    "__pycache__/",
    "*.pyc",
    ".git/",
    "node_modules/",
    ".venv/",
    "venv/",
    ".tox/",
    "*.egg-info/",
    "dist/",
    "build/",
    ".mypy_cache/",
    ".pytest_cache/",
    ".ruff_cache/",
]


class IgnorePatternLoader:
    """Load and merge ignore patterns from 5 sources."""

    def __init__(
        self,
        project_root: Path,
        config_excludes: list[str] | None = None,
    ) -> None:
        self.project_root = project_root
        self.config_excludes = config_excludes or []
        self._spec: PathSpec | None = None

    def load(self) -> PathSpec:
        """Load and merge patterns from all sources."""
        all_patterns: list[str] = []

        # Source 1: Built-in defaults (lowest priority)
        all_patterns.extend(DEFAULT_IGNORE_PATTERNS)

        # Source 2: .gitignore
        gitignore = self.project_root / ".gitignore"
        if gitignore.exists():
            all_patterns.extend(self._read_pattern_file(gitignore))

        # Source 3: .codesearchignore
        codesearchignore = self.project_root / ".codesearchignore"
        if codesearchignore.exists():
            all_patterns.extend(self._read_pattern_file(codesearchignore))

        # Source 4: config.yaml exclude patterns
        all_patterns.extend(self.config_excludes)

        # Source 5: Environment variable (highest priority)
        env_excludes = os.environ.get("CODE_SEARCH_EXCLUDE", "")
        if env_excludes:
            all_patterns.extend(env_excludes.split(","))

        self._spec = PathSpec.from_lines("gitwildmatch", all_patterns)
        return self._spec

    def should_ignore(self, file_path: str) -> bool:
        """Check if a file should be ignored."""
        if self._spec is None:
            self.load()
        assert self._spec is not None
        return self._spec.match_file(file_path)

    @staticmethod
    def _read_pattern_file(path: Path) -> list[str]:
        """Read patterns from a file, skipping comments and blanks."""
        patterns: list[str] = []
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                patterns.append(line)
        return patterns
