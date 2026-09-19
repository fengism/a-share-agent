import json
import logging
from typing import get_origin

from app.configuration.llm_routing import resolve_llm_routing
from app.configuration.provider_catalog import PROVIDER_DEFAULTS
from app.configuration.schema import PRIVATE_USER_KEYS, SECRET_KEYS, Settings

logger = logging.getLogger(__name__)


def coerce_setting_value(key: str, raw):
    """Convert a stored text value to its Settings field type."""
    field = Settings.model_fields.get(key)
    annotation = field.annotation if field is not None else str
    if annotation is bool:
        if isinstance(raw, bool):
            return raw
        return str(raw).strip().lower() in ("1", "true", "yes", "on")
    if annotation is int:
        return int(raw)
    if annotation is float:
        return float(raw)
    if get_origin(annotation) is list:
        value = json.loads(raw) if isinstance(raw, str) else raw
        if not isinstance(value, list):
            raise ValueError(f"{key} 必须是数组")
        return [str(item) for item in value]
    return raw if isinstance(raw, str) else str(raw)


def overlay_private(base: Settings, overrides: dict) -> Settings:
    """Overlay valid per-user values without mutating the global base."""
    patch: dict = {}
    for key, value in overrides.items():
        if key not in PRIVATE_USER_KEYS:
            continue
        if value is None or (isinstance(value, str) and value == ""):
            continue
        if key in SECRET_KEYS and (is_masked_secret(key, value) or not str(value).strip()):
            continue
        try:
            patch[key] = coerce_setting_value(key, value)
        except (ValueError, TypeError):
            logger.warning("忽略无法解析的用户私密配置项: %s", key)

    if not patch:
        return base

    merged = base.model_copy(update=patch)
    if "llm_provider" in patch and merged.llm_provider.lower() != base.llm_provider.lower():
        defaults = PROVIDER_DEFAULTS.get(str(merged.llm_provider).lower(), {})
        if "llm_base_url" not in patch and defaults.get("base_url"):
            merged.llm_base_url = defaults["base_url"]
        if "llm_model" not in patch and defaults.get("model"):
            merged.llm_model = defaults["model"]
        if "llm_api_mode" not in patch and defaults.get("api_mode"):
            merged.llm_api_mode = defaults["api_mode"]
        if "llm_api_version" not in patch:
            merged.llm_api_version = defaults.get("api_version", "")

    # A global credential may only be inherited for its original destination.
    # Enforce this on reads too, so previously stored unsafe overrides are protected.
    if "llm_api_key" not in patch and (
        resolve_llm_routing(merged).credential_scope != resolve_llm_routing(base).credential_scope
    ):
        merged.llm_api_key = ""
    if "iwencai_api_key" not in patch and merged.iwencai_base_url != base.iwencai_base_url:
        merged.iwencai_api_key = ""
    return merged


def mask_secret(value: str, visible: int = 4) -> str:
    """Mask the middle of a secret while retaining identifying edges."""
    if not value:
        return value
    if len(value) <= visible:
        return "***"
    if len(value) <= 8:
        return value[:visible] + "***"
    return value[:visible] + "***" + value[-visible:]


def is_masked_secret(key: str, value) -> bool:
    return key in SECRET_KEYS and isinstance(value, str) and "***" in value
