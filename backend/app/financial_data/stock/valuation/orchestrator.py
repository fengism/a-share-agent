import logging

from app.core.cache import analysis_cache as cache
from app.core.cache import dated_cache_key
from app.core.cache_policies import VALUATION
from app.core.concurrency.rate_limiter import akshare_semaphore, call_blocking
from app.core.concurrency.singleflight import AsyncSingleFlight
from app.core.market import is_hk_code, normalize_code, safe_float
from app.financial_data.stock.profile.basic_info import get_basic_info
from app.financial_data.stock.valuation.helpers import _get_akshare_provider
from app.financial_data.stock.valuation.schemas import StockValuation, ValuationPeer
from app.infrastructure.providers.provider_gateway import provider_gateway

logger = logging.getLogger(__name__)
_valuation_singleflight = AsyncSingleFlight[StockValuation]()
_VALUATION_CACHE_PREFIX = "valuation_v2"
_AGGREGATE_LABELS = ("行业平均", "行业中值", "行业均值")


def _row_code(value: object) -> str:
    """将表格中的代码列归一化为六位股票代码。"""
    text = str(value).strip()
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    return text


def _row_name(value: object) -> str:
    return str(value).strip()


def _is_aggregate_row(code: str, name: str) -> bool:
    """判断是否为行业平均/中值等汇总行，而不是可比的个股。"""
    if len(code) != 6 or not code.isdigit():
        return True
    return any(label in name for label in _AGGREGATE_LABELS)


def _parse_valuation_comparison(
    df, raw_code: str
) -> tuple[float | None, float | None, float | None, float | None, list[ValuationPeer]]:
    """从东财同行比较表中解析目标公司倍数与有效同行。

    东财接口会把排名末位的公司挪到首行，首行并不保证是目标公司；
    必须按代码定位目标行，否则会把同行的 PE/PB/PS 当成目标公司自身
    倍数，进而把 PB/PS 估值算到离现价数倍的位置。行业平均/中值行
    也必须从同行样本中剔除。

    Param:
        df: 同行比较表
        raw_code: 目标公司六位代码
    Return:
        (PE, PB, PS, 前瞻 PE, 同行列表) 元组
    """
    if df is None or len(df) == 0:
        return None, None, None, None, []

    target_row = None
    for _, row in df.iterrows():
        if _row_code(row.get("代码")) == raw_code:
            target_row = row
            break
    if target_row is None:
        logger.warning("估值比较表缺少目标代码 %s，改用基础信息回退", raw_code)

    pe_ttm = safe_float(target_row.get("市盈率-TTM")) if target_row is not None else None
    pb = safe_float(target_row.get("市净率-MRQ")) if target_row is not None else None
    ps_ttm = safe_float(target_row.get("市销率-TTM")) if target_row is not None else None
    pe_forward = safe_float(target_row.get("市盈率-25E")) if target_row is not None else None

    peers: list[ValuationPeer] = []
    seen: set[str] = set()
    for _, row in df.head(12).iterrows():
        peer_code = _row_code(row.get("代码"))
        peer_name = _row_name(row.get("简称"))
        if _is_aggregate_row(peer_code, peer_name) or peer_code == raw_code or peer_code in seen:
            continue
        seen.add(peer_code)
        peer = ValuationPeer(
            name=peer_name or peer_code,
            code=peer_code,
            pe_ttm=safe_float(row.get("市盈率-TTM")),
            pb=safe_float(row.get("市净率-MRQ")),
            ps_ttm=safe_float(row.get("市销率-TTM")),
        )
        peer._pe_forward = safe_float(row.get("市盈率-25E"))
        peers.append(peer)
    return pe_ttm, pb, ps_ttm, pe_forward, peers


async def _load_valuation(code: str) -> StockValuation:
    """获取股票当前估值与同行对比，并在缺失时回退到基础信息。

    Param:
        code: 股票代码
    Return:
        StockValuation 模型对象
    """
    if is_hk_code(code):
        from app.financial_data.hk.service import hk_market_service, normalize_hk_code

        norm_code = normalize_hk_code(code)
        cache_key = dated_cache_key(_VALUATION_CACHE_PREFIX, norm_code)
        cached = cache.get(cache_key)
        if cached is not None:
            cached_hk: StockValuation = StockValuation.model_validate(cached)
            return cached_hk
        hk_val = await hk_market_service.get_stock_valuation(norm_code)
        hk_peers: list[ValuationPeer] = []
        try:
            from app.financial_data.hk.industry_comparison import get_hk_stock_industry_comparison

            comp = await get_hk_stock_industry_comparison(norm_code)
            for p in comp.peers:
                if p.code == norm_code:
                    continue
                hk_peers.append(
                    ValuationPeer(
                        name=p.name,
                        code=p.code,
                        pe_ttm=p.pe,
                        pb=p.pb,
                        ps_ttm=None,
                    )
                )
        except Exception as exc:
            logger.debug("获取港股同行对比失败: %s", exc)

        result = StockValuation(
            code=norm_code,
            pe_ttm=hk_val.pe_ttm,
            pb=hk_val.pb,
            ps_ttm=hk_val.ps_ttm,
            peers=hk_peers,
        )
        cache.set(cache_key, result, ttl=VALUATION.ttl_seconds)
        return result

    sym = normalize_code(code)
    cache_key = dated_cache_key(_VALUATION_CACHE_PREFIX, sym.raw)
    cached = cache.get(cache_key)
    if cached is not None:
        cached_a: StockValuation = StockValuation.model_validate(cached)
        return cached_a

    pe_ttm: float | None = None
    pb: float | None = None
    ps_ttm: float | None = None
    pe_forward: float | None = None
    peers: list[ValuationPeer] = []

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
            pe_ttm, pb, ps_ttm, pe_forward, peers = _parse_valuation_comparison(df, sym.raw)
    except Exception:
        logger.info(f"估值数据获取失败，回退到基础信息: {sym.raw}")

    if pe_ttm is None or pb is None:
        try:
            basic_info = await get_basic_info(code)
            if pe_ttm is None:
                pe_ttm = basic_info.pe_ttm
            if pb is None:
                pb = basic_info.pb
        except Exception:
            logger.info(f"基础信息估值回退失败: {sym.raw}")

    result = StockValuation(
        code=sym.raw,
        pe_ttm=pe_ttm,
        pb=pb,
        ps_ttm=ps_ttm,
        peers=peers,
    )
    result._pe_forward = pe_forward
    cache.set(cache_key, result, ttl=VALUATION.ttl_seconds)
    return result


async def get_valuation(code: str) -> StockValuation:
    """获取股票估值，并合并相同股票的并发缓存未命中请求。"""
    if is_hk_code(code):
        from app.financial_data.hk.service import normalize_hk_code

        norm_code = normalize_hk_code(code)
        cache_key = dated_cache_key(_VALUATION_CACHE_PREFIX, norm_code)
        cached = cache.get(cache_key)
        if cached is not None:
            cached_hk_get: StockValuation = StockValuation.model_validate(cached)
            return cached_hk_get
        loaded_hk: StockValuation = await _valuation_singleflight.do(cache_key, lambda: _load_valuation(norm_code))
        return loaded_hk

    sym = normalize_code(code)
    cache_key = dated_cache_key(_VALUATION_CACHE_PREFIX, sym.raw)
    cached = cache.get(cache_key)
    if cached is not None:
        cached_a_get: StockValuation = StockValuation.model_validate(cached)
        return cached_a_get
    loaded_a: StockValuation = await _valuation_singleflight.do(cache_key, lambda: _load_valuation(code))
    return loaded_a
