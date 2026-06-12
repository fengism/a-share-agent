from __future__ import annotations

import asyncio
import ipaddress
import logging
import re
import json
import socket
from typing import Any
from urllib.parse import urlparse
import urllib.request
import urllib.error


from app.services.chat.tools.registry import Tool, registry

logger = logging.getLogger(__name__)

# 移除非内容标签，减少噪音
_REMOVE_TAGS = ("script", "style", "nav", "footer", "header", "aside", "noscript", "iframe")


class UnsafeUrlError(ValueError):
    """URL 指向私网/环回/元数据地址等不安全目标时抛出。"""


def _assert_url_safe(url: str) -> None:
    """校验 URL：仅允许 http/https 且目标主机不解析到私网/环回/元数据地址（SSRF 防护）。

    Param:
        url: 待抓取的 URL
    Return:
        无返回；不安全时抛出 UnsafeUrlError
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise UnsafeUrlError(f"仅支持 http/https，拒绝 scheme={parsed.scheme!r}")

    host = parsed.hostname
    if not host:
        raise UnsafeUrlError("URL 缺少主机名")

    # 解析主机名到所有 IP，逐一校验，避免 DNS 指向内网或云元数据地址
    try:
        addr_infos = socket.getaddrinfo(host, None)
    except socket.gaierror as e:
        raise UnsafeUrlError(f"主机名解析失败: {host}") from e

    for info in addr_infos:
        ip_str = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local      # 含 169.254.169.254 云元数据
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise UnsafeUrlError(f"拒绝访问内网/保留地址: {host} -> {ip_str}")


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

    优先使用 requests 快速抓取；若内容过少（疑似 JS 渲染页面）则自动降级到 Scrapling。

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

    if is_twitter_url(url):
        return await asyncio.to_thread(_fetch_tweet, url)

    try:
        _assert_url_safe(url)
    except UnsafeUrlError as e:
        logger.warning("拒绝抓取不安全 URL %s: %s", url, e)
        return {"url": url, "title": "", "content": "", "error": str(e)}

    # 阶段一：requests 快速抓取
    try:
        resp = http_get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"
        title, content = _extract_text(resp.text)
    except Exception as e:
        logger.info("requests 抓取失败 (%s)，尝试 Scrapling 降级: %s", url, e)
        return await _scrapling_fallback(url)

    # 阶段二：内容过少时降级到 Scrapling（JS 渲染页面）
    from app.services.chat.tools.web_fetch import needs_fallback
    if needs_fallback(content):
        logger.info("内容过少 (%d 字)，尝试 Scrapling 降级: %s", len(content), url)
        return await _scrapling_fallback(url)

    # 截断到合理长度，避免超出 LLM 上下文窗口
    max_len = 10000
    truncated = False
    if len(content) > max_len:
        content = content[:max_len]
        truncated = True

    result: dict[str, Any] = {
        "url": url,
        "author": "",
        "title": title,
        "content": content,
    }
    if truncated:
        result["note"] = f"内容已截断至 {max_len} 字符，原文更长"

    return result


async def _scrapling_fallback(url: str) -> dict[str, Any]:
    """使用 Scrapling 降级抓取，依次尝试 http → stealth → dynamic 模式。

    Param:
        url: 要抓取的 URL
    Return:
        包含 url、title、content 的字典
    """
    from app.services.chat.tools.web_fetch import scrapling_fetch, needs_fallback

    for mode in ("http", "stealth", "dynamic"):
        result = await scrapling_fetch(url, mode)
        if result.get("error"):
            logger.info("Scrapling %s 模式失败: %s", mode, result["error"])
            continue
        content = result.get("content", "")
        if not needs_fallback(content):
            # 成功获取到足够内容
            max_len = 10000
            if len(content) > max_len:
                result["content"] = content[:max_len]
                result["note"] = f"内容已截断至 {max_len} 字符，原文更长"
            return result

    # 所有模式都失败
    return {
        "url": url,
        "title": "",
        "content": "",
        "error": "所有抓取模式均失败，请检查 URL 是否有效",
    }


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


def is_twitter_url(url: str) -> bool:
    """判断 URL 是否为 X/Twitter 链接（按主机名匹配 x.com / twitter.com）。

    Param:
        url: 待判断的 URL
    Return:
        True 表示是 X/Twitter 链接
    """
    host = (urlparse(url).hostname or "").lower()
    return host == "x.com" or host == "twitter.com" or host.endswith(".x.com") or host.endswith(".twitter.com")


def parse_tweet_url(url: str) -> tuple:
    """Extract username and tweet_id from X/Twitter URL."""
    patterns = [
        r'(?:x\.com|twitter\.com)/(\w+)/status/(\d+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1), match.group(2)
    raise ValueError(f"Cannot parse tweet URL: {url}")


def _fetch_tweet(url: str) -> dict[str, Any]:
    """Fetch tweet text, stats, quotes, and full article content via FxTwitter API."""
    username, tweet_id = parse_tweet_url(url)
    result = {"url": url, "author": username, "tweet_id": tweet_id}

    api_url = f"https://api.fxtwitter.com/{username}/status/{tweet_id}"
    try:
        req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())

        if data.get("code") != 200:
            result["error"] = f"FxTwitter returned code {data.get('code')}: {data.get('message', 'Unknown')}"
            return result

        tweet = data["tweet"]
        title = ""
        content = tweet.get("text", "")
        tweet_data = {
            "text": tweet.get("text", ""),
            "author": tweet.get("author", {}).get("name", ""),
            "screen_name": tweet.get("author", {}).get("screen_name", ""),
            "likes": tweet.get("likes", 0),
            "retweets": tweet.get("retweets", 0),
            "bookmarks": tweet.get("bookmarks", 0),
            "views": tweet.get("views", 0),
            "replies_count": tweet.get("replies", 0),
            "created_at": tweet.get("created_at", ""),
            "is_note_tweet": tweet.get("is_note_tweet", False),
            "lang": tweet.get("lang", ""),
        }
    
        # Include quote tweet if present
        if tweet.get("quote"):
            qt = tweet["quote"]
            tweet_data["quote"] = {
                "text": qt.get("text", ""),
                "author": qt.get("author", {}).get("name", ""),
                "screen_name": qt.get("author", {}).get("screen_name", ""),
                "likes": qt.get("likes", 0),
                "retweets": qt.get("retweets", 0),
                "views": qt.get("views", 0),
            }
            content = qt.get("text", "")

        # Extract X Article (long-form content) if present
        article = tweet.get("article")
        if article:
            article_data = {
                "title": article.get("title", ""),
                "preview_text": article.get("preview_text", ""),
                "created_at": article.get("created_at", ""),
            }
            content = article.get("content", {})
            blocks = content.get("blocks", [])
            if blocks:
                full_text = "\n\n".join(
                    b.get("text", "") for b in blocks if b.get("text", "")
                )
                article_data["full_text"] = full_text
                article_data["word_count"] = len(full_text.split())
                article_data["char_count"] = len(full_text)
                title = article.get("title", "")
                content = full_text
            tweet_data["article"] = article_data
            tweet_data["is_article"] = True
        else:
            tweet_data["is_article"] = False
        
        if title == "" and content != "":
            title = content[0:20]
        result["title"] = title
        result["content"] = content
  
    except urllib.error.HTTPError as e:
        result["error"] = f"HTTP {e.code}: {e.reason}"
    except Exception as e:
        result["error"] = str(e)

    

    return result