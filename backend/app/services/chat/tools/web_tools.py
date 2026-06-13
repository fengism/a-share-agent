"""网页抓取工具：fetch_url / fetch_urls。

支持：
- SSRF 安全校验
- HTML→Markdown 结构化提取
- Meta 信息（OG / description / published_time）提取
- JS 渲染页面自动降级到 Scrapling
- X/Twitter 推文/FxTwitter API 抓取
- PDF 内容类型检测
- URL 结果 TTL 缓存
- 失败重试（指数退避）
- 智能截断（段落/句子边界）
- 批量并发抓取（fetch_urls）
"""

from __future__ import annotations

import asyncio
import logging
import random
import re
from datetime import datetime, timezone
from typing import Any

import httpx
from bs4 import BeautifulSoup, NavigableString, Tag

from app.services.chat.tools.registry import Tool, registry
from app.utils.cache import TTLCache
from app.utils.url_utils import USER_AGENTS, UnsafeUrlError, assert_url_safe, is_twitter_url, parse_tweet_url

logger = logging.getLogger(__name__)

# ── 常量 ──

_MAX_CONTENT_LEN = 10000
_FETCH_CACHE_TTL = 600  # 10 分钟缓存
_MAX_RETRIES = 2
_RETRY_BACKOFF = [1.0, 2.0]  # 指数退避秒数
_RETRY_STATUS_CODES = {500, 502, 503, 504}

# 移除非内容标签，减少噪音
_REMOVE_TAGS = ("script", "style", "nav", "footer", "header", "aside", "noscript", "iframe")

# URL 结果缓存
_fetch_cache = TTLCache()


# ── HTML → Markdown 转换 ──

def _html_to_markdown(element: Tag | BeautifulSoup) -> str:
    """将 BeautifulSoup 元素树转换为轻量级 Markdown 文本。

    处理：标题(h1-h6)、段落、列表(ul/ol)、链接、加粗、斜体、
    表格、引用块、图片(alt)、代码块、水平线。

    Param:
        element: BeautifulSoup Tag 或整个 soup 对象
    Return:
        Markdown 格式的文本
    """
    def _walk(node: Tag | NavigableString) -> str:
        if isinstance(node, NavigableString):
            text = str(node)
            return text if text.strip() else ""

        if not isinstance(node, Tag):
            return ""

        tag = node.name

        # 跳过移除标签
        if tag in _REMOVE_TAGS:
            return ""

        # 标题
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(tag[1])
            inner = _inline_text(node).strip()
            return f"\n\n{'#' * level} {inner}\n\n" if inner else ""

        # 段落
        if tag == "p":
            inner = _inline_text(node).strip()
            return f"\n\n{inner}\n\n" if inner else ""

        # 换行
        if tag == "br":
            return "\n"

        # 加粗
        if tag in ("strong", "b"):
            inner = _inline_text(node).strip()
            return f"**{inner}**" if inner else ""

        # 斜体
        if tag in ("em", "i"):
            inner = _inline_text(node).strip()
            return f"*{inner}*" if inner else ""

        # 行内代码
        if tag == "code" and not (node.parent and node.parent.name == "pre"):
            text = node.get_text()
            return f"`{text}`" if text else ""

        # 代码块
        if tag == "pre":
            code_el = node.find("code")
            text = code_el.get_text() if code_el else node.get_text()
            return f"\n\n```\n{text}\n```\n\n"

        # 链接
        if tag == "a":
            href = node.get("href", "")
            inner = _inline_text(node).strip()
            if inner and href and not href.startswith("#") and not href.startswith("javascript"):
                return f"[{inner}]({href})"
            return inner

        # 图片 → 只保留 alt 文本
        if tag == "img":
            alt = node.get("alt", "").strip()
            return f"[图片: {alt}]" if alt else ""

        # 引用块
        if tag == "blockquote":
            inner = _walk_children(node).strip()
            if inner:
                quoted = "\n".join(f"> {line}" for line in inner.split("\n"))
                return f"\n\n{quoted}\n\n"
            return ""

        # 水平线
        if tag == "hr":
            return "\n\n---\n\n"

        # 无序列表
        if tag == "ul":
            items = []
            for li in node.find_all("li", recursive=False):
                inner = _walk_children(li).strip()
                if inner:
                    items.append(f"- {inner}")
            return "\n\n" + "\n".join(items) + "\n\n" if items else ""

        # 有序列表
        if tag == "ol":
            items = []
            for i, li in enumerate(node.find_all("li", recursive=False), 1):
                inner = _walk_children(li).strip()
                if inner:
                    items.append(f"{i}. {inner}")
            return "\n\n" + "\n".join(items) + "\n\n" if items else ""

        # 表格
        if tag == "table":
            return _table_to_markdown(node)

        # 其他块级元素：递归子节点
        return _walk_children(node)

    def _inline_text(node: Tag) -> str:
        """提取行内文本，保留加粗/斜体等格式。"""
        parts = []
        for child in node.children:
            if isinstance(child, NavigableString):
                parts.append(str(child))
            elif isinstance(child, Tag):
                tag = child.name
                if tag in ("strong", "b"):
                    inner = _inline_text(child)
                    parts.append(f"**{inner}**" if inner else "")
                elif tag in ("em", "i"):
                    inner = _inline_text(child)
                    parts.append(f"*{inner}*" if inner else "")
                elif tag == "code":
                    text = child.get_text()
                    parts.append(f"`{text}`" if text else "")
                elif tag == "a":
                    href = child.get("href", "")
                    inner = _inline_text(child).strip()
                    if inner and href and not href.startswith("#") and not href.startswith("javascript"):
                        parts.append(f"[{inner}]({href})")
                    else:
                        parts.append(inner)
                elif tag == "br":
                    parts.append("\n")
                elif tag == "img":
                    alt = child.get("alt", "").strip()
                    if alt:
                        parts.append(f"[图片: {alt}]")
                else:
                    parts.append(_inline_text(child))
        return "".join(parts)

    def _walk_children(node: Tag) -> str:
        return "".join(_walk(child) for child in node.children)

    def _table_to_markdown(table: Tag) -> str:
        """将 HTML 表格转为 Markdown 表格。"""
        rows: list[list[str]] = []
        for tr in table.find_all("tr"):
            cells = []
            for cell in tr.find_all(["th", "td"]):
                cells.append(_inline_text(cell).strip().replace("|", "\\|"))
            rows.append(cells)

        if not rows:
            return ""

        # 确保所有行列数一致
        max_cols = max(len(r) for r in rows)
        for r in rows:
            while len(r) < max_cols:
                r.append("")

        lines = []
        # 表头
        lines.append("| " + " | ".join(rows[0]) + " |")
        lines.append("| " + " | ".join(["---"] * max_cols) + " |")
        # 数据行
        for row in rows[1:]:
            lines.append("| " + " | ".join(row) + " |")
        return "\n\n" + "\n".join(lines) + "\n\n"

    result = "".join(_walk(child) for child in element.children)
    return result


# ── Meta 信息提取 ──

def _extract_meta(soup: BeautifulSoup) -> dict[str, str]:
    """从 HTML <head> 中提取有价值的 meta 信息。

    提取：og:title, og:description, og:image, article:published_time,
    article:author, meta description, meta keywords, canonical。

    Param:
        soup: BeautifulSoup 解析后的文档
    Return:
        键值对字典，仅包含非空值
    """
    meta: dict[str, str] = {}

    def _get_meta_content(property_name: str) -> str:
        """按 property 或 name 属性查找 <meta> 标签的 content。"""
        el = soup.find("meta", attrs={"property": property_name}) or soup.find(
            "meta", attrs={"name": property_name}
        )
        if el and el.get("content"):
            return el["content"].strip()
        return ""

    # Open Graph
    for key in ("og:title", "og:description", "og:image"):
        val = _get_meta_content(key)
        if val:
            meta[key] = val

    # 文章信息
    for key in ("article:published_time", "article:author", "article:section"):
        val = _get_meta_content(key)
        if val:
            meta[key] = val

    # 常规 meta
    desc = _get_meta_content("description")
    if desc:
        meta["description"] = desc
    keywords = _get_meta_content("keywords")
    if keywords:
        meta["keywords"] = keywords

    # Canonical URL
    canonical = soup.find("link", attrs={"rel": "canonical"})
    if canonical and canonical.get("href"):
        meta["canonical_url"] = canonical["href"].strip()

    return meta


# ── 文本提取（增强版） ──

def _extract_text(html: str) -> tuple[dict[str, str], str]:
    """从 HTML 中提取结构化 Markdown 文本和 meta 信息。

    优先提取 <article> 或 <main> 内容，回退到 <body>。
    输出为 Markdown 格式，保留标题层级、列表、加粗等结构。

    Param:
        html: 原始 HTML 字符串
    Return:
        (meta_dict, markdown_text) 元组
    """
    soup = BeautifulSoup(html, "html.parser")

    # 提取 meta 信息
    meta = _extract_meta(soup)

    # 移除非内容标签
    for tag_name in _REMOVE_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    # 提取标题
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    if not title and meta.get("og:title"):
        title = meta["og:title"]

    # 优先提取 <article> 或 <main> 内容，回退到 body
    main = soup.find("article") or soup.find("main") or soup.find("body")
    if main is None:
        main = soup

    # 转换为 Markdown
    text = _html_to_markdown(main)

    # 合并连续空行
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()

    return meta, (title, text)


# ── 智能截断 ──

def _smart_truncate(text: str, max_len: int = _MAX_CONTENT_LEN) -> tuple[str, bool]:
    """智能截断文本到指定长度，在段落或句子边界处截断。

    优先在段落边界（\\n\\n）截断；其次在句子边界（！？。!?.）截断。
    截断后返回 (truncated_text, was_truncated)。

    Param:
        text: 待截断的文本
        max_len: 最大长度，默认 _MAX_CONTENT_LEN
    Return:
        (截断后的文本, 是否发生了截断) 元组
    """
    if len(text) <= max_len:
        return text, False

    # 在 max_len 附近寻找段落边界（向前搜索最多 500 字符）
    search_start = max(0, max_len - 500)
    chunk = text[search_start:max_len]

    # 尝试段落边界
    last_para = chunk.rfind("\n\n")
    if last_para > 0:
        cut = search_start + last_para
        return text[:cut].rstrip(), True

    # 尝试句子边界
    last_sent = -1
    for sep in ("！", "。", "？", "!", ".", "?", "\n"):
        pos = chunk.rfind(sep)
        if pos > last_sent:
            last_sent = pos

    if last_sent > 0:
        cut = search_start + last_sent + 1
        return text[:cut].rstrip(), True

    return text[:max_len], True


# ── 重试机制 ──

async def _http_get_with_retry(url: str, headers: dict, timeout: int = 15) -> httpx.Response:
    """带重试的 HTTP GET 请求，对 5xx/超时错误自动重试。

    同步 requests 调用通过 asyncio.to_thread 卸载到线程池，退避使用
    asyncio.sleep 避免阻塞事件循环。

    Param:
        url: 目标 URL
        headers: 请求头
        timeout: 请求超时秒数
    Return:
        httpx.Response 对象
    Raises:
        httpx.HTTPError: 重试耗尽后仍失败
    """
    from app.utils.http_client import get as http_get

    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            resp = await asyncio.to_thread(http_get, url, headers=headers, timeout=timeout)
            # 对 5xx 响应重试
            if resp.status_code in _RETRY_STATUS_CODES and attempt < _MAX_RETRIES:
                logger.info(
                    "HTTP %d 响应，重试 %d/%d: %s",
                    resp.status_code, attempt + 1, _MAX_RETRIES, url,
                )
                await asyncio.sleep(_RETRY_BACKOFF[min(attempt, len(_RETRY_BACKOFF) - 1)])
                continue
            resp.raise_for_status()
            return resp
        except Exception as e:
            last_exc = e
            if attempt < _MAX_RETRIES:
                logger.info(
                    "请求失败 (%s)，重试 %d/%d: %s",
                    type(e).__name__, attempt + 1, _MAX_RETRIES, url,
                )
                await asyncio.sleep(_RETRY_BACKOFF[min(attempt, len(_RETRY_BACKOFF) - 1)])
                continue
    raise last_exc  # type: ignore[misc]


# ── 内容类型检测 ──

def _detect_content_type(content_type_header: str | None) -> str:
    """根据 Content-Type 头检测内容类型。

    Param:
        content_type_header: HTTP 响应的 Content-Type 头值
    Return:
        内容类型字符串：html / pdf / json / xml / text / unknown
    """
    if not content_type_header:
        return "unknown"
    ct = content_type_header.split(";")[0].strip().lower()
    if "html" in ct:
        return "html"
    if "pdf" in ct:
        return "pdf"
    if "json" in ct:
        return "json"
    if "xml" in ct:
        return "xml"
    return "text"


def _handle_pdf_response(resp: Any, url: str) -> dict[str, Any]:
    """处理 PDF 类型的 HTTP 响应，尝试提取前几页文本。

    优先尝试 pdfplumber，回退到 PyPDF2，最终返回提示信息。

    Param:
        resp: HTTP 响应对象（content 为 PDF 二进制）
        url: 原始 URL
    Return:
        包含 url、title、content 的结果字典
    """
    pdf_bytes = resp.content
    text = ""

    # 尝试 pdfplumber
    try:
        import io
        import pdfplumber
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            pages_text = []
            for i, page in enumerate(pdf.pages):
                if i >= 5:  # 最多读取前 5 页
                    break
                page_text = page.extract_text()
                if page_text:
                    pages_text.append(page_text)
            text = "\n\n".join(pages_text)
    except ImportError:
        pass
    except Exception as e:
        logger.info("pdfplumber 提取失败: %s", e)

    # 回退到 PyPDF2
    if not text:
        try:
            import io
            from PyPDF2 import PdfReader
            reader = PdfReader(io.BytesIO(pdf_bytes))
            pages_text = []
            for i, page in enumerate(reader.pages):
                if i >= 5:
                    break
                page_text = page.extract_text()
                if page_text:
                    pages_text.append(page_text)
            text = "\n\n".join(pages_text)
        except ImportError:
            pass
        except Exception as e:
            logger.info("PyPDF2 提取失败: %s", e)

    if text:
        title = text[:60].split("\n")[0].strip() if text else ""
        return {
            "url": url,
            "title": title,
            "content": text,
            "content_type": "pdf",
        }

    return {
        "url": url,
        "title": "",
        "content": f"[PDF 文档，共 {len(pdf_bytes)} 字节。无法直接提取文本内容，请下载后阅读。]",
        "content_type": "pdf",
    }


# ── 核心抓取 ──

async def _fetch_url(url: str) -> dict[str, Any]:
    """抓取指定 URL 的网页内容并提取正文文本（Markdown 格式）。

    流程：缓存命中 → SSRF 校验 → http_get 重试 → 内容类型检测
    → PDF 处理 / HTML 提取 → 内容过少则降级 Scrapling → 智能截断。

    Param:
        url: 要抓取的网页 URL 地址
    Return:
        包含 url、title、content、meta 等信息的字典
    """
    # 缓存命中
    cached = _fetch_cache.get(f"fetch:{url}")
    if cached is not None:
        return cached

    # Twitter 特殊路径
    if is_twitter_url(url):
        return await _fetch_tweet(url)

    # SSRF 校验
    try:
        assert_url_safe(url)
    except UnsafeUrlError as e:
        logger.warning("拒绝抓取不安全 URL %s: %s", url, e)
        return {"url": url, "title": "", "content": "", "error": str(e)}

    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    # 阶段一：http_get 重试抓取
    try:
        resp = _http_get_with_retry(url, headers=headers, timeout=15)
        content_type = _detect_content_type(resp.headers.get("content-type"))
        resp.encoding = resp.apparent_encoding or "utf-8"

        # PDF 处理
        if content_type == "pdf":
            result = _handle_pdf_response(resp, url)
            _fetch_cache.set(f"fetch:{url}", result, _FETCH_CACHE_TTL)
            return result

        # HTML/文本处理
        meta, (title, content) = _extract_text(resp.text)

    except Exception as e:
        logger.info("http_get 抓取失败 (%s)，尝试 Scrapling 降级: %s", url, e)
        return await _scrapling_fallback(url)

    # 阶段二：内容过少时降级到 Scrapling（JS 渲染页面）
    from app.services.chat.tools.web_fetch import needs_fallback
    if needs_fallback(content):
        logger.info("内容过少 (%d 字)，尝试 Scrapling 降级: %s", len(content), url)
        return await _scrapling_fallback(url)

    # 智能截断
    truncated_content, was_truncated = _smart_truncate(content)

    now = datetime.now(timezone.utc).isoformat()
    result: dict[str, Any] = {
        "url": url,
        "title": title,
        "content": truncated_content,
        "content_type": content_type,
        "content_length": len(content),
        "fetched_at": now,
    }
    if meta:
        result["meta"] = meta
    if was_truncated:
        result["note"] = f"内容已截断至 {len(truncated_content)} 字符（原文 {len(content)} 字符）"

    _fetch_cache.set(f"fetch:{url}", result, _FETCH_CACHE_TTL)
    return result


async def _scrapling_fallback(url: str) -> dict[str, Any]:
    """使用 Scrapling 降级抓取，依次尝试 http → stealth → dynamic 模式。

    Param:
        url: 要抓取的 URL
    Return:
        包含 url、title、content 的字典
    """
    from app.services.chat.tools.web_fetch import needs_fallback, scrapling_fetch

    for mode in ("http", "stealth", "dynamic"):
        result = await scrapling_fetch(url, mode)
        if result.get("error"):
            logger.info("Scrapling %s 模式失败: %s", mode, result["error"])
            continue
        content = result.get("content", "")
        if not needs_fallback(content):
            truncated_content, was_truncated = _smart_truncate(content)
            result["content"] = truncated_content
            result["content_type"] = "html"
            result["content_length"] = len(content)
            result["fetched_at"] = datetime.now(timezone.utc).isoformat()
            if was_truncated:
                result["note"] = f"内容已截断至 {len(truncated_content)} 字符（原文 {len(content)} 字符）"
            _fetch_cache.set(f"fetch:{url}", result, _FETCH_CACHE_TTL)
            return result

    # 所有模式都失败
    return {
        "url": url,
        "title": "",
        "content": "",
        "error": "所有抓取模式均失败，请检查 URL 是否有效",
    }


# ── 批量抓取 ──

async def _fetch_urls(urls: list[str]) -> list[dict[str, Any]]:
    """并发抓取多个 URL，返回结果列表。

    每个 URL 独立处理，单个失败不影响其他。
    结果顺序与输入 urls 顺序一致。

    Param:
        urls: 要抓取的 URL 列表（最多 10 个）
    Return:
        结果字典列表，每个包含 url、title、content 等字段
    """
    if not urls:
        return []
    # 限制并发数，避免资源耗尽
    limited = urls[:10]
    return list(await asyncio.gather(*[_fetch_url(u) for u in limited]))


# ── Twitter 抓取（async） ──

async def _fetch_tweet(url: str) -> dict[str, Any]:
    """异步抓取 X/Twitter 推文，通过 FxTwitter API 获取文本、统计数据和完整文章内容。

    Param:
        url: X/Twitter 推文链接
    Return:
        包含 url、author、tweet_id、title、content 等信息的字典
    """
    username, tweet_id = parse_tweet_url(url)
    result: dict[str, Any] = {"url": url, "author": username, "tweet_id": tweet_id}

    api_url = f"https://api.fxtwitter.com/{username}/status/{tweet_id}"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(api_url, headers={"User-Agent": random.choice(USER_AGENTS)})
            resp.raise_for_status()
            data = resp.json()

        if data.get("code") != 200:
            result["error"] = f"FxTwitter returned code {data.get('code')}: {data.get('message', 'Unknown')}"
            return result

        tweet = data["tweet"]
        title = ""
        content = tweet.get("text", "")
        tweet_data: dict[str, Any] = {
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
            article_data: dict[str, Any] = {
                "title": article.get("title", ""),
                "preview_text": article.get("preview_text", ""),
                "created_at": article.get("created_at", ""),
            }
            article_content = article.get("content", {})
            blocks = article_content.get("blocks", [])
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

        if not title and content:
            title = content[:20]

        # 智能截断
        truncated_content, was_truncated = _smart_truncate(content)

        result["title"] = title
        result["content"] = truncated_content
        result["tweet_data"] = tweet_data
        result["content_type"] = "social"
        result["content_length"] = len(content)
        result["fetched_at"] = datetime.now(timezone.utc).isoformat()
        if was_truncated:
            result["note"] = f"内容已截断至 {len(truncated_content)} 字符（原文 {len(content)} 字符）"

    except httpx.HTTPStatusError as e:
        result["error"] = f"HTTP {e.response.status_code}: {e.response.reason_phrase}"
    except Exception as e:
        result["error"] = str(e)

    return result


# ── 工具注册 ──

def register_web_tools() -> None:
    """注册网页相关工具：fetch_url、fetch_urls。"""
    registry.register_tool(Tool(
        name="fetch_url",
        description=(
            "抓取指定 URL 的网页内容并提取正文文本（Markdown 格式）。"
            "当用户发送链接/URL、要求阅读网页、总结文章内容时调用。"
            "支持新闻、博客、研报（PDF）、X/Twitter 推文等公开网页。"
            "返回内容包含 meta 信息（标题、描述、发布时间）和结构化正文。"
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

    registry.register_tool(Tool(
        name="fetch_urls",
        description=(
            "批量并发抓取多个 URL 的网页内容并提取正文文本。"
            "当用户要求同时查看多篇文章、对比多个网页内容时调用。"
            "最多支持 10 个 URL。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "urls": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "要抓取的 URL 列表，如 [\"https://...\", \"https://...\"]",
                },
            },
            "required": ["urls"],
        },
        executor=_fetch_urls,
    ))
