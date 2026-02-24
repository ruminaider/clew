"""Tests for QueryTelemetry JSONL logger."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from clew.search.telemetry import QueryTelemetry


def _record_event(telemetry: QueryTelemetry, query: str = "find auth handler") -> None:
    """Record a standard telemetry event."""
    telemetry.record(
        query=query,
        intent="code",
        mode_used="semantic",
        result_count=5,
        top_score=0.87,
        z_score=1.23,
        confidence_label="high",
        reranked=True,
    )


class TestRecordsEventCorrectly:
    """Verify JSONL line has expected fields and values."""

    def test_records_event_correctly(self, tmp_path: Path) -> None:
        telemetry = QueryTelemetry(cache_dir=tmp_path, enabled=True)
        _record_event(telemetry)

        lines = telemetry.path.read_text().strip().split("\n")
        assert len(lines) == 1

        event = json.loads(lines[0])
        assert "timestamp" in event
        assert event["query_hash"] == hashlib.sha256(b"find auth handler").hexdigest()
        assert event["intent"] == "code"
        assert event["mode_used"] == "semantic"
        assert event["result_count"] == 5
        assert event["top_score"] == 0.87
        assert event["z_score"] == 1.23
        assert event["confidence_label"] == "high"
        assert event["reranked"] is True

    def test_appends_multiple_events(self, tmp_path: Path) -> None:
        telemetry = QueryTelemetry(cache_dir=tmp_path, enabled=True)
        _record_event(telemetry, query="first query")
        _record_event(telemetry, query="second query")

        lines = telemetry.path.read_text().strip().split("\n")
        assert len(lines) == 2

        event1 = json.loads(lines[0])
        event2 = json.loads(lines[1])
        assert event1["query_hash"] != event2["query_hash"]

    def test_timestamp_is_iso8601(self, tmp_path: Path) -> None:
        telemetry = QueryTelemetry(cache_dir=tmp_path, enabled=True)
        _record_event(telemetry)

        event = json.loads(telemetry.path.read_text().strip())
        # ISO 8601 with timezone: ends with +00:00 or Z
        ts = event["timestamp"]
        assert "T" in ts
        assert "+" in ts or "Z" in ts

    def test_scores_are_rounded(self, tmp_path: Path) -> None:
        telemetry = QueryTelemetry(cache_dir=tmp_path, enabled=True)
        telemetry.record(
            query="test",
            intent="debug",
            mode_used="semantic",
            result_count=3,
            top_score=0.87654321,
            z_score=1.23456789,
            confidence_label="high",
            reranked=False,
        )

        event = json.loads(telemetry.path.read_text().strip())
        assert event["top_score"] == 0.8765
        assert event["z_score"] == 1.2346


class TestNoOpWhenDisabled:
    """No file created when enabled=False."""

    def test_no_op_when_disabled(self, tmp_path: Path) -> None:
        telemetry = QueryTelemetry(cache_dir=tmp_path, enabled=False)
        _record_event(telemetry)

        assert not telemetry.path.exists()

    def test_enabled_property(self, tmp_path: Path) -> None:
        enabled = QueryTelemetry(cache_dir=tmp_path, enabled=True)
        disabled = QueryTelemetry(cache_dir=tmp_path, enabled=False)
        assert enabled.enabled is True
        assert disabled.enabled is False


class TestSilentFailureOnWriteError:
    """Doesn't raise when file is unwritable."""

    def test_silent_failure_on_write_error(self, tmp_path: Path) -> None:
        telemetry = QueryTelemetry(cache_dir=tmp_path / "nonexistent" / "deep" / "path")
        # Should not raise even with a plausible path
        # (the parent.mkdir call handles this, but let's test a truly unwritable case)
        _record_event(telemetry)  # Should succeed (mkdir creates parents)

    def test_silent_failure_on_readonly_dir(self, tmp_path: Path) -> None:
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        # Write a file, then make dir read-only
        telemetry = QueryTelemetry(cache_dir=readonly_dir, enabled=True)
        telemetry.path.touch()
        readonly_dir.chmod(0o444)

        try:
            # Should not raise
            _record_event(telemetry)
        finally:
            # Restore permissions for cleanup
            readonly_dir.chmod(0o755)


class TestQueryHashIsDeterministic:
    """Same query produces same hash."""

    def test_query_hash_is_deterministic(self, tmp_path: Path) -> None:
        telemetry = QueryTelemetry(cache_dir=tmp_path, enabled=True)
        _record_event(telemetry, query="find auth handler")
        _record_event(telemetry, query="find auth handler")

        lines = telemetry.path.read_text().strip().split("\n")
        event1 = json.loads(lines[0])
        event2 = json.loads(lines[1])
        assert event1["query_hash"] == event2["query_hash"]

    def test_different_queries_different_hashes(self, tmp_path: Path) -> None:
        telemetry = QueryTelemetry(cache_dir=tmp_path, enabled=True)
        _record_event(telemetry, query="find auth handler")
        _record_event(telemetry, query="database connection pool")

        lines = telemetry.path.read_text().strip().split("\n")
        event1 = json.loads(lines[0])
        event2 = json.loads(lines[1])
        assert event1["query_hash"] != event2["query_hash"]


class TestNoRawQueryInOutput:
    """Raw query text never appears in JSONL."""

    def test_no_raw_query_in_output(self, tmp_path: Path) -> None:
        query = "find the authentication handler for webhook payments"
        telemetry = QueryTelemetry(cache_dir=tmp_path, enabled=True)
        _record_event(telemetry, query=query)

        raw_content = telemetry.path.read_text()
        assert query not in raw_content
        # Also verify individual words that are distinctive don't appear
        # (hash is hex, so "webhook" and "authentication" should not be in output)
        assert "webhook" not in raw_content
        assert "authentication" not in raw_content

    def test_no_raw_query_in_json_values(self, tmp_path: Path) -> None:
        query = "unique_search_term_xyz_123"
        telemetry = QueryTelemetry(cache_dir=tmp_path, enabled=True)
        _record_event(telemetry, query=query)

        event = json.loads(telemetry.path.read_text().strip())
        for value in event.values():
            if isinstance(value, str):
                assert query not in value


class TestPathProperty:
    """Telemetry path is correctly constructed."""

    def test_path_in_cache_dir(self, tmp_path: Path) -> None:
        telemetry = QueryTelemetry(cache_dir=tmp_path, enabled=True)
        assert telemetry.path == tmp_path / "query_telemetry.jsonl"

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        deep_dir = tmp_path / "a" / "b" / "c"
        telemetry = QueryTelemetry(cache_dir=deep_dir, enabled=True)
        _record_event(telemetry)
        assert telemetry.path.exists()
