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


__all__ = [
    "ApplicationError",
    "InvalidRequestError",
    "ResourceConflictError",
    "ResourceNotFoundError",
    "UpstreamUnavailableError",
]
