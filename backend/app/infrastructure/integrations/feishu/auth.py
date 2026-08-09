"""飞书应用配置校验与租户令牌管理。"""

import hashlib
import time
from collections import OrderedDict
from collections.abc import Callable
from threading import Lock
from typing import Any

from app.configuration.schema import Settings
from app.infrastructure.integrations.feishu.errors import FeishuConfigError

TOKEN_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"

_TOKEN_CACHE_MAXSIZE = 128
_TOKEN_REFRESH_LOCK_COUNT = 16
_token_cache: OrderedDict[tuple[str, str], tuple[str, float]] = OrderedDict()
_token_cache_lock = Lock()
_token_refresh_locks = tuple(Lock() for _ in range(_TOKEN_REFRESH_LOCK_COUNT))


def _token_cache_key(app_id: str, app_secret: str) -> tuple[str, str]:
    secret_fingerprint = hashlib.sha256(app_secret.encode("utf-8")).hexdigest()
    return app_id, secret_fingerprint


def _get_cached_token(cache_key: tuple[str, str]) -> str | None:
    with _token_cache_lock:
        cached = _token_cache.get(cache_key)
        if cached is None:
            return None
        if time.monotonic() >= cached[1]:
            _token_cache.pop(cache_key, None)
            return None
        _token_cache.move_to_end(cache_key)
        return cached[0]


def _cache_token(cache_key: tuple[str, str], token: str, expires_in: float) -> None:
    refresh_margin = min(300.0, expires_in * 0.1)
    expires_at = time.monotonic() + max(0.0, expires_in - refresh_margin)
    with _token_cache_lock:
        _token_cache[cache_key] = (token, expires_at)
        _token_cache.move_to_end(cache_key)
        while len(_token_cache) > _TOKEN_CACHE_MAXSIZE:
            _token_cache.popitem(last=False)


def _token_refresh_lock(cache_key: tuple[str, str]) -> Lock:
    return _token_refresh_locks[hash(cache_key) % len(_token_refresh_locks)]


def clear_token_cache() -> None:
    with _token_cache_lock:
        _token_cache.clear()


class FeishuAuth:
    def __init__(
        self,
        settings_provider: Callable[[], Settings],
        session_provider: Callable[[], Any],
    ) -> None:
        self._settings_provider = settings_provider
        self._session_provider = session_provider

    def validate_settings(self) -> Settings:
        settings = self._settings_provider()
        if not settings.feishu_enabled:
            raise FeishuConfigError("FEISHU_ENABLED must be true to push to Feishu")
        if not settings.feishu_app_id.strip() or not settings.feishu_app_secret.strip():
            raise FeishuConfigError("FEISHU_APP_ID and FEISHU_APP_SECRET are required to push to Feishu")
        return settings

    def get_tenant_token(self) -> str:
        settings = self.validate_settings()
        app_id = settings.feishu_app_id.strip()
        app_secret = settings.feishu_app_secret.strip()
        cache_key = _token_cache_key(app_id, app_secret)
        cached_token = _get_cached_token(cache_key)
        if cached_token is not None:
            return cached_token
        with _token_refresh_lock(cache_key):
            cached_token = _get_cached_token(cache_key)
            if cached_token is not None:
                return cached_token
            response = self._session_provider().post(
                TOKEN_URL,
                json={
                    "app_id": app_id,
                    "app_secret": app_secret,
                },
                timeout=10,
            )
            if response.status_code >= 400:
                raise RuntimeError(f"飞书认证失败: {response.text[:300]}")
            data = response.json()
            if data.get("code", -1) != 0:
                raise RuntimeError(f"飞书认证失败: {data.get('msg', 'unknown error')}")
            token = data["tenant_access_token"]
            _cache_token(cache_key, token, max(0.0, float(data.get("expire", 7200))))
            return token

    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.get_tenant_token()}",
            "Content-Type": "application/json",
        }
