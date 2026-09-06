"""股票基础资料字段归一化与来源合并。"""

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from app.core.market import SymbolFormats, safe_float, safe_string
from app.domain.stock import StockConcept, StockConceptInfo
from app.financial_data.stock.profile.schemas import StockBasicInfo
from app.financial_data.stock.profile.sources import (
    EASTMONEY_STOCK_PROFILE,
    STOCK_CONCEPT_MAPPING,
    SW_INDUSTRY_CLASSIFICATION,
    TDX_HTTP_FINANCE,
    TDX_HTTP_STOCK_QUOTE,
    TENCENT_STOCK_CONCEPTS,
    TENCENT_STOCK_QUOTE,
    source_contracts,
)


@dataclass(frozen=True)
class BasicInfoInputs:
    eastmoney_profile: dict[str, Any]
    exchange_profile: dict[str, Any]
    exchange_source_id: str
    spot_row: pd.Series | None
    spot_source_id: str
    name_map: dict[str, str]
    name_map_source_id: str
    stock_concepts: StockConceptInfo
    concepts_available: bool
    tencent_quote: dict[str, Any]
    tdx_http_quote: dict[str, Any] = field(default_factory=dict)
    tdx_http_finance: dict[str, Any] = field(default_factory=dict)
    sw_industry_record: dict[str, Any] | None = None
    stock_concept_record: dict[str, Any] | None = None


def format_listing_date(value: Any) -> str | None:
    """将 YYYYMMDD 或其他格式的上市日期统一格式化为 YYYY-MM-DD。"""
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    return text or None


def _pick_text(
    field_sources: dict[str, str],
    field_name: str,
    *candidates: tuple[Any, str],
) -> str | None:
    for value, source_id in candidates:
        text = safe_string(value)
        if text is None:
            continue
        field_sources[field_name] = source_id
        return text
    return None


def _pick_number(
    field_sources: dict[str, str],
    field_name: str,
    *candidates: tuple[Any, str],
    allow_zero: bool = False,
) -> float | None:
    for value, source_id in candidates:
        number = safe_float(value)
        if number is None or (number == 0 and not allow_zero):
            continue
        field_sources[field_name] = source_id
        return number
    return None


def _estimate_shares_from_spot(spot_row: pd.Series | None, market_cap_field: str) -> float | None:
    if spot_row is None:
        return None
    market_cap = safe_float(spot_row.get(market_cap_field))
    price = safe_float(spot_row.get("最新价"))
    if market_cap in (None, 0) or price in (None, 0):
        return None
    return market_cap / price



_EASTMONEY_PROFILE_FILLABLE_FIELDS = (
    "name",
    "listing_date",
    "total_shares",
    "circulating_shares",
    "market_cap",
    "float_market_cap",
    "current_price",
    "first_industry",
)


def missing_eastmoney_profile_fields(result: StockBasicInfo) -> list[str]:
    """Return fields that EastMoney profile can still fill after preferred sources merge."""
    return [
        field_name
        for field_name in _EASTMONEY_PROFILE_FILLABLE_FIELDS
        if field_name not in result.field_sources
    ]

def build_basic_info(symbol: SymbolFormats, inputs: BasicInfoInputs) -> StockBasicInfo:
    """按显式优先级合并基础资料，并记录每个字段的实际来源。"""
    field_sources: dict[str, str] = {}
    profile = inputs.eastmoney_profile
    exchange = inputs.exchange_profile
    quote = inputs.tencent_quote
    tdx_quote = inputs.tdx_http_quote
    tdx_finance = inputs.tdx_http_finance
    spot = inputs.spot_row
    spot_source = inputs.spot_source_id
    exchange_source = inputs.exchange_source_id

    name = _pick_text(
        field_sources,
        "name",
        (exchange.get("name"), exchange_source),
        (quote.get("name"), TENCENT_STOCK_QUOTE.id),
        (tdx_quote.get("name"), TDX_HTTP_STOCK_QUOTE.id),
        (profile.get("name"), EASTMONEY_STOCK_PROFILE.id),
        (spot.get("名称") if spot is not None else None, spot_source),
        (inputs.name_map.get(symbol.raw), inputs.name_map_source_id),
    )
    listing_date = _pick_text(
        field_sources,
        "listing_date",
        (exchange.get("listing_date"), exchange_source),
        (format_listing_date(tdx_finance.get("list_date")), TDX_HTTP_FINANCE.id),
        (format_listing_date(profile.get("list_date")), EASTMONEY_STOCK_PROFILE.id),
    )
    total_shares = _pick_number(
        field_sources,
        "total_shares",
        (tdx_finance.get("total_shares"), TDX_HTTP_FINANCE.id),
        (exchange.get("total_shares"), exchange_source),
        (profile.get("total_shares"), EASTMONEY_STOCK_PROFILE.id),
        (_estimate_shares_from_spot(spot, "总市值"), spot_source),
    )
    circulating_shares = _pick_number(
        field_sources,
        "circulating_shares",
        (tdx_finance.get("float_shares"), TDX_HTTP_FINANCE.id),
        (exchange.get("circulating_shares"), exchange_source),
        (profile.get("float_shares"), EASTMONEY_STOCK_PROFILE.id),
        (_estimate_shares_from_spot(spot, "流通市值"), spot_source),
    )
    pe_ttm = _pick_number(
        field_sources,
        "pe_ttm",
        (quote.get("pe_ttm"), TENCENT_STOCK_QUOTE.id),
        (spot.get("市盈率-动态") if spot is not None else None, spot_source),
    )
    pb = _pick_number(
        field_sources,
        "pb",
        (quote.get("pb"), TENCENT_STOCK_QUOTE.id),
        (spot.get("市净率") if spot is not None else None, spot_source),
    )
    market_cap = _pick_number(
        field_sources,
        "market_cap",
        (quote.get("mcap"), TENCENT_STOCK_QUOTE.id),
        (profile.get("mcap"), EASTMONEY_STOCK_PROFILE.id),
        (spot.get("总市值") if spot is not None else None, spot_source),
    )
    float_market_cap = _pick_number(
        field_sources,
        "float_market_cap",
        (quote.get("float_mcap"), TENCENT_STOCK_QUOTE.id),
        (profile.get("float_mcap"), EASTMONEY_STOCK_PROFILE.id),
        (spot.get("流通市值") if spot is not None else None, spot_source),
    )
    turnover_pct = _pick_number(
        field_sources,
        "turnover_pct",
        (quote.get("turnover_pct"), TENCENT_STOCK_QUOTE.id),
        (spot.get("换手率") if spot is not None else None, spot_source),
        allow_zero=True,
    )
    current_price = _pick_number(
        field_sources,
        "current_price",
        (quote.get("price"), TENCENT_STOCK_QUOTE.id),
        (tdx_quote.get("price"), TDX_HTTP_STOCK_QUOTE.id),
        (profile.get("price"), EASTMONEY_STOCK_PROFILE.id),
        (spot.get("最新价") if spot is not None else None, spot_source),
    )
    pe_static = _pick_number(
        field_sources,
        "pe_static",
        (quote.get("pe_static"), TENCENT_STOCK_QUOTE.id),
    )

    exchange_industry = _pick_text(
        field_sources,
        "exchange_industry",
        (exchange.get("industry"), exchange_source),
    )

    sw_ind = inputs.sw_industry_record
    if sw_ind and sw_ind.get("sw_level1_name"):
        first_industry = StockConcept(code="", name=str(sw_ind["sw_level1_name"]))
        field_sources["first_industry"] = SW_INDUSTRY_CLASSIFICATION.id
    elif inputs.stock_concepts.first_concept is not None:
        first_industry = inputs.stock_concepts.first_concept
        field_sources["first_industry"] = TENCENT_STOCK_CONCEPTS.id
    else:
        industry_name = _pick_text(
            field_sources,
            "first_industry",
            (profile.get("industry"), EASTMONEY_STOCK_PROFILE.id),
        )
        if industry_name:
            first_industry = StockConcept(code="", name=str(industry_name))
        else:
            first_industry = None

    if sw_ind and sw_ind.get("sw_level2_name"):
        second_industry = StockConcept(code="", name=str(sw_ind["sw_level2_name"]))
        field_sources["second_industry"] = SW_INDUSTRY_CLASSIFICATION.id
    elif inputs.stock_concepts.second_concept is not None:
        second_industry = inputs.stock_concepts.second_concept
        field_sources["second_industry"] = TENCENT_STOCK_CONCEPTS.id
    else:
        second_industry = None

    if sw_ind and sw_ind.get("sw_level3_name"):
        third_industry = StockConcept(
            code=str(sw_ind.get("sw_industry_code") or ""),
            name=str(sw_ind["sw_level3_name"]),
        )
        field_sources["third_industry"] = SW_INDUSTRY_CLASSIFICATION.id
    else:
        third_industry = None

    cnp_rec = inputs.stock_concept_record
    if cnp_rec and cnp_rec.get("concepts"):
        concepts = [StockConcept(code=name, name=name) for name in cnp_rec["concepts"]]
        field_sources["concepts"] = STOCK_CONCEPT_MAPPING.id
    elif inputs.concepts_available:
        concepts = inputs.stock_concepts.concepts
        field_sources["concepts"] = TENCENT_STOCK_CONCEPTS.id
    else:
        concepts = None

    return StockBasicInfo(
        code=symbol.raw,
        name=str(name or symbol.raw),
        listing_date=listing_date,
        total_shares=total_shares,
        circulating_shares=circulating_shares,
        pe_ttm=pe_ttm,
        pb=pb,
        market_cap=market_cap,
        float_market_cap=float_market_cap,
        turnover_pct=turnover_pct,
        exchange_industry=exchange_industry,
        first_industry=first_industry,
        second_industry=second_industry,
        third_industry=third_industry,
        current_price=current_price,
        pe_static=pe_static,
        concepts=concepts,
        data_sources=source_contracts(list(field_sources.values())),
        field_sources=field_sources,
    )
