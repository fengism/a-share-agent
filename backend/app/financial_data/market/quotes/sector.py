import logging
from datetime import UTC, date, datetime
from typing import cast

from app.core.cache import dated_cache_key_no_day
from app.core.cache import market_cache as cache
from app.core.concurrency.rate_limiter import (
    baidu_semaphore,
    call_blocking,
    cls_semaphore,
    eastmoney_semaphore,
    kaipanhong_semaphore,
    tencent_semaphore,
)
from app.core.concurrency.singleflight import AsyncSingleFlight
from app.core.exceptions import InvalidRequestError, UpstreamUnavailableError
from app.core.market import market_today, safe_float
from app.financial_data.market.trading_session import (
    get_market_date_on_or_before,
    resolve_market_data_cache_policy,
)
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider

logger = logging.getLogger(__name__)
_industry_rankings_singleflight: AsyncSingleFlight[dict] = AsyncSingleFlight()



def _get_kaipanhong_provider():
    return get_provider("kaipanhong")


def _get_cls_provider():
    return get_provider("cls")


def _get_baidu_provider():
    return get_provider("baidu")


def _get_eastmoney_provider():
    return get_provider("eastmoney")


def _get_tencent_provider():
    return get_provider("tencent")


def _normalize_tencent_sectors(top_df, bottom_df) -> dict:
    seen = set()
    sectors: list[dict] = []
    for _, row in top_df.iterrows():
        name = str(row.get("板块名称", ""))
        if name in seen:
            continue
        seen.add(name)
        sectors.append(
            {
                "rank": len(sectors) + 1,
                "name": name,
                "change_pct": safe_float(row.get("涨跌幅")),
                "code": str(row.get("板块代码", "")),
                "up_count": None,
                "down_count": None,
                "leader": str(row.get("领涨跌股票名称", "")),
                "leader_change": safe_float(row.get("领涨股票-涨跌幅")),
            }
        )
    for _, row in bottom_df.iterrows():
        name = str(row.get("板块名称", ""))
        if name in seen:
            continue
        seen.add(name)
        sectors.append(
            {
                "rank": len(sectors) + 1,
                "name": name,
                "change_pct": safe_float(row.get("涨跌幅")),
                "code": str(row.get("板块代码", "")),
                "up_count": None,
                "down_count": None,
                "leader": str(row.get("领涨跌股票名称", "")),
                "leader_change": safe_float(row.get("领涨股票-涨跌幅")),
            }
        )
    sectors.sort(key=lambda item: item["change_pct"] or 0, reverse=True)
    for index, item in enumerate(sectors):
        item["rank"] = index + 1
    return {"sectors": sectors, "total": len(sectors)}


def _response_metadata(target_date: date, *, source: str, fund_data_available: bool) -> dict:
    return {
        "date": target_date.isoformat(),
        "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": source,
        "fund_data_available": fund_data_available,
    }


async def _load_industry_rankings(target_date: date) -> dict:
    date_text = target_date.isoformat()
    try:
        result = await provider_gateway.call(
            "kaipanhong",
            "industry_rankings",
            lambda: call_blocking(
                _get_kaipanhong_provider().fetch_industry_rankings,
                date_text,
                semaphore=kaipanhong_semaphore,
            ),
        )
        sectors = result.get("sectors") or []
        if sectors or target_date < market_today():
            return {
                "sectors": sectors,
                "total": len(sectors),
                **_response_metadata(
                    target_date,
                    source="开盘红",
                    fund_data_available=True,
                ),
                "date": result.get("date") or date_text,
            }
        raise RuntimeError("开盘红当日行业排名返回空数据")
    except Exception as error:
        logger.warning("开盘红行业排名获取失败: %s", error)
        if target_date < market_today():
            raise UpstreamUnavailableError("开盘红历史行业排行上游暂时不可用") from error

    for provider_name, label, fetch_fn, semaphore in [
        ("cls", "财联社", lambda: _get_cls_provider().fetch_industry_rankings(50), cls_semaphore),
        (
            "eastmoney",
            "东方财富",
            lambda: _get_eastmoney_provider().fetch_industry_rankings(50),
            eastmoney_semaphore,
        ),
        ("baidu", "百度", lambda: _get_baidu_provider().fetch_industry_rankings(50), baidu_semaphore),
    ]:
        try:
            result = await provider_gateway.call(
                provider_name,
                "industry_rankings",
                lambda fetch_fn=fetch_fn, semaphore=semaphore: call_blocking(
                    fetch_fn,
                    semaphore=semaphore,
                ),
            )
            sectors = result.get("top", [])
            if not sectors:
                raise RuntimeError(f"{label}行业排名返回空数据")
            return {
                "sectors": sectors,
                "total": result.get("total", len(sectors)),
                **_response_metadata(
                    target_date,
                    source=label,
                    fund_data_available=False,
                ),
            }
        except Exception as error:
            logger.warning("%s行业排名获取失败: %s", label, error)

    try:
        top_df, bottom_df = await provider_gateway.call(
            "tencent",
            "industry_rankings",
            lambda: call_blocking(
                _get_tencent_provider().fetch_industry_rankings,
                semaphore=tencent_semaphore,
            ),
        )
        data = _normalize_tencent_sectors(top_df, bottom_df)
        data.update(
            _response_metadata(
                target_date,
                source="腾讯",
                fund_data_available=False,
            )
        )
        return data
    except Exception as error:
        logger.warning("腾讯行业排名获取失败: %s", error)
        # 五个数据源全部失败。此前这里返回一个 source="" 的「成功」响应（sectors: []），
        # 而 load_and_cache 会把它按盘中 TTL 写进缓存——一次全站故障就能把行业排行
        # 毒化一整天，且前端拿到的 JSON 结构完全合法，无法与「当日无数据」区分。
        # 抛错更诚实：调用方能明确知道是上游不可用，并且不会污染缓存。
        raise UpstreamUnavailableError("行业排行上游暂时不可用") from error


async def get_industry_rankings(requested_date: date | None = None) -> dict:
    """获取指定日期的行业涨跌与资金排行。"""
    requested_target = requested_date or market_today()
    if requested_target > market_today():
        raise InvalidRequestError("行业排行不能查询未来日期")

    target_date = await get_market_date_on_or_before(requested_target)
    policy = await resolve_market_data_cache_policy("daily", target_date)
    cache_key = dated_cache_key_no_day("industry_rankings", target_date.isoformat())
    if policy.read_cache:
        cached = cache.get(cache_key)
        if cached is not None:
            return cast(dict, cached)

    async def load_and_cache() -> dict:
        data = await _load_industry_rankings(target_date)
        if policy.write_cache and policy.ttl_seconds is not None:
            cache.set(cache_key, data, ttl=policy.ttl_seconds)
        return data

    return cast(
        dict,
        await _industry_rankings_singleflight.do(cache_key, load_and_cache),
    )
