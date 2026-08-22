"""Twitter 市场情报输入选择与内容指纹。"""

import hashlib
import json

TWITTER_ANALYSIS_INPUT_CHAR_BUDGET = 18_000


def select_twitter_content(
    items: list[dict],
    limit: int,
    *,
    char_budget: int = TWITTER_ANALYSIS_INPUT_CHAR_BUDGET,
) -> list[dict]:
    """按新鲜度顺序去重并裁剪到总字符预算。"""
    selected = []
    seen = set()
    used_chars = 0
    for item in items:
        title = str(item.get("title") or "").strip()[:200]
        content = str(item.get("content") or "").strip()
        publish_time = str(item.get("publish_time") or "")[:50]
        url = str(item.get("url") or "").strip()[:500]
        if not title and not content:
            continue
        identity = url or hashlib.sha256(f"{title}\n{content}".encode()).hexdigest()
        if identity in seen:
            continue
        fixed_chars = len(title) + len(publish_time) + len(url)
        available_content_chars = char_budget - used_chars - fixed_chars
        if available_content_chars <= 0:
            break
        content = content[: min(1000, available_content_chars)]
        seen.add(identity)
        selected.append(
            {
                "title": title,
                "content": content,
                "publish_time": publish_time,
                "url": url,
            }
        )
        used_chars += fixed_chars + len(content)
        if len(selected) >= limit:
            break
    return selected


def twitter_content_hash(items: list[dict]) -> str:
    payload = json.dumps(items, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()
