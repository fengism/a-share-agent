"""复权因子对账：逐次除权事件比对四套因子口径。

排查背景：个股 K 线的复权价有三个互相独立的口径并存——
  * 本地因子表（TDX XDXR 仿射，或 TDX 不可用时的新浪乘性兜底）
  * 上游腾讯 / 东财 / 财联社 / AkShare 直接返回的复权价
  * merge_local_daily_kline 把"本地复权价"与"上游复权价"按同日期拼接，
    但不校验两段基准是否一致，拼接处可能出现价格断层。

本工具只读、不写库，把每个除权日的隐含每股影响拆开对比，回答"哪家数据有偏差"。

用法:
  uv run python -m app.scripts.reconcile_adjustment_factors [--codes 600519,000858]
      [--start 2019-01-01] [--end 2026-10-13] [--tol 0.005] [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from app.domain.timezones import market_today

# 因子序列的"跳变点"就是除权日；每段只取末值即可还原阶梯函数。
_SOURCE_LABELS = ("tdx_xdxr", "sina", "tencent", "eastmoney")


@dataclass
class FactorSeries:
    """某个来源的 hfq 隐含因子序列（锚定上市日）。"""

    label: str
    points: dict[str, float] = field(default_factory=dict)
    error: str | None = None

    def add(self, day: str, value: float) -> None:
        if value and value == value and value > 0:
            self.points[day] = float(value)

    def step_value(self, day: str) -> float | None:
        """取该日期生效的因子值（阶梯函数，向前找最近一个点）。"""
        if not self.points:
            return None
        candidates = [key for key in self.points if key <= day]
        if not candidates:
            return None
        return self.points[max(candidates)]

    @property
    def available(self) -> bool:
        return bool(self.points)


def _safe_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and number > 0 else None


# ── 各来源取数 ────────────────────────────────────────────────────────────────
def _tdx_factor_series(code: str, start: str, end: str) -> FactorSeries:
    """本地权威口径：TDX XDXR 仿射因子（能表达送配股）。"""
    from tdxhub.gbbq import adjustment_factors, normalize_gbbq

    from app.infrastructure.providers.registry import get_provider
    from app.modules.market_daily.adjustment import canonical_adjustment_anchor

    series = FactorSeries("tdx_xdxr")
    try:
        raw = get_provider("tdxhub").fetch_stock_xdxr(code)
        actions = normalize_gbbq(raw)
    except Exception as error:
        series.error = f"{type(error).__name__}: {error}"
        return series
    if actions is None or actions.empty:
        series.error = "TDX XDXR 返回空"
        return series

    dates = pd.bdate_range(canonical_adjustment_anchor(), end).strftime("%Y-%m-%d").tolist()
    frame = adjustment_factors(dates, actions).iloc[1:]
    for day, (_, row) in zip(dates[1:], frame.iterrows(), strict=False):
        if start <= day <= end:
            # hfq_price = raw * hfq_mul + hfq_add，取 mul 作为主项（add 相对量级极小）
            series.add(day, _safe_float(row["hfq_mul"]) or 0.0)

    # TDX 降级时会返回"非空但无意义"的 XDXR 帧（协议层 unpack 失败），规范化后
    # 仍是一张合法表，算出来的因子恒为 1.0。若不做校验，这种平序列会被当成基准
    # 源，导致所有除权事件的基准步长都是 1、对账结果静默变成"0 事件"。
    distinct = {round(value, 8) for value in series.points.values()}
    if len(series.points) > 1 and len(distinct) < 2:
        series.points.clear()
        series.error = "TDX XDXR 因子序列恒定（上游降级或该股无公司行为）"
    return series


def _sina_factor_series(code: str, start: str, end: str) -> FactorSeries:
    """新浪乘性因子（只能在除权日有值，阶梯函数）。"""
    from app.infrastructure.providers.registry import get_provider

    series = FactorSeries("sina")
    try:
        raw_factors = get_provider("sina").fetch_adjustment_factors(code)
    except Exception as error:
        series.error = f"{type(error).__name__}: {error}"
        return series
    frame = raw_factors.get("hfq") if isinstance(raw_factors, dict) else None
    if frame is None or len(frame) == 0:
        series.error = "新浪 hfq 因子为空"
        return series
    frame = frame.copy()
    frame["日期"] = pd.to_datetime(frame["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    frame = frame.dropna(subset=["日期"])
    for day, value in zip(frame["日期"], frame["factor"], strict=True):
        if start <= str(day) <= end:
            series.add(str(day), _safe_float(value) or 0.0)
    return series


def _implied_factor_from_kline(
    label: str,
    code: str,
    start: str,
    end: str,
    loader,
) -> FactorSeries:
    """从「复权价 / 不复权价」反推上游的隐含 hfq 因子。"""
    series = FactorSeries(label)
    try:
        raw = loader(adjust="")
        adjusted = loader(adjust="hfq")
    except Exception as error:
        series.error = f"{type(error).__name__}: {error}"
        return series
    if raw is None or adjusted is None or raw.empty or adjusted.empty:
        series.error = "上游返回空"
        return series

    day_column = "日期" if "日期" in raw.columns else "date"
    close_column = "收盘" if "收盘" in raw.columns else "close"

    merged = adjusted[[day_column, close_column]].merge(
        raw[[day_column, close_column]], on=day_column, suffixes=("_adj", "_raw"),
    )
    for day, adj, unadj in zip(merged[day_column], merged[f"{close_column}_adj"], merged[f"{close_column}_raw"], strict=True):
        denominator = _safe_float(unadj)
        if denominator is None:
            continue
        series.add(str(day), (_safe_float(adj) or 0.0) / denominator)
    return series


def collect_series(code: str, start: str, end: str) -> dict[str, FactorSeries]:
    from app.infrastructure.providers.registry import get_provider

    tencent = get_provider("tencent")
    eastmoney = get_provider("eastmoney")
    return {
        "tdx_xdxr": _tdx_factor_series(code, start, end),
        "sina": _sina_factor_series(code, start, end),
        "tencent": _implied_factor_from_kline(
            "tencent", code, start, end,
            lambda adjust: tencent.fetch_stock_kline(code, start, end, adjust=adjust),
        ),
        "eastmoney": _implied_factor_from_kline(
            "eastmoney", code, start, end,
            lambda adjust: eastmoney.fetch_kline(code, "daily", start.replace("-", ""), end.replace("-", ""), adjust=adjust),
        ),
    }


# ── 比对 ──────────────────────────────────────────────────────────────────────
def _reference_label(series: dict[str, FactorSeries]) -> str | None:
    """基准源：本地权威的 TDX 仿射因子；不可用时退回覆盖最广的可用来源。

    「可用」要求序列真的随除权而变——恒定序列会让每个事件的基准步长都是 1，
    对账结果会静默退化成「0 事件」。
    """
    def _usable(label: str) -> bool:
        factor_series = series[label]
        if not factor_series.available:
            return False
        if label == "sina":
            return True  # 纯事件清单，每个点即一次除权
        return len({round(value, 8) for value in factor_series.points.values()}) >= 2

    if _usable("tdx_xdxr"):
        return "tdx_xdxr"
    for label in _SOURCE_LABELS:
        if _usable(label):
            return label
    return None


def _step_dates(series: FactorSeries, tolerance: float) -> set[str]:
    """因子序列的阶跃点。"""
    days = sorted(series.points)
    return {
        current
        for previous, current in zip(days, days[1:], strict=False)
        if abs(series.points[current] / series.points[previous] - 1.0) > tolerance
    }


def _detect_ex_right_dates(
    series: dict[str, FactorSeries],
    tolerance: float,
    reference_label: str,
) -> tuple[list[str], list[dict[str, Any]]]:
    """定位除权日，返回 (确认事件, 仅单一来源跳变的可疑点)。

    刻意**不**用不复权价的跳空缺口来定位：实测 600519 会把 2024-09-24~10-09 的
    连板暴涨、2019-05-06 的关税冲击一起误判成除权日——除权跳空和大幅涨跌在价格
    上无法区分。

    因子阶跃是可靠信号（除权会让因子变，涨跌不会），但只信单一来源不够：腾讯的
    隐含因子在部分非除权日也会出现 >0.5% 的跳动（复权价与不复权价都只保留两位
    小数，大幅波动行情下舍入会放大）。因此要求**至少两个来源同时阶跃**才确认，
    新浪的因子表本身是纯事件清单、每个点都是一次除权，直接采信。
    """
    per_source = {
        label: set(series[label].points) if label == "sina" and series[label].available
        else _step_dates(series[label], tolerance)
        for label in _SOURCE_LABELS
        if series[label].available
    }
    # 恒定序列没有参考价值，不参与投票，否则会稀释真实事件。
    per_source = {
        label: days for label, days in per_source.items()
        if days or label == reference_label
    }

    votes: dict[str, list[str]] = {}
    for label, days in per_source.items():
        for day in days:
            votes.setdefault(day, []).append(label)

    confirmed = sorted(day for day, labels in votes.items() if len(labels) >= 2)
    suspects = sorted(
        ({"date": day, "only": labels[0]} for day, labels in votes.items() if len(labels) == 1),
        key=lambda item: item["date"],
    )
    return confirmed, suspects


def reconcile(code: str, series: dict[str, FactorSeries], tolerance: float) -> dict[str, Any]:
    reference = _reference_label(series)
    if reference is None:
        return {"code": code, "status": "全部来源不可用", "series": {}, "events": []}

    ref_series = series[reference]
    ref_last = ref_series.step_value(max(ref_series.points))
    events: list[dict[str, Any]] = []

    ex_dates, suspects = _detect_ex_right_dates(series, tolerance, reference)
    for ex_date in ex_dates:
        before_day = _previous_day(ref_series, ex_date)
        reference_before = ref_series.step_value(before_day)
        reference_after = ref_series.step_value(ex_date)
        if not reference_before or not reference_after:
            continue
        reference_step = reference_after / reference_before
        if abs(reference_step - 1.0) < 1e-6:
            continue

        row: dict[str, Any] = {
            "ex_date": ex_date,
            "reference": reference,
            "reference_step": round(reference_step, 8),
            "sources": {},
            "divergences": {},
        }
        for label in _SOURCE_LABELS:
            if label == reference:
                continue
            after = series[label].step_value(ex_date)
            before = series[label].step_value(before_day)
            if after is None or not before:
                row["sources"][label] = None
                continue
            source_step = after / before
            offset = source_step / reference_step - 1.0
            row["sources"][label] = {
                "step": round(source_step, 8),
                "offset_pct": round(offset, 8),
            }
            if abs(offset) > tolerance:
                row["divergences"][label] = round(offset, 6)
        events.append(row)

    anchor_offsets = {}
    if ref_last:
        for label in _SOURCE_LABELS:
            if label == reference or not series[label].available:
                continue
            last = series[label].step_value(max(series[label].points))
            if last:
                anchor_offsets[label] = round(last / ref_last - 1.0, 6)

    return {
        "code": code,
        "status": "ok",
        "reference": reference,
        "anchor_offsets": anchor_offsets,
        "unavailable": {
            label: series[label].error for label in _SOURCE_LABELS if series[label].error
        },
        "single_source_steps": suspects,
        "events": events,
        "diverged_events": sum(1 for event in events if event["divergences"]),
        "total_events": len(events),
    }


def _previous_day(series: FactorSeries, day: str) -> str:
    earlier = [key for key in series.points if key < day]
    return max(earlier) if earlier else min(series.points)


def _render(report: dict[str, Any]) -> str:
    code = report["code"]
    lines: list[str] = []
    if report["status"] != "ok":
        lines.append(f"{code}: {report['status']}")
        return "\n".join(lines)

    lines.append(f"\n{'=' * 96}")
    lines.append(f"{code}  基准源={report['reference']}  确认除权事件={report['total_events']}  有分歧={report['diverged_events']}")
    unavailable = report.get("unavailable") or {}
    if unavailable:
        lines.append(f"  不可用来源: {unavailable}")
    offsets = report.get("anchor_offsets") or {}
    if offsets:
        lines.append("  末端整体尺度差(非事件级): " + "  ".join(
            f"{label}={value:+.4%}" for label, value in offsets.items()
        ))
    suspects = report.get("single_source_steps") or []
    if suspects:
        only: dict[str, int] = {}
        for item in suspects:
            only[item["only"]] = only.get(item["only"], 0) + 1
        lines.append("  仅单一来源阶跃(疑似舍入噪声，未计入事件): " + "  ".join(
            f"{label}×{count}" for label, count in sorted(only.items())
        ))
    if not report["events"]:
        return "\n".join(lines)

    header = f"{'除权日':<12}{'基准步长':>12}" + "".join(f"{label:>18}" for label in offsets)
    lines.append(header)
    lines.append("-" * 96)
    for event in report["events"]:
        row = f"{event['ex_date']:<12}{event['reference_step']:>12.6f}"
        for label in offsets:
            source = event["sources"].get(label) or {}
            step, offset = source.get("step"), source.get("offset_pct")
            if step is None:
                row += f"{'—':>18}"
            else:
                mark = " ⚠" if label in event["divergences"] else ""
                row += f"{f'{step:.6f}({offset:+.2%})':>18}"[:18] + mark
        lines.append(row)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="复权因子对账（只读）")
    parser.add_argument("--codes", default="600519", help="逗号分隔的股票代码")
    parser.add_argument("--start", default="2019-01-01")
    parser.add_argument("--end", default=market_today().isoformat())
    parser.add_argument("--tol", type=float, default=0.005, help="事件级步长偏差告警阈值")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args(argv)

    reports = []
    for code in [item.strip() for item in args.codes.split(",") if item.strip()]:
        series = collect_series(code, args.start, args.end)
        report = reconcile(code, series, args.tol)
        reports.append(report)
        if not args.json:
            print(_render(report))

    if args.json:
        print(json.dumps(reports, ensure_ascii=False, indent=2))
    elif reports:
        total = sum(item["total_events"] for item in reports)
        diverged = sum(item["diverged_events"] for item in reports)
        print(f"\n合计: 除权事件 {total} 次，有分歧 {diverged} 次")
    return 0


if __name__ == "__main__":
    sys.exit(main())