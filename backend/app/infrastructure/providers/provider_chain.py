import logging
import time
from dataclasses import dataclass
from typing import Awaitable, Callable, Generic, TypeVar

from app.infrastructure.providers.provider_gateway import provider_gateway

logger = logging.getLogger(__name__)
T = TypeVar("T")

_MAX_LOGGED_ERROR_CHARS = 300


def _error_detail(error: Exception) -> str:
    """Render the real upstream failure so a chain log is actionable.

    ``ProviderAttempt.on_error`` is a static human-facing hint ("腾讯实时行情不可用"):
    useful context, but useless for telling a 403 apart from a 404 or a malformed
    response. Log the actual exception as ``message`` and keep the hint as ``hint``.
    Bound the length and collapse newlines so one failure stays one log line.
    """
    detail = " ".join(str(error).split())
    if not detail:
        return type(error).__name__
    if len(detail) > _MAX_LOGGED_ERROR_CHARS:
        return detail[:_MAX_LOGGED_ERROR_CHARS] + "..."
    return detail


@dataclass(frozen=True)
class ProviderAttempt(Generic[T]):
    """Purpose: 数据源提供者的单次尝试配置，包含标签、加载函数和错误处理回调。"""

    label: str
    loader: Callable[[], Awaitable[T]]
    on_error: str | None = None
    max_attempts: int | None = None
    retry_budget_seconds: float | None = None


@dataclass(frozen=True)
class ProviderAttemptResult:
    """Purpose: 单次数据源尝试的结果记录，包含标签、状态、耗时和错误信息。"""

    label: str
    success: bool
    elapsed_ms: float
    error_type: str | None = None
    error_message: str | None = None


@dataclass(frozen=True)
class ProviderChainReport:
    """Purpose: 整个 provider chain 的执行报告，包含所有尝试结果和最终选中的提供者。"""

    attempts: list[ProviderAttemptResult]
    selected_label: str | None = None


class BaseProviderChain(Generic[T]):
    """Purpose: 提供者链的基类，按顺序执行多个 ProviderAttempt，成功即返回，失败则尝试下一个。"""

    def __init__(self, attempts: list[ProviderAttempt[T]], operation: str = "provider_chain"):
        """Initialize the chain with the ordered list of provider attempts.

        Param:
            attempts: ordered list of provider attempts to execute
        """
        self.attempts = attempts
        self.operation = operation

    async def run(self) -> T:
        """Run the provider chain and return the first successful result.

        Param:
            None
        Return:
            the value returned by the first successful attempt's loader
        """
        result, _ = await self.run_with_report()
        return result

    async def run_with_report(self) -> tuple[T, ProviderChainReport]:
        """Run the provider chain and return both the result and a report.

        Param:
            None
        Return:
            tuple of (result value, ProviderChainReport with all attempt outcomes)
        """
        attempt_results: list[ProviderAttemptResult] = []
        last_error: Exception | None = None
        for attempt_index, attempt in enumerate(self.attempts):
            start = time.perf_counter()
            try:
                result = await provider_gateway.call(
                    attempt.label,
                    self.operation,
                    attempt.loader,
                    is_fallback_attempt=attempt_index > 0,
                    max_attempts=attempt.max_attempts,
                    retry_budget_seconds=attempt.retry_budget_seconds,
                )
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
                logger.debug(
                    "provider attempt failed: label=%s, elapsed_ms=%.2f, error_type=%s, hint=%s, message=%s",
                    attempt.label,
                    elapsed_ms,
                    type(exc).__name__,
                    attempt.on_error or "",
                    _error_detail(exc),
                )
                continue

            elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
            attempt_results.append(ProviderAttemptResult(label=attempt.label, success=True, elapsed_ms=elapsed_ms))
            logger.debug("provider attempt succeeded: label=%s, elapsed_ms=%.2f", attempt.label, elapsed_ms)
            return result, ProviderChainReport(attempts=attempt_results, selected_label=attempt.label)

        if last_error is not None:
            raise last_error
        raise RuntimeError("provider chain is empty")
