from enum import StrEnum

import httpx
import requests
from curl_cffi.requests import exceptions as curl_errors

from app.core.exceptions import (
    UpstreamEmptyResponseError,
    UpstreamRateLimitedError,
    UpstreamUnavailableError,
)


class ProviderErrorCategory(StrEnum):
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    TRANSIENT = "transient"
    PERMANENT = "permanent"
    CIRCUIT_OPEN = "circuit_open"


class ProviderCircuitOpenError(UpstreamUnavailableError):
    pass


def classify_provider_error(exc: Exception) -> ProviderErrorCategory:
    if isinstance(exc, ProviderCircuitOpenError):
        return ProviderErrorCategory.CIRCUIT_OPEN
    if isinstance(exc, UpstreamRateLimitedError):
        # 上游明确按频率拒绝，等待退避后重试可恢复。
        return ProviderErrorCategory.RATE_LIMIT
    if isinstance(exc, UpstreamEmptyResponseError):
        # 成功响应但内容不可用：按 IP 限流时上游常返回 200 + 空体。归为瞬时故障，
        # 熔断器才会计数并在持续空返回时打开，而不是每次都重跑整条降级链。
        return ProviderErrorCategory.TRANSIENT
    if isinstance(exc, (requests.Timeout, httpx.TimeoutException, curl_errors.Timeout, TimeoutError)):
        return ProviderErrorCategory.TIMEOUT
    if isinstance(exc, (requests.HTTPError, httpx.HTTPStatusError, curl_errors.HTTPError)):
        status = exc.response.status_code if exc.response is not None else None
        if status == 429:
            return ProviderErrorCategory.RATE_LIMIT
        if status is not None and status >= 500:
            return ProviderErrorCategory.TRANSIENT
        return ProviderErrorCategory.PERMANENT
    if isinstance(exc, (httpx.UnsupportedProtocol, httpx.LocalProtocolError, curl_errors.CertificateVerifyError)):
        return ProviderErrorCategory.PERMANENT
    if isinstance(exc, (httpx.TransportError, curl_errors.ConnectionError, curl_errors.ProxyError)):
        return ProviderErrorCategory.TRANSIENT
    # curl_cffi 的所有请求异常都继承 OSError，配置/URL/证书错误不能被兜底误判为瞬时故障。
    if isinstance(exc, curl_errors.RequestException):
        return ProviderErrorCategory.PERMANENT
    if isinstance(exc, (requests.ConnectionError, ConnectionError, OSError)):
        return ProviderErrorCategory.TRANSIENT
    return ProviderErrorCategory.PERMANENT


def is_retryable(category: ProviderErrorCategory) -> bool:
    return category in {
        ProviderErrorCategory.TIMEOUT,
        ProviderErrorCategory.RATE_LIMIT,
        ProviderErrorCategory.TRANSIENT,
    }
