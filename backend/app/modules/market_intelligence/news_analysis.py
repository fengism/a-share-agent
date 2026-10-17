"""市场新闻情报分析服务。"""

import hashlib
import json
import logging
from typing import Any, cast

from app.core.cache import analysis_cache as cache
from app.core.cache import dated_cache_key
from app.core.concurrency.singleflight import AsyncSingleFlight
from app.financial_data.market.public import get_market_feed
from app.infrastructure.llm.sync_client import llm_chat

_analysis_singleflight: AsyncSingleFlight[dict] = AsyncSingleFlight()
_FALLBACK_CACHE_TTL_SECONDS = 30

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一位资深市场分析师。你需要分析一组市场资讯，提炼出对投资决策有价值的关键信息。

## 输出要求
返回严格的 JSON 对象，包含以下字段：

{
  "market_sentiment": "偏多 或 中性 或 偏空",
  "summary": "用 2-3 句话总结当前市场核心要点",
  "sections": [
    {
      "title": "板块名称",
      "icon": "emoji",
      "items": [
        {"text": "要点描述", "refs": [1, 3]},
        {"text": "要点描述", "refs": [5]}
      ]
    }
  ]
}

每个 item 是一个对象，包含：
- text: 要点描述（不超过 30 字）
- refs: 支撑该观点的资讯编号列表（对应输入中 [i] 的编号），选取最相关的 1-3 条

## 分类维度
根据资讯内容，灵活组织 sections，常见的有：
- 宏观政策（🏦）：央行、财政、监管等政策动向
- 行业热点（🔥）：板块异动、题材发酵、技术突破
- 资金动向（💰）：北向资金、融资融券、大宗交易
- 公司动态（📊）：业绩预告、重组并购、高管变动
- 风险提示（⚠️）：制裁、退市、暴雷、监管处罚
- 海外影响（🌍）：美联储、地缘政治、全球市场

## 原则
- 每个 section 的 items 控制在 2-5 条
- 只提取有明确市场影响的信息，忽略噪音
- 基于资讯事实判断，不做无依据推测
- refs 必须是输入中真实存在的编号
- 只输出 JSON，不要输出其他内容"""


def _get(item, key: str, default="") -> str:
    """兼容 Pydantic 模型和 dict"""
    if hasattr(item, key):
        return str(getattr(item, key, default) or default)
    if isinstance(item, dict):
        return str(item.get(key, default) or default)
    return str(default)


def _build_prompt(items) -> str:
    """构造提供给 LLM 的资讯分析提示词。

    Param:
        items: 新闻条目列表（dict 或 Pydantic 模型）
    Return:
        多行字符串形式的用户提示词
    """
    lines = []
    for i, item in enumerate(items[:80], 1):
        source = _get(item, "source")
        title = _get(item, "title")
        content = _get(item, "content")[:100]
        time_str = _get(item, "publish_time")
        url = _get(item, "url")
        url_part = f" {url}" if url else ""
        lines.append(f"[{i}] [{source}] {time_str} | {title} — {content}{url_part}")
    return f"以下是最近的市场资讯（共 {min(len(items), 80)} 条），请分析归类：\n\n" + "\n".join(lines)


def _fallback_analysis(items) -> dict[str, Any]:
    """LLM 失败时的兜底分析"""
    source_counts: dict[str, int] = {}
    for item in items:
        src = _get(item, "source") or "未知"
        source_counts[src] = source_counts.get(src, 0) + 1

    return {
        "degraded": True,
        "warning": "AI 资讯分析暂时不可用，当前为确定性来源汇总。",
        "market_sentiment": "中性",
        "summary": f"共聚合 {len(items)} 条资讯，来自 {len(source_counts)} 个渠道。AI 分析暂时不可用，请查看右侧资讯详情。",
        "sections": [
            {
                "title": "数据来源分布",
                "icon": "📰",
                "items": [{"text": f"{src}: {cnt} 条"} for src, cnt in sorted(source_counts.items(), key=lambda x: -x[1])],
            }
        ],
    }


def _resolve_refs(result: dict[str, Any], items: list) -> dict[str, Any]:
    """将 LLM 输出中每个 item 的 refs 编号解析为实际 URL 和标题。

    Param:
        result: LLM 返回的分析字典，sections[].items[] 可能是 str 或 dict
        items: 原始新闻列表，索引与 prompt 中的 [i] 对应
    Return:
        原地修改后的 result，items 统一为 {"text": ..., "urls": [...]} 格式
    """
    # 建立编号 → {title, url} 映射（prompt 中编号从 1 开始）
    ref_map = {}
    for i, item in enumerate(items[:80], 1):
        url = _get(item, "url")
        title = _get(item, "title")
        if url:
            ref_map[i] = {"title": title or "", "url": url}

    for section in result.get("sections", []):
        normalized: list[dict[str, Any]] = []
        for item in section.get("items", []):
            if isinstance(item, str):
                normalized.append({"text": item, "urls": []})
            elif isinstance(item, dict):
                text = item.get("text", "")
                refs = item.get("refs", [])
                # 收集所有有效 ref 的 URL 和标题
                urls: list[dict[str, str]] = []
                for ref in refs:
                    if isinstance(ref, int) and ref in ref_map:
                        urls.append(ref_map[ref])
                normalized.append({"text": text, "urls": urls})
            else:
                normalized.append({"text": str(item), "urls": []})
        section["items"] = normalized
    return result


async def analyze_market_news() -> dict[str, Any]:
    """调用 LLM 对市场资讯流进行结构化分析，失败时降级返回兜底分析。

    使用 SingleFlight 防止并发重复调用 LLM。

    分析对象是公共资讯流，结果与用户无关：缓存键只含日期与内容哈希，
    所有用户共享同一份分析（N 个用户只调用一次 LLM）。

    Return:
        包含 market_sentiment/summary/sections 字段的结构化分析字典
    """
    items = await get_market_feed()
    if not items:
        return _fallback_analysis([])

    # 内容哈希必须进 singleflight 的去重键。items 是每次请求重新取的，若去重键只有 user_id，
    # 请求 B 在 A 的 LLM 调用在途时到达，B 会直接拿到「针对旧 feed」的分析，且返回值不带
    # 任何降级标记，前端与上游都察觉不到。
    content_hash = hashlib.md5(
        "\n".join(_get(item, "title") for item in items[:80]).encode()
    ).hexdigest()
    cache_key = dated_cache_key("news_analysis", content_hash)

    async def _load() -> dict[str, Any]:
        cached = cache.get(cache_key)
        if cached is not None:
            return cast(dict[str, Any], cached)

        try:
            user_prompt = _build_prompt(items)
            raw = await llm_chat(
                [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                task="news_analysis",
            )
            # strip markdown fences if present
            text = raw.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[-1]
            if text.endswith("```"):
                text = text.rsplit("```", 1)[0]
            text = text.strip()
            result = json.loads(text)
            if not isinstance(result, dict):
                raise ValueError("AI 资讯分析输出必须为 JSON 对象")
            _resolve_refs(result, items)
            cache.set(cache_key, result, ttl=300)
            return result
        except Exception as e:
            logger.warning("AI 资讯分析降级: error_type=%s error=%s", type(e).__name__, e)
            fallback = _fallback_analysis(items)
            cache.set(cache_key, fallback, ttl=_FALLBACK_CACHE_TTL_SECONDS)
            return fallback

    return cast(dict[str, Any], await _analysis_singleflight.do(cache_key, _load))
