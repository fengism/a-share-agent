import logging
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProviderAttempt:
    label: str
    loader: Callable[[], Awaitable[Any]]
    on_error: str | None = None


@dataclass(frozen=True)
class ProviderAttemptResult:
    label: str
    success: bool
    elapsed_ms: float
    error_type: str | None = None
    error_message: str | None = None


@dataclass(frozen=True)
class ProviderChainReport:
    attempts: list[ProviderAttemptResult]
    selected_label: str | None = None


class BaseProviderChain:
    def __init__(self, attempts: list[ProviderAttempt]):
        self.attempts = attempts

    async def run(self):
        result, _ = await self.run_with_report()
        return result

    async def run_with_report(self):
        attempt_results: list[ProviderAttemptResult] = []
        last_error: Exception | None = None
        for attempt in self.attempts:
            start = time.perf_counter()
            try:
                result = await attempt.loader()
            except Exception as exc:
                elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
                last_error = exc
                attempt_results.append(
                    ProviderAttemptResult(
                        label=attempt.label,
                        success=False,
                        elapsed_ms=elapsed_ms,
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                    )
                )
                logger.info(
                    "provider attempt failed: label=%s, elapsed_ms=%.2f, error_type=%s, message=%s",
                    attempt.label,
                    elapsed_ms,
                    type(exc).__name__,
                    attempt.on_error or "",
                )
                continue

            elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
            attempt_results.append(ProviderAttemptResult(label=attempt.label, success=True, elapsed_ms=elapsed_ms))
            logger.debug("provider attempt succeeded: label=%s, elapsed_ms=%.2f", attempt.label, elapsed_ms)
            return result, ProviderChainReport(attempts=attempt_results, selected_label=attempt.label)

        if last_error is not None:
            raise last_error
        raise RuntimeError("provider chain is empty")
