"""估值计算通用辅助函数。"""

import logging
import math
import re
from datetime import date

from app.core.market import safe_float
from app.financial_data.stock.valuation.schemas import InstitutionForecast, PeerMetricStats
from app.infrastructure.providers.registry import get_provider

logger = logging.getLogger(__name__)


def _get_akshare_provider():
    """Lazily resolve the Akshare provider singleton."""
    return get_provider("akshare")


def _get_ths_provider():
    """Lazily resolve the THS provider singleton."""
    return get_provider("ths")


def _median_positive(values: list[float | None]) -> float | None:
    """计算列表中正值的中位数。

    Param:
        values: 数值列表，允许 None
    Return:
        正值中位数，无正值时返回 None
    """
    series = sorted(value for value in values if value is not None and math.isfinite(value) and value > 0)
    if not series:
        return None
    mid = len(series) // 2
    if len(series) % 2 == 1:
        return round(series[mid], 4)
    return round((series[mid - 1] + series[mid]) / 2, 4)


def _parse_report_date(value: object) -> date | None:
    text = str(value or "").strip()[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _row_metric(row: dict, aliases: tuple[str, ...]) -> float | None:
    for alias in aliases:
        value = safe_float(row.get(alias))
        if value is not None and math.isfinite(value):
            return value
    return None


def _derive_ttm_report_metric(
    rows: list[dict],
    aliases: tuple[str, ...],
    report_date: str | None,
) -> tuple[float | None, str]:
    """按“本期累计 + 上年全年 - 上年同期”推导 TTM。"""
    current_date = _parse_report_date(report_date)
    if current_date is None:
        return None, "unavailable"

    values_by_date = {
        parsed: value
        for row in rows
        if (parsed := _parse_report_date(row.get("REPORT_DATE") or row.get("REPORT_DATE_NAME"))) is not None
        if (value := _row_metric(row, aliases)) is not None
    }
    current_value = values_by_date.get(current_date)
    if current_value is None:
        return None, "unavailable"
    if current_date.month == 12 and current_date.day == 31:
        return current_value, "reported_annual"

    prior_annual = values_by_date.get(date(current_date.year - 1, 12, 31))
    prior_comparable = values_by_date.get(date(current_date.year - 1, current_date.month, current_date.day))
    if prior_annual is not None and prior_comparable is not None:
        ttm_value = current_value + prior_annual - prior_comparable
        return (ttm_value, "reported_ttm") if math.isfinite(ttm_value) else (None, "unavailable")
    annualized_value = _annualize_report_metric(current_value, current_date.isoformat())
    return (annualized_value, "annualized_fallback") if annualized_value is not None else (None, "unavailable")


def _annual_metric_cagr(
    rows: list[dict],
    aliases: tuple[str, ...],
    report_date: str | None = None,
) -> tuple[float | None, int | None]:
    values_by_year = {
        parsed.year: value
        for row in rows
        if (parsed := _parse_report_date(row.get("REPORT_DATE") or row.get("REPORT_DATE_NAME"))) is not None
        and parsed.month == 12
        and parsed.day == 31
        if (value := _row_metric(row, aliases)) is not None and value > 0
    }
    if not values_by_year:
        return None, None

    latest_year = max(values_by_year)
    current_date = _parse_report_date(report_date)
    if current_date is not None and current_date.year - latest_year > 2:
        return None, None

    latest_value = values_by_year[latest_year]
    for years in (3, 2):
        initial_value = values_by_year.get(latest_year - years)
        if initial_value is not None and initial_value > 0:
            ratio = latest_value / initial_value
            if not math.isfinite(ratio):
                continue
            growth_rate = ratio ** (1 / years) - 1
            if math.isfinite(growth_rate):
                return growth_rate, years
    return None, None


def _derive_normalized_dcf_growth(
    profit_rows: list[dict],
    revenue_yoy: float | None,
    net_profit_yoy: float | None,
    report_date: str | None = None,
) -> tuple[float, str, float]:
    """优先使用年度收入和利润 CAGR，缺失时回退到最新一期同比。"""
    revenue_cagr, revenue_years = _annual_metric_cagr(
        profit_rows,
        ("TOTAL_OPERATE_INCOME", "OPERATE_INCOME", "TOTAL_REVENUE"),
        report_date,
    )
    profit_cagr, profit_years = _annual_metric_cagr(
        profit_rows,
        ("PARENT_NETPROFIT", "NET_PROFIT"),
        report_date,
    )
    annual_growth = [value for value in (revenue_cagr, profit_cagr) if value is not None]
    if annual_growth:
        growth_rate = sum(sorted(annual_growth)[(len(annual_growth) - 1) // 2 : len(annual_growth) // 2 + 1]) / (
            2 if len(annual_growth) == 2 else 1
        )
        periods = sorted({years for years in (revenue_years, profit_years) if years is not None})
        period_text = "/".join(str(years) for years in periods)
        metric_text = "营收与净利润" if len(annual_growth) == 2 else "营收或净利润"
        return (
            max(-0.05, min(growth_rate, 0.15)),
            f"{metric_text}近 {period_text} 年 CAGR",
            1.0 if len(annual_growth) == 2 else 0.8,
        )

    latest_growth = [
        value / 100 for value in (revenue_yoy, net_profit_yoy) if value is not None and math.isfinite(value)
    ]
    if latest_growth:
        growth_rate = sum(latest_growth) / len(latest_growth)
        return (
            max(-0.05, min(growth_rate, 0.15)),
            "缺少有效年度历史，采用最新一期同比均值",
            0.65 if len(latest_growth) == 2 else 0.5,
        )
    return 0.03, "缺少有效增长数据，采用 3% 默认增速", 0.2


def _robust_peer_metric(values: list[float | None]) -> tuple[float | None, PeerMetricStats]:
    """用 MAD 剔除极端同行倍数，并返回中位数及样本统计。"""
    valid = [value for value in values if value is not None and math.isfinite(value) and value > 0]
    if not valid:
        return None, PeerMetricStats()

    filtered = valid
    if len(valid) >= 4:
        center = _median_positive(valid)
        deviations = sorted(abs(value - center) for value in valid) if center is not None else []
        mad = None
        if deviations:
            mid = len(deviations) // 2
            mad = deviations[mid] if len(deviations) % 2 else (deviations[mid - 1] + deviations[mid]) / 2
        if center is not None and mad not in (None, 0):
            threshold = 3.0 * 1.4826 * mad
            filtered = [value for value in valid if abs(value - center) <= threshold]

    sample_size = len(filtered)
    excluded_count = len(values) - sample_size
    confidence_score = min(1.0, sample_size / 5)
    if sample_size < 2:
        confidence_score *= 0.5
    return (
        _median_positive(filtered),
        PeerMetricStats(
            sample_size=sample_size,
            excluded_count=excluded_count,
            confidence_score=round(confidence_score, 4),
        ),
    )


def _normalize_growth_rate(value: float | None) -> float:
    """将历史同比百分点归一化到小数形式并限制在 0-15% 区间。

    Param:
        value: 历史同比增长率，单位为百分点
    Return:
        归一化后的小数增长率
    """
    if value is None or not math.isfinite(value):
        return 0.03
    rate = value / 100
    return max(0.0, min(rate, 0.15))


def _normalize_peg_growth_rate(
    value: float | None,
    *,
    percentage_points: bool = False,
) -> float | None:
    """归一化 PEG 用增长率，过低或异常时返回 None。

    Param:
        value: 增长率
        percentage_points: 输入是否为百分点；否则按小数处理
    Return:
        归一化后的小数增长率，不满足条件时返回 None
    """
    if value is None or not math.isfinite(value):
        return None
    rate = value / 100 if percentage_points else value
    if not math.isfinite(rate) or rate <= 0.03:
        return None
    return min(rate, 0.50)


def _parse_forecast_year(value: object) -> int | None:
    """从字符串中解析出 4 位年份数字。

    Param:
        value: 任意值，会先转换为字符串
    Return:
        年份整数，未匹配到时返回 None
    """
    match = re.search(r"\d{4}", str(value or ""))
    if match is None:
        return None
    return int(match.group(0))


def _select_forecast(forecasts: list[InstitutionForecast], metric: str, min_year: int) -> InstitutionForecast | None:
    """从机构预测中挑选指定指标和最小年份的最优条目。

    Param:
        forecasts: 机构预测列表
        metric: 指标名（如 EPS）
        min_year: 最低年份
    Return:
        优先选取年份较近、机构数较多的预测，未命中返回 None
    """
    candidates = []
    for forecast in forecasts:
        year = _parse_forecast_year(forecast.year)
        if forecast.metric != metric or year is None or year < min_year:
            continue
        if forecast.mean_value is None or not math.isfinite(forecast.mean_value) or forecast.mean_value <= 0:
            continue
        if forecast.institution_count is not None and (
            not math.isfinite(forecast.institution_count) or forecast.institution_count < 0
        ):
            continue
        candidates.append((year, -(forecast.institution_count or 0), forecast))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]))
    return candidates[0][2]


def _forecast_confidence_adjustment(forecast: InstitutionForecast) -> float:
    """按机构数量与预测离散度计算置信度调整值。

    Param:
        forecast: 单条机构预测
    Return:
        置信度调整数（负数表示降低）
    """
    adjustment = 0.0
    institution_count = forecast.institution_count or 0
    if not math.isfinite(institution_count) or institution_count < 0:
        institution_count = 0
    if institution_count < 2:
        adjustment -= 0.15
    elif institution_count < 5:
        adjustment -= 0.08
    forecast_range = (forecast.min_value, forecast.mean_value, forecast.max_value)
    if all(value is not None and math.isfinite(value) for value in forecast_range) and forecast.mean_value != 0:
        if (forecast.max_value - forecast.min_value) / abs(forecast.mean_value) > 0.6:
            adjustment -= 0.12
    return adjustment


def _confidence_text(score: float) -> str:
    """将置信度数值映射为 high/medium/low 文本。

    Param:
        score: 置信度数值
    Return:
        置信度文本标签
    """
    if score >= 0.75:
        return "high"
    if score >= 0.5:
        return "medium"
    return "low"


def _value_range(
    per_share_value: float | None, confidence_score: float | None, extra_spread: float = 0.0
) -> list[float] | None:
    """按置信度生成公允价值上下区间。

    Param:
        per_share_value: 每股公允价值
        confidence_score: 置信度数值
        extra_spread: 额外宽幅
    Return:
        [下限, 上限] 列表，缺失输入时返回 None
    """
    if per_share_value is None or not math.isfinite(per_share_value):
        return None
    confidence = 0.5 if confidence_score is None else confidence_score
    if not math.isfinite(confidence):
        confidence = 0.5
    confidence = max(0.0, min(confidence, 1.0))
    if not math.isfinite(extra_spread):
        extra_spread = 0.0
    spread = (0.12 if confidence >= 0.75 else 0.18 if confidence >= 0.5 else 0.25) + extra_spread
    endpoints = (
        per_share_value * (1 - spread),
        per_share_value * (1 + spread),
    )
    if not all(math.isfinite(endpoint) for endpoint in endpoints):
        return None
    return [round(endpoint, 2) for endpoint in endpoints]


def _fallback_target_multiple(
    current_multiple: float | None, percentile: float | None
) -> tuple[float | None, str | None]:
    """同行锚缺失时拒绝由当前倍数循环推导目标倍数。

    Param:
        current_multiple: 当前倍数
        percentile: 历史百分位
    Return:
        (目标倍数, 依据说明) 元组
    """
    if current_multiple is None or current_multiple <= 0:
        return None, "当前倍数与独立同行锚均不可用"
    percentile_note = f"，当前处于近三年 {percentile:.1f}% 分位" if percentile is not None else ""
    return None, f"缺少独立同行估值锚{percentile_note}"


def _derive_ttm_basis(
    market_cap: float | None, current_multiple: float | None, fallback_metric: float | None
) -> float | None:
    """根据市值与倍数反推 TTM 基础指标。

    Param:
        market_cap: 总市值
        current_multiple: 当前倍数
        fallback_metric: 缺失时使用的回退值
    Return:
        TTM 基础指标，全部缺失时返回 None
    """
    if (
        market_cap is not None
        and math.isfinite(market_cap)
        and market_cap > 0
        and current_multiple is not None
        and math.isfinite(current_multiple)
        and current_multiple > 0
    ):
        value = market_cap / current_multiple
        if math.isfinite(value):
            return value
    return fallback_metric if fallback_metric is not None and math.isfinite(fallback_metric) else None


def _annualize_report_metric(value: float | None, report_date: str | None) -> float | None:
    """按报告期将单季度/半年度指标年化。

    Param:
        value: 报告期指标值
        report_date: 报告期字符串
    Return:
        年化后的指标值
    """
    if value is None or not math.isfinite(value):
        return None
    annualized_value = value
    if not report_date:
        return annualized_value
    text = str(report_date)
    if "03-31" in text or "一季" in text:
        annualized_value = value * 4
    elif "06-30" in text or "中报" in text:
        annualized_value = value * 2
    elif "09-30" in text or "三季" in text:
        annualized_value = value * 4 / 3
    return annualized_value if math.isfinite(annualized_value) else None


def _current_peg(current_pe: float | None, growth_rate: float | None) -> float | None:
    """根据当前 PE 与增长率计算当前 PEG。

    Param:
        current_pe: 当前 PE
        growth_rate: 增长率（小数形式）
    Return:
        当前 PEG，数据无效时返回 None
    """
    if (
        current_pe is None
        or not math.isfinite(current_pe)
        or current_pe <= 0
        or growth_rate is None
        or not math.isfinite(growth_rate)
        or growth_rate <= 0
    ):
        return None
    peg = current_pe / (growth_rate * 100)
    return round(peg, 4) if math.isfinite(peg) else None
