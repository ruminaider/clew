"""Unified change detection: git-aware primary, file-hash fallback."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from code_search.indexer.cache import CacheDB


@dataclass
class ChangeResult:
    """Result of change detection."""

    added: list[str] = field(default_factory=list)
    modified: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    source: Literal["git", "hash"] = "hash"


class ChangeDetector:
    """Unified change detection: try git first, fall back to file-hash."""

    def __init__(self, project_root: Path, cache: CacheDB) -> None:
        from code_search.indexer.file_hash import FileHashTracker
        from code_search.indexer.git_tracker import GitChangeTracker

        self._git = GitChangeTracker(project_root)
        self._hash = FileHashTracker(cache)
        self._cache = cache

    def detect_changes(self, file_paths: list[str], collection: str = "code") -> ChangeResult:
        """Detect changes using git if available, otherwise file hashes."""
        if self._git.is_git_repo():
            last_commit = self._cache.get_last_indexed_commit(collection)
            if last_commit:
                return self._from_git(last_commit, file_paths)
        return self._from_hash(file_paths)

    def _from_git(self, last_commit: str, file_paths: list[str]) -> ChangeResult:
        """Use git diff for change detection."""
        changes = self._git.get_changes_since(last_commit)

        # Filter to only requested files
        file_set = set(file_paths)

        added = [f for f in changes["added"] if f in file_set]
        modified = [f for f in changes["modified"] if f in file_set]
        deleted = list(changes["deleted"])  # deleted files won't be in file_paths

        # Renamed = delete old + add new
        for rename in changes["renamed"]:
            deleted.append(rename["from"])
            if rename["to"] in file_set:
                added.append(rename["to"])

        # Files in file_paths not in any change category are unchanged
        changed_set = set(added) | set(modified)
        unchanged = [f for f in file_paths if f not in changed_set]

        return ChangeResult(
            added=added,
            modified=modified,
            deleted=deleted,
            unchanged=unchanged,
            source="git",
        )

    def _from_hash(self, file_paths: list[str]) -> ChangeResult:
        """Use file-hash comparison for change detection."""
        changes = self._hash.detect_changes(file_paths)
        return ChangeResult(
            added=changes["added"],
            modified=changes["modified"],
            deleted=[],  # hash tracker can't detect deletions
            unchanged=changes["unchanged"],
            source="hash",
        )

    def get_current_commit(self) -> str | None:
        """Get current git HEAD commit (for saving after indexing)."""
        if self._git.is_git_repo():
            return self._git.get_current_commit()
        return None
