"""单元测试：LLM 客户端抽象层（强制覆盖 .env 环境变量）。"""
import os

import pytest

from app.config import Settings
from app.services.llm.client import (
    _resolve_chat_endpoint,
)


class TestResolveChatEndpoint:
    """_resolve_chat_endpoint 的默认值解析测试"""

    # 保存原始环境变量，测试时隔离
    _ENV_OVERRIDES = {
        "llm_provider": "",
        "llm_api_key": "",
        "llm_base_url": "",
        "llm_model": "",
    }

    def _make_settings(self, **kwargs):
        """创建 Settings 实例，用环境变量覆盖确保不受 .env 影响。"""
        env_patch = {
            "llm_provider": "",
            "llm_api_key": "",
            "llm_base_url": "",
            "llm_model": "",
        }
        env_patch.update(kwargs)
        return Settings(**env_patch)

    def test_default_deepseek(self):
        settings = self._make_settings(llm_provider="deepseek", llm_api_key="sk-test")
        api_key, base_url, model = _resolve_chat_endpoint(settings)
        assert api_key == "sk-test"
        assert base_url == "https://api.deepseek.com"
        assert model == "deepseek-v4-flash"

    def test_default_qwen(self):
        settings = self._make_settings(llm_provider="qwen", llm_api_key="sk-test")
        api_key, base_url, model = _resolve_chat_endpoint(settings)
        assert base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"
        assert model == "qwen-plus"

    def test_default_openai(self):
        settings = self._make_settings(llm_provider="openai", llm_api_key="sk-test")
        api_key, base_url, model = _resolve_chat_endpoint(settings)
        assert base_url == "https://api.openai.com/v1"
        assert model == "gpt-4o-mini"

    def test_default_zhipu(self):
        settings = self._make_settings(llm_provider="zhipu", llm_api_key="sk-test")
        api_key, base_url, model = _resolve_chat_endpoint(settings)
        assert base_url == "https://open.bigmodel.cn/api/paas/v4"
        assert model == "GLM-4.7-Flash"

    def test_custom_overrides_all_defaults(self):
        """自定义 base_url 和 model 应覆盖 provider 默认值。"""
        settings = self._make_settings(
            llm_provider="deepseek",
            llm_api_key="sk-test",
            llm_base_url="https://custom.example.com/v1",
            llm_model="custom-model",
        )
        api_key, base_url, model = _resolve_chat_endpoint(settings)
        assert base_url == "https://custom.example.com/v1"
        assert model == "custom-model"

    def test_unknown_provider_falls_back(self):
        """未知 provider 使用 OpenAI 默认值。"""
        settings = self._make_settings(llm_provider="unknown", llm_api_key="sk-test")
        api_key, base_url, model = _resolve_chat_endpoint(settings)
        assert base_url == "https://api.openai.com/v1"
        assert model == "gpt-4o-mini"


class TestProviderDefaults:
    """验证 PROVIDER_DEFAULTS 配置正确。"""

    def test_all_providers_have_keys(self):
        from app.config import PROVIDER_DEFAULTS
        for name, cfg in PROVIDER_DEFAULTS.items():
            assert "base_url" in cfg, f"{name} missing base_url"
            assert "model" in cfg, f"{name} missing model"
            assert cfg["base_url"], f"{name} has empty base_url"
            assert cfg["model"], f"{name} has empty model"
