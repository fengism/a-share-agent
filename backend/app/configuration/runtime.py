from __future__ import annotations

import logging
from collections.abc import Callable
from threading import Lock

from app.configuration.crypto_contracts import ConfigEncryptionError
from app.configuration.effective import is_masked_secret, overlay_private
from app.configuration.provider_catalog import PROVIDER_DEFAULTS
from app.configuration.schema import Settings
from app.core.request_context import (
    get_current_user_id,
    get_or_create_effective_settings,
    invalidate_settings_cache,
)

logger = logging.getLogger(__name__)

_current_settings: Settings | None = None
_settings_lock = Lock()
_user_settings_loader: Callable[[int], dict] | None = None


def build_updated_settings(current: Settings, patch: dict) -> Settings:
    """Build a copy-on-write global settings snapshot."""
    old_provider = current.llm_provider.lower()
    old_defaults = PROVIDER_DEFAULTS.get(old_provider, {})
    updated = current.model_copy(deep=True)

    for key, value in patch.items():
        if value is None or not hasattr(current, key) or is_masked_secret(key, value):
            continue
        setattr(updated, key, value)

    new_provider = updated.llm_provider.lower()
    new_defaults = PROVIDER_DEFAULTS.get(new_provider, {})
    if new_provider != old_provider:
        if updated.llm_base_url == old_defaults.get("base_url") and "base_url" in new_defaults:
            updated.llm_base_url = new_defaults["base_url"]
        if updated.llm_model == old_defaults.get("model") and "model" in new_defaults:
            updated.llm_model = new_defaults["model"]
    return updated


def get_settings() -> Settings:
    """获取全局复用的 Settings 实例，首次调用时自动加载配置。"""
    global _current_settings
    if _current_settings is not None:
        return _current_settings
    with _settings_lock:
        if _current_settings is None:
            _current_settings = Settings()
    return _current_settings


def configure_user_settings_loader(loader: Callable[[int], dict]) -> None:
    """配置用户级设置读取器，由应用装配层注入持久化实现。"""
    global _user_settings_loader
    _user_settings_loader = loader
    invalidate_settings_cache()


def effective_settings_for_user(
    user_id: int | None,
    *,
    user_settings_loader: Callable[[int], dict] | None = None,
) -> Settings:
    """返回指定用户的生效配置；user_id 为空时返回全局基线。"""
    base = get_settings()
    if user_id is None:
        return base

    loader = user_settings_loader or _user_settings_loader
    if loader is None:
        return base
    try:
        overrides = loader(user_id)
    except ConfigEncryptionError:
        logger.error("解密用户私密配置失败 user_id=%s", user_id)
        raise
    except Exception:
        logger.warning("加载用户私密配置失败 user_id=%s", user_id, exc_info=True)
        return base
    if not overrides:
        return base
    return overlay_private(base, overrides)


def get_effective_settings(
    *,
    user_settings_loader: Callable[[int], dict] | None = None,
) -> Settings:
    """返回当前请求用户的生效配置，无用户上下文时回退全局基线。"""
    return get_or_create_effective_settings(
        lambda: effective_settings_for_user(
            get_current_user_id(),
            user_settings_loader=user_settings_loader,
        )
    )


def update_settings(patch: dict) -> Settings:
    """更新全局配置快照，支持密钥掩码识别及 provider 自动切换。"""
    global _current_settings
    with _settings_lock:
        if _current_settings is None:
            _current_settings = Settings()
        updated = build_updated_settings(_current_settings, patch)
        _current_settings = updated
    invalidate_settings_cache()
    return updated
