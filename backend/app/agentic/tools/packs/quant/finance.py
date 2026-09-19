"""固定财务公式；仅接收数值，不执行表达式或代码。"""

from __future__ import annotations

import math
import statistics
from typing import Any

from app.agentic.tools.validation import ToolArgumentsError, validate_value

_NUMBER = {"type": "number"}
_NONNEGATIVE = {"type": "number", "minimum": 0}
_SERIES = {"type": "array", "items": _NUMBER, "minItems": 1, "maxItems": 10_000}
_FIELDS = {
    "start_value": _NONNEGATIVE,
    "end_value": _NONNEGATIVE,
    "distributions": _NONNEGATIVE,
    "years": {"type": "number", "minimum": 0, "maximum": 1000},
    "cash_flows": _SERIES,
    "discount_rate": _NUMBER,
    "terminal_growth_rate": _NUMBER,
    "initial_investment": _NONNEGATIVE,
    "returns": {**_SERIES, "minItems": 2, "items": {"type": "number", "minimum": -1}},
    "periods_per_year": {"type": "integer", "minimum": 1, "maximum": 10_000},
    "values": {**_SERIES, "items": _NONNEGATIVE},
    "numerator": _NUMBER,
    "denominator": _NUMBER,
}
# Each operation has its own required/optional arguments, checked again at the execution boundary.
_ARGUMENTS = {
    "return": (("start_value", "end_value"), ("distributions",)),
    "cagr": (("start_value", "end_value", "years"), ()),
    "npv": (("cash_flows", "discount_rate"), ()),
    "dcf": (("cash_flows", "discount_rate", "terminal_growth_rate"), ("initial_investment",)),
    "volatility": (("returns", "periods_per_year"), ()),
    "max_drawdown": (("values",), ()),
    "ratio": (("numerator", "denominator"), ()),
}
FINANCIAL_PARAMETERS = {
    "type": "object",
    "properties": {
        "operation": {"type": "string", "enum": list(_ARGUMENTS)},
        "inputs": {
            "type": "object",
            "properties": _FIELDS,
            "additionalProperties": False,
            "description": "return:start_value/end_value/distributions(可选); cagr:start_value/end_value/years; "
            "npv:cash_flows(含t0)/discount_rate; dcf:cash_flows(从t1)/discount_rate/terminal_growth_rate/"
            "initial_investment(可选); volatility:returns/periods_per_year; max_drawdown:values; "
            "ratio:numerator/denominator。比率均为小数，例如10%=0.1。",
        },
    },
    "required": ["operation", "inputs"],
    "additionalProperties": False,
}


def _positive(value: float, name: str) -> None:
    if value <= 0:
        raise ToolArgumentsError(f"{name} 必须大于 0")


def _discount(cash_flows: list[float], rate: float, start: int) -> float:
    if rate <= -1:
        raise ToolArgumentsError("discount_rate 必须大于 -1")
    return math.fsum(flow / (1 + rate) ** t for t, flow in enumerate(cash_flows, start))


def _compute(operation: str, p: dict[str, Any]) -> tuple[dict, str, list[str]]:
    if operation in {"return", "cagr"}:
        start, end = p["start_value"], p["end_value"]
        _positive(start, "start_value")
        if operation == "return":
            return (
                {"value": (end - start + p.get("distributions", 0)) / start},
                "(end_value - start_value + distributions) / start_value",
                ["单期总收益率；分红计入收益但不假设再投资；不计税费与期间外部资金流。"],
            )
        _positive(p["years"], "years")
        value = -1.0 if end == 0 else math.expm1((math.log(end) - math.log(start)) / p["years"])
        return {"value": value}, "(end_value / start_value) ** (1 / years) - 1", ["年复合增长率；无中间资金流。"]
    if operation == "npv":
        return (
            {"value": _discount(p["cash_flows"], p["discount_rate"], 0)},
            "sum(CF[t] / (1 + r) ** t, t=0..n)",
            ["首项为 t0 现金流，初始支出用负数；等间隔期末现金流；折现率与期长一致。"],
        )
    if operation == "dcf":
        rate, growth = p["discount_rate"], p["terminal_growth_rate"]
        if growth <= -1 or rate <= growth:
            raise ToolArgumentsError("DCF 要求 discount_rate > terminal_growth_rate > -1")
        flows = p["cash_flows"]
        forecast = _discount(flows, rate, 1)
        terminal = flows[-1] * (1 + growth) / (rate - growth)
        discounted_terminal = terminal / (1 + rate) ** len(flows)
        present_value = forecast + discounted_terminal
        return (
            {
                "forecast_present_value": forecast,
                "terminal_value": terminal,
                "terminal_present_value": discounted_terminal,
                "present_value": present_value,
                "net_present_value": present_value - p.get("initial_investment", 0),
            },
            "PV = sum(CF[t]/(1+r)**t, t=1..n) + CF[n]*(1+g)/(r-g)/(1+r)**n; NPV=PV-initial_investment",
            [
                "首项为第1年末现金流，等间隔年度折现；终值采用永续增长；终值可为负。",
                "现金流须口径一致；企业现金流折现值不是股权价值，不自动扣债或除以股数。",
            ],
        )
    if operation == "volatility":
        return (
            {"value": statistics.stdev(p["returns"]) * math.sqrt(p["periods_per_year"])},
            "sample_std(returns, ddof=1) * sqrt(periods_per_year)",
            ["输入为等间隔简单收益率而非价格或百分数；样本标准差；按独立同分布假设年化。"],
        )
    if operation == "max_drawdown":
        values = p["values"]
        _positive(values[0], "values[0]")
        peak, peak_index, trough_index, worst_peak, worst = values[0], 0, 0, 0, 0.0
        for index, value in enumerate(values):
            if value > peak:
                peak, peak_index = value, index
            drawdown = value / peak - 1
            if drawdown < worst:
                worst, worst_peak, trough_index = drawdown, peak_index, index
        return (
            {"value": worst, "peak_index": worst_peak, "trough_index": trough_index},
            "min(value[t] / max(value[0:t+1]) - 1)",
            ["输入按时间升序排列的非负净值；最大回撤为[-1,0]小数；索引从0开始；并列取最早一段。"],
        )
    if p["denominator"] == 0:
        raise ToolArgumentsError("denominator 不得为 0")
    return (
        {"value": p["numerator"] / p["denominator"]},
        "numerator / denominator",
        ["分子分母需同币种、同期间、同口径。"],
    )


async def calculate_financial_metric(operation: str, inputs: dict[str, Any]) -> dict[str, Any]:
    try:
        validate_value({"operation": operation, "inputs": inputs}, FINANCIAL_PARAMETERS)
        required, optional = _ARGUMENTS[operation]
        validate_value(
            inputs,
            {
                "type": "object",
                "properties": {k: _FIELDS[k] for k in (*required, *optional)},
                "required": list(required),
                "additionalProperties": False,
            },
        )
        result, formula, assumptions = _compute(operation, inputs)
        if not all(math.isfinite(value) for value in result.values()):
            raise ToolArgumentsError("计算结果超出有限数值范围")
    except (ToolArgumentsError, ArithmeticError, ValueError) as exc:
        return {
            "ok": False,
            "error_code": "invalid_arguments",
            "error": f"固定公式参数或数值范围无效：{exc}。请修正输入，不要转用 Python 绕过校验。",
        }
    return {
        "ok": True,
        "operation": operation,
        "result": result,
        "formula": formula,
        "assumptions": ["比率使用小数（0.1=10%）；双精度近似计算，不用于分币级记账。", *assumptions],
    }
