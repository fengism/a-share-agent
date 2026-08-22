from __future__ import annotations

import asyncio
import logging
import time
from typing import Awaitable, Callable, TypeVar

from app.configuration import get_settings
from app.core.concurrency.rate_limiter import call_blocking as run_blocking
from app.core.metrics import metrics
from app.core.operational import ProviderCircuitSnapshot
from app.core.retry import RetryPolicy
from app.infrastructure.providers.provider_circuit import ProviderCircuitBreaker
from app.infrastructure.providers.provider_policy import (
    ProviderCircuitOpenError,
    ProviderErrorCategory,
    classify_provider_error,
    is_retryable,
)

T = TypeVar("T")

logger = logging.getLogger(__name__)


def _is_retryable(category: ProviderErrorCategory) -> bool:
    return is_retryable(category)


def _retry_after_seconds(error: Exception) -> float | None:
    direct_value = getattr(error, "retry_after_seconds", None)
    if direct_value is not None:
        try:
            return max(0.0, float(direct_value))
        except (TypeError, ValueError):
            return None
    response = getattr(error, "response", None)
    headers = getattr(response, "headers", None)
    if headers is None or not hasattr(headers, "get"):
        return None
    raw_value = headers.get("Retry-After")
    if raw_value is None:
        return None
    try:
        return max(0.0, float(raw_value))
    except (TypeError, ValueError):
        return None


def _retry_policy(settings, max_attempts: int | None, retry_budget_seconds: float | None) -> RetryPolicy:
    return RetryPolicy(
        max_attempts=max(1, max_attempts or settings.provider_gateway_max_attempts),
        base_delay_seconds=max(0.0, settings.provider_retry_base_seconds),
        max_elapsed_seconds=max(
            0.0,
            retry_budget_seconds
            if retry_budget_seconds is not None
            else getattr(settings, "provider_retry_budget_seconds", 5.0),
        ),
        jitter_seconds=max(0.0, getattr(settings, "provider_retry_jitter_seconds", 0.1)),
    )


class ProviderGateway:
    def __init__(self) -> None:
        self._circuit_breaker = ProviderCircuitBreaker()
        self._lock = self._circuit_breaker.lock
        self._circuits = self._circuit_breaker.circuits

    async def call(
        self,
        provider: str,
        operation: str,
        loader: Callable[[], Awaitable[T]],
        *,
        is_fallback_attempt: bool = False,
        max_attempts: int | None = None,
        retry_budget_seconds: float | None = None,
    ) -> T:
        settings = get_settings()
        retry_policy = _retry_policy(settings, max_attempts, retry_budget_seconds)
        threshold = max(1, settings.provider_failure_threshold)
        open_seconds = max(0.0, settings.provider_circuit_open_seconds)
        circuit_key = (provider, operation)
        half_open = self._before_call(circuit_key, open_seconds)
        last_error: Exception | None = None
        last_category = ProviderErrorCategory.PERMANENT
        request_started_at = time.perf_counter()

        try:
            for attempt_number in range(1, retry_policy.max_attempts + 1):
                started_at = time.perf_counter()
                try:
                    result = await loader()
                except Exception as exc:
                    elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
                    category = classify_provider_error(exc)
                    last_error = exc
                    last_category = category
                    metrics.record_provider_attempt(
                        provider,
                        operation=operation,
                        success=False,
                        duration_ms=elapsed_ms,
                        fallback=is_fallback_attempt,
                        error_type=type(exc).__name__,
                    )
                    logger.warning(
                        "provider call failed provider=%s operation=%s attempt=%s category=%s error_type=%s",
                        provider,
                        operation,
                        attempt_number,
                        category.value,
                        type(exc).__name__,
                    )
                    delay = retry_policy.delay_seconds(
                        attempt_number,
                        retry_after_seconds=_retry_after_seconds(exc),
                    )
                    if not _is_retryable(category) or not retry_policy.can_retry(
                        attempt_number=attempt_number,
                        elapsed_seconds=time.perf_counter() - request_started_at,
                        delay_seconds=delay,
                    ):
                        break
                    await asyncio.sleep(delay)
                    continue

                elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
                self._record_success(circuit_key)
                metrics.record_provider_attempt(
                    provider,
                    operation=operation,
                    success=True,
                    duration_ms=elapsed_ms,
                    fallback=is_fallback_attempt,
                )
                return result
        except asyncio.CancelledError:
            if half_open:
                self._release_half_open(circuit_key)
            raise

        self._record_failure(circuit_key, last_category, threshold, half_open)
        if last_error is not None:
            raise last_error
        raise RuntimeError(f"provider call failed without an exception: {provider}.{operation}")

    async def call_blocking(
        self,
        provider: str,
        operation: str,
        func: Callable[..., T],
        *args,
        semaphore=None,
        is_fallback_attempt: bool = False,
        max_attempts: int | None = None,
        retry_budget_seconds: float | None = None,
        **kwargs,
    ) -> T:
        return await self.call(
            provider,
            operation,
            lambda: run_blocking(func, *args, semaphore=semaphore, **kwargs),
            is_fallback_attempt=is_fallback_attempt,
            max_attempts=max_attempts,
            retry_budget_seconds=retry_budget_seconds,
        )

    def call_sync(
        self,
        provider: str,
        operation: str,
        loader: Callable[[], T],
        *,
        is_fallback_attempt: bool = False,
        max_attempts: int | None = None,
        retry_budget_seconds: float | None = None,
    ) -> T:
        settings = get_settings()
        retry_policy = _retry_policy(settings, max_attempts, retry_budget_seconds)
        threshold = max(1, settings.provider_failure_threshold)
        open_seconds = max(0.0, settings.provider_circuit_open_seconds)
        circuit_key = (provider, operation)
        half_open = self._before_call(circuit_key, open_seconds)
        last_error: Exception | None = None
        last_category = ProviderErrorCategory.PERMANENT
        request_started_at = time.perf_counter()

        for attempt_number in range(1, retry_policy.max_attempts + 1):
            started_at = time.perf_counter()
            try:
                result = loader()
            except Exception as exc:
                elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
                category = classify_provider_error(exc)
                last_error = exc
                last_category = category
                metrics.record_provider_attempt(
                    provider,
                    operation=operation,
                    success=False,
                    duration_ms=elapsed_ms,
                    fallback=is_fallback_attempt,
                    error_type=type(exc).__name__,
                )
                logger.warning(
                    "provider call failed provider=%s operation=%s attempt=%s category=%s error_type=%s",
                    provider,
                    operation,
                    attempt_number,
                    category.value,
                    type(exc).__name__,
                )
                delay = retry_policy.delay_seconds(
                    attempt_number,
                    retry_after_seconds=_retry_after_seconds(exc),
                )
                if not _is_retryable(category) or not retry_policy.can_retry(
                    attempt_number=attempt_number,
                    elapsed_seconds=time.perf_counter() - request_started_at,
                    delay_seconds=delay,
                ):
                    break
                time.sleep(delay)
                continue

            self._record_success(circuit_key)
            metrics.record_provider_attempt(
                provider,
                operation=operation,
                success=True,
                duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
                fallback=is_fallback_attempt,
            )
            return result

        self._record_failure(circuit_key, last_category, threshold, half_open)
        if last_error is not None:
            raise last_error
        raise RuntimeError(f"provider call failed without an exception: {provider}.{operation}")

    def _before_call(self, key: tuple[str, str], open_seconds: float) -> bool:
        try:
            return self._circuit_breaker.before_call(key, open_seconds, time.monotonic())
        except ProviderCircuitOpenError:
            provider, operation = key
            metrics.record_provider_attempt(
                provider,
                operation=operation,
                success=False,
                duration_ms=0,
                error_type=ProviderCircuitOpenError.__name__,
            )
            raise

    def _record_success(self, key: tuple[str, str]) -> None:
        self._circuit_breaker.record_success(key)

    def _record_failure(
        self,
        key: tuple[str, str],
        category: ProviderErrorCategory,
        threshold: int,
        half_open: bool,
    ) -> None:
        self._circuit_breaker.record_failure(
            key,
            retryable=_is_retryable(category),
            threshold=threshold,
            half_open=half_open,
            clock=time.monotonic,
        )

    def _release_half_open(self, key: tuple[str, str]) -> None:
        self._circuit_breaker.release_half_open(key)

    def snapshot(self) -> dict[str, ProviderCircuitSnapshot]:
        settings = get_settings()
        open_seconds = max(0.0, settings.provider_circuit_open_seconds)
        return self._circuit_breaker.snapshot(open_seconds, time.monotonic())

    def reset(self) -> None:
        self._circuit_breaker.reset()


provider_gateway = ProviderGateway()
