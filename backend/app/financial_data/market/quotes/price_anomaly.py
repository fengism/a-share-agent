"""市场交易所异动查询服务。"""

import hashlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from app.configuration.paths import DATA_DIR
from app.core.cache import dated_cache_key
from app.core.cache import market_cache as cache
from app.core.cache_policies import PRICE_ANOMALY
from app.core.concurrency.rate_limiter import call_blocking, eastmoney_semaphore
from app.core.concurrency.singleflight import AsyncSingleFlight
from app.core.exceptions import UpstreamUnavailableError
from app.financial_data.market.quotes.schemas import (
    MarketPriceAnomalyCountResponse,
    MarketPriceAnomalyResponse,
)
from app.infrastructure.persistence.json_storage import atomic_write_json
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider

logger = logging.getLogger(__name__)

PRICE_ANOMALY_CACHE_TTL_SECONDS = PRICE_ANOMALY.ttl_seconds
_price_anomaly_singleflight = AsyncSingleFlight[MarketPriceAnomalyResponse]()
_price_anomaly_count_singleflight = AsyncSingleFlight[MarketPriceAnomalyCountResponse]()
_SNAPSHOT_DIR = DATA_DIR / "snapshots" / "market_price_anomaly"
_SNAPSHOT_VERSION = 1
_ResponseT = TypeVar("_ResponseT", bound=BaseModel)


def _detail_snapshot_path(page_size: int, page_no: int) -> Path:
    return _SNAPSHOT_DIR / f"detail-{page_size}-{page_no}.json"


def _count_snapshot_path(
    page_size: int,
    page_no: int,
    sort_key: str,
    sort_dir: str,
) -> Path:
    sort_hash = hashlib.sha256(f"{sort_key}\0{sort_dir}".encode()).hexdigest()[:12]
    return _SNAPSHOT_DIR / f"count-{page_size}-{page_no}-{sort_hash}.json"


def _write_snapshot(path: Path, response: BaseModel) -> None:
    try:
        atomic_write_json(
            path,
            {
                "version": _SNAPSHOT_VERSION,
                "response": response.model_dump(mode="json"),
            },
        )
    except Exception as error:
        logger.warning("交易所异动快照写入失败 path=%s error=%s", path, error)


def _read_snapshot(path: Path, response_type: type[_ResponseT]) -> _ResponseT | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("version") != _SNAPSHOT_VERSION:
            return None
        return response_type.model_validate(payload["response"])
    except FileNotFoundError:
        return None
    except (AttributeError, OSError, KeyError, TypeError, ValueError) as error:
        logger.warning("忽略无效交易所异动快照 path=%s error=%s", path, error)
        return None


async def get_market_price_anomaly(
    page_size: int = 200,
    page_no: int = 1,
) -> MarketPriceAnomalyResponse:
    """获取交易所异动明细。"""
    snapshot_path = _detail_snapshot_path(page_size, page_no)
    cache_key = dated_cache_key("market_price_anomaly", page_size, page_no)
    cached = cache.get(cache_key)
    if cached is not None:
        return MarketPriceAnomalyResponse.model_validate(cached)

    async def load() -> MarketPriceAnomalyResponse:
        cached_after_wait = cache.get(cache_key)
        if cached_after_wait is not None:
            return MarketPriceAnomalyResponse.model_validate(cached_after_wait)
        provider = get_provider("eastmoney")
        try:
            payload = await provider_gateway.call(
                "eastmoney",
                "market_price_anomaly",
                lambda: call_blocking(
                    provider.fetch_market_price_anomaly,
                    page_size,
                    page_no,
                    semaphore=eastmoney_semaphore,
                ),
            )
        except Exception as error:
            logger.warning("交易所异动明细获取失败: %s", error)
            snapshot = _read_snapshot(snapshot_path, MarketPriceAnomalyResponse)
            if snapshot is not None:
                return snapshot.model_copy(update={"is_stale": True})
            raise UpstreamUnavailableError("交易所异动上游暂时不可用") from error

        result = MarketPriceAnomalyResponse(
            date=payload.get("date", ""),
            fetched_at=datetime.now(UTC).isoformat(timespec="seconds"),
            page_no=page_no,
            page_size=page_size,
            pages=payload.get("pages", 0),
            items=payload.get("items") or [],
        )
        _write_snapshot(snapshot_path, result)
        cache.set(cache_key, result, ttl=PRICE_ANOMALY_CACHE_TTL_SECONDS)
        return result

    return await _price_anomaly_singleflight.do(cache_key, load)


async def get_market_price_anomaly_count(
    page_size: int = 50,
    page_no: int = 1,
    sort_key: str = "",
    sort_dir: str = "",
) -> MarketPriceAnomalyCountResponse:
    """获取按标的聚合的交易所异动统计。"""
    snapshot_path = _count_snapshot_path(page_size, page_no, sort_key, sort_dir)
    cache_key = dated_cache_key(
        "market_price_anomaly_count",
        page_size,
        page_no,
        sort_key,
        sort_dir,
    )
    cached = cache.get(cache_key)
    if cached is not None:
        return MarketPriceAnomalyCountResponse.model_validate(cached)

    async def load() -> MarketPriceAnomalyCountResponse:
        cached_after_wait = cache.get(cache_key)
        if cached_after_wait is not None:
            return MarketPriceAnomalyCountResponse.model_validate(cached_after_wait)
        provider = get_provider("eastmoney")
        try:
            payload = await provider_gateway.call(
                "eastmoney",
                "market_price_anomaly_count",
                lambda: call_blocking(
                    provider.fetch_market_price_anomaly_count,
                    page_size,
                    page_no,
                    sort_key,
                    sort_dir,
                    semaphore=eastmoney_semaphore,
                ),
            )
        except Exception as error:
            logger.warning("交易所异动统计获取失败: %s", error)
            snapshot = _read_snapshot(snapshot_path, MarketPriceAnomalyCountResponse)
            if snapshot is not None:
                return snapshot.model_copy(update={"is_stale": True})
            raise UpstreamUnavailableError("交易所异动上游暂时不可用") from error

        result = MarketPriceAnomalyCountResponse(
            date=payload.get("date", ""),
            fetched_at=datetime.now(UTC).isoformat(timespec="seconds"),
            page_no=page_no,
            page_size=page_size,
            pages=payload.get("pages", 0),
            items=payload.get("items") or [],
        )
        _write_snapshot(snapshot_path, result)
        cache.set(cache_key, result, ttl=PRICE_ANOMALY_CACHE_TTL_SECONDS)
        return result

    return await _price_anomaly_count_singleflight.do(cache_key, load)
