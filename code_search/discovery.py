"""Centralized file discovery with ignore and safety filtering."""

from __future__ import annotations

import logging
from pathlib import Path

from .indexer.ignore import IgnorePatternLoader
from .models import ProjectConfig
from .safety import SafetyChecker

logger = logging.getLogger(__name__)

DEFAULT_EXTENSIONS: set[str] = {".py", ".ts", ".tsx", ".js", ".jsx", ".md"}


def discover_files(
    project_root: Path,
    config: ProjectConfig,
    extensions: set[str] | None = None,
) -> list[Path]:
    """Discover indexable files under project_root, applying ignore and safety filters.

    Args:
        project_root: Root directory to scan.
        config: Project configuration with security and safety settings.
        extensions: File extensions to include. Defaults to DEFAULT_EXTENSIONS.

    Returns:
        Sorted list of file paths that pass all filters.
    """
    exts = extensions if extensions is not None else DEFAULT_EXTENSIONS

    ignore_loader = IgnorePatternLoader(project_root, config.security.exclude_patterns)
    ignore_loader.load()

    safety = SafetyChecker(config.safety)

    result: list[Path] = []
    for path in project_root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in exts:
            continue

        relative = str(path.relative_to(project_root))

        if ignore_loader.should_ignore(relative):
            continue

        if not safety.check_file(str(path), path.stat().st_size):
            continue

        result.append(path)

    result.sort()
    return result
