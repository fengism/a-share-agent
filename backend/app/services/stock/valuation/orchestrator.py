import logging

import pandas as pd

from app.models.stock import DCFValuationResult, InstitutionForecast, StockBasicInfo, ValuationDetail, ValuationFundamentals, ValuationMethodResult, ValuationMultiples, ValuationPeer, ValuationPeerSummary, ValuationPercentiles, ValuationProfile
from app.services.providers import get_provider
from app.utils.cache import cache, dated_cache_key
from app.utils.rate_limiter import call_blocking, akshare_semaphore, ths_semaphore
from app.utils.data_clean import safe_float

logger = logging.getLogger(__name__)

import asyncio
from datetime import datetime
from app.services.stock.basic_info import get_basic_info
from app.services.stock.financials import get_financial_metrics
from app.utils.symbol_utils import normalize_code

from app.services.stock.valuation.helpers import (
    _median_positive, _normalize_growth_rate, _normalize_peg_growth_rate,
    _parse_forecast_year, _select_forecast, _forecast_confidence_adjustment,
    _confidence_text, _value_range, _fallback_target_multiple,
    _derive_ttm_basis, _annualize_report_metric, _current_peg,
    _get_akshare_provider, _get_ths_provider,
)
from app.services.stock.valuation.profile import (
    _normalize_industry_text, _contains_any, _calc_roe, _is_loss_making,
    _classify_stock_profile, _target_peg_by_profile, _cap_peg_target_pe,
    _derive_peg_growth_rate,
)
from app.services.stock.valuation.methods import (
    _build_multiple_valuation, _build_peg_valuation, _build_dcf_valuation,
)
from app.services.stock.valuation.blending import (
    _base_method_weights, _adjust_method_weights, _apply_weights,
    _build_blended_value, _build_blended_range,
    _build_valuation_view, _build_valuation_summary,
)

async def get_valuation(code: str) -> dict:
    """获取股票当前估值与同行对比，并在缺失时回退到基础信息。

    Param:
        code: 股票代码
    Return:
        包含 code/pe_ttm/pb/ps_ttm/peers 字段的字典
    """
    sym = normalize_code(code)
    cache_key = dated_cache_key("valuation", sym.raw)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    result: dict = {"code": sym.raw, "pe_ttm": None, "pb": None, "ps_ttm": None, "peers": []}

    try:
        df = await call_blocking(_get_akshare_provider().fetch_stock_valuation_comparison, semaphore=akshare_semaphore, symbol=sym.prefixed_upper)
        if len(df) > 0:
            row = df.iloc[0]
            result["pe_ttm"] = safe_float(row.get("市盈率-TTM"))
            result["pb"] = safe_float(row.get("市净率-MRQ"))
            result["ps_ttm"] = safe_float(row.get("市销率-TTM"))
        peers = []
        for _, row in df.head(10).iterrows():
            peer_name = str(row.get("简称", "")).strip()
            peer_code = str(row.get("代码", "")).strip()
            if not peer_code or peer_code in {"行业中值", "行业平均"} or peer_name in {"行业中值", "行业平均"}:
                continue
            peers.append(
                {
                    "name": peer_name,
                    "code": peer_code,
                    "pe_ttm": safe_float(row.get("市盈率-TTM")),
                    "pb": safe_float(row.get("市净率-MRQ")),
                    "ps_ttm": safe_float(row.get("市销率-TTM")),
                }
            )
        result["peers"] = peers
    except Exception:
        logger.info(f"估值数据获取失败，回退到基础信息: {sym.raw}")

    if result["pe_ttm"] is None or result["pb"] is None:
        try:
            basic_info = await get_basic_info(code)
            if result["pe_ttm"] is None:
                result["pe_ttm"] = basic_info.pe_ttm
            if result["pb"] is None:
                result["pb"] = basic_info.pb
        except Exception:
            logger.info(f"基础信息估值回退失败: {sym.raw}")

    cache.set(cache_key, result, ttl=86400)
    return result

