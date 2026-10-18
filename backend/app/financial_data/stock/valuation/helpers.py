"""估值计算通用辅助函数。"""

import logging
import math
import re
from collections.abc import Sequence
from datetime import date

from app.core.market import safe_float
from app.financial_data.stock.valuation.schemas import (
    InstitutionForecast,
    PeerMetricStats,
    ValuationPeer,
)
from app.infrastructure.providers.registry import get_provider

logger = logging.getLogger(__name__)


def _get_akshare_provider():
    """Lazily resolve the Akshare provider singleton."""
    return get_provider("akshare")


def _get_ths_provider():
    """Lazily resolve the THS provider singleton."""
    return get_provider("ths")


def _median_positive(values: Sequence[float | None]) -> float | None:
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


def _peer_implied_ratios(
    peers: list[ValuationPeer],
    numerator_attr: str,
    denominator_attr: str,
) -> list[float]:
    """由同行估值倍数反推财务比率。

    PB/PE 近似 ROE，PS/PE 近似净利率。同行样本与目标公司使用同一张
    估值比较表，口径一致，无需额外抓取同行财报。

    Param:
        peers: 同行列表
        numerator_attr: 分子字段名（如 pb）
        denominator_attr: 分母字段名（如 pe_ttm）
    Return:
        正且有限的比率列表
    """
    ratios: list[float] = []
    for peer in peers:
        numerator = getattr(peer, numerator_attr, None)
        denominator = getattr(peer, denominator_attr, None)
        if (
            numerator is None
            or denominator is None
            or not math.isfinite(numerator)
            or not math.isfinite(denominator)
            or numerator <= 0
            or denominator <= 0
        ):
            continue
        ratio = numerator / denominator
        if math.isfinite(ratio) and ratio > 0:
            ratios.append(ratio)
    return ratios


def _percentile_positive(values: list[float], quantile: float) -> float | None:
    """计算正值列表的分位数（线性插值）。"""
    series = sorted(value for value in values if math.isfinite(value) and value > 0)
    if not series:
        return None
    position = max(0.0, min(quantile, 1.0)) * (len(series) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return round(series[lower], 6)
    weight = position - lower
    return round(series[lower] * (1 - weight) + series[upper] * weight, 6)


def _peer_quality_benchmark(
    peers: list[ValuationPeer],
    numerator_attr: str,
    denominator_attr: str,
    target_metric: float | None,
) -> tuple[float | None, str | None]:
    """为高盈利质量公司选择更保守的同行质量基准。

    直接拿同行中位数做质量基准，会把行业龙头的估值推到现价的数倍；
    目标公司质量高于同行中位数时，改用同行上四分位作为对标基准，
    只给“优于上四分位”的部分溢价；低于中位数时仍对标中位数。

    Param:
        peers: 同行列表
        numerator_attr: 分子字段名（如 pb）
        denominator_attr: 分母字段名（如 pe_ttm）
        target_metric: 目标公司财务比率
    Return:
        (质量基准, 基准说明) 元组
    """
    ratios = _peer_implied_ratios(peers, numerator_attr, denominator_attr)
    if len(ratios) < 2:
        return None, None
    median = _percentile_positive(ratios, 0.5)
    if median is None:
        return None, None
    if target_metric is not None and math.isfinite(target_metric) and target_metric > median:
        return _percentile_positive(ratios, 0.75), "同行上四分位"
    return median, "同行中位数"


def _cap_target_multiple(
    target_multiple: float | None,
    current_multiple: float | None,
    *,
    label: str,
    max_ratio: float = 1.5,
) -> tuple[float | None, str | None]:
    """用当前倍数给同行目标倍数设置上限，避免同行盈利失真时估值失控。

    Param:
        target_multiple: 同行目标倍数
        current_multiple: 目标公司当前倍数
        label: 倍数名称（PE/PB/PS）
        max_ratio: 目标倍数相对当前倍数的上限
    Return:
        (受约束的目标倍数, 约束说明) 元组
    """
    if (
        target_multiple is None
        or current_multiple is None
        or not math.isfinite(target_multiple)
        or not math.isfinite(current_multiple)
        or target_multiple <= 0
        or current_multiple <= 0
    ):
        return target_multiple, None
    cap = current_multiple * max_ratio
    if target_multiple <= cap:
        return target_multiple, None
    return round(cap, 4), f"目标 {label} 按当前 {label} {max_ratio:.1f} 倍约束"


def _quality_adjusted_multiple(
    base_multiple: float | None,
    stock_metric: float | None,
    peer_metric: float | None,
    *,
    label: str,
    lower: float = 0.4,
    upper: float = 2.5,
    min_peer_metric: float = 0.03,
) -> tuple[float | None, str | None]:
    """按财务质量差异调整同行倍数。

    直接把同行中位数套到高 ROE/高净利率公司上，会系统性低估其价值；
    反之低质量公司会被高估。这里按目标公司与同行的财务比率差异缩放
    目标倍数，并做上下限截断，避免极端值放大。同行比率本身过低
    （例如周期底部全行业微利）时不做调整，否则会把失真倍数放大。

    Param:
        base_multiple: 同行倍数中位数
        stock_metric: 目标公司财务比率（ROE 或净利率）
        peer_metric: 同行财务比率基准
        label: 财务比率名称
        lower: 调整系数下限
        upper: 调整系数上限
        min_peer_metric: 同行比率低于该值时不做质量调整
    Return:
        (调整后倍数, 调整说明) 元组
    """
    if base_multiple is None or not math.isfinite(base_multiple) or base_multiple <= 0:
        return base_multiple, None
    if (
        stock_metric is None
        or peer_metric is None
        or not math.isfinite(stock_metric)
        or not math.isfinite(peer_metric)
        or peer_metric <= 0
    ):
        return base_multiple, None
    if peer_metric < min_peer_metric:
        return base_multiple, f"同行 {label} 过低（{peer_metric * 100:.1f}%），不做质量调整"
    if stock_metric > 0:
        raw_factor = stock_metric / peer_metric
    else:
        raw_factor = 1 + stock_metric / peer_metric
    if not math.isfinite(raw_factor):
        return base_multiple, None
    factor = lower if raw_factor <= 0 else max(lower, min(raw_factor, upper))
    note = f"按 {label} 质量调整 ×{factor:.2f}"
    if abs(factor - raw_factor) > 1e-9:
        note += f"（原始 {raw_factor:.2f}，已截断）"
    return round(base_multiple * factor, 4), note


def _parse_report_date(value: object) -> date | None:
    text = str(value or "").strip()[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _row_metric(row: dict, aliases: tuple[str, ...]) -> float | None:
    for alias in aliases:
        value: float | None = safe_float(row.get(alias))
        if value is not None and math.isfinite(value):
            return value
    return None


def _derive_ttm_report_metric(
    rows: list[dict],
    aliases: tuple[str, ...],
    report_date: str | None,
    yoy: float | None = None,
) -> tuple[float | None, str]:
    """按“本期累计 + 上年全年 - 上年同期”推导 TTM。

    上年同期报告缺失但本期同比可用时，用同比反推上年同期，避免直接
    把半年报/季报简单年化造成季节性失真。
    """
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
    if prior_annual is not None and yoy is not None and math.isfinite(yoy) and yoy > -99.0:
        growth_denominator = 1 + yoy / 100
        if growth_denominator > 0:
            estimated_prior_comparable = current_value / growth_denominator
            if math.isfinite(estimated_prior_comparable):
                ttm_value = current_value + prior_annual - estimated_prior_comparable
                if math.isfinite(ttm_value):
                    return ttm_value, "reported_ttm_yoy_bridge"
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


def _annual_metric_average(
    rows: list[dict],
    aliases: tuple[str, ...],
    years: int = 3,
) -> float | None:
    """计算最近若干年年报指标的平均值，用于周期股的正常化盈利。"""
    values_by_year = {
        parsed.year: value
        for row in rows
        if (parsed := _parse_report_date(row.get("REPORT_DATE") or row.get("REPORT_DATE_NAME"))) is not None
        and parsed.month == 12
        and parsed.day == 31
        if (value := _row_metric(row, aliases)) is not None
    }
    if not values_by_year:
        return None
    latest_year = max(values_by_year)
    values = [
        values_by_year[year]
        for year in range(latest_year - years + 1, latest_year + 1)
        if year in values_by_year
    ]
    if len(values) < 2:
        return None
    average = sum(values) / len(values)
    return average if math.isfinite(average) else None


def _latest_annual_metric(rows: list[dict], aliases: tuple[str, ...]) -> float | None:
    """取最近一期年报指标。"""
    values_by_year = {
        parsed.year: value
        for row in rows
        if (parsed := _parse_report_date(row.get("REPORT_DATE") or row.get("REPORT_DATE_NAME"))) is not None
        and parsed.month == 12
        and parsed.day == 31
        if (value := _row_metric(row, aliases)) is not None
    }
    if not values_by_year:
        return None
    value = values_by_year[max(values_by_year)]
    return value if math.isfinite(value) else None


def _normalized_metric_basis(
    rows: list[dict],
    aliases: tuple[str, ...],
    ttm_value: float | None,
) -> tuple[float | None, str | None]:
    """构造周期股正常化盈利基准。

    优先使用近三年年报平均；历史期数不足时，用最近一期年报与 TTM
    的平均值做两点平滑，仍比直接使用峰值/低谷 TTM 稳定。

    Param:
        rows: 利润表行
        aliases: 指标别名
        ttm_value: 当前 TTM 指标
    Return:
        (正常化指标, 口径说明) 元组
    """
    average = _annual_metric_average(rows, aliases, 3)
    if average is not None:
        return average, "近三年平均"
    latest_annual = _latest_annual_metric(rows, aliases)
    if (
        latest_annual is not None
        and ttm_value is not None
        and math.isfinite(latest_annual)
        and math.isfinite(ttm_value)
    ):
        smoothed = (latest_annual + ttm_value) / 2
        return (smoothed, "近一年与 TTM 平均") if math.isfinite(smoothed) else (None, None)
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
    if not math.isfinite(rate) or rate <= 0.08:
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
    if all(value is not None and math.isfinite(value) for value in forecast_range) and forecast.mean_value not in (None, 0):
        assert forecast.min_value is not None and forecast.max_value is not None and forecast.mean_value is not None
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
