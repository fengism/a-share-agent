#!/usr/bin/env python3
"""Scrapling 抓取模块：提供 async scrapling_fetch() 供 web_tools 调用，也支持 CLI 直接运行。

依赖安装（可选）：
    uv sync --extra web-fetch
    playwright install chromium && playwright install-deps chromium

Usage (CLI):
    python -m app.services.chat.tools.web_fetch <url> [--mode http|stealth|dynamic]
"""

from __future__ import annotations

import re
import logging
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
    import importlib
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
    import asyncio

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

    return {"url": url, "title": title, "content": text}


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


# ── CLI 入口 ──

def main() -> None:
    """命令行入口：抓取指定 URL 并输出纯文本或 JSON。"""
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(description="Scrapling URL 抓取工具")
    parser.add_argument("url", help="要抓取的 URL")
    parser.add_argument(
        "--mode", choices=["http", "stealth", "dynamic"], default="http",
        help="抓取模式：http（快速）/ stealth（反爬）/ dynamic（JS 渲染）",
    )
    parser.add_argument("--selector", "-s", help="CSS 选择器提取特定元素")
    parser.add_argument("--attr", default="text", help="提取元素的属性（text/html/href 等）")
    parser.add_argument("--json", action="store_true", help="以 JSON 格式输出")
    parser.add_argument("-q", "--quiet", action="store_true", help="静默模式")
    args = parser.parse_args()

    if args.quiet:
        logging.disable(logging.INFO)

    if args.selector:
        # 选择器模式：直接同步获取 page 对象
        try:
            fetcher_cls = _get_fetcher(args.mode)
            page = fetcher_cls.get(args.url) if args.mode == "http" \
                else fetcher_cls.fetch(args.url, headless=True, network_idle=True)
        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(1)

        elements = page.css(args.selector)
        if not elements:
            print(f"未匹配到元素: {args.selector}", file=sys.stderr)
            sys.exit(1)

        results = []
        for el in elements:
            if args.attr == "text":
                val = el.text or el.get_all_text()
            elif args.attr == "html":
                val = el.html_content
            else:
                val = el.attrib.get(args.attr, "")
            results.append(val.strip())

        if args.json:
            print(json.dumps(results, ensure_ascii=False, indent=2))
        else:
            print("\n".join(r for r in results if r))
    else:
        # 纯文本模式：使用 async API
        import asyncio
        result = asyncio.run(scrapling_fetch(args.url, args.mode))

        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif result.get("error"):
            print(f"ERROR: {result['error']}", file=sys.stderr)
            sys.exit(1)
        else:
            print(result.get("content", ""))


if __name__ == "__main__":
    main()
