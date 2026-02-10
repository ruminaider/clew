"""Safety limit enforcement for indexing."""

from __future__ import annotations

import logging

from .models import SafetyConfig

logger = logging.getLogger(__name__)


class SafetyChecker:
    """Enforce safety limits to prevent runaway indexing."""

    def __init__(self, config: SafetyConfig) -> None:
        self.config = config

    def check_file(self, file_path: str, file_size: int) -> bool:
        """Return False if file should be skipped due to size."""
        if file_size > self.config.max_file_size_bytes:
            logger.warning(
                "Skipping %s: %d bytes > %d limit",
                file_path,
                file_size,
                self.config.max_file_size_bytes,
            )
            return False
        return True

    def check_total_chunks(self, current_count: int, new_chunks: int) -> bool:
        """Return False if adding chunks would exceed total limit."""
        if current_count + new_chunks > self.config.max_total_chunks:
            logger.error(
                "Safety limit: %d chunks would exceed %d limit",
                current_count + new_chunks,
                self.config.max_total_chunks,
            )
            return False
        return True

    def check_collection_chunks(
        self,
        collection_name: str,
        current_count: int,
        new_chunks: int,
    ) -> bool:
        """Return False if adding chunks would exceed collection limit."""
        limit = self.config.collection_limits.get(collection_name)
        if limit is None:
            return True
        if current_count + new_chunks > limit:
            logger.error(
                "Collection '%s' safety limit: %d chunks would exceed %d limit",
                collection_name,
                current_count + new_chunks,
                limit,
            )
            return False
        return True
