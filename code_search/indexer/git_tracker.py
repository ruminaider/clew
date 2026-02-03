"""Git-aware change detection (primary tier).

Tier 1: git diff --name-status for add/modify/delete/rename detection.
Tier 2 fallback: FileHashTracker for non-git repos.
See Tradeoff D resolution.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class GitChangeTracker:
    """Detect file changes using git diff."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root

    def is_git_repo(self) -> bool:
        """Check if project root is inside a git repository."""
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            cwd=self.project_root,
        )
        return result.returncode == 0

    def get_current_commit(self) -> str | None:
        """Get current HEAD commit hash."""
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=self.project_root,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None

    def get_changes_since(self, last_commit: str) -> dict[str, list[Any]]:
        """Get file changes since last indexed commit.

        Returns dict with keys: added, modified, deleted, renamed.
        Renamed entries are dicts with "from" and "to" keys.
        """
        result = subprocess.run(
            ["git", "diff", "--name-status", last_commit, "HEAD"],
            capture_output=True,
            text=True,
            cwd=self.project_root,
        )

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
