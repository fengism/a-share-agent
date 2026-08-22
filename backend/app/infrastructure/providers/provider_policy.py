from enum import StrEnum

import requests

from app.core.exceptions import UpstreamUnavailableError


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
    if isinstance(exc, (requests.Timeout, TimeoutError)):
        return ProviderErrorCategory.TIMEOUT
    if isinstance(exc, requests.HTTPError):
        status = exc.response.status_code if exc.response is not None else None
        if status == 429:
            return ProviderErrorCategory.RATE_LIMIT
        if status is not None and status >= 500:
            return ProviderErrorCategory.TRANSIENT
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
