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


class UpstreamEmptyResponseError(UpstreamUnavailableError):
    """上游返回了成功响应，但内容不可用（空体、被限流后返回空 K 线等）。

    必须与永久失败区分开：腾讯等接口被按 IP 限流时，HTTP 仍是 200、body 却只剩
    ``v_sh600519="";``。若按 ValueError 归入 permanent，ProviderCircuitBreaker 会
    在 record_failure 里直接重置计数（``provider_circuit.record_failure`` 对非
    retryable 错误走 ``circuits[key] = CircuitState()``），熔断器永远打不开，
    上游持续空返回时每个请求都要白跑一遍完整降级链。
    """

    default_code = "upstream_empty_response"


__all__ = [
    "ApplicationError",
    "InvalidRequestError",
    "ResourceConflictError",
    "ResourceNotFoundError",
    "UpstreamEmptyResponseError",
    "UpstreamRateLimitedError",
    "UpstreamUnavailableError",
]
