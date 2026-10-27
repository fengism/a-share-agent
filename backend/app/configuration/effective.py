import json
import logging
from typing import Literal, get_args, get_origin

from app.configuration.api_models import PRIVATE_USER_KEYS, SECRET_KEYS
from app.configuration.provider_catalog import PROVIDER_DEFAULTS
from app.configuration.schema import Settings

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
    if get_origin(annotation) is dict or annotation is dict:
        value = json.loads(raw) if isinstance(raw, str) else raw
        if not isinstance(value, dict):
            raise ValueError(f"{key} 必须是 JSON 对象")
        return value
    if get_origin(annotation) is list:
        value = json.loads(raw) if isinstance(raw, str) else raw
        if not isinstance(value, list):
            raise ValueError(f"{key} 必须是数组")
        return [str(item) for item in value]
    if get_origin(annotation) is Literal:
        # 枚举字段必须校验：model_copy(update=...) 不会触发 pydantic 校验，
        # 非法存量值（如手工改库）会静默进入生效配置。
        allowed = get_args(annotation)
        text = raw if isinstance(raw, str) else str(raw)
        if text not in allowed:
            raise ValueError(f"{key} 取值必须是 {allowed} 之一")
        return text
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

    merged: Settings = base.model_copy(update=patch)
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

    # 用户未独立配置个人 API Key 时，**只有端点仍然是管理员那套**才复用管理员 Key。
    #
    # 否则会出现凭据泄漏：普通用户把 llm_base_url 指向自己的服务（或把 provider 换成别家），
    # 而 llm_api_key 仍继承全局值 —— 管理员 Key 就会被发送到用户/第三方指定的地址。
    # 端点不一致时一律要求用户自备 Key（本地 Ollama 这类无需 Key 的服务本来就是空值）。
    if not (patch.get("llm_api_key") or "").strip() and base.llm_api_key:
        if _same_llm_endpoint(merged, base):
            merged.llm_api_key = base.llm_api_key
        else:
            merged.llm_api_key = ""
    if "iwencai_api_key" not in patch and merged.iwencai_base_url != base.iwencai_base_url:
        merged.iwencai_api_key = ""
    return merged


def _same_llm_endpoint(left: Settings, right: Settings) -> bool:
    """两个配置是否指向同一个 LLM 端点（决定能否共用同一个 Key）。"""

    def normalize(value: str) -> str:
        return str(value or "").strip().rstrip("/").lower()

    return (
        normalize(left.llm_base_url) == normalize(right.llm_base_url)
        and str(left.llm_provider or "").strip().lower()
        == str(right.llm_provider or "").strip().lower()
    )


def inherited_private_keys(overrides: dict) -> list[str]:
    """列出该用户仍沿用**全局基线**的私密配置字段。

    用户值为空串/空白或只剩掩码（前端回显的脱敏值）时视为"未配置"，
    即生效值来自管理员（全局）配置——前端据此显示「使用管理员配置」。
    """
    inherited: list[str] = []
    for key in sorted(PRIVATE_USER_KEYS):
        value = overrides.get(key)
        if value is None:
            inherited.append(key)
        elif isinstance(value, str) and not value.strip():
            inherited.append(key)
        elif key in SECRET_KEYS and is_masked_secret(key, value):
            inherited.append(key)
    return inherited


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
