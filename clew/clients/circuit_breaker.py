"""Simple circuit breaker for external API resilience."""

from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """Track consecutive failures and block calls during cooldown."""

    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        cooldown_seconds: float = 60.0,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self._consecutive_failures = 0
        self._opened_at: float | None = None

    @property
    def is_open(self) -> bool:
        if self._opened_at is None:
            return False
        elapsed = time.monotonic() - self._opened_at
        if elapsed >= self.cooldown_seconds:
            self._reset()
            return False
        return True

    def record_success(self) -> None:
        if self._consecutive_failures > 0:
            logger.debug("CircuitBreaker[%s]: reset after success", self.name)
        self._consecutive_failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures >= self.failure_threshold and self._opened_at is None:
            self._opened_at = time.monotonic()
            logger.warning(
                "CircuitBreaker[%s]: OPEN after %d consecutive failures (cooldown=%.0fs)",
                self.name,
                self._consecutive_failures,
                self.cooldown_seconds,
            )

    def _reset(self) -> None:
        logger.info("CircuitBreaker[%s]: CLOSED (cooldown expired)", self.name)
        self._consecutive_failures = 0
        self._opened_at = None
