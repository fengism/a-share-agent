import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

from app.services.base.file_snapshot import BaseFileSnapshotService
from app.services.providers import get_provider
from app.services.base.spot_snapshot import load_spot_snapshot_file
from app.utils.rate_limiter import call_blocking, baidu_semaphore, eastmoney_semaphore, sina_semaphore

logger = logging.getLogger(__name__)

_STOCK_NAME_MAP_MIN_SIZE = 4000
_STOCK_NAME_FILE = Path(__file__).resolve().parent.parent.parent.parent / "data" / "stock_names.json"
_STOCK_NAME_MAP_SERVICE = BaseFileSnapshotService[dict[str, str]](
    cache_key="stock_name_map",
    ttl=86400,
    file_path=_STOCK_NAME_FILE,
)


def _get_baidu_provider():
    """Lazily resolve the Baidu provider singleton."""
    return get_provider("baidu")


def _get_eastmoney_provider():
    """Lazily resolve the EastMoney provider singleton."""
    return get_provider("eastmoney")


def _get_sina_provider():
    """Lazily resolve the Sina provider singleton."""
    return get_provider("sina")


def _load_stock_name_file() -> dict[str, str] | None:
    """从本地 JSON 文件加载股票名称映射。

    Param:
        无
    Return:
        股票代码到名称的字典，数据量不足或异常时返回 None
    """
    try:
        if _STOCK_NAME_FILE.exists():
            with open(_STOCK_NAME_FILE, "r", encoding="utf-8") as f:
                mapping = json.load(f)
            if isinstance(mapping, dict) and len(mapping) >= _STOCK_NAME_MAP_MIN_SIZE:
                logger.info(f"从本地文件加载股票名称映射: {len(mapping)} 只")
                return mapping
            logger.info(f"本地文件映射不足({len(mapping) if isinstance(mapping, dict) else 0}只)，需重新获取")
    except Exception as e:
        logger.warning(f"读取本地股票名称文件失败: {e}")
    return None


def _load_stock_name_map_from_spot_snapshot() -> dict[str, str] | None:
    """从本地市场快照文件提取股票名称映射。

    Param:
        无
    Return:
        股票代码到名称的字典，数据量不足或异常时返回 None
    """
    try:
        df = load_spot_snapshot_file()
        if df is None or df.empty or "代码" not in df.columns or "名称" not in df.columns:
            return None
        # 向量化构建映射，比 iterrows 快一个数量级
        valid = df["代码"].notna() & df["名称"].notna()
        mapping = dict(zip(df.loc[valid, "代码"].astype(str), df.loc[valid, "名称"].astype(str)))
        if len(mapping) >= _STOCK_NAME_MAP_MIN_SIZE:
            logger.info(f"从本地快照文件加载股票名称映射: {len(mapping)} 只")
            return mapping
    except Exception as e:
        logger.warning(f"从本地快照文件加载股票名称映射失败: {e}")
    return None


def _save_stock_name_file(mapping: dict[str, str]) -> None:
    """将股票名称映射保存到本地 JSON 文件。

    Param:
        mapping: 股票代码到名称的字典
    Return:
        无
    """
    try:
        _STOCK_NAME_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_STOCK_NAME_FILE, "w", encoding="utf-8") as f:
            json.dump(mapping, f, ensure_ascii=False, indent=2)
        logger.info(f"股票名称映射已保存到本地文件: {len(mapping)} 只")
    except Exception as e:
        logger.warning(f"保存本地股票名称文件失败: {e}")


async def _fetch_stock_name_map_remote() -> dict[str, str]:
    """按顺序从百度、东方财富、新浪远程获取股票名称映射。

    Param:
        无
    Return:
        股票代码到名称的字典，全部失败时返回空字典
    """
    try:
        stocks = await call_blocking(_get_baidu_provider().fetch_stock_names, semaphore=baidu_semaphore)
        if len(stocks) >= _STOCK_NAME_MAP_MIN_SIZE:
            mapping = {s["code"]: s["name"] for s in stocks}
            logger.info(f"股票名称映射(百度): {len(mapping)} 只")
            return mapping
        logger.info(f"百度股票列表不足({len(stocks)}只)，尝试东方财富")
    except Exception as e:
        logger.info(f"百度股票列表获取失败: {e}，尝试东方财富")

    try:
        stocks = await call_blocking(_get_eastmoney_provider().fetch_stock_names, semaphore=eastmoney_semaphore)
        if len(stocks) >= _STOCK_NAME_MAP_MIN_SIZE:
            mapping = {s["code"]: s["name"] for s in stocks}
            logger.info(f"股票名称映射(东方财富): {len(mapping)} 只")
            return mapping
        logger.info(f"东方财富股票列表不足({len(stocks)}只)，尝试新浪")
    except Exception as e:
        logger.info(f"东方财富股票列表获取失败: {e}，尝试新浪")

    try:
        stocks = await call_blocking(_get_sina_provider().fetch_stock_names, semaphore=sina_semaphore)
        mapping = {s["code"]: s["name"] for s in stocks}
        logger.info(f"股票名称映射(新浪): {len(mapping)} 只")
        return mapping
    except Exception as e:
        logger.error(f"新浪股票列表也获取失败: {e}")
        return {}


async def get_stock_name_map() -> dict[str, str]:
    """获取股票名称映射，优先缓存→快照→文件→远程。

    Param:
        无
    Return:
        股票代码到名称的字典
    """
    cached = _STOCK_NAME_MAP_SERVICE.get_cached()
    if cached is not None:
        return cached

    snapshot_mapping = _load_stock_name_map_from_spot_snapshot() or {}
    file_mapping = _load_stock_name_file() or {}
    if snapshot_mapping or file_mapping:
        merged_mapping = {**file_mapping, **snapshot_mapping}
        _STOCK_NAME_MAP_SERVICE.set_cached(merged_mapping)
        return merged_mapping

    mapping = await _fetch_stock_name_map_remote()
    if mapping:
        _STOCK_NAME_MAP_SERVICE.set_cached(mapping)
        _save_stock_name_file(mapping)
    return mapping


async def _refresh_stock_name_map() -> None:
    """后台刷新股票名称映射并落地缓存与文件。

    Param:
        无
    Return:
        无
    """
    try:
        mapping = await _fetch_stock_name_map_remote()
        if mapping:
            _STOCK_NAME_MAP_SERVICE.set_cached(mapping)
            _save_stock_name_file(mapping)
            logger.info(f"股票名称映射后台刷新完成: {len(mapping)} 只")
    except Exception as e:
        logger.error(f"股票名称映射后台刷新失败: {e}")


async def build_stock_name_map() -> None:
    """预热股票名称映射；当本地文件超过 24 小时则触发后台刷新。

    Param:
        无
    Return:
        无
    """
    await get_stock_name_map()
    if _STOCK_NAME_FILE.exists():
        mtime = _STOCK_NAME_FILE.stat().st_mtime
        age_hours = (datetime.now().timestamp() - mtime) / 3600
        if age_hours > 24:
            asyncio.create_task(_refresh_stock_name_map())
