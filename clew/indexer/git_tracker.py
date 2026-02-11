"""Git-aware change detection (primary tier).

Tier 1: git diff --name-status for add/modify/delete/rename detection.
Tier 2 fallback: FileHashTracker for non-git repos.
See Tradeoff D resolution.
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_GIT_TIMEOUT_SECONDS = 5


@dataclass
class StalenessInfo:
    """Information about how stale the index is relative to the repo."""

    is_stale: bool
    commits_behind: int  # -1 if unknown (non-git, error)
    has_uncommitted_changes: bool
    last_indexed_commit: str | None
    current_commit: str | None


class GitChangeTracker:
    """Detect file changes using git diff."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root

    def is_git_repo(self) -> bool:
        """Check if project root is inside a git repository."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=_GIT_TIMEOUT_SECONDS,
            )
            return result.returncode == 0
        except FileNotFoundError:
            logger.warning("git not found on PATH")
            return False
        except subprocess.TimeoutExpired:
            logger.warning("git rev-parse timed out after %ds", _GIT_TIMEOUT_SECONDS)
            return False

    def get_current_commit(self) -> str | None:
        """Get current HEAD commit hash.

        Falls back to `git describe --always` for detached HEAD states
        where rev-parse might give an unexpected result.
        """
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=_GIT_TIMEOUT_SECONDS,
            )
            if result.returncode == 0:
                return result.stdout.strip()

            # Fallback for detached HEAD or other edge cases
            result = subprocess.run(
                ["git", "describe", "--always"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=_GIT_TIMEOUT_SECONDS,
            )
            if result.returncode == 0:
                return result.stdout.strip()

            return None
        except FileNotFoundError:
            logger.warning("git not found on PATH")
            return None
        except subprocess.TimeoutExpired:
            logger.warning("git rev-parse/describe timed out")
            return None

    def is_merging_or_rebasing(self) -> bool:
        """Check if the repo is in a merge or rebase state."""
        git_dir = self.project_root / ".git"

        # For worktrees, .git is a file pointing to the real git dir
        if git_dir.is_file():
            try:
                content = git_dir.read_text().strip()
                if content.startswith("gitdir:"):
                    git_dir = Path(content.split(":", 1)[1].strip())
            except OSError:
                return False

        merge_indicators = [
            git_dir / "MERGE_HEAD",
            git_dir / "rebase-merge",
            git_dir / "rebase-apply",
        ]
        return any(p.exists() for p in merge_indicators)

    def check_staleness(self, last_indexed_commit: str | None) -> StalenessInfo:
        """Check how stale the index is relative to the current repo state."""
        current_commit = self.get_current_commit()

        if not self.is_git_repo() or current_commit is None:
            return StalenessInfo(
                is_stale=True,
                commits_behind=-1,
                has_uncommitted_changes=False,
                last_indexed_commit=last_indexed_commit,
                current_commit=current_commit,
            )

        # Check uncommitted changes
        has_uncommitted = False
        try:
            result = subprocess.run(
                ["git", "diff-index", "--quiet", "HEAD"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=_GIT_TIMEOUT_SECONDS,
            )
            has_uncommitted = result.returncode != 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        if last_indexed_commit is None:
            return StalenessInfo(
                is_stale=True,
                commits_behind=-1,
                has_uncommitted_changes=has_uncommitted,
                last_indexed_commit=None,
                current_commit=current_commit,
            )

        if last_indexed_commit == current_commit:
            return StalenessInfo(
                is_stale=has_uncommitted,
                commits_behind=0,
                has_uncommitted_changes=has_uncommitted,
                last_indexed_commit=last_indexed_commit,
                current_commit=current_commit,
            )

        # Count commits between last indexed and current
        commits_behind = -1
        try:
            result = subprocess.run(
                ["git", "rev-list", "--count", f"{last_indexed_commit}..HEAD"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=_GIT_TIMEOUT_SECONDS,
            )
            if result.returncode == 0:
                commits_behind = int(result.stdout.strip())
        except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
            pass

        return StalenessInfo(
            is_stale=True,
            commits_behind=commits_behind,
            has_uncommitted_changes=has_uncommitted,
            last_indexed_commit=last_indexed_commit,
            current_commit=current_commit,
        )

    def get_changes_since(self, last_commit: str) -> dict[str, list[Any]]:
        """Get file changes since last indexed commit.

        Returns dict with keys: added, modified, deleted, renamed.
        Renamed entries are dicts with "from" and "to" keys.
        """
        if self.is_merging_or_rebasing():
            logger.warning(
                "Repo is in merge/rebase state — change detection may be incomplete"
            )

        try:
            result = subprocess.run(
                ["git", "diff", "--name-status", last_commit, "HEAD"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=_GIT_TIMEOUT_SECONDS,
            )
        except FileNotFoundError:
            logger.warning("git not found on PATH, returning empty changes")
            return {"added": [], "modified": [], "deleted": [], "renamed": []}
        except subprocess.TimeoutExpired:
            logger.warning("git diff timed out after %ds", _GIT_TIMEOUT_SECONDS)
            return {"added": [], "modified": [], "deleted": [], "renamed": []}

        changes: dict[str, list[Any]] = {
            "added": [],
            "modified": [],
            "deleted": [],
            "renamed": [],
        }

        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("\t")
            status = parts[0]
            if status == "A":
                changes["added"].append(parts[1])
            elif status == "M":
                changes["modified"].append(parts[1])
            elif status == "D":
                changes["deleted"].append(parts[1])
            elif status.startswith("R"):
                changes["renamed"].append({"from": parts[1], "to": parts[2]})

        return changes
