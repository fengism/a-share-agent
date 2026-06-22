import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

from openai import AsyncOpenAI, OpenAI

from app.config import Settings, PROVIDER_DEFAULTS, get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OpenAIChatRuntime:
    """OpenAI chat.completions 运行时配置。"""

    client: OpenAI
    model: str


@dataclass(frozen=True)
class AsyncOpenAIChatRuntime:
    """异步 OpenAI chat.completions 运行时配置。"""

    client: AsyncOpenAI
    model: str


class LLMClient(ABC):
    """LLM 客户端抽象基类，定义统一的 chat 接口。"""

    @abstractmethod
    def chat(self, messages: list[dict], temperature: float = 0.1, json_format: bool = False) -> str:
        """调用 LLM 进行对话。

        Param:
            messages: OpenAI 格式的消息列表
            temperature: 生成温度，默认 0.1
            json_format: 是否要求返回 JSON 格式
        Return:
            LLM 生成的文本内容
        """
        ...


class OpenAICompatibleClient(LLMClient):
    """兼容 OpenAI 接口的 LLM 客户端实现，支持 DeepSeek/Qwen/OpenAI/Zhipu 等。"""

    def __init__(self, api_key: str, base_url: str, model: str, timeout: float):
        """初始化 OpenAI 兼容客户端。

        Param:
            api_key: API 密钥
            base_url: API 基础 URL
            model: 模型名称
        Return:
            无
        """
        self.client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)
        self.model = model
        logger.info(f"初始化OpenAI兼容客户端: model={model}, base_url={base_url}")

    def chat(self, messages: list[dict], temperature: float = 0.1, json_format: bool = False) -> str:
        """调用 OpenAI 兼容接口进行对话。

        Param:
            messages: OpenAI 格式的消息列表
            temperature: 生成温度，默认 0.1
            json_format: 是否要求返回 JSON 格式
        Return:
            LLM 生成的文本内容
        """
        logger.info(f"LLM请求: model={self.model}, messages数={len(messages)}, temperature={temperature}")
        try:
            kwargs = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
            }
            if json_format:
                kwargs["response_format"] = {"type": "json_object"}
            resp = self.client.chat.completions.create(**kwargs)
            content = resp.choices[0].message.content
            usage = resp.usage
            prompt_tokens = usage.prompt_tokens if usage else "?"
            completion_tokens = usage.completion_tokens if usage else "?"
            logger.info(f"LLM响应: model={self.model}, tokens={prompt_tokens}/{completion_tokens}")
            return content
        except Exception as e:
            logger.error(f"LLM调用失败: model={self.model}, error={e}", exc_info=True)
            raise


class LiteLLMClient(LLMClient):
    """基于 litellm 的 LLM 客户端实现，用于 Claude 等非 OpenAI 协议模型。"""

    def __init__(self, api_key: str, model: str, base_url: str | None = None, timeout: float = 120.0):
        """初始化 LiteLLM 客户端。

        Param:
            api_key: API 密钥
            model: 模型名称
            base_url: API 基础 URL，可选
        Return:
            无
        """
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.timeout = timeout
        logger.info(f"初始化LiteLLM客户端: model={model}, base_url={base_url}")

    def chat(self, messages: list[dict], temperature: float = 0.1, json_format: bool = False) -> str:
        """通过 litellm 调用 LLM 进行对话。

        Param:
            messages: OpenAI 格式的消息列表
            temperature: 生成温度，默认 0.1
            json_format: 是否要求返回 JSON 格式
        Return:
            LLM 生成的文本内容
        """
        from litellm import completion

        logger.info(f"LiteLLM请求: model={self.model}, messages数={len(messages)}")
        kwargs: dict = {
            "model": self.model,
            "messages": messages,
            "api_key": self.api_key,
            "temperature": temperature,
            "timeout": self.timeout,
        }
        if self.base_url:
            kwargs["api_base"] = self.base_url

        try:
            resp = completion(**kwargs)
            content = resp.choices[0].message.content
            logger.info(f"LiteLLM响应: model={self.model}, 响应长度={len(content)}")
            return content
        except Exception as e:
            logger.error(f"LiteLLM调用失败: model={self.model}, error={e}", exc_info=True)
            raise


_client_cache: LLMClient | None = None
_cache_key: tuple | None = None


def create_llm_client(settings: Settings | None = None) -> LLMClient:
    """根据配置创建对应的 LLM 客户端实例，相同配置下复用单例。

    当 provider/api_key/base_url/model 任一变化时自动重建客户端，
    复用 HTTP 连接池以提升性能。

    Param:
        settings: 配置对象，默认读取全局设置
    Return:
        LLMClient 实例
    """
    global _client_cache, _cache_key

    if settings is None:
        settings = get_settings()

    provider = settings.llm_provider.lower()
    current_key = (provider, settings.llm_api_key, settings.llm_base_url, settings.llm_model)

    if _client_cache is not None and _cache_key == current_key:
        return _client_cache

    logger.info(f"创建LLM客户端: provider={provider}")

    if provider in ("deepseek", "qwen", "openai", "zhipu"):
        defaults = PROVIDER_DEFAULTS.get(provider, {})
        base_url = settings.llm_base_url or defaults.get("base_url", "https://api.openai.com/v1")
        model = settings.llm_model or defaults.get("model", "gpt-4o-mini")
        client = OpenAICompatibleClient(
            api_key=settings.llm_api_key,
            base_url=base_url,
            model=model,
            timeout=float(settings.llm_timeout_seconds),
        )
    elif provider == "claude":
        model = settings.llm_model or "anthropic/claude-sonnet-4-6"
        client = LiteLLMClient(
            api_key=settings.llm_api_key,
            model=model,
            base_url=settings.llm_base_url,
            timeout=float(settings.llm_timeout_seconds),
        )
    else:
        logger.error(f"不支持的LLM提供商: {provider}")
        raise ValueError(f"Unsupported LLM provider: {provider}")

    _client_cache = client
    _cache_key = current_key
    return client


def _resolve_chat_endpoint(settings: Settings | None = None) -> tuple[str, str, str]:
    """解析聊天 chat.completions 运行时所需的 api_key、base_url 和 model。

    Param:
        settings: 配置对象，默认读取全局设置
    Return:
        (api_key, base_url, model) 三元组
    """
    if settings is None:
        settings = get_settings()

    provider = settings.llm_provider.lower()
    defaults = PROVIDER_DEFAULTS.get(provider, {})
    base_url = settings.llm_base_url or defaults.get("base_url", "https://api.openai.com/v1")
    model = settings.llm_model or defaults.get("model", "gpt-4o-mini")
    return settings.llm_api_key, base_url, model


def create_openai_chat_runtime(settings: Settings | None = None) -> OpenAIChatRuntime:
    """创建基于 openai SDK 的 chat.completions 运行时。"""
    api_key, base_url, model = _resolve_chat_endpoint(settings)
    timeout = float(getattr(settings, "llm_timeout_seconds", 120.0)) if settings is not None else 120.0
    client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)
    return OpenAIChatRuntime(client=client, model=model)


def create_async_openai_chat_runtime(settings: Settings | None = None) -> AsyncOpenAIChatRuntime:
    """创建基于 openai SDK 的异步 chat.completions 运行时。

    Param:
        settings: 配置对象，默认读取全局设置
    Return:
        AsyncOpenAIChatRuntime，包含 AsyncOpenAI 客户端和模型名称
    """
    api_key, base_url, model = _resolve_chat_endpoint(settings)
    timeout = float(getattr(settings, "llm_timeout_seconds", 120.0)) if settings is not None else 120.0
    client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=timeout)
    return AsyncOpenAIChatRuntime(client=client, model=model)
