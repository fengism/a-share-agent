from typing import Literal, TypedDict

#: ``Settings.llm_api_mode`` 允许的取值；与 catalog 中的 ``api_mode`` 必须一致。
LLMApiMode = Literal["auto", "openai", "litellm"]


class ProviderDefaults(TypedDict, total=False):
    """LLM provider 目录中单个条目的字段。

    ``total=False``：并非每个 provider 都声明全部字段（目前仅 ``api_version`` 可选）。
    """

    label: str
    description: str
    api_mode: LLMApiMode
    api_key_required: bool
    base_url: str
    model: str
    api_version: str


PROVIDER_DEFAULTS: dict[str, ProviderDefaults] = {
    "deepseek": {
        "label": "DeepSeek",
        "description": "DeepSeek 官方 OpenAI 兼容接口",
        "api_mode": "openai",
        "api_key_required": True,
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-v4-flash",
    },
    "qwen": {
        "label": "通义千问 (Qwen)",
        "description": "阿里云百炼 OpenAI 兼容接口",
        "api_mode": "openai",
        "api_key_required": True,
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
    },
    "openai": {
        "label": "OpenAI",
        "description": "OpenAI 官方 Chat Completions 接口",
        "api_mode": "openai",
        "api_key_required": True,
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
    },
    "zhipu": {
        "label": "智谱 (GLM)",
        "description": "智谱 BigModel OpenAI 兼容接口",
        "api_mode": "openai",
        "api_key_required": True,
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model": "GLM-4.7-Flash",
    },
    "claude": {
        "label": "Claude",
        "description": "Anthropic 原生接口，通过 LiteLLM 适配",
        "api_mode": "litellm",
        "api_key_required": True,
        "base_url": "https://api.anthropic.com",
        "model": "anthropic/claude-sonnet-4-6",
    },
    "gemini": {
        "label": "Google Gemini",
        "description": "Google AI Studio，通过 LiteLLM 适配",
        "api_mode": "litellm",
        "api_key_required": True,
        "base_url": "https://generativelanguage.googleapis.com",
        "model": "gemini/gemini-2.5-flash",
    },
    "moonshot": {
        "label": "Moonshot / Kimi",
        "description": "Moonshot OpenAI 兼容接口",
        "api_mode": "openai",
        "api_key_required": True,
        "base_url": "https://api.moonshot.cn/v1",
        "model": "moonshot-v1-8k",
    },
    "openrouter": {
        "label": "OpenRouter",
        "description": "OpenRouter 多模型 OpenAI 兼容网关",
        "api_mode": "openai",
        "api_key_required": True,
        "base_url": "https://openrouter.ai/api/v1",
        "model": "openai/gpt-4o-mini",
    },
    "siliconflow": {
        "label": "硅基流动",
        "description": "SiliconFlow 多模型 OpenAI 兼容接口",
        "api_mode": "openai",
        "api_key_required": True,
        "base_url": "https://api.siliconflow.cn/v1",
        "model": "Qwen/Qwen2.5-7B-Instruct",
    },
    "ollama": {
        "label": "Ollama（本地）",
        "description": "本地 Ollama OpenAI 兼容接口，无需 API Key",
        "api_mode": "openai",
        "api_key_required": False,
        "base_url": "http://localhost:11434/v1",
        "model": "qwen3:8b",
    },
    "azure": {
        "label": "Azure OpenAI",
        "description": "Azure OpenAI，通过 LiteLLM 适配部署名与 API Version",
        "api_mode": "litellm",
        "api_key_required": True,
        "api_version": "2024-10-21",
        "base_url": "https://YOUR-RESOURCE.openai.azure.com",
        "model": "azure/YOUR_DEPLOYMENT",
    },
    "custom": {
        "label": "自定义 API",
        "description": "自定义 OpenAI 兼容或 LiteLLM 支持的接口",
        "api_mode": "openai",
        "api_key_required": False,
        "base_url": "http://localhost:8000/v1",
        "model": "your-model",
    },
}
