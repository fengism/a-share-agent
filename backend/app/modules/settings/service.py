import logging
from dataclasses import dataclass
from urllib.parse import urlparse

from app import configuration as config
from app.configuration.effective import is_masked_secret, overlay_private
from app.core.concurrency.rate_limiter import call_blocking, misc_semaphore
from app.core.request_context import invalidate_settings_cache
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

    from app.agentic.agents.catalog import list_agent_profiles
    from app.agentic.bootstrap import register_all_capabilities
    from app.agentic.catalog import registry

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

    # 管理员保存大模型配置时，自动同步至系统全局配置，供后台常驻任务及未独立配置 Key 的用户复用
    if is_admin:
        llm_global_values = {
            key: value for key, value in values_to_store.items()
            if key in config.GLOBAL_LLM_KEYS
        }
        if llm_global_values:
            global_values_to_store.update(llm_global_values)

    if {
        "llm_provider", "llm_api_mode", "llm_api_version", "llm_api_key",
        "llm_base_url", "llm_model",
    } & private_patch.keys():
        overrides = dict(user_config_store.get_user_config(user_id))
        overrides.update(values_to_store)
        candidate = overlay_private(config.get_settings(), overrides)
        resolve_llm_client_spec(candidate)

    if {"outbound_proxy_type", "outbound_proxy_url"} & global_patch.keys():
        candidate_type = global_patch.get(
            "outbound_proxy_type", getattr(config.get_settings(), "outbound_proxy_type", "none")
        )
        candidate_url = global_values_to_store.get(
            "outbound_proxy_url", getattr(config.get_settings(), "outbound_proxy_url", "")
        )
        if candidate_type and candidate_type != "none" and candidate_url:
            from app.infrastructure.http.proxy import normalize_proxy_url
            normalized = normalize_proxy_url(candidate_url, candidate_type)
            if "outbound_proxy_url" in global_values_to_store:
                global_values_to_store["outbound_proxy_url"] = normalized

    if values_to_store:
        user_config_store.set_user_config(user_id, values_to_store)
        invalidate_settings_cache()

    updated_global_settings = None
    if global_values_to_store:
        global_config_store.set_global_config(global_values_to_store)
        updated_global_settings = config.update_settings(global_values_to_store)

    logger.info(
        "Config update by user=%s private=%s global=%s",
        user_id,
        list(private_patch),
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

    url = _models_request_url(base_url, api_version)
    headers = {}
    if api_version:
        headers["api-key"] = api_key
    elif api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    def _default_get():
        return get_session().get(url, headers=headers or None, timeout=15)

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
    except Exception as error:
        raise LlmModelsUnavailableError(f"{type(error).__name__}: {error}") from error
