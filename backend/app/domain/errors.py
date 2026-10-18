"""Framework-neutral application errors and transient-failure classification."""

from __future__ import annotations

import logging
from functools import lru_cache
from uuid import uuid4


class ApplicationError(Exception):
    default_code = "application_error"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.code = code or self.default_code


class InvalidRequestError(ApplicationError):
    default_code = "bad_request"


class ResourceNotFoundError(ApplicationError):
    default_code = "not_found"


class ResourceConflictError(ApplicationError):
    default_code = "conflict"


class UpstreamUnavailableError(ApplicationError):
    default_code = "upstream_unavailable"


class UpstreamRateLimitedError(UpstreamUnavailableError):
    """上游按请求频率拒绝服务，等待后重试通常可以恢复。"""

    default_code = "upstream_rate_limited"


class UpstreamEmptyResponseError(UpstreamUnavailableError):
    """上游返回了成功响应，但内容不可用（空体、被限流后返回空 K 线等）。"""

    default_code = "upstream_empty_response"


def build_internal_error(message: str) -> tuple[str, str]:
    """生成可供用户反馈的错误编号与脱敏提示。"""
    error_id = uuid4().hex[:12]
    return error_id, f"{message}（错误编号：{error_id}）"


def log_internal_error(
    logger: logging.Logger,
    operation: str,
    exc: Exception,
    public_message: str,
) -> tuple[str, str]:
    """记录完整异常，并返回不包含内部实现细节的用户提示。"""
    error_id, detail = build_internal_error(public_message)
    logger.error("%s失败 error_id=%s: %s", operation, error_id, exc, exc_info=True)
    return error_id, detail


# 只有明确的瞬时性异常才允许模型原样重试。默认不可重试：把编程错误（TypeError）、
# 权限错误（PermissionError）、配置错误（RuntimeError）标成可重试，会诱导 Agent
# 拿着同样的参数原地重试，直到 max_rounds 耗尽——正是本次排查反复看到的失败模式。
_TRANSIENT_ERROR_TYPES: frozenset[type[BaseException]] = frozenset({
    TimeoutError,  # 含 asyncio.TimeoutError；工具级超时有独立分支，这里兜底
    ConnectionError,  # 连接被拒 / 被重置 / 管道断裂
    InterruptedError,  # 系统调用被信号中断
})

# HTTP 状态码里「换个时间重试就能成」的那部分。4xx（除限流/超时）不在此列：
# 参数错、没权限、未找到，重试一万次也是同样结果。
_TRANSIENT_HTTP_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})


@lru_cache(maxsize=1)
def _third_party_transient_types() -> frozenset[type[BaseException]]:
    """登记实际在用的 HTTP 客户端的网络异常。

    必须显式登记，不能只判内置类型：``requests.exceptions.ConnectionError`` 与
    ``Timeout`` 继承 ``RequestException(IOError)``，和内置 ``ConnectionError``
    （``OSError`` 子类）是**兄弟类而非子类**。只认内置类型会把真实的连接失败、
    读超时判成「不可重试」，并且还明确告诉模型「原样重试无效」。

    这是兜底而不是正解：正解是各 provider 在 gateway 层就把网络异常归一化成
    ``UpstreamUnavailableError``（``Tool.execute`` 已按可重试处理那一分支）。
    """
    types: set[type[BaseException]] = set()
    try:
        from requests import exceptions as requests_exceptions
    except ImportError:  # pragma: no cover - requests 是既有依赖
        pass
    else:
        types.update({
            requests_exceptions.ConnectionError,
            requests_exceptions.Timeout,
            requests_exceptions.ChunkedEncodingError,
        })
    try:
        import httpx
    except ImportError:  # pragma: no cover - 可选依赖
        pass
    else:
        types.add(httpx.TransportError)
    return frozenset(types)


def _http_status(error: BaseException) -> int | None:
    response = getattr(error, "response", None)
    for candidate in (response, error):
        status = getattr(candidate, "status_code", None)
        if isinstance(status, int):
            return status
    return None


@lru_cache(maxsize=1)
def _transient_error_types() -> tuple[type[BaseException], ...]:
    """``isinstance`` 只接受 tuple，两个集合在这里合成一次并缓存。"""
    return (*_TRANSIENT_ERROR_TYPES, *_third_party_transient_types())


def is_transient_error(error: BaseException) -> bool:
    """该异常是否值得让模型原样重试。

    刻意保守：漏判成不可重试，Agent 只是换个工具或来源；误判成可重试，
    Agent 会重复同一调用，把工具配额和 LLM 往返全部浪费在同一个死结上。
    """
    if isinstance(error, _transient_error_types()):
        return True
    status = _http_status(error)
    return status is not None and status in _TRANSIENT_HTTP_STATUS


__all__ = [
    "ApplicationError",
    "InvalidRequestError",
    "ResourceConflictError",
    "ResourceNotFoundError",
    "UpstreamEmptyResponseError",
    "UpstreamRateLimitedError",
    "UpstreamUnavailableError",
    "build_internal_error",
    "is_transient_error",
    "log_internal_error",
]
