from __future__ import annotations

import logging
import re
from typing import Any

from app.services.chat.tools.registry import Tool, registry

logger = logging.getLogger(__name__)

# 移除非内容标签，减少噪音
_REMOVE_TAGS = ("script", "style", "nav", "footer", "header", "aside", "noscript", "iframe")


def _extract_text(html: str) -> str:
    """从 HTML 中提取干净的纯文本内容。

    Param:
        html: 原始 HTML 字符串
    Return:
        去除标签后的纯文本，多余空行已合并
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")

    # 移除非内容标签
    for tag_name in _REMOVE_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    # 提取标题
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()

    # 优先提取 <article> 或 <main> 内容，回退到 body
    main = soup.find("article") or soup.find("main") or soup.find("body")
    if main is None:
        main = soup

    text = main.get_text(separator="\n")

    # 清理：合并连续空行、去除首尾空白
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()

    return title, text


async def _fetch_url(url: str) -> Any:
    """抓取指定 URL 的网页内容并提取纯文本。

    Param:
        url: 要抓取的网页 URL 地址
    Return:
        包含 url、title 和 content 的字典
    """
    from app.utils.http_client import get as http_get

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    resp = http_get(url, headers=headers, timeout=15)
    resp.raise_for_status()

    # 根据响应编码设置
    resp.encoding = resp.apparent_encoding or "utf-8"

    title, content = _extract_text(resp.text)

    # 截断到合理长度，避免超出 LLM 上下文窗口
    max_len = 10000
    truncated = False
    if len(content) > max_len:
        content = content[:max_len]
        truncated = True

    result: dict[str, Any] = {
        "url": url,
        "title": title,
        "content": content,
    }
    if truncated:
        result["note"] = f"内容已截断至 {max_len} 字符，原文更长"

    return result


def register_web_tools() -> None:
    """注册网页相关技能：fetch_url。"""
    registry.register_tool(Tool(
        name="fetch_url",
        description=(
            "抓取指定 URL 的网页内容并提取正文文本。"
            "当用户发送链接/URL、要求阅读网页、总结文章内容时调用。"
            "支持新闻、博客、研报等公开网页。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "要抓取的网页 URL 地址，如 https://finance.sina.com.cn/...",
                },
            },
            "required": ["url"],
        },
        executor=_fetch_url,
    ))
