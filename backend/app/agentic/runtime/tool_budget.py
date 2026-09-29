"""Safe budget diagnostics shared by model tool responses and public events."""

from typing import Any


def budget_rejection_message(diagnostics: Any) -> str:
    fallback = "工具调用额度受限，本次未执行；未记录具体限制原因"
    if not isinstance(diagnostics, dict):
        return fallback
    reason = diagnostics.get("reason")
    if not isinstance(reason, str):
        return fallback
    if reason == "deadline":
        return "本次分析时限已耗尽，尚未开始的工具请求未执行；请基于已有信息作答"
    keys = ("used", "limit") if reason in {"total_limit", "search_total", "search_burst"} else ("remaining", "reserved")
    if any(type(diagnostics.get(key)) is not int or not 0 <= diagnostics[key] <= 1_000_000 for key in keys):
        return fallback
    first, second = (diagnostics[key] for key in keys)
    if reason == "total_limit":
        return f"本次回答工具总额度已用尽（已使用或预留 {first}/{second} 次），本次未执行"
    if reason == "search_total":
        return f"搜索总额度已用尽（已使用或预留 {first}/{second} 次），本次未执行；请读取已有来源"
    if reason == "search_burst":
        return f"连续搜索已达上限（{first}/{second} 次），本次未执行；请先读取已发现的网页/PDF正文"
    if reason in {"body_reserve", "followup_reserve"}:
        purpose = "网页/PDF正文读取" if reason == "body_reserve" else "后续补查"
        return f"剩余 {first} 次工具额度中 {second} 次为{purpose}预留，本次未执行"
    return fallback
