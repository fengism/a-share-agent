"""Shared acceptance checks for K-line Provider Chain responses."""

import math
from datetime import date, timedelta

import pandas as pd

from app.core.exceptions import UpstreamEmptyResponseError
from app.core.market import market_today

# 内容类校验失败一律用 UpstreamEmptyResponseError：上游返回了成功响应却没给出
# 可用内容（限流空体、截断、陈旧），属于瞬时故障，熔断器需要计数才能在 provider
# 持续降级时打开。只有「请求日期非法」是调用方错误，保持 ValueError 走永久失败。

_PERIOD_STALE_TOLERANCE_DAYS = {
    "daily": 20,
    "weekly": 45,
    "monthly": 70,
}

# 允许的最长空洞（以工作日计）。实测 A 股长假最大空洞为 8 个工作日
#（2026 春节 02-13→02-24），留出余量后日线取 12；周/月线按各自粒度成比例放宽。
_GAP_TOLERANCE_WEEKDAYS = {
    "daily": 12,
    "weekly": 20,
    "monthly": 60,
    "annual": 260,
}
# 只有跨度够大才做覆盖度判定，避免单日请求被最小条数约束误伤。
_MIN_WEEKDAYS_FOR_COVERAGE = 20
# 覆盖度下限：中国 A 股年均约 243 个交易日 / 261 个工作日（≈93%），叠加长假与
# 长期停牌后取 60%，既能识别截断，又不会对正常响应误报。
_COVERAGE_RATIO = 0.6


def _column(frame: pd.DataFrame, *names: str) -> pd.Series:
    for name in names:
        if name in frame.columns:
            return frame[name]
    return pd.Series(index=frame.index, dtype="object")


def _weekdays(start: date, end: date) -> int:
    """工作日数量，作为交易日数量的保守下界。"""
    if end <= start:
        return 0
    total_days = (end - start).days
    full_weeks, remainder = divmod(total_days, 7)
    count = full_weeks * 5
    for offset in range(remainder + 1):
        if (start + timedelta(days=full_weeks * 7 + offset)).weekday() < 5:
            count += 1
    return count


def _reject_gaps(source: str, dates: list[date], period: str) -> None:
    """拒绝内部出现超长空洞的序列。

    Provider 的分页一旦在中途失败，要么抛错降级，要么只回一部分（SDK 明确不把
    失败响应当作"数据结束"，因此残缺多半来自上游截断）。这类残缺序列的最新一根
    仍然很新，能通过既有的陈旧度校验，所以必须按内部连续性单独判定。
    """
    tolerance = _GAP_TOLERANCE_WEEKDAYS.get(period, _GAP_TOLERANCE_WEEKDAYS["daily"])
    for previous, current in zip(dates, dates[1:], strict=False):
        if _weekdays(previous, current) > tolerance:
            raise UpstreamEmptyResponseError(
                f"{source} K 线存在超长数据空洞: from={previous.isoformat()} "
                f"to={current.isoformat()} missing_weekdays={_weekdays(previous, current)}"
            )


def _reject_insufficient_coverage(
    source: str,
    row_count: int,
    requested_start: date,
    requested_end: date,
) -> None:
    """拒绝明显短于请求窗口的响应。

    仅供"标的必然有完整历史"的调用方启用（如指数）。个股可能是次新股：请求一年
    只能回上市以来的几十根，这是合法数据，套用本检查会造成误杀，因此默认关闭。
    """
    expected = _weekdays(requested_start, requested_end)
    if expected < _MIN_WEEKDAYS_FOR_COVERAGE:
        return
    required = math.ceil(expected * _COVERAGE_RATIO)
    if row_count < required:
        raise UpstreamEmptyResponseError(
            f"{source} K 线覆盖度不足: rows={row_count} required={required} "
            f"window={requested_start.isoformat()}..{requested_end.isoformat()}"
        )


def validate_kline_frame(
    source: str,
    frame: pd.DataFrame,
    *,
    start_date: str,
    end_date: str,
    period: str,
    today: date | None = None,
    require_coverage: bool = False,
) -> pd.DataFrame:
    """Filter malformed rows and reject empty, out-of-range, stale, or truncated data."""
    if frame.empty:
        raise UpstreamEmptyResponseError(f"{source} 未返回有效 K 线")
    parsed_dates = pd.to_datetime(_column(frame, "日期", "date"), errors="coerce")
    start = pd.to_datetime(start_date, errors="coerce")
    end = pd.to_datetime(end_date, errors="coerce")
    if pd.isna(start) or pd.isna(end):
        raise ValueError(f"{source} K 线请求日期无效")

    open_price = pd.to_numeric(_column(frame, "开盘", "open"), errors="coerce")
    close_price = pd.to_numeric(_column(frame, "收盘", "close"), errors="coerce")
    high_price = pd.to_numeric(_column(frame, "最高", "high"), errors="coerce")
    low_price = pd.to_numeric(_column(frame, "最低", "low"), errors="coerce")
    valid = (
        parsed_dates.notna()
        & (parsed_dates >= start)
        & (parsed_dates <= end)
        & (open_price > 0)
        & (close_price > 0)
        & (high_price >= pd.concat([open_price, close_price], axis=1).max(axis=1))
        & (low_price > 0)
        & (low_price <= pd.concat([open_price, close_price], axis=1).min(axis=1))
    )
    accepted = frame.loc[valid].copy()
    accepted_dates = parsed_dates.loc[valid]
    if accepted.empty:
        raise UpstreamEmptyResponseError(f"{source} K 线 OHLC 或日期范围无有效数据")

    expected_end = min(end.date(), today or market_today())
    tolerance = _PERIOD_STALE_TOLERANCE_DAYS.get(period, 20)
    latest_date = accepted_dates.max().date()
    if latest_date < expected_end - timedelta(days=tolerance):
        raise UpstreamEmptyResponseError(
            f"{source} K 线数据陈旧: latest={latest_date.isoformat()} expected_end={expected_end.isoformat()}"
        )

    ordered = sorted(accepted_dates.dt.date)
    _reject_gaps(source, ordered, period)
    if require_coverage:
        _reject_insufficient_coverage(source, len(ordered), start.date(), expected_end)
    return accepted.reset_index(drop=True)
