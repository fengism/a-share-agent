import json
from dataclasses import dataclass, field, replace
from typing import Any, cast

from app.configuration.llm_routing import LLMRouting, resolve_llm_routing
from app.configuration.provider_catalog import PROVIDER_DEFAULTS
from app.configuration.schema import Settings
from app.domain.llm import LLMConfigurationError
from app.infrastructure.llm import tool_support
from app.infrastructure.llm.capabilities import LLMCapabilities, capabilities_for_settings, resolve_llm_capabilities


@dataclass(frozen=True)
class LLMClientSpec:
    provider: str
    api_mode: str
    api_key: str = field(repr=False)
    base_url: str = field(repr=False)
    model: str
    api_version: str
    timeout: float
    capabilities: LLMCapabilities | None = None
    #: 厂商私有请求字段（settings.llm_extra_body）；不参与能力判定，只透传到请求体。
    extra_body: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def effective_capabilities(self) -> LLMCapabilities:
        return self.capabilities or resolve_llm_capabilities(
            provider=self.provider, api_mode=self.api_mode, model=self.model,
            base_url=self.base_url, api_version=self.api_version,
        )

    @property
    def key(self) -> tuple[str, str, str, str, str, str, float, LLMCapabilities, str]:
        return (
            self.provider,
            self.api_mode,
            self.api_key,
            self.base_url,
            self.model,
            self.api_version,
            self.timeout,
            self.effective_capabilities,
            # dict 不可哈希：按规范化 JSON 参与池键，改 extra_body 即换新客户端。
            json.dumps(self.extra_body, sort_keys=True, default=str),
        )


def simple_task_enabled(settings: Settings, task: str) -> bool:
    """该任务是否应使用子模型：需配置 ``llm_sub_model``，且任务在启用清单内（清单为空=全部）。"""
    if not settings.llm_sub_model.strip():
        return False
    configured = {
        item.strip()
        for item in settings.llm_simple_tasks.split(",")
        if item.strip()
    }
    return not configured or task in configured


def apply_task_model(settings: Settings, *, simple: bool = False, task: str | None = None) -> Settings:
    """简单/高频任务改用子模型：仅在配置了 ``llm_sub_model`` 时替换 model。

    仅替换 model（provider/base_url/api_key 不变），因此凭证隔离与连接池键
    （键含 model）都能自然生效，无需改动路由/流式链路。
    ``task`` 按 ``llm_simple_tasks`` 白名单判定；``simple`` 用于显式强制。
    """
    if not (simple or (task is not None and simple_task_enabled(settings, task))):
        return settings
    sub_model = settings.llm_sub_model.strip()
    if not sub_model or sub_model == settings.llm_model:
        return settings
    return cast(Settings, settings.model_copy(update={"llm_model": sub_model}))


def task_uses_sub_model(settings: Settings, *, simple: bool = False, task: str | None = None) -> bool:
    """本次调用是否真的会切到子模型（用于失败后是否回退主模型）。"""
    return apply_task_model(settings, simple=simple, task=task) is not settings


def _capabilities_with_runtime_facts(settings: Settings, *, routing: LLMRouting) -> LLMCapabilities:
    """在配置能力之上叠加运行时发现的事实。

    目前只有一条：该路由的网关拒绝过 tools（``tool_support`` 记忆）。降级在这里
    生效而不是写进 ``capabilities``，是因为后者是"配置 → 能力"的纯函数；这样
    工具请求整形、流式判定、子模型回退都自动一致，无需在 Agent 循环里加分支。
    """
    capabilities = capabilities_for_settings(settings)
    route = tool_support.route_key(
        provider=routing.provider,
        api_mode=routing.api_mode,
        base_url=routing.base_url,
        model=routing.model,
    )
    if tool_support.tools_unsupported(route):
        # native_tool_calling=False 会让流式/并行/强指定等高级位在下次解析时
        # 自然派生为 False，这里只需翻倒这一个开关。
        capabilities = replace(capabilities, native_tool_calling=False)
    return capabilities


def _ensure_base_url_allowed(base_url: str, *, allow_private: bool, provider: str) -> None:
    """出网目标校验：拒绝云元数据/链路本地，按开关拒绝私网。

    在 spec 构建处（唯一把 settings 变成 base_url 的咽喉）校验，因此自建/中转/
    官方三条路径共用同一份策略，也不需要在每个客户端工厂里重复。
    """
    if not base_url.strip():
        return
    from app.infrastructure.http.url_guard import describe_blocked_target

    reason = describe_blocked_target(base_url, allow_private=allow_private)
    if reason is not None:
        raise LLMConfigurationError(
            f"{provider} 的 Base URL 被出网策略拒绝：{reason}"
            "（自建服务请改指向本机或内网地址，并确认 LLM_ALLOW_PRIVATE_ENDPOINTS）"
        )


def _shares_global_endpoint(settings: Settings, global_settings: Settings) -> bool:
    """两者是否指向同一个 LLM 端点（凭据实际被发往的地址）。

    只比较解析后的 ``base_url``：Key 是发给这个地址的，provider 标签本身不决定流向。
    同一个 URL 只写法定（大小写/尾斜杠）不同不应触发"不共享"。
    """

    def normalize(value: str) -> str:
        return str(value or "").strip().rstrip("/").lower()

    if settings is global_settings:
        return True
    return normalize(resolve_llm_routing(settings).base_url) == normalize(
        resolve_llm_routing(global_settings).base_url
    )


def resolve_llm_client_spec(settings: Settings) -> LLMClientSpec:
    """Resolve provider defaults and explicit settings into a pool key."""
    routing = resolve_llm_routing(settings)
    provider = routing.provider
    defaults = PROVIDER_DEFAULTS.get(provider, PROVIDER_DEFAULTS["openai"])
    api_mode = routing.api_mode
    if api_mode not in {"openai", "litellm"}:
        raise ValueError(f"Unsupported LLM API mode: {api_mode}")

    api_key = str(getattr(settings, "llm_api_key", "") or "").strip()
    if not api_key:
        from app.configuration import get_settings

        global_settings = get_settings()
        # 只有端点仍是全局那套时才回退复用全局 Key。
        #
        # 否则普通用户把自己配置里的 base_url 指向自建/第三方网关后，管理员 Key 会被
        # 发送到那个地址（凭据泄漏）。这是**唯一**把 settings 变成实际上线请求的咽喉，
        # 所以在此处再兜一层：即便上游（overlay / 存量数据 / 后台任务）漏了，
        # 也不会把全局凭据带到别的端点；缺 Key 时由下面的校验给出明确报错。
        if _shares_global_endpoint(settings, global_settings):
            api_key = str(getattr(global_settings, "llm_api_key", "") or "").strip()
    if not api_key and defaults.get("api_key_required", True):
        label = str(defaults.get("label") or provider)
        raise LLMConfigurationError(
            f"{label} 缺少 API Key，请在设置页填写个人 API Key，或由管理员配置全局 Key"
        )
    if not api_key and not defaults.get("api_key_required", True):
        api_key = "local"
    _ensure_base_url_allowed(routing.base_url, allow_private=bool(
        getattr(settings, "llm_allow_private_endpoints", True)
    ), provider=provider)
    return LLMClientSpec(
        provider=provider,
        api_mode=api_mode,
        api_key=api_key,
        base_url=routing.base_url,
        model=routing.model,
        api_version=routing.api_version,
        timeout=float(getattr(settings, "llm_timeout_seconds", 120.0)),
        capabilities=_capabilities_with_runtime_facts(settings, routing=routing),
        extra_body=dict(getattr(settings, "llm_extra_body", {}) or {}),
    )
