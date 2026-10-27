"""运行时事实："该路由的网关不支持原生工具调用"。

为什么不只摘掉 tools 重试一次：Agent 一轮只发一次工具请求，不记忆的话每一轮
都要先吃一次 400，再排队等一次 LLM 槽位——`chat_max_rounds` 轮下来就是几十次
无谓往返。这里按 ``(provider, api_mode, base_url, model)`` 记住事实，让后续请求
直接按"无工具网关"处理（能力位降级 → 工具参数不再发送 → 模型退回正文方言）。

TTL 而不是永久：用户可能升级网关或打开 ``--enable-auto-tool-choice``，半小时后
自动重探；换 model / base_url 自然就是新路由。进程内存储，重启即清零。
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from app.configuration.llm_routing import resolve_llm_routing
from app.configuration.schema import Settings

#: 记忆有效期：够长以覆盖一次会话的全部工具轮，够短以在网关升级后自动重探。
TOOL_SUPPORT_TTL_SECONDS = 1800.0


@dataclass(frozen=True, slots=True)
class ToolSupportRoute:
    """路由维度与 ``LLMClientSpec.key`` 保持一致，避免跨模型误降级。"""

    provider: str
    api_mode: str
    base_url: str
    model: str


_lock = threading.Lock()
_unsupported: dict[ToolSupportRoute, float] = {}


def route_key(
    *, provider: str, api_mode: str, base_url: str, model: str,
) -> ToolSupportRoute:
    return ToolSupportRoute(
        provider=(provider or "").strip().lower(),
        api_mode=(api_mode or "").strip().lower(),
        base_url=(base_url or "").strip(),
        model=(model or "").strip(),
    )


def route_key_for_settings(settings: Settings, *, model: str | None = None) -> ToolSupportRoute:
    routing = resolve_llm_routing(settings)
    return route_key(
        provider=routing.provider,
        api_mode=routing.api_mode,
        base_url=routing.base_url,
        model=routing.model if not model else model,
    )


def mark_tools_unsupported(route: ToolSupportRoute, *, now: float | None = None) -> None:
    timestamp = time.monotonic() if now is None else now
    with _lock:
        _unsupported[route] = timestamp + TOOL_SUPPORT_TTL_SECONDS


def tools_unsupported(route: ToolSupportRoute, *, now: float | None = None) -> bool:
    timestamp = time.monotonic() if now is None else now
    with _lock:
        expires_at = _unsupported.get(route)
        if expires_at is None:
            return False
        if expires_at <= timestamp:
            _unsupported.pop(route, None)
            return False
        return True


def reset_tool_support() -> None:
    """清空记忆（测试与"保存模型配置后重探"用）。"""
    with _lock:
        _unsupported.clear()


__all__ = [
    "TOOL_SUPPORT_TTL_SECONDS",
    "ToolSupportRoute",
    "mark_tools_unsupported",
    "reset_tool_support",
    "route_key",
    "route_key_for_settings",
    "tools_unsupported",
]
