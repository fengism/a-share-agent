"""Twitter 分析领域结果到 API 结果的转换。"""

from datetime import datetime, timezone


def render_twitter_analysis_markdown(analysis: dict) -> str:
    lines = ["## 核心结论", "", analysis["summary"] or "暂无明确结论"]
    if analysis["core_views"]:
        lines.extend(["", "## 核心观点", ""])
        for view in analysis["core_views"]:
            references = " ".join(f"[{reference['index']}]" for reference in view["references"])
            suffix = f"（{view['stance']}，置信度 {view['confidence']}%）"
            lines.append(f"- {view['text']}{suffix} {references}".rstrip())
    if analysis["sectors"] or analysis["stocks"]:
        lines.extend(["", "## 关注方向", ""])
        if analysis["sectors"]:
            lines.append("- 板块：" + "、".join(analysis["sectors"]))
        if analysis["stocks"]:
            lines.append("- 公司：" + "、".join(analysis["stocks"]))
    if analysis["risks"]:
        lines.extend(["", "## 风险提示", ""])
        lines.extend(f"- {risk}" for risk in analysis["risks"])
    return "\n".join(lines)


def build_twitter_analysis_result(username: str, sources: list[dict], analysis: dict) -> dict:
    return {
        "username": username,
        "content_count": len(sources),
        "sources": sources,
        "article_count": len(sources),
        "articles": sources,
        "analysis": render_twitter_analysis_markdown(analysis),
        **analysis,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "cache_hit": False,
    }


def build_empty_twitter_analysis_result(username: str) -> dict:
    return {
        "username": username,
        "content_count": 0,
        "sources": [],
        "article_count": 0,
        "articles": [],
        "analysis": f"用户 @{username} 暂无可分析的推文或文章。",
        "summary": "暂无可分析的推文或文章",
        "stance": "中性",
        "confidence": 0,
        "core_views": [],
        "sectors": [],
        "stocks": [],
        "risks": [],
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "cache_hit": False,
    }


def mark_twitter_analysis_cache_hit(cached: dict) -> dict:
    result = dict(cached)
    sources = result.get("sources") or result.get("articles") or []
    content_count = result.get("content_count", result.get("article_count", len(sources)))
    result.update(
        {
            "content_count": content_count,
            "sources": sources,
            "article_count": content_count,
            "articles": sources,
            "cache_hit": True,
        }
    )
    result.setdefault("summary", "")
    result.setdefault("stance", "中性")
    result.setdefault("confidence", 0)
    result.setdefault("core_views", [])
    result.setdefault("sectors", [])
    result.setdefault("stocks", [])
    result.setdefault("risks", [])
    result.setdefault("generated_at", "")
    return result
