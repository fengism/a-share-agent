"""Framework-neutral application errors."""


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
    """上游按请求频率拒绝服务，等待后重试通常可以恢复。

    与永久失败区分开，才能让 ProviderGateway 按瞬时故障退避重试。
    """

    default_code = "upstream_rate_limited"


__all__ = [
    "ApplicationError",
    "InvalidRequestError",
    "ResourceConflictError",
    "ResourceNotFoundError",
    "UpstreamRateLimitedError",
    "UpstreamUnavailableError",
]
