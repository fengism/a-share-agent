"""估值计算通用辅助函数。"""

import logging
import re

from app.infrastructure.providers.registry import get_provider
from app.market_data.stock.valuation.schemas import InstitutionForecast

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
    series = sorted(value for value in values if value is not None and value > 0)
    if not series:
        return None
    mid = len(series) // 2
    if len(series) % 2 == 1:
        return round(series[mid], 4)
    return round((series[mid - 1] + series[mid]) / 2, 4)

def _normalize_growth_rate(value: float | None) -> float:
    """将增长率归一化到小数形式并限制在 0-15% 区间。

    Param:
        value: 增长率，可能为百分数或小数
    Return:
        归一化后的小数增长率
    """
    if value is None:
        return 0.03
    rate = value / 100 if abs(value) > 1 else value
    return max(0.0, min(rate, 0.15))

def _normalize_peg_growth_rate(value: float | None) -> float | None:
    """归一化 PEG 用增长率，过低或异常时返回 None。

    Param:
        value: 增长率，可能为百分数或小数
    Return:
        归一化后的小数增长率，不满足条件时返回 None
    """
    if value is None:
        return None
    rate = value / 100 if abs(value) > 1 else value
    if rate <= 0.03:
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
        if forecast.mean_value is None or forecast.mean_value <= 0:
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
    if institution_count < 2:
        adjustment -= 0.15
    elif institution_count < 5:
        adjustment -= 0.08
    if forecast.min_value is not None and forecast.max_value is not None and forecast.mean_value not in (None, 0):
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

def _value_range(per_share_value: float | None, confidence_score: float | None, extra_spread: float = 0.0) -> list[float] | None:
    """按置信度生成公允价值上下区间。

    Param:
        per_share_value: 每股公允价值
        confidence_score: 置信度数值
        extra_spread: 额外宽幅
    Return:
        [下限, 上限] 列表，缺失输入时返回 None
    """
    if per_share_value is None:
        return None
    confidence = confidence_score or 0.5
    spread = (0.12 if confidence >= 0.75 else 0.18 if confidence >= 0.5 else 0.25) + extra_spread
    return [round(per_share_value * (1 - spread), 2), round(per_share_value * (1 + spread), 2)]

def _fallback_target_multiple(current_multiple: float | None, percentile: float | None) -> tuple[float | None, str | None]:
    """当无同行数据时按历史百分位推导目标倍数。

    Param:
        current_multiple: 当前倍数
        percentile: 历史百分位
    Return:
        (目标倍数, 依据说明) 元组
    """
    if current_multiple is None or current_multiple <= 0:
        return None, None
    if percentile is None:
        return round(current_multiple, 4), "当前倍数"
    if percentile >= 80:
        return round(current_multiple * 0.85, 4), "当前倍数按历史高位折价"
    if percentile <= 20:
        return round(current_multiple * 1.15, 4), "当前倍数按历史低位修复"
    return round(current_multiple, 4), "当前倍数"

def _derive_ttm_basis(market_cap: float | None, current_multiple: float | None, fallback_metric: float | None) -> float | None:
    """根据市值与倍数反推 TTM 基础指标。

    Param:
        market_cap: 总市值
        current_multiple: 当前倍数
        fallback_metric: 缺失时使用的回退值
    Return:
        TTM 基础指标，全部缺失时返回 None
    """
    if market_cap not in (None, 0) and current_multiple not in (None, 0) and current_multiple > 0:
        return market_cap / current_multiple
    return fallback_metric

def _annualize_report_metric(value: float | None, report_date: str | None) -> float | None:
    """按报告期将单季度/半年度指标年化。

    Param:
        value: 报告期指标值
        report_date: 报告期字符串
    Return:
        年化后的指标值
    """
    if value is None:
        return None
    if not report_date:
        return value
    text = str(report_date)
    if "03-31" in text or "一季" in text:
        return value * 4
    if "06-30" in text or "中报" in text:
        return value * 2
    if "09-30" in text or "三季" in text:
        return value * 4 / 3
    return value

def _current_peg(current_pe: float | None, growth_rate: float | None) -> float | None:
    """根据当前 PE 与增长率计算当前 PEG。

    Param:
        current_pe: 当前 PE
        growth_rate: 增长率（小数形式）
    Return:
        当前 PEG，数据无效时返回 None
    """
    if current_pe is None or current_pe <= 0 or growth_rate is None or growth_rate <= 0:
        return None
    return round(current_pe / (growth_rate * 100), 4)
