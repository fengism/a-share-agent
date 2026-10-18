"""Compatibility facade for framework-neutral application errors."""

from app.domain.errors import (
    ApplicationError as ApplicationError,
)
from app.domain.errors import (
    InvalidRequestError as InvalidRequestError,
)
from app.domain.errors import (
    ResourceConflictError as ResourceConflictError,
)
from app.domain.errors import (
    ResourceNotFoundError as ResourceNotFoundError,
)
from app.domain.errors import (
    UpstreamEmptyResponseError as UpstreamEmptyResponseError,
)
from app.domain.errors import (
    UpstreamRateLimitedError as UpstreamRateLimitedError,
)
from app.domain.errors import (
    UpstreamUnavailableError as UpstreamUnavailableError,
)

__all__ = [
    "ApplicationError",
    "InvalidRequestError",
    "ResourceConflictError",
    "ResourceNotFoundError",
    "UpstreamEmptyResponseError",
    "UpstreamRateLimitedError",
    "UpstreamUnavailableError",
]
