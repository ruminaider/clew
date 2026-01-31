"""Tests for safety limit enforcement."""

import logging

import pytest

from code_search.models import SafetyConfig
from code_search.safety import SafetyChecker


class TestSafetyCheckerFileSize:
    def test_small_file_allowed(self) -> None:
        checker = SafetyChecker(SafetyConfig())
        assert checker.check_file("small.py", 1000) is True

    def test_file_at_limit_allowed(self) -> None:
        checker = SafetyChecker(SafetyConfig(max_file_size_bytes=1_048_576))
        assert checker.check_file("exact.py", 1_048_576) is True

    def test_large_file_rejected(self) -> None:
        checker = SafetyChecker(SafetyConfig(max_file_size_bytes=1_048_576))
        assert checker.check_file("huge.min.js", 5_000_000) is False

    def test_custom_limit(self) -> None:
        checker = SafetyChecker(SafetyConfig(max_file_size_bytes=5000))
        assert checker.check_file("small.py", 4999) is True
        assert checker.check_file("big.py", 5001) is False


class TestSafetyCheckerTotalChunks:
    def test_within_limit(self) -> None:
        checker = SafetyChecker(SafetyConfig(max_total_chunks=500_000))
        assert checker.check_total_chunks(499_990, 5) is True

    def test_at_limit(self) -> None:
        checker = SafetyChecker(SafetyConfig(max_total_chunks=500_000))
        assert checker.check_total_chunks(499_990, 10) is True

    def test_exceeds_limit(self) -> None:
        checker = SafetyChecker(SafetyConfig(max_total_chunks=500_000))
        assert checker.check_total_chunks(499_990, 20) is False

    def test_custom_limit(self) -> None:
        checker = SafetyChecker(SafetyConfig(max_total_chunks=1000))
        assert checker.check_total_chunks(999, 1) is True
        assert checker.check_total_chunks(999, 2) is False


class TestSafetyCheckerCollectionLimits:
    def test_no_collection_limit_allows_all(self) -> None:
        checker = SafetyChecker(SafetyConfig())
        assert checker.check_collection_chunks("code", 999_999, 1) is True

    def test_collection_limit_enforced(self) -> None:
        checker = SafetyChecker(
            SafetyConfig(collection_limits={"code": 10_000})
        )
        assert checker.check_collection_chunks("code", 9_999, 1) is True
        assert checker.check_collection_chunks("code", 9_999, 2) is False

    def test_unlisted_collection_unlimited(self) -> None:
        checker = SafetyChecker(
            SafetyConfig(collection_limits={"code": 10_000})
        )
        assert checker.check_collection_chunks("docs", 999_999, 1) is True


class TestSafetyCheckerLogging:
    def test_rejected_file_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        checker = SafetyChecker(SafetyConfig(max_file_size_bytes=1024))
        with caplog.at_level(logging.WARNING):
            checker.check_file("big.py", 2048)
        assert "big.py" in caplog.text

    def test_rejected_chunks_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        checker = SafetyChecker(SafetyConfig(max_total_chunks=1000))
        with caplog.at_level(logging.ERROR):
            checker.check_total_chunks(999, 10)
        assert "1009" in caplog.text or "1000" in caplog.text
