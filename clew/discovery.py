"""Centralized file discovery with ignore and safety filtering."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from .indexer.ignore import IgnorePatternLoader
from .models import ProjectConfig
from .safety import SafetyChecker

logger = logging.getLogger(__name__)

DEFAULT_EXTENSIONS: set[str] = {".py", ".ts", ".tsx", ".js", ".jsx", ".md"}


def _git_ls_files(project_root: Path) -> list[Path] | None:
    """Return absolute resolved paths from git ls-files, or None on failure."""
    try:
        proc = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            cwd=project_root,
            capture_output=True,
            timeout=10,
        )
        if proc.returncode != 0:
            logger.warning("git ls-files exited %d, falling back to rglob", proc.returncode)
            return None

        raw = proc.stdout.decode()
        if not raw:
            return []

        paths: list[Path] = []
        for entry in raw.split("\0"):
            if entry:
                paths.append((project_root / entry).resolve())
        return paths
    except FileNotFoundError:
        logger.warning("git not found, falling back to rglob")
        return None
    except subprocess.TimeoutExpired:
        logger.warning("git ls-files timed out, falling back to rglob")
        return None
    except subprocess.CalledProcessError:
        logger.warning("git ls-files failed, falling back to rglob")
        return None


def _rglob_files(project_root: Path) -> list[Path]:
    """Return absolute paths from recursive glob (fallback)."""
    return [p.resolve() for p in project_root.rglob("*") if p.is_file()]


def discover_files(
    project_root: Path,
    config: ProjectConfig,
    extensions: set[str] | None = None,
) -> list[Path]:
    """Discover indexable files under project_root, applying ignore and safety filters.

    Tries git ls-files first for performance; falls back to rglob if not
    in a git repo or git is unavailable.

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

    # Try git ls-files first; fall back to rglob
    candidates = _git_ls_files(project_root)
    if candidates is None:
        candidates = _rglob_files(project_root)

    result: list[Path] = []
    for path in candidates:
        if not path.is_file():
            continue
        if path.suffix not in exts:
            continue

        relative = str(path.relative_to(project_root.resolve()))

        if ignore_loader.should_ignore(relative):
            continue

        if not safety.check_file(str(path), path.stat().st_size):
            continue

        result.append(path)

    result.sort()
    return result
