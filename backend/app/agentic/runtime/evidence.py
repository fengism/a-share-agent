"""Shared evidence payload decoding and deterministic user-facing gap reports.

No raw errors, tool payloads or model prose are interpolated into gap reports.
They may contain credentials, prompt-injection text or unsupported claims.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from collections.abc import Iterable
from typing import Any

from app.agentic.agents.contracts import AgentExecutionResult

_LABELS = {
    "fundamental": "基本面",
    "technical": "技术面",
    "news": "新闻情绪",
    "risk": "风险",
    "macro": "宏观",
    "general-chat": "当前问题",
}
_FAILURES = {
    "timeout": "数据获取超时",
    "upstream_unavailable": "数据源暂不可用",
    "rate_limited": "数据源请求受限",
    "invalid_arguments": "工具参数未通过校验",
    "tool_context_budget_exhausted": "证据上下文预算已用尽",
    "tool_budget_exceeded": "工具调用预算已用尽",
    "skill_budget_exceeded": "Skill 加载额度已用尽",
}


def decode_tool_payload(content: str) -> Any:
    """Decode serialized tool content, unwrapping the ``{ok, data}`` envelope.

    Non-JSON content is returned as-is so text heuristics can still inspect it.
    """
    try:
        value = json.loads(content)
    except (TypeError, ValueError, json.JSONDecodeError):
        return content
    if isinstance(value, dict) and value.get("ok") is True and "data" in value:
        return value["data"]
    return value


def flatten_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return "\n".join(flatten_text(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return "\n".join(flatten_text(item) for item in value)
    return str(value) if value is not None else ""


def has_finite_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return math.isfinite(value)
    if isinstance(value, dict):
        return any(has_finite_number(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(has_finite_number(item) for item in value)
    return False


def safe_tool_failure_code(content: str) -> str:
    if len(content) > 100_000:
        return ""
    try:
        data = json.loads(content)
        error = data.get("error") if isinstance(data, dict) else None
        code = error.get("code") if isinstance(error, dict) else None
        return code if isinstance(code, str) and code in _FAILURES else ""
    except (ValueError, TypeError):
        return ""


def tool_failure_label(content: str) -> str:
    """Short user-safe label for one failed tool result; never raw payload text."""
    return _FAILURES.get(safe_tool_failure_code(content), "工具调用失败")


def evidence_gap_reason(result: AgentExecutionResult) -> str:
    reasons: list[str] = []
    reason = result.outcome.reason
    if reason.code not in {"", "stop", "tool_calls"}:
        reasons.append(reason.description)
    for item in result.tool_results:
        failure = _FAILURES.get(item.failure_code)
        if failure and failure not in reasons:
            reasons.append(failure)
    evidence_items = [item for item in result.tool_results if not item.instruction]
    if not evidence_items:
        reasons.append("未取得数据工具结果，不能声称已完成查询")
    else:
        if any(item.skipped for item in evidence_items):
            reasons.append("部分工具请求未执行或被合并复用")
        if any(item.is_error for item in evidence_items):
            reasons.append("部分工具调用失败")
        if any(not item.is_error and not item.skipped and not item.evidence_state.usable_acquisition for item in evidence_items):
            reasons.append("部分工具未返回有效数据")
        if any(item.evidence_state.usable_acquisition and not item.evidence_state.usable_context for item in evidence_items):
            reasons.append("部分已获取数据未进入模型上下文")
    if not reasons:
        reasons.append("该维度未完整完成；已有上下文证据不代表其余问题已核实")
    return "；".join(reasons[:4])


def build_evidence_gap_report(results: Iterable[AgentExecutionResult]) -> str:
    items = list(results)
    lines = [
        "## 本次分析未形成可靠结论",
        "以下是取证进展与缺口说明，不是投资分析结论；缺少数据不等于没有风险。",
        "",
        "### 已取得什么 / 还缺什么",
    ]
    for result in items[:8]:
        counts: Counter[str] = Counter()
        for tool in result.tool_results:
            category = (
                "Skill 指令"
                if tool.instruction
                else "上下文有效"
                if tool.evidence_state.usable_context
                else "已跳过或复用"
                if tool.skipped
                else "失败"
                if tool.is_error
                else "未进入上下文"
                if tool.evidence_state.usable_acquisition
                else "无有效数据"
            )
            counts[category] += 1
        label = _LABELS.get(result.agent_name, "分析任务")
        summary = "、".join(f"{key} {value} 条" for key, value in counts.items()) or "没有工具结果记录"
        lines.append(f"- **{label}**：{summary}。{evidence_gap_reason(result)}。")
    if not items:
        lines.append("- 没有可用分析记录，无法确认查询进展。")
    if len(items) > 8:
        lines.append(f"- 另有 {len(items) - 8} 个维度未展开。")
    lines += [
        "",
        "工具结果条数包含缓存/重复结果，不代表独立信息源数量；未提供原始证据时不能据此推断行情或财务表现。",
        "",
        "### 下一步",
        "- 缩小到一个标的、一个分析维度和明确日期范围，优先补齐对应公告、财报、新闻或行情证据。",
        "- 数据源超时或限流时稍后重试；预算不足时拆分问题，避免原样连续重试。",
        "- 若提示模型认证、权限或格式问题，先检查模型配置；也可提供可访问的原始资料再分析。",
        "",
        "在证据补齐前，不给出确定的买卖方向、目标价或仓位建议。",
    ]
    return "\n".join(lines)
