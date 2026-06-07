import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd
from app.services.base.file_snapshot import BaseFileSnapshotService
from app.services.providers.akshare import akshare_provider as _akshare_provider
from app.services.providers.eastmoney import eastmoney_provider as _eastmoney_provider
from app.services.providers.sina import sina_provider as _sina_provider
from app.utils.rate_limiter import call_blocking

logger = logging.getLogger(__name__)

_SPOT_SNAPSHOT_FILE = Path(__file__).resolve().parent.parent.parent.parent / "data" / "stock_spot_snapshot.json"
_spot_snapshot_service = BaseFileSnapshotService[pd.DataFrame](
    cache_key="stock_spot_all",
    ttl=300,
    file_path=_SPOT_SNAPSHOT_FILE,
)


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
    if market_cap.max(skipna=True) and market_cap.max(skipna=True) < 1e10:
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
        if not rows:
            return None
        df = pd.DataFrame(rows)
        if "代码" not in df.columns or len(df.index) < 3000:
            return None
        df = _normalize_market_cap_units(df)
        logger.info(f"从本地文件加载全市场快照: {len(df)} 条")
        return df
    except Exception as e:
        logger.warning(f"读取本地全市场快照失败: {e}")
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
        payload = {
            "updated_at": datetime.now().isoformat(),
            "rows": normalized_df.to_dict(orient="records"),
        }
        with open(_SPOT_SNAPSHOT_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        logger.info(f"全市场快照已写入本地文件: {len(df)} 条")
    except Exception as e:
        logger.warning(f"保存本地全市场快照失败: {e}")


async def _fetch_spot_east() -> pd.DataFrame | None:
    """Fetch spot snapshot via direct Eastmoney provider call.

    Param:
        None
    Return:
        DataFrame of spot rows, or None on failure
    """
    try:
        return await call_blocking(_eastmoney_provider.fetch_spot_snapshot)
    except Exception as e:
        logger.info(f"东方财富直连快照获取失败: {e}")
        return None


async def _fetch_spot_sina_vip() -> pd.DataFrame | None:
    """Fetch spot snapshot via Sina VIP provider call.

    Param:
        None
    Return:
        DataFrame of spot rows, or None on failure
    """
    try:
        return await call_blocking(_sina_provider.fetch_spot_snapshot)
    except Exception as e:
        logger.info(f"新浪VIP快照获取失败: {e}")
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
            df = await _fetch_spot_east()
        if df is None or df.empty:
            try:
                df = await call_blocking(_akshare_provider.fetch_stock_spot_snapshot)
            except Exception as e:
                logger.info(f"后台刷新全市场快照失败: {e}")
                return
        if df is not None and not df.empty:
            _spot_snapshot_service.set_cached(df)
            _save_spot_snapshot_file(df)
    finally:
        _spot_snapshot_service.clear_refresh_task()


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

    file_df = load_spot_snapshot_file()
    if file_df is not None:
        _spot_snapshot_service.set_cached(file_df)
        _spot_snapshot_service.start_refresh(_refresh_spot_snapshot_file())
        return file_df

    df = await _fetch_spot_sina_vip()
    if df is not None and not df.empty:
        _spot_snapshot_service.set_cached(df)
        _save_spot_snapshot_file(df)
        return df

    df = await _fetch_spot_east()
    if df is not None and not df.empty:
        _spot_snapshot_service.set_cached(df)
        _save_spot_snapshot_file(df)
        return df

    try:
        df = await call_blocking(_akshare_provider.fetch_spot_em)
        _spot_snapshot_service.set_cached(df)
        _save_spot_snapshot_file(df)
        return df
    except Exception as e:
        logger.info(f"akshare全市场快照不可用: {e}")
    return None
