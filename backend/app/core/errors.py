"""Compatibility facade for framework-neutral error helpers."""

from app.domain.errors import (
    build_internal_error as build_internal_error,
)
from app.domain.errors import (
    is_transient_error as is_transient_error,
)
from app.domain.errors import (
    log_internal_error as log_internal_error,
)

__all__ = [
    "build_internal_error",
    "is_transient_error",
    "log_internal_error",
]
