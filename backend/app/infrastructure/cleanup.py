"""Compatibility facade for the shared async cleanup helper."""

from app.domain.async_utils import wait_for_cleanup as wait_for_cleanup

__all__ = ["wait_for_cleanup"]
