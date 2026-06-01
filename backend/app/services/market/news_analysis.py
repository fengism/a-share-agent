import hashlib
import json
import logging

from app.config import get_settings
from app.services.llm.client import create_llm_client
from app.services.market.news import get_market_feed
from app.utils.cache import cache, dated_cache_key

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一位资深市场分析师。你需要分析一组市场资讯，提炼出对投资决策有价值的关键信息。

## 输出要求
返回严格的 JSON 对象，包含以下字段：

{
  "market_sentiment": "偏多 或 中性 或 偏空",
  "summary": "用 2-3 句话总结当前市场核心要点",
  "sections": [
    {"title": "板块名称", "icon": "emoji", "items": ["要点1", "要点2"]}
  ]
}

## 分类维度
根据资讯内容，灵活组织 sections，常见的有：
- 宏观政策（🏦）：央行、财政、监管等政策动向
- 行业热点（🔥）：板块异动、题材发酵、技术突破
- 资金动向（💰）：北向资金、融资融券、大宗交易
- 公司动态（📊）：业绩预告、重组并购、高管变动
- 风险提示（⚠️）：制裁、退市、暴雷、监管处罚
- 海外影响（🌍）：美联储、地缘政治、全球市场

## 原则
- 每个 section 的 items 控制在 2-5 条，每条不超过 30 字
- 只提取有明确市场影响的信息，忽略噪音
- 基于资讯事实判断，不做无依据推测
- 只输出 JSON，不要输出其他内容"""


def _get(item, key: str, default="") -> str:
    """兼容 Pydantic 模型和 dict"""
    if hasattr(item, key):
        return getattr(item, key, default) or default
    if isinstance(item, dict):
        return item.get(key, default) or default
    return default


def _build_prompt(items) -> str:
    lines = []
    for i, item in enumerate(items[:80], 1):
        source = _get(item, "source")
        title = _get(item, "title")
        content = _get(item, "content")[:100]
        time_str = _get(item, "publish_time")
        lines.append(f"[{i}] [{source}] {time_str} | {title} — {content}")
    return f"以下是最近的市场资讯（共 {min(len(items), 80)} 条），请分析归类：\n\n" + "\n".join(lines)


def _fallback_analysis(items) -> dict:
    """LLM 失败时的兜底分析"""
    source_counts = {}
    for item in items:
        src = _get(item, "source") or "未知"
        source_counts[src] = source_counts.get(src, 0) + 1

    return {
        "market_sentiment": "中性",
        "summary": f"共聚合 {len(items)} 条资讯，来自 {len(source_counts)} 个渠道。AI 分析暂时不可用，请查看右侧资讯详情。",
        "sections": [
            {
                "title": "数据来源分布",
                "icon": "📰",
                "items": [f"{src}: {cnt} 条" for src, cnt in sorted(source_counts.items(), key=lambda x: -x[1])],
            }
        ],
    }


async def analyze_market_news() -> dict:
    items = await get_market_feed()
    if not items:
        return _fallback_analysis([])

    # 用标题生成内容指纹，只有资讯变化时才重新调用 LLM
    top_titles = [_get(item, "title") for item in items[:80]]
    content_hash = hashlib.md5("\n".join(top_titles).encode()).hexdigest()

    cache_key = dated_cache_key("news_analysis")
    hash_key = dated_cache_key("news_analysis_hash")
    cached = cache.get(cache_key)
    cached_hash = cache.get(hash_key)
    if cached is not None and cached_hash == content_hash:
        return cached

    try:
        settings = get_settings()
        llm_client = create_llm_client(settings)
        user_prompt = _build_prompt(items)
        raw = llm_client.chat(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
        )
        # strip markdown fences if present
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        text = text.strip()
        result = json.loads(text)
        cache.set(cache_key, result, ttl=3600)
        cache.set(hash_key, content_hash, ttl=3600)
        return result
    except Exception as e:
        logger.warning(f"AI 资讯分析失败: {e}")
        fallback = _fallback_analysis(items)
        cache.set(cache_key, fallback, ttl=300)
        cache.set(hash_key, content_hash, ttl=300)
        return fallback
