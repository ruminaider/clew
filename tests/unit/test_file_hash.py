"""Tests for file-hash change detection."""

from pathlib import Path

import pytest

from clew.indexer.cache import CacheDB
from clew.indexer.file_hash import FileHashTracker


class TestFileHashTracker:
    @pytest.fixture
    def cache(self, temp_cache_dir: Path) -> CacheDB:
        return CacheDB(temp_cache_dir)

    @pytest.fixture
    def tracker(self, cache: CacheDB) -> FileHashTracker:
        return FileHashTracker(cache)

    def test_compute_hash_deterministic(self, tmp_path: Path, tracker: FileHashTracker) -> None:
        f = tmp_path / "test.py"
        f.write_text("hello world")
        h1 = tracker.compute_hash(str(f))
        h2 = tracker.compute_hash(str(f))
        assert h1 == h2

    def test_compute_hash_changes_with_content(
        self, tmp_path: Path, tracker: FileHashTracker
    ) -> None:
        f = tmp_path / "test.py"
        f.write_text("version 1")
        h1 = tracker.compute_hash(str(f))
        f.write_text("version 2")
        h2 = tracker.compute_hash(str(f))
        assert h1 != h2

    def test_new_file_detected_as_added(self, tmp_path: Path, tracker: FileHashTracker) -> None:
        f = tmp_path / "new.py"
        f.write_text("new file")
        changes = tracker.detect_changes([str(f)])
        assert str(f) in changes["added"]
        assert changes["modified"] == []
        assert changes["unchanged"] == []

    def test_modified_file_detected(self, tmp_path: Path, tracker: FileHashTracker) -> None:
        f = tmp_path / "mod.py"
        f.write_text("original")
        tracker.update_hash(str(f), tracker.compute_hash(str(f)), ["chunk1"])
        f.write_text("modified content")
        changes = tracker.detect_changes([str(f)])
        assert str(f) in changes["modified"]

    def test_unchanged_file_detected(self, tmp_path: Path, tracker: FileHashTracker) -> None:
        f = tmp_path / "same.py"
        f.write_text("unchanged")
        tracker.update_hash(str(f), tracker.compute_hash(str(f)), ["chunk1"])
        changes = tracker.detect_changes([str(f)])
        assert str(f) in changes["unchanged"]

    def test_mixed_changes(self, tmp_path: Path, tracker: FileHashTracker) -> None:
        new = tmp_path / "new.py"
        new.write_text("new")

        existing = tmp_path / "existing.py"
        existing.write_text("existing")
        tracker.update_hash(str(existing), tracker.compute_hash(str(existing)), ["c1"])

        modified = tmp_path / "modified.py"
        modified.write_text("original")
        tracker.update_hash(str(modified), tracker.compute_hash(str(modified)), ["c2"])
        modified.write_text("changed")

        changes = tracker.detect_changes([str(new), str(existing), str(modified)])
        assert str(new) in changes["added"]
        assert str(existing) in changes["unchanged"]
        assert str(modified) in changes["modified"]
