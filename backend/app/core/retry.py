"""Retry delay and budget calculations without transport dependencies."""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int
    base_delay_seconds: float
    max_elapsed_seconds: float
    jitter_seconds: float = 0.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts 必须大于 0")
        if min(self.base_delay_seconds, self.max_elapsed_seconds, self.jitter_seconds) < 0:
            raise ValueError("重试延迟和预算不能小于 0")

    def delay_seconds(
        self,
        attempt_number: int,
        *,
        retry_after_seconds: float | None = None,
    ) -> float:
        exponential = self.base_delay_seconds * (2 ** max(0, attempt_number - 1))
        retry_after = max(0.0, retry_after_seconds or 0.0)
        jitter = float(random.uniform(0.0, self.jitter_seconds)) if self.jitter_seconds else 0.0
        return float(max(exponential, retry_after) + jitter)

    def can_retry(self, *, attempt_number: int, elapsed_seconds: float, delay_seconds: float) -> bool:
        return (
            attempt_number < self.max_attempts
            and elapsed_seconds + delay_seconds <= self.max_elapsed_seconds
        )


__all__ = ["RetryPolicy"]
