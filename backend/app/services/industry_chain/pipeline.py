import asyncio
import json
import logging
import re

from app.config import get_settings
from app.models.industry_chain import IndustryChainProgress, IndustryChainResult
from app.services.industry_chain.prompts import SYSTEM_PROMPT, build_user_prompt
from app.services.industry_chain.storage import save_industry_chain
from app.services.llm.client import create_llm_client
from app.utils.cache import cache
from app.utils.rate_limiter import call_blocking

logger = logging.getLogger(__name__)

_STAGES = [
    "搜索产业链相关公司",
    "获取行业数据与研报",
    "AI 生成分析报告",
]


async def _emit(callback, event: IndustryChainProgress):
    """触发进度回调，callback 为空时跳过。

    Param:
        callback: 进度回调协程函数，可为 None
        event: 进度事件对象
    Return:
        无
    """
    if callback:
        await callback(event)


def _safe_parse_llm_json(text: str):
    """容错解析 LLM 返回的 JSON 字符串。

    LLM 经常在 JSON 字符串值里输出字面换行（而非 \\n 转义），导致标准 json.loads 失败。
    这里依次尝试：
      1. 直接 json.loads
      2. 把字符串值中的字面换行转义后再 json.loads
      3. 提取首个平衡的 {...} 子串再试

    Param:
        text: LLM 原始响应文本
    Return:
        解析后的对象（dict / list 等），失败返回 None
    """
    if not text:
        return None
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass

    try:
        escaped = re.sub(r'(?<=":)\s*\n', r"\\n", text)
        return json.loads(escaped)
    except (json.JSONDecodeError, ValueError):
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        candidate = text[start:end + 1]
        try:
            return json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            pass
        try:
            return json.loads(re.sub(r"(?<=:)\s*\n", r"\\n", candidate))
        except (json.JSONDecodeError, ValueError):
            pass
    return None


async def _collect_data(name: str) -> dict:
    """并行采集产业链相关数据"""
    from app.services.chat.tools.stock_helpers import (
        iwencai_query,
        iwencai_search,
        iwencai_select_stock,
    )

    # 问财搜索：产业链公司
    stocks_task = iwencai_select_stock(f"{name}产业链 上中下游", limit=20)
    # 问财搜索：行业数据
    industry_task = iwencai_query(f"{name}行业 市场规模 竞争格局", limit=10)
    # 问财搜索：研报
    reports_task = iwencai_search(f"{name}产业链 研报", channel="report", size=10)

    stocks, industry_data, reports = await asyncio.gather(
        stocks_task, industry_task, reports_task, return_exceptions=True
    )

    # 行业排名（东财）
    rankings = None
    try:
        from app.services.providers import get_provider
        rankings = await call_blocking(get_provider("eastmoney").fetch_industry_rankings, 50)
    except Exception:
        pass

    return {
        "stocks": stocks if not isinstance(stocks, Exception) else {"error": str(stocks)},
        "industry_data": industry_data if not isinstance(industry_data, Exception) else {"error": str(industry_data)},
        "reports": reports if not isinstance(reports, Exception) else {"error": str(reports)},
        "rankings": rankings,
    }


async def run_industry_chain_analysis(
    name: str,
    progress_callback=None,
) -> IndustryChainResult:
    """产业链分析主流程"""
    # 检查缓存
    cache_key = f"industry_chain:{name}"
    cached = cache.get(cache_key)
    if cached is not None:
        await _emit(progress_callback, IndustryChainProgress(
            type="complete", stage="cached", message="使用缓存结果", result=cached.model_dump(),
        ))
        return cached

    try:
        # 阶段 1：数据采集
        await _emit(progress_callback, IndustryChainProgress(
            type="stage_started", stage=_STAGES[0], message="搜索产业链相关数据...",
        ))
        data = await _collect_data(name)
        await _emit(progress_callback, IndustryChainProgress(
            type="stage_completed", stage=_STAGES[0], message="数据采集完成",
        ))

        # 阶段 2：行业数据整理
        await _emit(progress_callback, IndustryChainProgress(
            type="stage_started", stage=_STAGES[1], message="整理行业数据...",
        ))
        await _emit(progress_callback, IndustryChainProgress(
            type="stage_completed", stage=_STAGES[1], message="数据整理完成",
        ))

        # 阶段 3：LLM 分析
        await _emit(progress_callback, IndustryChainProgress(
            type="stage_started", stage=_STAGES[2], message="AI 正在生成分析报告...",
        ))

        settings = get_settings()
        llm_client = create_llm_client(settings)
        user_prompt = build_user_prompt(name, data)
        raw = llm_client.chat(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
        )

        # 清理 markdown fences
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        text = text.strip()

        # 解析 LLM 返回的 JSON（包含 llm_report + charts）
        result = IndustryChainResult(name=name)
        parsed = _safe_parse_llm_json(text)
        if isinstance(parsed, dict):
            result.llm_review = parsed.get("llm_report", "")
            result.charts = parsed.get("charts", [])
            result.summary = parsed.get("summary", "")
            result.drivers = parsed.get("drivers", [])
            result.risks = parsed.get("risks", [])
            result.key_stocks = parsed.get("key_stocks", [])
            # 新版 prompt 把上中下游放在 level/sections 字段；尽量回填
            for level_key, target in (
                ("upstream", "upstream"),
                ("midstream", "midstream"),
                ("downstream", "downstream"),
            ):
                value = parsed.get(target)
                if not value and isinstance(parsed.get("sections"), list):
                    value = [
                        item for item in parsed["sections"] if isinstance(item, dict) and item.get("level") == level_key
                    ]
                if value:
                    setattr(result, target, value)
        else:
            # 纯 Markdown 报告
            result.llm_review = text

        cache.set(cache_key, result, ttl=3600)

        try:
            save_industry_chain(name, result)
        except Exception as save_exc:
            logger.warning("产业链存档失败: name=%s, error=%s", name, save_exc)

        await _emit(progress_callback, IndustryChainProgress(
            type="complete", stage="done", message="分析完成", result=result.model_dump(),
        ))
        return result

    except Exception as e:
        logger.error(f"产业链分析失败: {e}", exc_info=True)
        await _emit(progress_callback, IndustryChainProgress(
            type="error", stage="error", message=f"分析失败: {e}",
        ))
        raise
