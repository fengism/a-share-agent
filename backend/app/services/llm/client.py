import logging
from abc import ABC, abstractmethod

from openai import OpenAI

from app.config import Settings, PROVIDER_DEFAULTS, get_settings

logger = logging.getLogger(__name__)


class LLMClient(ABC):
    @abstractmethod
    def chat(self, messages: list[dict], temperature: float = 0.1, json_format: bool = False) -> str:
        ...


class OpenAICompatibleClient(LLMClient):
    def __init__(self, api_key: str, base_url: str, model: str):
        self.client = OpenAI(api_key=api_key, base_url=base_url, timeout=45.0)
        self.model = model
        logger.info(f"初始化OpenAI兼容客户端: model={model}, base_url={base_url}")

    def chat(self, messages: list[dict], temperature: float = 0.1, json_format: bool = False) -> str:
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
            logger.info(f"LLM响应: model={self.model}, tokens={usage.prompt_tokens}/{usage.completion_tokens if usage else '?'}")
            return content
        except Exception as e:
            logger.error(f"LLM调用失败: model={self.model}, error={e}", exc_info=True)
            raise


class LiteLLMClient(LLMClient):
    def __init__(self, api_key: str, model: str, base_url: str | None = None):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        logger.info(f"初始化LiteLLM客户端: model={model}, base_url={base_url}")

    def chat(self, messages: list[dict], temperature: float = 0.1, json_format: bool = False) -> str:
        from litellm import completion

        logger.info(f"LiteLLM请求: model={self.model}, messages数={len(messages)}")
        kwargs: dict = {
            "model": self.model,
            "messages": messages,
            "api_key": self.api_key,
            "temperature": temperature,
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


def create_llm_client(settings: Settings | None = None) -> LLMClient:
    if settings is None:
        settings = get_settings()

    provider = settings.llm_provider.lower()
    logger.info(f"创建LLM客户端: provider={provider}")

    if provider in ("deepseek", "qwen", "openai", "zhipu"):
        defaults = PROVIDER_DEFAULTS.get(provider, {})
        base_url = settings.llm_base_url or defaults.get("base_url", "https://api.openai.com/v1")
        model = settings.llm_model or defaults.get("model", "gpt-4o-mini")
        return OpenAICompatibleClient(
            api_key=settings.llm_api_key,
            base_url=base_url,
            model=model,
        )
    elif provider == "claude":
        model = settings.llm_model or "anthropic/claude-sonnet-4-6"
        return LiteLLMClient(
            api_key=settings.llm_api_key,
            model=model,
            base_url=settings.llm_base_url,
        )
    else:
        logger.error(f"不支持的LLM提供商: {provider}")
        raise ValueError(f"Unsupported LLM provider: {provider}")
