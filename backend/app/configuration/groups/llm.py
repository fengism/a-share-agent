"""大模型（LLM）配置分组。"""

from __future__ import annotations

from typing import Any

from pydantic import Field, field_validator

from app.configuration.groups.base import ConfigGroup
from app.configuration.llm_compatibility import (
    LLMCompatibilityOverride,
    validate_extra_body,
)
from app.configuration.provider_catalog import LLMApiMode


class LLMGroup(ConfigGroup):
    """LLM 路由、凭据、生成预算与兼容性开关。"""

    PREFIX = "llm_"

    llm_provider: str = "zhipu"
    llm_api_mode: LLMApiMode = "auto"
    llm_api_version: str = ""
    llm_api_key: str = ""
    llm_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    # 是否允许 LLM Base URL 指向 RFC1918/IPv6 ULA 内网地址（默认关闭）。
    # ``llm_base_url`` 是任何登录用户可写的字段，放开等于把服务器变成内网探测器。
    # 回环（127.0.0.1/::1）始终允许，因此本机 Ollama 无需开启；
    # 同机 docker 服务名（解析到 172.x）或内网网关才需要设为 true。
    # 云元数据与链路本地网段（169.254/16、100.64/10）无论此开关如何都拦截。
    llm_allow_private_endpoints: bool = False
    llm_model: str = "GLM-4.7-Flash"
    # 简单/高频任务（如逐条资讯解读）使用的子模型；留空则复用主模型。
    # 与主模型共用 provider/base_url/api_key，仅替换 model，避免子任务超时。
    llm_sub_model: str = ""
    # 允许使用子模型的任务清单（逗号分隔）；留空=全部已接入的任务。
    # 可选值：chat_routing / macro_item / news_analysis / twitter_analysis
    llm_simple_tasks: str = ""
    llm_temperature: float = 0.1
    # 模型上下文长度（tokens）；0 表示未设置，历史裁剪沿用默认 40k 字符预算。
    llm_context_length_tokens: int = Field(default=0, ge=0)
    llm_timeout_seconds: int = Field(default=300, gt=0)
    # Deployment policy; current provider/model is never changed by these limits.
    llm_generation_timeout_seconds: float = Field(default=1200.0, gt=0)
    llm_generation_max_completion_tokens: int = Field(default=8192, ge=1)
    llm_max_attempts: int = Field(default=2, ge=1, le=3)
    llm_model_max_completion_tokens: int | None = Field(default=None, ge=1)
    llm_stream_include_usage: bool = True
    llm_json_mode_enabled: bool = True
    llm_compatibility_overrides: list[LLMCompatibilityOverride] = Field(default_factory=list, repr=False)
    # 厂商私有请求字段（如 Qwen enable_thinking / GLM thinking）；受治理字段会被拒绝。
    llm_extra_body: dict[str, Any] = Field(default_factory=dict)

    @field_validator("llm_extra_body")
    @classmethod
    def validate_extra_body_field(cls, value: Any) -> dict[str, Any]:
        return validate_extra_body(value)
