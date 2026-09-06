"""交易所互动易与 e 互动董秘官方问答服务。"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import akshare as ak

from app.core.cache import market_cache as cache
from app.core.market import normalize_code

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 600


async def get_interactive_qa(code: str, keyword: str = "", limit: int = 15) -> dict[str, Any]:
    """获取上市公司在交易所互动平台（互动易/e互动）上的董秘官方问答记录，支持按关键词过滤。"""
    normalized_code = normalize_code(code).raw
    clean_kw = keyword.strip().lower()
    cache_key = f"interactive_qa_{normalized_code}_{clean_kw}_{limit}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    qa_list: list[dict[str, Any]] = []
    company_name = ""

    try:
        df = await asyncio.to_thread(ak.stock_irm_cninfo, symbol=normalized_code)
        if df is not None and not df.empty:
            if "公司简称" in df.columns and len(df) > 0:
                company_name = str(df.iloc[0].get("公司简称", ""))

            # 过滤有明确回答内容的记录
            df_valid = df.dropna(subset=["回答内容"])
            for _, row in df_valid.iterrows():
                q_text = str(row.get("问题") or "").strip()
                a_text = str(row.get("回答内容") or "").strip()
                q_time = str(row.get("提问时间") or "").strip()
                a_time = str(row.get("更新时间") or "").strip()
                q_user = str(row.get("提问者") or "投资者").strip()
                a_user = str(row.get("回答者") or "董秘/公司管理层").strip()
                source = str(row.get("来源") or "交易所互动平台").strip()

                if not q_text or not a_text:
                    continue

                # 关键词匹配
                if clean_kw:
                    if clean_kw not in q_text.lower() and clean_kw not in a_text.lower():
                        continue

                qa_list.append({
                    "question": q_text,
                    "answer": a_text,
                    "ask_time": q_time,
                    "answer_time": a_time,
                    "questioner": q_user,
                    "answerer": a_user,
                    "platform": source,
                })
    except Exception as exc:
        logger.warning("获取 %s 董秘互动易问答失败: %s", normalized_code, exc)

    # 优先按回答时间降序排列
    qa_list.sort(key=lambda x: x.get("answer_time") or x.get("ask_time") or "", reverse=True)

    result = {
        "code": normalized_code,
        "company_name": company_name,
        "keyword_filter": clean_kw if clean_kw else None,
        "total_matched_count": len(qa_list),
        "items": qa_list[:limit],
        "compliance_note": "董秘及公司在交易所互动平台上的答复具有上市公司法定披露与事实求证效力，可作为传闻求证、订单合作与业务进展的官方事实依据。",
    }

    cache.set(cache_key, result, ttl=_CACHE_TTL_SECONDS)
    return result
