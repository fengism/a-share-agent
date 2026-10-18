from datetime import datetime, timezone
from typing import Any, Callable

import httpx

from app.agentic.tools.application import get_application_tool_handlers
from app.agentic_integration.tools.packs.web.content import smart_truncate
from app.agentic_integration.tools.packs.web.url_security import parse_tweet_url
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider


async def fetch_tweet(
    url: str,
    *,
    truncate_func: Callable[[str], tuple[str, bool]] = smart_truncate,
) -> dict[str, Any]:
    """Fetch a public X/Twitter post through FxTwitter."""
    username, tweet_id = parse_tweet_url(url)
    result: dict[str, Any] = {"url": url, "author": username, "tweet_id": tweet_id}
    try:
        data = await provider_gateway.call(
            "twitter",
            "fetch_tweet",
            lambda: get_provider("twitter").fetch_tweet(username, tweet_id),
        )

        if data.get("code") != 200:
            result["error"] = (
                f"FxTwitter returned code {data.get('code')}: "
                f"{data.get('message', 'Unknown')}"
            )
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

        if tweet.get("quote"):
            quote = tweet["quote"]
            tweet_data["quote"] = {
                "text": quote.get("text", ""),
                "author": quote.get("author", {}).get("name", ""),
                "screen_name": quote.get("author", {}).get("screen_name", ""),
                "likes": quote.get("likes", 0),
                "retweets": quote.get("retweets", 0),
                "views": quote.get("views", 0),
            }
            content = quote.get("text", "")

        article = tweet.get("article")
        if article:
            article_data: dict[str, Any] = {
                "title": article.get("title", ""),
                "preview_text": article.get("preview_text", ""),
                "created_at": article.get("created_at", ""),
            }
            blocks = article.get("content", {}).get("blocks", [])
            if blocks:
                full_text = "\n\n".join(
                    block.get("text", "") for block in blocks if block.get("text", "")
                )
                article_data.update(
                    full_text=full_text,
                    word_count=len(full_text.split()),
                    char_count=len(full_text),
                )
                title = article.get("title", "")
                content = full_text
            tweet_data["article"] = article_data
            tweet_data["is_article"] = True
        else:
            tweet_data["is_article"] = False

        if not title and content:
            title = content[:20]
        truncated_content, was_truncated = truncate_func(content)
        result.update(
            title=title,
            content=truncated_content,
            tweet_data=tweet_data,
            content_type="social",
            content_length=len(content),
            fetched_at=datetime.now(timezone.utc).isoformat(),
        )
        if was_truncated:
            result["note"] = (
                f"内容已截断至 {len(truncated_content)} 字符（原文 {len(content)} 字符）"
            )
    except httpx.HTTPStatusError as error:
        result["error"] = f"HTTP {error.response.status_code}: {error.response.reason_phrase}"
    except Exception as error:
        result["error"] = str(error)
    return result


async def execute_twitter_analyze(username: str) -> str:
    """Analyze the latest posts and long-form articles from one Twitter user."""
    result = await get_application_tool_handlers().analyze_twitter_user(username)
    content_count = result.get("content_count", result.get("article_count", 0))
    sources = result.get("sources", result.get("articles", []))
    if content_count == 0:
        return f"用户 @{username} 暂无可分析的推文或文章。"

    lines = [
        f"## Twitter 用户 @{username} 观点分析",
        "",
        f"共分析 {content_count} 条推文与文章。",
        "",
        "---",
        "",
        "### AI 分析",
        "",
        result["analysis"],
        "",
        "---",
        "",
        f"### 内容摘要（前 {min(content_count, 20)} 条）",
        "",
    ]
    for index, source in enumerate(sources, 1):
        content_preview = (source["content"] or "")[:200]
        lines.extend(
            [
                f"{index}. **{source['title']}** ({source['publish_time']})",
                f"   {content_preview}",
                f"   [{source['url']}]({source['url']})",
                "",
            ]
        )
    return "\n".join(lines)
