import asyncio
import json
import logging
import re

from app.config import get_settings
from app.models.industry_chain import IndustryChainProgress, IndustryChainResult
from app.services.industry_chain.prompts import SYSTEM_PROMPT, build_user_prompt
from app.services.industry_chain.storage import save_industry_chain
from app.services.llm.client import llm_chat
from app.utils.cache import cache
from app.utils.rate_limiter import call_blocking, eastmoney_semaphore

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

    LLM 经常在 JSON 字符串值里输出字面换行（而非 \n 转义），导致标准 json.loads 失败。
    这里依次尝试：
      1. 直接 json.loads
      2. 逐字符修复字符串内的字面换行和未转义引号后 json.loads
      3. 提取首个平衡的 {...} 子串再试

    Param:
        text: LLM 原始响应文本
    Return:
        解析后的对象（dict / list 等），失败返回 None
    """
    if not text:
        return None
    # 方法 1: 直接 json.loads
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass
    # 方法 2: 逐字符修复字符串内的字面换行和未转义引号
    fixed = _fix_json_newlines(text)
    try:
        return json.loads(fixed)
    except (json.JSONDecodeError, ValueError):
        pass
    # 方法 3: 提取首个平衡的 {...} 子串再试
    start = text.find("{")
    end = _find_matching_brace(text, start) if start != -1 else -1
    if start != -1 and end > start:
        candidate = text[start:end + 1]
        try:
            return json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            pass
        fixed2 = _fix_json_newlines(candidate)
        try:
            return json.loads(fixed2)
        except (json.JSONDecodeError, ValueError):
            pass
    return None


def _find_matching_brace(text: str, start: int) -> int:
    """找到从 start 位置 { 开始的匹配 }（跳过字符串内的假括号）。"""
    depth = 0
    in_str = False
    i = start
    while i < len(text):
        ch = text[i]
        if in_str:
            if ch == '\\':
                i += 2
                continue
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    return -1


def _fix_json_newlines(text: str) -> str:
    """修复 JSON 字符串值中的字面换行和未转义引号。

    逐字符扫描，仅在字符串值（双引号内）做替换：
    - 字面换行 \n/\r → 转义为 \n
    - 属于字符串内容而非结尾的 " → 转义为 \"
    """
    out = []
    in_str = False
    i = 0
    while i < len(text):
        ch = text[i]
        if in_str:
            if ch == '\\':
                out.append(ch)
                i += 1
                if i < len(text):
                    out.append(text[i])
                    i += 1
            elif ch == '"':
                rest = text[i + 1:].lstrip()
                if not rest or rest[0] in (',', ']', '}', '\n', '\r'):
                    out.append(ch)
                    in_str = False
                    i += 1
                else:
                    out.append('\\"')
                    i += 1
            elif ch == '\n':
                out.append('\\n')
                i += 1
            elif ch == '\r':
                out.append('\\r')
                i += 1
            else:
                out.append(ch)
                i += 1
        else:
            out.append(ch)
            if ch == '"':
                in_str = True
            i += 1
    return ''.join(out)


def _unescape_json_string(s: str) -> str:
    """简单反转义 JSON 字符串中的 \n、\" 等转义序列。"""
    result = []
    i = 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            nxt = s[i + 1]
            if nxt == "n":
                result.append("\n")
            elif nxt == "r":
                result.append("\r")
            elif nxt == "t":
                result.append("\t")
            elif nxt == '"':
                result.append('"')
            elif nxt == "\\":
                result.append("\\")
            else:
                result.append(s[i])
                result.append(nxt)
            i += 2
        else:
            result.append(s[i])
            i += 1
    return "".join(result)


def _try_extract_llm_report(text: str) -> str | None:
    """当 JSON 解析失败时，从原始文本中手动提取 llm_report 字段值。

    使用逐字符扫描方式，定位 "llm_report" 后的冒号和引号，
    提取引号内的原始内容，不做 JSON 转义处理。
    """
    for prefix in ('"llm_report"', "'llm_report'"):
        idx = text.find(prefix)
        if idx == -1:
            continue
        after_prefix = text[idx + len(prefix):]
        colon = after_prefix.find(":")
        if colon == -1:
            continue
        content = after_prefix[colon + 1:].lstrip()
        if not content:
            continue
        if content[0] not in ('"', "'"'"', "'", '\'"'):
            continue
        delim = content[0]
        j = 1
        while j < len(content):
            if content[j] == "\\":
                j += 2
                continue
            if content[j] == delim:
                return content[1:j]
            j += 1
        # 没有找到匹配的结束引号，换 prefix 继续搜索
    return None

    """对 LLM 生成的 ECharts option 做后处理，修复常见缺漏。

    包括：补全 backgroundColor、tooltip、grid、roam 等关键属性，
    确保暗色主题配色完整。
    """
    enhanced = []
    for chart in charts:
        if not isinstance(chart, dict):
            continue
        opt = chart.get("option", {})
        if not isinstance(opt, dict):
            chart["option"] = {}
            enhanced.append(chart)
            continue

        chart_type = chart.get("type", "")
        series = opt.get("series", [])

        # 1) background
        if "backgroundColor" not in opt:
            opt["backgroundColor"] = "transparent"

        # 2) tooltip
        if "tooltip" not in opt:
            if chart_type in ("tree",):
                opt["tooltip"] = {"trigger": "item", "triggerOn": "mousemove"}
            else:
                opt["tooltip"] = {
                    "trigger": "axis",
                    "backgroundColor": "rgba(15,23,42,0.9)",
                    "borderColor": "#334155",
                    "textStyle": {"color": "#e5e7eb", "fontSize": 12},
                }

        # 3) grid for cartesian charts
        if chart_type in ("bar", "line") and "grid" not in opt:
            opt["grid"] = {"containLabel": True, "left": 40, "right": 20, "bottom": 40, "top": 20}
        elif chart_type in ("bar", "line") and isinstance(opt.get("grid"), dict):
            opt["grid"]["containLabel"] = opt["grid"].get("containLabel", True)

        # 4) dark theme fallbacks for cartesian axes
        if chart_type in ("bar", "line"):
            for axis_key in ("xAxis", "yAxis"):
                axis = opt.get(axis_key)
                if isinstance(axis, dict) and "axisLabel" in axis:
                    al = axis["axisLabel"]
                    if isinstance(al, dict) and "color" not in al:
                        al["color"] = "#9ca3af"
                elif isinstance(axis, list):
                    for a in axis:
                        if isinstance(a, dict) and "axisLabel" in a:
                            al = a["axisLabel"]
                            if isinstance(al, dict) and "color" not in al:
                                al["color"] = "#9ca3af"

        # 5) tree chart defaults
        if chart_type == "tree":
            for s in series if isinstance(series, list) else []:
                if isinstance(s, dict) and s.get("type") == "tree":
                    s.setdefault("roam", True)
                    s.setdefault("top", 20)
                    s.setdefault("left", 80)
                    s.setdefault("bottom", 20)
                    s.setdefault("right", 80)
                    s.setdefault("expandAndCollapse", True)
                    s.setdefault("initialTreeDepth", 5)
                    if "lineStyle" not in s:
                        s["lineStyle"] = {"color": "#4b5563", "width": 1.5}
                    if "label" not in s:
                        s["label"] = {"position": "left", "fontSize": 12, "color": "#e5e7eb"}
                    if "leaves" not in s:
                        s["leaves"] = {"label": {"position": "right", "fontSize": 12, "color": "#e5e7eb"}}

        chart["option"] = opt
        enhanced.append(chart)

    return enhanced


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
        rankings = await call_blocking(get_provider("eastmoney").fetch_industry_rankings, 50, semaphore=eastmoney_semaphore)
    except Exception as e:
        logger.debug("行业排名获取失败（非关键）: %s", e)

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
        user_prompt = build_user_prompt(name, data)
        raw = await llm_chat(
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
            result.charts = _enhance_chart_options(parsed.get("charts", []))
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
            # JSON 解析失败，尝试手动提取 llm_report 字段
            extracted = _try_extract_llm_report(text)
            result.llm_review = _unescape_json_string(extracted) if extracted else (text or "（AI 分析报告生成失败，请重试）")
            if extracted:
                logger.info("产业链分析 JSON 解析失败，通过手动提取恢复 llm_report, name=%s", name)
            else:
                logger.warning("产业链分析 JSON 解析失败，手动提取也失败，使用原始文本作为 llm_review, name=%s", name)
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
