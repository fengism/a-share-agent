"""股票名称映射服务。"""

import json
import logging
from time import time

from app.configuration.paths import DATA_DIR
from app.core.concurrency.rate_limiter import (
    baidu_semaphore,
    call_blocking,
    eastmoney_semaphore,
    misc_semaphore,
    sina_semaphore,
)
from app.core.concurrency.singleflight import AsyncSingleFlight
from app.infrastructure.persistence.file_snapshot import BaseFileSnapshotService
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider
from app.market_data.stock.quotes.spot_snapshot import load_spot_snapshot_file

logger = logging.getLogger(__name__)

_STOCK_NAME_MAP_MIN_SIZE = 4000
_STOCK_NAME_FILE = DATA_DIR / "stock_names.json"
_STOCK_NAME_MAP_SERVICE = BaseFileSnapshotService[dict[str, str]](
    cache_key="stock_name_map",
    ttl=86400,
    file_path=_STOCK_NAME_FILE,
)
_STOCK_NAME_FILE_MAX_AGE_SECONDS = 24 * 60 * 60
_stock_name_map_singleflight: AsyncSingleFlight[dict[str, str]] = AsyncSingleFlight()


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
    tmp_path = _STOCK_NAME_FILE.with_name(f"{_STOCK_NAME_FILE.name}.tmp")
    try:
        _STOCK_NAME_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(_STOCK_NAME_FILE)
        logger.info(f"股票名称映射已保存到本地文件: {len(mapping)} 只")
    except Exception as e:
        logger.warning(f"保存本地股票名称文件失败: {e}")
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            logger.debug("清理股票名称映射临时文件失败: %s", tmp_path, exc_info=True)


def _load_local_stock_name_map() -> dict[str, str]:
    """Load and merge the standalone name file and local market snapshot."""
    snapshot_mapping = _load_stock_name_map_from_spot_snapshot() or {}
    file_mapping = _load_stock_name_file() or {}
    return {**file_mapping, **snapshot_mapping}


def _mapping_from_stocks(stocks: list[dict], source: str) -> dict[str, str]:
    mapping = {
        str(stock["code"]): str(stock["name"])
        for stock in stocks
        if stock.get("code") and stock.get("name")
    }
    if len(mapping) >= _STOCK_NAME_MAP_MIN_SIZE:
        logger.info(f"股票名称映射({source}): {len(mapping)} 只")
        return mapping
    logger.info(f"{source}股票列表不足({len(mapping)}只)")
    return {}


def _stock_name_file_needs_refresh() -> bool:
    try:
        if not _STOCK_NAME_FILE.exists():
            return True
        return time() - _STOCK_NAME_FILE.stat().st_mtime > _STOCK_NAME_FILE_MAX_AGE_SECONDS
    except OSError as e:
        logger.warning(f"检查本地股票名称文件新鲜度失败: {e}")
        return True


async def _fetch_stock_name_map_remote() -> dict[str, str]:
    """按顺序从百度、东方财富、新浪远程获取股票名称映射。

    Param:
        无
    Return:
        股票代码到名称的字典，全部失败时返回空字典
    """
    try:
        stocks = await provider_gateway.call(
            "baidu",
            "stock_names",
            lambda: call_blocking(
                _get_baidu_provider().fetch_stock_names,
                semaphore=baidu_semaphore,
            ),
        )
        mapping = _mapping_from_stocks(stocks, "百度")
        if mapping:
            return mapping
    except Exception as e:
        logger.info(f"百度股票列表获取失败: {e}，尝试东方财富")

    try:
        stocks = await provider_gateway.call(
            "eastmoney",
            "stock_names",
            lambda: call_blocking(
                _get_eastmoney_provider().fetch_stock_names,
                semaphore=eastmoney_semaphore,
            ),
        )
        mapping = _mapping_from_stocks(stocks, "东方财富")
        if mapping:
            return mapping
    except Exception as e:
        logger.info(f"东方财富股票列表获取失败: {e}，尝试新浪")

    try:
        stocks = await provider_gateway.call(
            "sina",
            "stock_names",
            lambda: call_blocking(
                _get_sina_provider().fetch_stock_names,
                semaphore=sina_semaphore,
            ),
        )
        return _mapping_from_stocks(stocks, "新浪")
    except Exception as e:
        logger.error(f"新浪股票列表也获取失败: {e}")
        return {}


async def _cache_and_persist_stock_name_map(mapping: dict[str, str]) -> dict[str, str]:
    _STOCK_NAME_MAP_SERVICE.set_cached(mapping)
    await call_blocking(
        _save_stock_name_file,
        mapping,
        semaphore=misc_semaphore,
    )
    return mapping


async def _load_stock_name_map() -> dict[str, str]:
    cached = _STOCK_NAME_MAP_SERVICE.get_cached()
    if cached is not None:
        return cached

    local_mapping = await call_blocking(
        _load_local_stock_name_map,
        semaphore=misc_semaphore,
    )
    if local_mapping:
        _STOCK_NAME_MAP_SERVICE.set_cached(local_mapping)
        return local_mapping

    mapping = await _fetch_stock_name_map_remote()
    if mapping:
        return await _cache_and_persist_stock_name_map(mapping)
    return {}


async def get_stock_name_map() -> dict[str, str]:
    """获取股票名称映射，优先缓存→本地合并映射→远程。

    Param:
        无
    Return:
        股票代码到名称的字典
    """
    cached = _STOCK_NAME_MAP_SERVICE.get_cached()
    if cached is not None:
        return cached

    return await _stock_name_map_singleflight.do(
        _STOCK_NAME_MAP_SERVICE.cache_key,
        _load_stock_name_map,
    )


async def _refresh_stock_name_map() -> None:
    """后台刷新股票名称映射并落地缓存与文件。

    Param:
        无
    Return:
        无
    """
    mapping = await _fetch_stock_name_map_remote()
    if not mapping:
        raise RuntimeError("远程股票名称映射为空")
    await _cache_and_persist_stock_name_map(mapping)
    logger.info(f"股票名称映射后台刷新完成: {len(mapping)} 只")


async def build_stock_name_map() -> None:
    """预热股票名称映射；当本地文件超过 24 小时则触发后台刷新。

    Param:
        无
    Return:
        无
    """
    mapping = await get_stock_name_map()
    if not mapping:
        raise RuntimeError("股票名称映射预热结果为空")
    needs_refresh = await call_blocking(
        _stock_name_file_needs_refresh,
        semaphore=misc_semaphore,
    )
    if needs_refresh:
        await _refresh_stock_name_map()
