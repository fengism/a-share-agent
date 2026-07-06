import logging

import pandas as pd

from app.models.stock import DCFValuationResult, InstitutionForecast, StockBasicInfo, ValuationDetail, ValuationFundamentals, ValuationMethodResult, ValuationMultiples, ValuationPeer, ValuationPeerSummary, ValuationPercentiles, ValuationProfile
from app.services.providers import get_provider
from app.utils.cache import cache, dated_cache_key
from app.utils.rate_limiter import call_blocking, akshare_semaphore, ths_semaphore
from app.utils.data_clean import safe_float

logger = logging.getLogger(__name__)

import re

FINANCIAL_KEYWORDS = ("银行", "保险", "证券", "券商", "多元金融", "金融")
CYCLICAL_KEYWORDS = ("煤炭", "有色", "钢铁", "化工", "航运", "石油", "建材", "矿", "金属")
GROWTH_KEYWORDS = ("半导体", "软件", "电子", "计算机", "医药", "新能源", "机器人", "通信", "芯片")
STABLE_KEYWORDS = ("白酒", "食品", "饮料", "公用事业", "电力", "高速", "运营商", "水务", "燃气")

def _normalize_industry_text(basic_info: StockBasicInfo) -> str:
    """合并一级和二级行业名称为单一字符串。

    Param:
        basic_info: 股票基本信息
    Return:
        以空格连接的行业名称
    """
    names = [
        basic_info.first_industry.name if basic_info.first_industry else "",
        basic_info.second_industry.name if basic_info.second_industry else "",
    ]
    return " ".join(name for name in names if name)

def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    """判断文本是否包含任一关键词。

    Param:
        text: 待检查文本
        keywords: 关键词元组
    Return:
        命中任一关键词返回 True
    """
    return any(keyword in text for keyword in keywords)

def _calc_roe(fundamentals: ValuationFundamentals) -> float | None:
    """根据净利润和股东权益计算 ROE。

    Param:
        fundamentals: 估值基本面数据
    Return:
        ROE 小数值，数据不足时返回 None
    """
    if fundamentals.net_profit is None or fundamentals.shareholders_equity in (None, 0):
        return None
    return fundamentals.net_profit / fundamentals.shareholders_equity

def _is_loss_making(fundamentals: ValuationFundamentals) -> bool:
    """判断公司是否处于亏损状态。

    Param:
        fundamentals: 估值基本面数据
    Return:
        净利润或扣非净利润为负时返回 True
    """
    return any(value is not None and value < 0 for value in [fundamentals.net_profit, fundamentals.non_net_profit])

def _classify_stock_profile(basic_info: StockBasicInfo, fundamentals: ValuationFundamentals) -> ValuationProfile:
    """根据行业和财务指标对股票进行画像分类。

    Param:
        basic_info: 股票基本信息
        fundamentals: 估值基本面数据
    Return:
        ValuationProfile 对象，含分类和理由
    """
    industry_text = _normalize_industry_text(basic_info)
    rationale: list[str] = []
    if _is_loss_making(fundamentals):
        rationale.append("净利润或扣非净利润为负，盈利法估值可靠性较低")
        return ValuationProfile(category="loss_making", label="亏损/利润承压类", rationale=rationale)
    if _contains_any(industry_text, FINANCIAL_KEYWORDS):
        rationale.append(f"行业属性偏金融：{industry_text}")
        return ValuationProfile(category="financial", label="金融类", rationale=rationale)
    if _contains_any(industry_text, CYCLICAL_KEYWORDS):
        rationale.append(f"行业属性偏周期：{industry_text}")
        return ValuationProfile(category="cyclical", label="周期类", rationale=rationale)
    revenue_growth = _normalize_growth_rate(fundamentals.revenue_yoy)
    profit_growth = _normalize_growth_rate(fundamentals.net_profit_yoy)
    if _contains_any(industry_text, GROWTH_KEYWORDS) or revenue_growth >= 0.12 or profit_growth >= 0.12:
        rationale.append(f"行业或增速具备成长属性：{industry_text or '行业数据不足'}")
        return ValuationProfile(category="growth", label="成长类", rationale=rationale)
    if _contains_any(industry_text, STABLE_KEYWORDS) or (fundamentals.operating_cashflow is not None and fundamentals.operating_cashflow > 0 and fundamentals.net_profit is not None and fundamentals.net_profit > 0):
        rationale.append(f"现金流和利润为正，行业或经营特征偏稳定：{industry_text or '行业数据不足'}")
        return ValuationProfile(category="stable", label="稳定经营类", rationale=rationale)
    rationale.append("未匹配到强行业特征，采用通用估值权重")
    return ValuationProfile(category="general", label="通用类", rationale=rationale)

def _target_peg_by_profile(profile: ValuationProfile) -> float | None:
    """根据股票画像选择 PEG 目标倍数。

    Param:
        profile: 估值画像对象
    Return:
        目标 PEG，亏损画像返回 None
    """
    target_by_category = {
        "growth": 1.1,
        "stable": 1.0,
        "general": 1.0,
        "cyclical": 0.8,
        "financial": 0.8,
        "loss_making": None,
    }
    return target_by_category.get(profile.category, 1.0)

def _cap_peg_target_pe(raw_target_pe: float, current_pe: float | None, peer_pe_median: float | None) -> tuple[float, list[str]]:
    """对 PEG 推导的目标 PE 设置上下限约束。

    Param:
        raw_target_pe: 原始目标 PE
        current_pe: 当前 PE
        peer_pe_median: 同行 PE 中位数
    Return:
        (受约束的目标 PE, 约束注释列表) 元组
    """
    capped = max(5.0, min(raw_target_pe, 60.0))
    notes: list[str] = []
    if capped != raw_target_pe:
        notes.append("目标 PE 按 5-60 倍区间约束")
    if peer_pe_median is not None and peer_pe_median > 0:
        peer_cap = peer_pe_median * 1.5
        if capped > peer_cap:
            capped = peer_cap
            notes.append("目标 PE 按同行 PE 中位数 1.5 倍约束")
    if current_pe is not None and current_pe > 0:
        current_cap = current_pe * 1.5
        if capped > current_cap:
            capped = current_cap
            notes.append("目标 PE 按当前 PE 1.5 倍约束")
    return round(capped, 4), notes

def _derive_peg_growth_rate(forecasts: list[InstitutionForecast], net_profit_ttm: float | None, total_shares: float | None, net_profit_yoy: float | None) -> tuple[float | None, str | None, float]:
    """综合机构预测与历史同比推导 PEG 用增长率。

    Param:
        forecasts: 机构预测列表
        net_profit_ttm: TTM 净利润
        total_shares: 总股本
        net_profit_yoy: 净利润同比增长率
    Return:
        (增长率, 增长依据描述, 置信度) 元组
    """
    current_year = datetime.now().year
    if net_profit_ttm is not None and net_profit_ttm > 0 and total_shares not in (None, 0):
        ttm_eps = net_profit_ttm / total_shares
        forecast = _select_forecast(forecasts, "EPS", current_year)
        forecast_year = _parse_forecast_year(forecast.year) if forecast is not None else None
        if forecast is not None and forecast.mean_value is not None and forecast_year is not None and ttm_eps > 0:
            years_forward = max(forecast_year - current_year + 1, 1)
            growth_rate = _normalize_peg_growth_rate((forecast.mean_value / ttm_eps) ** (1 / years_forward) - 1)
            if growth_rate is not None:
                confidence_score = max(0.3, min(0.8, 0.72 + _forecast_confidence_adjustment(forecast)))
                basis = f"机构 EPS 一致预期推导增长率 {growth_rate * 100:.1f}%（{forecast.year}，机构数 {forecast.institution_count or 0:g}）"
                return growth_rate, basis, confidence_score

    growth_rate = _normalize_peg_growth_rate(net_profit_yoy)
    if growth_rate is not None:
        return growth_rate, f"历史净利润同比增长率 {growth_rate * 100:.1f}%", 0.45
    return None, None, 0.3

