"""Lightweight JSONL telemetry logger for search queries.

Appends one line per query to `.clew/query_telemetry.jsonl`.
Privacy-preserving: logs query hashes, not raw queries.
Silent failure: telemetry never breaks search.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

TELEMETRY_FILENAME = "query_telemetry.jsonl"


class QueryTelemetry:
    """Lightweight JSONL telemetry logger for search queries."""

    def __init__(self, cache_dir: Path, *, enabled: bool = True) -> None:
        self._enabled = enabled
        self._path = cache_dir / TELEMETRY_FILENAME

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def path(self) -> Path:
        return self._path

    def record(
        self,
        *,
        query: str,
        intent: str,
        mode_used: str,
        result_count: int,
        top_score: float,
        z_score: float,
        confidence_label: str,
        reranked: bool,
    ) -> None:
        """Append a telemetry event. Silent on failure.

        Args:
            query: Raw query text (hashed before writing, never stored raw).
            intent: Classified intent string (e.g. "code", "debug").
            mode_used: Search mode ("semantic" or "exhaustive").
            result_count: Number of results returned.
            top_score: Score of the first result (0.0 if no results).
            z_score: Confidence Z-score value.
            confidence_label: Confidence label ("high", "medium", "low").
            reranked: Whether reranking was applied.
        """
        if not self._enabled:
            return

        try:
            event = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "query_hash": hashlib.sha256(query.encode()).hexdigest(),
                "intent": intent,
                "mode_used": mode_used,
                "result_count": result_count,
                "top_score": round(top_score, 4),
                "z_score": round(z_score, 4),
                "confidence_label": confidence_label,
                "reranked": reranked,
            }
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._path, "a") as f:
                f.write(json.dumps(event) + "\n")
        except Exception:
            logger.debug("Telemetry write failed", exc_info=True)
