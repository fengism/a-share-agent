from __future__ import annotations

import asyncio
import json
import logging
from typing import Any
from uuid import uuid4

from app.agentic.catalog import registry
from app.agentic.contracts import AgentEvidence
from app.agentic.events import AgentEvent
from app.agentic.protocol import ToolCallFunction, ToolCallInfo, ToolResultInfo
from app.agentic.semantics import EvidenceState
from app.agentic_integration.bootstrap import register_all_capabilities
from app.core.market import is_hk_code

logger = logging.getLogger(__name__)

# 单个预取工具调用硬时限（秒），防止某个慢数据源阻塞整个流水线
_PREFETCH_TIMEOUT_SECONDS = 25.0


def _build_prefetch_plan(code: str) -> list[tuple[str, dict[str, Any]]]:
    """根据个股市场类型规划必须并行预取的确定性工具及参数。"""
    if is_hk_code(code):
        return [
            ("get_hk_stock_profile", {"code": code}),
            ("get_hk_stock_industry_comparison", {"code": code}),
            ("get_hk_stock_technical_indicators", {"code": code, "period": "daily"}),
            ("get_hk_market_overview", {}),
        ]
    return [
        ("get_stock_info", {"code": code}),
        ("get_stock_valuation_detail", {"code": code}),
        ("analyze_financials", {"code": code}),
        ("get_stock_technical_indicators", {"code": code, "period": "daily"}),
        ("get_stock_risk_data", {"code": code}),
        ("get_market_overview", {}),
    ]


async def _execute_single_tool(
    tool_name: str,
    arguments: dict[str, Any],
    event_callback: Any = None,
) -> AgentEvidence | None:
    tool = registry.get_tool(tool_name)
    if tool is None:
        logger.debug("[Prefetch] 工具 %s 未注册，跳过预取", tool_name)
        return None

    call_id = f"prefetch_{tool_name}_{uuid4().hex[:8]}"
    args_json = json.dumps(arguments, ensure_ascii=False)
    tool_call = ToolCallInfo(
        id=call_id,
        function=ToolCallFunction(name=tool_name, arguments=args_json),
    )

    if event_callback is not None:
        try:
            await event_callback(AgentEvent(type="tool_call", tool_call=tool_call))
        except Exception as exc:
            logger.debug("[Prefetch] tool_call 事件回调异常: %s", exc)

    try:
        res: ToolResultInfo = await asyncio.wait_for(
            registry.execute_tool(tool_call, execution_context=None),
            timeout=_PREFETCH_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        logger.warning("[Prefetch] 工具 %s 执行超时或异常: %s", tool_name, exc)
        return None

    if event_callback is not None:
        try:
            await event_callback(AgentEvent(type="tool_result", tool_result=res))
        except Exception as exc:
            logger.debug("[Prefetch] tool_result 事件回调异常: %s", exc)

    if res.is_error:
        logger.warning("[Prefetch] 工具 %s 返回错误: %s", tool_name, res.content[:200])
        return None

    state = EvidenceState.from_content(res.content, is_error=res.is_error)
    if not state.usable_acquisition:
        logger.debug("[Prefetch] 工具 %s 返回数据为空或不可用", tool_name)
        return None

    return AgentEvidence(
        tool_call_id=call_id,
        tool_name=tool_name,
        arguments=args_json,
        content=res.content,
        is_error=False,
    )


async def prefetch_stock_baseline(
    code: str,
    event_callback: Any = None,
) -> list[AgentEvidence]:
    """并发预取个股分析所需的确定性基础事实底座。

    在启动 LLM 调研前，以纯异步高并发方式直接拉取行情快照、估值分位、
    三张表财务数据、量价技术指标及大盘宏观背景。成功拉取的数据将作为初始证据
    直接注入 Agent，消除大模型串行推理和反复下发工具调用的巨大延迟。
    """
    register_all_capabilities()
    plan = _build_prefetch_plan(code)
    tasks = [
        _execute_single_tool(tool_name, args, event_callback=event_callback)
        for tool_name, args in plan
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    evidences: list[AgentEvidence] = []
    for item in results:
        if isinstance(item, AgentEvidence):
            evidences.append(item)
        elif isinstance(item, Exception):
            logger.warning("[Prefetch] 预取任务捕获到未处理异常: %s", item)

    logger.info(
        "[Prefetch] 完成个股 %s 基线事实并发预取: 计划 %d 个，成功取得 %d 个有效证据",
        code,
        len(plan),
        len(evidences),
    )
    return evidences
