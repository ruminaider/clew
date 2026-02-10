"""Tests for git-aware change detection."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from clew.indexer.git_tracker import GitChangeTracker


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    return tmp_path


class TestIsGitRepo:
    def test_is_git_repo_true(self, project_root: Path) -> None:
        tracker = GitChangeTracker(project_root)
        with patch("clew.indexer.git_tracker.subprocess") as mock_sub:
            mock_sub.run.return_value = Mock(returncode=0, stdout="true\n")
            assert tracker.is_git_repo() is True

    def test_is_git_repo_false(self, project_root: Path) -> None:
        tracker = GitChangeTracker(project_root)
        with patch("clew.indexer.git_tracker.subprocess") as mock_sub:
            mock_sub.run.return_value = Mock(returncode=128, stdout="")
            assert tracker.is_git_repo() is False


class TestGetCurrentCommit:
    def test_returns_commit_hash(self, project_root: Path) -> None:
        tracker = GitChangeTracker(project_root)
        with patch("clew.indexer.git_tracker.subprocess") as mock_sub:
            mock_sub.run.return_value = Mock(returncode=0, stdout="abc123def\n")
            assert tracker.get_current_commit() == "abc123def"

    def test_returns_none_on_error(self, project_root: Path) -> None:
        tracker = GitChangeTracker(project_root)
        with patch("clew.indexer.git_tracker.subprocess") as mock_sub:
            mock_sub.run.return_value = Mock(returncode=128, stdout="")
            assert tracker.get_current_commit() is None


class TestGetChangesSince:
    def test_parses_added_modified_deleted(self, project_root: Path) -> None:
        tracker = GitChangeTracker(project_root)
        git_output = "A\tnew_file.py\nM\tmodified.py\nD\tdeleted.py\n"
        with patch("clew.indexer.git_tracker.subprocess") as mock_sub:
            mock_sub.run.return_value = Mock(returncode=0, stdout=git_output)
            changes = tracker.get_changes_since("abc123")
        assert changes["added"] == ["new_file.py"]
        assert changes["modified"] == ["modified.py"]
        assert changes["deleted"] == ["deleted.py"]

    def test_parses_renamed(self, project_root: Path) -> None:
        tracker = GitChangeTracker(project_root)
        git_output = "R100\told_name.py\tnew_name.py\n"
        with patch("clew.indexer.git_tracker.subprocess") as mock_sub:
            mock_sub.run.return_value = Mock(returncode=0, stdout=git_output)
            changes = tracker.get_changes_since("abc123")
        assert len(changes["renamed"]) == 1
        assert changes["renamed"][0] == {"from": "old_name.py", "to": "new_name.py"}

    def test_empty_output(self, project_root: Path) -> None:
        tracker = GitChangeTracker(project_root)
        with patch("clew.indexer.git_tracker.subprocess") as mock_sub:
            mock_sub.run.return_value = Mock(returncode=0, stdout="")
            changes = tracker.get_changes_since("abc123")
        assert changes == {"added": [], "modified": [], "deleted": [], "renamed": []}

    def test_multiple_changes(self, project_root: Path) -> None:
        tracker = GitChangeTracker(project_root)
        git_output = "A\ta.py\nA\tb.py\nM\tc.py\n"
        with patch("clew.indexer.git_tracker.subprocess") as mock_sub:
            mock_sub.run.return_value = Mock(returncode=0, stdout=git_output)
            changes = tracker.get_changes_since("abc123")
        assert len(changes["added"]) == 2
        assert len(changes["modified"]) == 1
