"""Compatibility exports; search adapters live in the provider layer."""

from app.infrastructure.providers.web_search import (
    BaiduSearchNoApi,
    BaseNoApiKeySearchEngine,
    BingCnSearchNoAPI,
    GoogleSearchNoAPI,
    So360SearchNoApi,
)

__all__ = [
    "BaiduSearchNoApi",
    "BaseNoApiKeySearchEngine",
    "BingCnSearchNoAPI",
    "GoogleSearchNoAPI",
    "So360SearchNoApi",
]
