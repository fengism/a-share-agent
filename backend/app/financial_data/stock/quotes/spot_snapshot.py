"""全市场实时行情快照。"""

import json
import logging
from datetime import datetime

import pandas as pd

from app.configuration.paths import DATA_DIR
from app.core.concurrency.rate_limiter import (
    akshare_semaphore,
    call_blocking,
    eastmoney_semaphore,
    misc_semaphore,
    sina_semaphore,
)
from app.core.concurrency.singleflight import AsyncSingleFlight
from app.domain.timezones import market_now
from app.financial_data.stock.quotes.sources import (
    AKSHARE_SPOT_SOURCE_ID,
    EASTMONEY_SPOT_SOURCE_ID,
    KNOWN_SPOT_SOURCE_IDS,
    LEGACY_SPOT_SOURCE_ID,
    SINA_CN_RANK_SPOT_SOURCE_ID,
    SINA_SPOT_SOURCE_ID,
    get_spot_source,
    mark_spot_source,
)
from app.infrastructure.persistence.file_snapshot import BaseFileSnapshotService
from app.infrastructure.persistence.json_storage import atomic_write_text
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider

logger = logging.getLogger(__name__)

_SPOT_SNAPSHOT_FILE = DATA_DIR / "stock_spot_snapshot.json"
_SPOT_FILE_FRESH_SECONDS = 5 * 60
_SPOT_FILE_MAX_STALE_SECONDS = 24 * 60 * 60
_SPOT_AS_OF_ATTR = "stock_spot_as_of"
_SPOT_IS_STALE_ATTR = "stock_spot_is_stale"
_spot_snapshot_service = BaseFileSnapshotService[pd.DataFrame](
    cache_key="stock_spot_all",
    ttl=300,
    file_path=_SPOT_SNAPSHOT_FILE,
)
_spot_snapshot_singleflight: AsyncSingleFlight[pd.DataFrame | None] = AsyncSingleFlight()


def _get_akshare_provider():
    """Lazily resolve the Akshare provider singleton."""
    return get_provider("akshare")


def _get_eastmoney_provider():
    """Lazily resolve the EastMoney provider singleton."""
    return get_provider("eastmoney")


def _get_sina_provider():
    """Lazily resolve the Sina provider singleton."""
    return get_provider("sina")


def _normalize_market_cap_units(df: pd.DataFrame) -> pd.DataFrame:
    """Scale up small market-cap values to the standard unit (yuan).

    Param:
        df: DataFrame containing a "总市值" column
    Return:
        DataFrame with normalized "总市值" (and "流通市值" if present) in yuan
    """
    result = df.copy()
    if "总市值" not in result.columns:
        return result
    market_cap = pd.to_numeric(result["总市值"], errors="coerce")
    max_cap = market_cap.max(skipna=True)
    if pd.notna(max_cap) and 0 < max_cap < 1e10:
        result["总市值"] = market_cap * 10000
        if "流通市值" in result.columns:
            result["流通市值"] = pd.to_numeric(result["流通市值"], errors="coerce") * 10000
    return result


def load_spot_snapshot_file() -> pd.DataFrame | None:
    """Load the cached full-market spot snapshot from local JSON file.

    Param:
        None
    Return:
        DataFrame of spot rows, or None if file missing, malformed, or too small
    """
    try:
        if not _SPOT_SNAPSHOT_FILE.exists():
            return None
        with open(_SPOT_SNAPSHOT_FILE, "r", encoding="utf-8") as f:
            payload = json.load(f)
        rows = payload.get("rows") if isinstance(payload, dict) else None
        updated_at = payload.get("updated_at") if isinstance(payload, dict) else None
        if not rows or not isinstance(updated_at, str):
            return None
        parsed_updated_at = datetime.fromisoformat(updated_at)
        if parsed_updated_at.tzinfo is not None:
            now = datetime.now(parsed_updated_at.tzinfo)
        else:
            now = market_now()
        age_seconds = max(0.0, (now - parsed_updated_at).total_seconds())
        if age_seconds > _SPOT_FILE_MAX_STALE_SECONDS:
            logger.warning(
                "本地全市场快照已过期，拒绝作为实时行情: age_seconds=%.0f updated_at=%s",
                age_seconds,
                updated_at,
            )
            return None
        df = pd.DataFrame(rows)
        if "代码" not in df.columns or len(df.index) < 3000:
            return None
        df = _normalize_market_cap_units(df)
        source_id = payload.get("source_id", LEGACY_SPOT_SOURCE_ID)
        if not isinstance(source_id, str) or source_id not in KNOWN_SPOT_SOURCE_IDS:
            source_id = LEGACY_SPOT_SOURCE_ID
        mark_spot_source(df, source_id)
        df.attrs[_SPOT_AS_OF_ATTR] = parsed_updated_at.isoformat()
        df.attrs[_SPOT_IS_STALE_ATTR] = age_seconds > _SPOT_FILE_FRESH_SECONDS
        logger.info(
            "从本地文件加载全市场快照: rows=%s age_seconds=%.0f stale=%s",
            len(df), age_seconds, df.attrs[_SPOT_IS_STALE_ATTR],
        )
        return df
    except Exception as e:
        logger.warning('读取本地全市场快照失败: %s', e)
        return None


def _save_spot_snapshot_file(df: pd.DataFrame) -> None:
    """Persist the full-market spot snapshot to the local JSON file.

    Param:
        df: DataFrame of spot rows to save
    Return:
        None
    """
    try:
        _SPOT_SNAPSHOT_FILE.parent.mkdir(parents=True, exist_ok=True)
        normalized_df = _normalize_market_cap_units(df)
        updated_at = market_now().isoformat()
        payload = {
            "updated_at": updated_at,
            "source_id": get_spot_source(normalized_df),
            "rows": normalized_df.to_dict(orient="records"),
        }
        atomic_write_text(
            _SPOT_SNAPSHOT_FILE,
            json.dumps(payload, ensure_ascii=False),
        )
        df.attrs[_SPOT_AS_OF_ATTR] = updated_at
        df.attrs[_SPOT_IS_STALE_ATTR] = False
        logger.info('全市场快照已写入本地文件: %s 条', len(df))
    except Exception as e:
        logger.warning('保存本地全市场快照失败: %s', e)


async def _fetch_spot_east() -> pd.DataFrame | None:
    """Fetch spot snapshot via direct Eastmoney provider call.

    Param:
        None
    Return:
        DataFrame of spot rows, or None on failure
    """
    try:
        frame = await provider_gateway.call(
            "eastmoney",
            "spot_snapshot",
            lambda: call_blocking(
                _get_eastmoney_provider().fetch_spot_snapshot,
                semaphore=eastmoney_semaphore,
            ),
        )
        if frame is None:
            return None
        return mark_spot_source(frame, EASTMONEY_SPOT_SOURCE_ID)
    except Exception as e:
        logger.info('东方财富直连快照获取失败: %s', e)
        return None


async def _fetch_spot_sina_vip() -> pd.DataFrame | None:
    """Fetch spot snapshot via Sina VIP provider call.

    Param:
        None
    Return:
        DataFrame of spot rows, or None on failure
    """
    try:
        frame = await provider_gateway.call(
            "sina",
            "spot_snapshot",
            lambda: call_blocking(
                _get_sina_provider().fetch_spot_snapshot,
                semaphore=sina_semaphore,
            ),
        )
        if frame is None:
            return None
        return mark_spot_source(frame, SINA_SPOT_SOURCE_ID)
    except Exception as e:
        logger.info('新浪VIP快照获取失败: %s', e)
        return None


async def _fetch_spot_sina_rank() -> pd.DataFrame | None:
    """Fetch the full-market Screener fallback through Sina cnrank."""
    try:
        frame = await provider_gateway.call(
            "sina",
            "spot_snapshot_cnrank",
            lambda: call_blocking(
                _get_sina_provider().fetch_stock_rank_snapshot,
                semaphore=sina_semaphore,
            ),
        )
        if frame is None or frame.empty:
            return None
        return mark_spot_source(frame, SINA_CN_RANK_SPOT_SOURCE_ID)
    except Exception as error:
        logger.info("新浪 cnrank 快照获取失败: %s", error)
        return None


async def _fetch_spot_akshare() -> pd.DataFrame | None:
    """Fetch the EastMoney snapshot through AkShare and mark its actual API source."""
    try:
        frame = await provider_gateway.call(
            "akshare",
            "spot_snapshot",
            lambda: call_blocking(
                _get_akshare_provider().fetch_stock_spot_snapshot,
                semaphore=akshare_semaphore,
            ),
        )
        if frame is None:
            return None
        return mark_spot_source(frame, AKSHARE_SPOT_SOURCE_ID)
    except Exception as e:
        logger.info("AkShare 全市场快照获取失败: %s", e)
        return None


async def _refresh_spot_snapshot_file() -> None:
    """Refresh the cached and persisted spot snapshot from the best available provider.

    Param:
        None
    Return:
        None
    """
    try:
        df = await _fetch_spot_sina_vip()
        if df is None or df.empty:
            df = await _fetch_spot_sina_rank()
        if df is None or df.empty:
            df = await _fetch_spot_east()
        if df is None or df.empty:
            df = await _fetch_spot_akshare()
        if df is not None and not df.empty:
            _spot_snapshot_service.set_cached(df)
            await call_blocking(
                _save_spot_snapshot_file,
                df,
                semaphore=misc_semaphore,
            )
    finally:
        _spot_snapshot_service.clear_refresh_task()


async def _cache_and_persist_snapshot(df: pd.DataFrame) -> pd.DataFrame:
    _spot_snapshot_service.set_cached(df)
    await call_blocking(
        _save_spot_snapshot_file,
        df,
        semaphore=misc_semaphore,
    )
    return df


async def _load_spot_snapshot() -> pd.DataFrame | None:
    df = _spot_snapshot_service.get_cached()
    if df is not None:
        return df

    file_df = await call_blocking(
        load_spot_snapshot_file,
        semaphore=misc_semaphore,
    )
    if file_df is not None:
        _spot_snapshot_service.set_cached(file_df)
        _spot_snapshot_service.start_refresh(_refresh_spot_snapshot_file)
        return file_df

    df = await _fetch_spot_sina_vip()
    if df is not None and not df.empty:
        return await _cache_and_persist_snapshot(df)

    df = await _fetch_spot_sina_rank()
    if df is not None and not df.empty:
        return await _cache_and_persist_snapshot(df)

    df = await _fetch_spot_east()
    if df is not None and not df.empty:
        return await _cache_and_persist_snapshot(df)

    df = await _fetch_spot_akshare()
    if df is not None and not df.empty:
        return await _cache_and_persist_snapshot(df)
    return None


async def get_spot_snapshot() -> pd.DataFrame | None:
    """Get the full-market spot snapshot, loading from cache, file, or live providers.

    Param:
        None
    Return:
        DataFrame of spot rows, or None if all sources fail
    """
    df = _spot_snapshot_service.get_cached()
    if df is not None:
        return df

    return await _spot_snapshot_singleflight.do(
        _spot_snapshot_service.cache_key,
        _load_spot_snapshot,
    )
