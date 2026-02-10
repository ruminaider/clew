"""File-hash based change detection (secondary to git-diff)."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .cache import CacheDB


class FileHashTracker:
    """File-hash based change detection (secondary to git-diff)."""

    def __init__(self, cache: CacheDB) -> None:
        self.cache = cache

    def compute_hash(self, file_path: str) -> str:
        """Compute SHA256 hash of file contents."""
        content = Path(file_path).read_bytes()
        return hashlib.sha256(content).hexdigest()

    def detect_changes(self, file_paths: list[str]) -> dict[str, list[str]]:
        """Classify files as added, modified, or unchanged."""
        changes: dict[str, list[str]] = {
            "added": [],
            "modified": [],
            "unchanged": [],
        }

        for path in file_paths:
            current_hash = self.compute_hash(path)
            cached_hash = self.cache.get_file_hash(path)

            if cached_hash is None:
                changes["added"].append(path)
            elif cached_hash != current_hash:
                changes["modified"].append(path)
            else:
                changes["unchanged"].append(path)

        return changes

    def update_hash(self, file_path: str, file_hash: str, chunk_ids: list[str]) -> None:
        """Update cached hash after successful indexing."""
        self.cache.set_file_chunks(file_path, file_hash, chunk_ids)
