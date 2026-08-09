"""Scrapling 抓取适配器：为 Web Fetch 提供受控降级。

依赖安装（可选）：
    uv sync --extra web-fetch
    playwright install chromium && playwright install-deps chromium
"""

from __future__ import annotations

import asyncio
import importlib
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_MIN_CONTENT_LEN = 200  # 低于此长度视为 JS 渲染页面，需降级

# ── Fetcher 模式映射（避免重复 import 逻辑） ──

_FETCHER_MAP: dict[str, tuple[str, str]] = {
    "http":     ("scrapling.fetchers", "Fetcher"),
    "stealth":  ("scrapling.fetchers", "StealthyFetcher"),
    "dynamic":  ("scrapling.fetchers", "DynamicFetcher"),
}


def _get_fetcher(mode: str):
    """根据模式名称懒加载对应的 Scrapling Fetcher 类。"""
    module_path, class_name = _FETCHER_MAP.get(mode, _FETCHER_MAP["http"])
    mod = importlib.import_module(module_path)
    return getattr(mod, class_name)


# ── 公开 API ──

async def scrapling_fetch(url: str, mode: str = "http") -> dict[str, Any]:
    """使用 Scrapling 抓取网页并提取纯文本。

    Param:
        url: 要抓取的 URL
        mode: 抓取模式 — http（快速）/ stealth（反爬）/ dynamic（JS 渲染）
    Return:
        包含 url、title、content 的字典；失败时含 error 字段
    """
    def _sync():
        fetcher_cls = _get_fetcher(mode)
        if mode == "http":
            return fetcher_cls.get(url)
        return fetcher_cls.fetch(url, headless=True, network_idle=True)

    try:
        page = await asyncio.to_thread(_sync)
    except Exception as e:
        logger.warning("Scrapling %s 抓取失败: %s", mode, e)
        return {"url": url, "error": f"Scrapling ({mode}) 抓取失败: {e}"}

    text = _clean_text(
        page.get_all_text(" ", ignore_tags=("script", "style", "noscript"))
    )

    title = ""
    if hasattr(page, "css"):
        title_els = page.css("title")
        if title_els:
            title = (title_els[0].text or "").strip()

    final_url = str(getattr(page, "url", "") or url)
    return {"url": final_url, "title": title, "content": text}


def needs_fallback(content: str) -> bool:
    """判断 basic HTTP 抓取的内容是否需要 Scrapling 降级。

    Param:
        content: basic HTTP 抓取到的正文内容
    Return:
        True 表示内容过少，建议降级
    """
    return len(content) < _MIN_CONTENT_LEN


# ── 内部工具 ──

def _clean_text(text: str) -> str:
    """清理文本：合并连续空行、去除首尾空白。"""
    return re.sub(r"\n{3,}", "\n\n", text).strip()
