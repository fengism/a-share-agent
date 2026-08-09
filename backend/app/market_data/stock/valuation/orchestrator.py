import logging

from app.core.cache import cache, dated_cache_key
from app.core.concurrency.rate_limiter import akshare_semaphore, call_blocking
from app.core.market import normalize_code, safe_float
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.market_data.stock.profile.basic_info import get_basic_info
from app.market_data.stock.valuation.helpers import _get_akshare_provider

logger = logging.getLogger(__name__)


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
        df = await provider_gateway.call(
            "akshare",
            "stock_valuation_comparison",
            lambda: call_blocking(
                _get_akshare_provider().fetch_stock_valuation_comparison,
                semaphore=akshare_semaphore,
                symbol=sym.prefixed_upper,
            ),
        )
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
