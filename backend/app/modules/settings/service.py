import logging
from dataclasses import dataclass
from urllib.parse import urlparse

from app import configuration as config
from app.configuration.effective import is_masked_secret, overlay_private
from app.configuration.provider_catalog import PROVIDER_DEFAULTS
from app.core.concurrency.rate_limiter import call_blocking, misc_semaphore
from app.core.request_context import invalidate_settings_cache
from app.domain.llm import LLMConfigurationError
from app.infrastructure.llm.spec import resolve_llm_client_spec
from app.infrastructure.persistence import global_config_store, user_config_store
from app.modules.settings.schemas import LlmModelsRequest

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SettingsUpdateResult:
    settings: config.Settings
    global_settings: config.Settings | None
    global_patch: dict


class GlobalSettingsPermissionError(Exception):
    def __init__(self, fields: list[str]):
        self.fields = tuple(sorted(fields))
        super().__init__(", ".join(self.fields))


class UnknownChatCapabilityError(Exception):
    def __init__(self, names: list[str]):
        self.names = tuple(sorted(names))
        super().__init__(", ".join(self.names))


def _normalize_chat_capability_preferences(patch: dict) -> dict:
    if not {"disabled_chat_skills", "disabled_chat_agents"} & patch.keys():
        return patch

    from app.agentic.catalog import registry
    from app.agentic_integration.agents.catalog import list_agent_profiles
    from app.agentic_integration.bootstrap import register_all_capabilities

    register_all_capabilities()
    known_names = {
        "disabled_chat_skills": [skill.name for skill in registry.list_skills()],
        "disabled_chat_agents": [profile.name for profile in list_agent_profiles()],
    }
    normalized = dict(patch)
    unknown: list[str] = []
    for field, catalog_names in known_names.items():
        if field not in patch:
            continue
        requested = set(patch[field])
        unknown.extend(sorted(requested - set(catalog_names)))
        normalized[field] = [name for name in catalog_names if name in requested]
    if unknown:
        raise UnknownChatCapabilityError(unknown)
    return normalized


def get_inherited_private_keys(user_id: int) -> list[str]:
    """该用户仍沿用全局基线的私密配置字段（其余为个人覆盖）。"""
    return config.inherited_private_keys(user_config_store.get_user_config(user_id))


def get_user_settings(user_id: int) -> config.Settings:
    return config.effective_settings_for_user(
        user_id,
        user_settings_loader=user_config_store.get_user_config,
    )


def update_user_settings(
    user_id: int,
    is_admin: bool,
    patch: dict,
) -> SettingsUpdateResult:
    if not patch:
        return SettingsUpdateResult(
            settings=get_user_settings(user_id),
            global_settings=None,
            global_patch={},
        )

    patch = _normalize_chat_capability_preferences(patch)

    private_patch = {key: value for key, value in patch.items() if key in config.PRIVATE_USER_KEYS}
    global_patch = {key: value for key, value in patch.items() if key in config.PERSISTED_GLOBAL_KEYS}
    if global_patch and not is_admin:
        raise GlobalSettingsPermissionError(list(global_patch))

    values_to_store = {key: value for key, value in private_patch.items() if not is_masked_secret(key, value)}
    global_values_to_store = {key: value for key, value in global_patch.items() if not is_masked_secret(key, value)}

    # 显式传空串的私密字段 = "清空个人覆盖"（前端「改用管理员配置」走这条路）。
    #
    # 直接删行而不是写空串：`overlay_private` 本来就跳过空值，两种写法生效结果相同，
    # 但删行不会留下永远读不到的死数据，也避免"看着清掉了其实还留着一行"的困惑。
    # 掩码值（前端回显的脱敏串）依然忽略，不会被误删。
    cleared_keys = [
        key
        for key, value in values_to_store.items()
        if isinstance(value, str) and not value.strip()
    ]
    for key in cleared_keys:
        values_to_store.pop(key, None)

    # 管理员保存大模型/推送通道配置时，自动同步至系统全局配置，
    # 供后台常驻任务及未独立配置 Key 的用户复用
    if is_admin:
        llm_global_values = {
            key: value for key, value in values_to_store.items()
            if key in config.GLOBAL_SYNCED_KEYS
        }
        if llm_global_values:
            global_values_to_store.update(llm_global_values)

    # 简化约束：普通用户若修改大模型端点或凭据，必须同时设置 Base URL 与 API Key；
    # 不能只设置 key 而沿用管理员 url，也不能只改 url 而不设 key。
    # 仅修改温度（llm_temperature）、模型（llm_model）等其他字段不受此限。
    if not is_admin:
        has_new_key = bool((values_to_store.get("llm_api_key") or "").strip())
        has_new_url = bool((values_to_store.get("llm_base_url") or "").strip())
        is_clearing_llm = "llm_api_key" in cleared_keys and "llm_base_url" in cleared_keys

        if not is_clearing_llm:
            if has_new_key and not has_new_url:
                current_user_cfg = user_config_store.get_user_config(user_id)
                if not (current_user_cfg.get("llm_base_url") or "").strip():
                    raise LLMConfigurationError("不能只设置 API Key，自定义端点需同时配置 Base URL 与 API Key")
            if has_new_url and not has_new_key:
                provider = values_to_store.get("llm_provider") or config.get_settings().llm_provider
                provider_def = PROVIDER_DEFAULTS.get(str(provider).lower(), {})
                if provider_def.get("api_key_required", True):
                    current_user_cfg = user_config_store.get_user_config(user_id)
                    if not (current_user_cfg.get("llm_api_key") or "").strip():
                        raise LLMConfigurationError("不能只修改 Base URL，自定义端点需同时配置 Base URL 与 API Key")

    if {
        "llm_provider", "llm_api_mode", "llm_api_version", "llm_api_key",
        "llm_base_url", "llm_model",
    } & private_patch.keys():
        overrides = dict(user_config_store.get_user_config(user_id))
        overrides.update(values_to_store)
        candidate = overlay_private(config.get_settings(), overrides)
        resolve_llm_client_spec(candidate)

    if {"outbound_proxy_type", "outbound_proxy_url"} & global_patch.keys():
        current_network = config.get_settings().network
        candidate_type = global_patch.get("outbound_proxy_type", current_network.outbound_proxy_type)
        candidate_url = global_values_to_store.get(
            "outbound_proxy_url", current_network.outbound_proxy_url
        )
        if candidate_type and candidate_type != "none" and candidate_url:
            from app.infrastructure.http.proxy import normalize_proxy_url
            normalized = normalize_proxy_url(candidate_url, candidate_type)
            if "outbound_proxy_url" in global_values_to_store:
                global_values_to_store["outbound_proxy_url"] = normalized

    if cleared_keys:
        user_config_store.delete_user_config_keys(user_id, cleared_keys)

    if values_to_store:
        user_config_store.set_user_config(user_id, values_to_store)
        invalidate_settings_cache()

    updated_global_settings = None
    if global_values_to_store:
        global_config_store.set_global_config(global_values_to_store)
        updated_global_settings = config.update_settings(global_values_to_store)

    logger.info(
        "Config update by user=%s private=%s cleared=%s global=%s",
        user_id,
        list(private_patch),
        cleared_keys,
        list(global_values_to_store),
    )
    return SettingsUpdateResult(
        settings=get_user_settings(user_id),
        global_settings=updated_global_settings,
        global_patch=global_values_to_store,
    )


class LlmModelsUnavailableError(RuntimeError):
    """模型列表拉取失败（网络、鉴权或响应格式）。"""


def _models_request_url(base_url: str, api_version: str) -> str:
    base = base_url.strip().rstrip("/")
    url = f"{base}/models"
    if api_version:
        url = f"{url}?api-version={api_version}"
    return url


async def fetch_llm_models(
    user_id: int,
    payload: "LlmModelsRequest",
    *,
    settings_provider=None,
    blocking_runner=call_blocking,
    http_get=None,
) -> list[str]:
    """用 Base URL + API Key 拉取 OpenAI 兼容模型列表。

    请求中留空或为掩码值的字段回退到该用户已保存的模型配置；http_get 可注入便于测试。
    """
    from app.infrastructure.http.client import get_session

    settings = (settings_provider or get_user_settings)(user_id)
    base_url = (payload.base_url or "").strip() or settings.llm_base_url.strip()
    api_key = (payload.api_key or "").strip()
    if not api_key or is_masked_secret("llm_api_key", api_key):
        api_key = settings.llm_api_key.strip()
    api_version = (payload.api_version or "").strip() or settings.llm_api_version.strip()

    if not base_url:
        raise LlmModelsUnavailableError("请先填写 Base URL")
    parsed = urlparse(base_url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise LlmModelsUnavailableError("Base URL 必须是有效的 HTTP/HTTPS 地址")
    # 出网策略：这条路径会带着用户的 API Key 请求用户自填的地址，是最直接的 SSRF 面。
    from app.infrastructure.http.url_guard import (
        MAX_REDIRECT_HOPS,
        OutboundUrlBlockedError,
        describe_blocked_target,
        resolve_redirect_target,
    )

    allow_private = bool(getattr(config.get_settings(), "llm_allow_private_endpoints", False))
    blocked = describe_blocked_target(base_url, allow_private=allow_private)
    if blocked is not None:
        raise LlmModelsUnavailableError(f"Base URL 被出网策略拒绝：{blocked}")

    url = _models_request_url(base_url, api_version)
    headers = {}
    if api_version:
        headers["api-key"] = api_key
    elif api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    def _default_get():
        # 逐跳校验重定向：requests 默认跟随 3xx，否则公网地址可以用 302 把服务端
        # 引到元数据/内网地址，绕过上面的第一跳校验。
        target = url
        response = get_session().get(
            target, headers=headers or None, timeout=15, allow_redirects=False
        )
        hops = 0
        while response.is_redirect and hops < MAX_REDIRECT_HOPS:
            location = response.headers.get("Location") or response.headers.get("location") or ""
            target = resolve_redirect_target(target, location, allow_private=allow_private)
            hops += 1
            response = get_session().get(
                target, headers=headers or None, timeout=15, allow_redirects=False
            )
        return response

    def _parse(response) -> list[str]:
        if response.status_code >= 400:
            raise LlmModelsUnavailableError(f"上游返回 {response.status_code}：{response.text[:200]}")
        try:
            body = response.json()
        except ValueError as exc:
            raise LlmModelsUnavailableError("上游响应不是有效 JSON") from exc
        items = body.get("data") if isinstance(body, dict) else None
        if items is None and isinstance(body, dict):
            items = body.get("models")
        if not isinstance(items, list):
            raise LlmModelsUnavailableError("上游响应缺少模型列表")
        models = []
        for item in items:
            model_id = item.get("id") or item.get("model") if isinstance(item, dict) else item
            if isinstance(model_id, str) and model_id.strip():
                models.append(model_id.strip())
        return sorted(set(models))

    getter = http_get or _default_get
    try:
        response = await blocking_runner(getter, semaphore=misc_semaphore)
        return await blocking_runner(lambda: _parse(response), semaphore=misc_semaphore)
    except LlmModelsUnavailableError:
        raise
    except OutboundUrlBlockedError as error:
        raise LlmModelsUnavailableError(f"Base URL 被出网策略拒绝：{error.reason}") from error
    except Exception as error:
        raise LlmModelsUnavailableError(f"{type(error).__name__}: {error}") from error
