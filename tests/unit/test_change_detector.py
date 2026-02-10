"""Tests for unified change detection module."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from clew.indexer.change_detector import ChangeDetector


@pytest.fixture
def mock_cache() -> Mock:
    return Mock()


@patch("clew.indexer.file_hash.FileHashTracker")
@patch("clew.indexer.git_tracker.GitChangeTracker")
class TestDetectChangesGitPath:
    def test_git_path_with_last_commit(
        self, mock_git_cls: Mock, mock_hash_cls: Mock, mock_cache: Mock
    ) -> None:
        """Git repo + last commit -> uses git diff, returns ChangeResult with source='git'."""
        mock_git = mock_git_cls.return_value
        mock_git.is_git_repo.return_value = True
        mock_git.get_changes_since.return_value = {
            "added": ["new.py"],
            "modified": ["changed.py"],
            "deleted": ["removed.py"],
            "renamed": [],
        }
        mock_cache.get_last_indexed_commit.return_value = "abc123"

        detector = ChangeDetector(Path("/fake"), mock_cache)
        result = detector.detect_changes(["new.py", "changed.py", "existing.py"])

        assert result.source == "git"
        assert result.added == ["new.py"]
        assert result.modified == ["changed.py"]
        assert result.deleted == ["removed.py"]
        assert result.unchanged == ["existing.py"]

    def test_git_renamed_files(
        self, mock_git_cls: Mock, mock_hash_cls: Mock, mock_cache: Mock
    ) -> None:
        """Renamed files are treated as delete old + add new."""
        mock_git = mock_git_cls.return_value
        mock_git.is_git_repo.return_value = True
        mock_git.get_changes_since.return_value = {
            "added": [],
            "modified": [],
            "deleted": [],
            "renamed": [{"from": "old_name.py", "to": "new_name.py"}],
        }
        mock_cache.get_last_indexed_commit.return_value = "abc123"

        detector = ChangeDetector(Path("/fake"), mock_cache)
        result = detector.detect_changes(["new_name.py", "other.py"])

        assert result.source == "git"
        assert "new_name.py" in result.added
        assert "old_name.py" in result.deleted

    def test_git_filters_to_requested_files(
        self, mock_git_cls: Mock, mock_hash_cls: Mock, mock_cache: Mock
    ) -> None:
        """Only files in file_paths appear in added/modified results."""
        mock_git = mock_git_cls.return_value
        mock_git.is_git_repo.return_value = True
        mock_git.get_changes_since.return_value = {
            "added": ["a.py", "b.py", "not_requested.py"],
            "modified": ["c.py", "also_not_requested.py"],
            "deleted": [],
            "renamed": [],
        }
        mock_cache.get_last_indexed_commit.return_value = "abc123"

        detector = ChangeDetector(Path("/fake"), mock_cache)
        result = detector.detect_changes(["a.py", "c.py", "unchanged.py"])

        assert result.added == ["a.py"]
        assert "not_requested.py" not in result.added
        assert result.modified == ["c.py"]
        assert "also_not_requested.py" not in result.modified

    def test_git_unchanged_files(
        self, mock_git_cls: Mock, mock_hash_cls: Mock, mock_cache: Mock
    ) -> None:
        """Files not in git diff are classified as unchanged."""
        mock_git = mock_git_cls.return_value
        mock_git.is_git_repo.return_value = True
        mock_git.get_changes_since.return_value = {
            "added": ["new.py"],
            "modified": [],
            "deleted": [],
            "renamed": [],
        }
        mock_cache.get_last_indexed_commit.return_value = "abc123"

        detector = ChangeDetector(Path("/fake"), mock_cache)
        result = detector.detect_changes(["new.py", "stable1.py", "stable2.py"])

        assert result.unchanged == ["stable1.py", "stable2.py"]
        assert "new.py" not in result.unchanged


@patch("clew.indexer.file_hash.FileHashTracker")
@patch("clew.indexer.git_tracker.GitChangeTracker")
class TestDetectChangesHashFallback:
    def test_hash_fallback_not_git_repo(
        self, mock_git_cls: Mock, mock_hash_cls: Mock, mock_cache: Mock
    ) -> None:
        """Not a git repo -> uses file hash, source='hash'."""
        mock_git = mock_git_cls.return_value
        mock_git.is_git_repo.return_value = False

        mock_hash = mock_hash_cls.return_value
        mock_hash.detect_changes.return_value = {
            "added": ["new.py"],
            "modified": ["changed.py"],
            "unchanged": ["same.py"],
        }

        detector = ChangeDetector(Path("/fake"), mock_cache)
        result = detector.detect_changes(["new.py", "changed.py", "same.py"])

        assert result.source == "hash"
        assert result.added == ["new.py"]
        assert result.modified == ["changed.py"]
        assert result.unchanged == ["same.py"]
        assert result.deleted == []

    def test_hash_fallback_no_last_commit(
        self, mock_git_cls: Mock, mock_hash_cls: Mock, mock_cache: Mock
    ) -> None:
        """Git repo but no last commit (fresh index) -> uses hash fallback."""
        mock_git = mock_git_cls.return_value
        mock_git.is_git_repo.return_value = True

        mock_cache.get_last_indexed_commit.return_value = None

        mock_hash = mock_hash_cls.return_value
        mock_hash.detect_changes.return_value = {
            "added": ["a.py", "b.py"],
            "modified": [],
            "unchanged": [],
        }

        detector = ChangeDetector(Path("/fake"), mock_cache)
        result = detector.detect_changes(["a.py", "b.py"])

        assert result.source == "hash"
        assert result.added == ["a.py", "b.py"]
        mock_hash.detect_changes.assert_called_once_with(["a.py", "b.py"])


@patch("clew.indexer.file_hash.FileHashTracker")
@patch("clew.indexer.git_tracker.GitChangeTracker")
class TestGetCurrentCommit:
    def test_get_current_commit_returns_hash(
        self, mock_git_cls: Mock, mock_hash_cls: Mock, mock_cache: Mock
    ) -> None:
        """Git repo returns commit hash."""
        mock_git = mock_git_cls.return_value
        mock_git.is_git_repo.return_value = True
        mock_git.get_current_commit.return_value = "deadbeef123"

        detector = ChangeDetector(Path("/fake"), mock_cache)
        assert detector.get_current_commit() == "deadbeef123"

    def test_get_current_commit_not_git(
        self, mock_git_cls: Mock, mock_hash_cls: Mock, mock_cache: Mock
    ) -> None:
        """Non-git repo returns None."""
        mock_git = mock_git_cls.return_value
        mock_git.is_git_repo.return_value = False

        detector = ChangeDetector(Path("/fake"), mock_cache)
        assert detector.get_current_commit() is None
