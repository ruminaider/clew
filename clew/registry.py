"""Central project registry for cross-repo discovery.

Tracks all indexed projects in ~/.clew/projects.json so agents and scripts
can find any project's cache directory by name or path.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


def _registry_path() -> Path:
    """Return path to the central registry file."""
    return Path.home() / ".clew" / "projects.json"


def _load_registry() -> dict:
    """Load registry from disk. Returns empty structure if missing."""
    path = _registry_path()
    if not path.exists():
        return {"projects": {}}
    try:
        data = json.loads(path.read_text())
        if "projects" not in data:
            data["projects"] = {}
        return data
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to read registry %s: %s", path, e)
        return {"projects": {}}


def _save_registry(data: dict) -> None:
    """Write registry to disk, creating parent directory if needed."""
    path = _registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def register_project(
    name: str,
    project_root: Path,
    cache_dir: Path,
    collection_name: str,
) -> None:
    """Register or update a project in the central registry.

    Args:
        name: Project name (typically the directory name).
        project_root: Absolute path to the project root.
        cache_dir: Absolute path to the .clew cache directory.
        collection_name: Qdrant collection name for this project.
    """
    data = _load_registry()
    data["projects"][name] = {
        "project_root": str(project_root.resolve()),
        "cache_dir": str(cache_dir.resolve()),
        "collection_name": collection_name,
        "last_indexed": datetime.now(timezone.utc).isoformat(),
    }
    _save_registry(data)
    logger.debug("Registered project %r at %s", name, project_root)


def list_projects() -> list[dict]:
    """Return all registered projects sorted by name.

    Each dict has: name, project_root, cache_dir, collection_name, last_indexed.
    """
    data = _load_registry()
    result = []
    for name, info in sorted(data["projects"].items()):
        result.append({"name": name, **info})
    return result


def find_project(name_or_path: str) -> dict | None:
    """Find a project by name or path.

    Matching order:
    1. Exact name match
    2. Exact project_root path match (resolved)
    3. Basename of project_root match

    Returns dict with name, project_root, cache_dir, collection_name, last_indexed
    or None if not found.
    """
    data = _load_registry()
    projects = data["projects"]

    # 1. Exact name match
    if name_or_path in projects:
        return {"name": name_or_path, **projects[name_or_path]}

    # Resolve the input as a path for path-based matching
    try:
        resolved = str(Path(name_or_path).resolve())
    except (OSError, ValueError):
        resolved = name_or_path

    # 2. Exact project_root match
    for name, info in projects.items():
        if info["project_root"] == resolved:
            return {"name": name, **info}

    # 3. Basename match (e.g., "evvy" matches "/Users/x/Work/evvy")
    for name, info in projects.items():
        if Path(info["project_root"]).name == name_or_path:
            return {"name": name, **info}

    return None


def unregister_project(name: str) -> bool:
    """Remove a project from the registry.

    Returns True if the project was found and removed, False otherwise.
    """
    data = _load_registry()
    if name in data["projects"]:
        del data["projects"][name]
        _save_registry(data)
        logger.debug("Unregistered project %r", name)
        return True
    return False
