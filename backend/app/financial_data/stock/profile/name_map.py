"""股票名称映射服务。"""

import asyncio
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from time import time
from typing import cast

from app.configuration.paths import DATA_DIR
from app.core.concurrency.rate_limiter import (
    baidu_semaphore,
    call_blocking,
    eastmoney_semaphore,
    misc_semaphore,
    sina_semaphore,
    tdx_semaphore,
)
from app.core.concurrency.singleflight import AsyncSingleFlight
from app.financial_data.stock.profile.exchange_master import ExchangeStockMaster, get_exchange_stock_master
from app.financial_data.stock.profile.name_sources import (
    KNOWN_STOCK_NAME_SOURCE_IDS,
    LEGACY_STOCK_NAMES_SOURCE_ID,
    SSE_STOCK_NAMES_SOURCE_ID,
)
from app.financial_data.stock.profile.short_names import (
    build_pinyin_index,
    build_short_name_index,
    extract_pinyin_tokens,
    has_specific_stock_context,
    has_stock_context,
    normalize_name,
)
from app.financial_data.stock.profile.sources import (
    BAIDU_STOCK_NAMES,
    CNINFO_STOCK_NAMES,
    EASTMONEY_STOCK_NAMES,
    SINA_STOCK_NAMES,
    TDXHUB_STOCK_NAMES,
    BasicDataSourceSpec,
)
from app.financial_data.stock.quotes.sources import KNOWN_SPOT_SOURCE_IDS, get_spot_source
from app.financial_data.stock.quotes.spot_snapshot import load_spot_snapshot_file
from app.infrastructure.persistence.file_snapshot import BaseFileSnapshotService
from app.infrastructure.persistence.json_storage import atomic_write_text
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider

logger = logging.getLogger(__name__)

_STOCK_NAME_MAP_MIN_SIZE = 4000
_STOCK_NAME_FILE = DATA_DIR / "stock_names.json"


@dataclass(frozen=True)
class StockNameMapSnapshot:
    """股票名称映射及按股票保留的实际来源。"""

    mapping: dict[str, str]
    default_source_id: str
    source_overrides: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_source(cls, mapping: dict[str, str], source_id: str) -> "StockNameMapSnapshot":
        return cls(mapping=mapping, default_source_id=_normalize_source_id(source_id))

    @classmethod
    def empty(cls) -> "StockNameMapSnapshot":
        return cls.from_source({}, LEGACY_STOCK_NAMES_SOURCE_ID)

    @classmethod
    def merge(
        cls,
        base: "StockNameMapSnapshot | None",
        overlay: "StockNameMapSnapshot | None",
    ) -> "StockNameMapSnapshot | None":
        if overlay is None:
            return base
        if base is None:
            return overlay
        mapping = {**base.mapping, **overlay.mapping}
        overrides = dict(overlay.source_overrides)
        for code in base.mapping.keys() - overlay.mapping.keys():
            source_id = base.source_for(code)
            if source_id != overlay.default_source_id:
                overrides[code] = source_id
        return cls(
            mapping=mapping,
            default_source_id=overlay.default_source_id,
            source_overrides=overrides,
        )

    def source_for(self, code: str) -> str:
        return self.source_overrides.get(code, self.default_source_id)


@dataclass(frozen=True)
class StockNameSourceAttempt:
    source: BasicDataSourceSpec
    display_name: str
    fetcher_factory: Callable[[], Callable[[], list[dict]]]
    semaphore: asyncio.Semaphore


def _build_stock_name_detection_index(snapshot: StockNameMapSnapshot) -> tuple[str, ...]:
    names: set[str] = set()
    for raw in snapshot.mapping.values():
        name = normalize_name(raw)
        if len(name) < 2:
            continue
        names.add(name)
        if len(name) > 2 and name.endswith(("A", "B")):
            names.add(name[:-1])
    return tuple(sorted(names, key=lambda name: (-len(name), name)))


def _ensure_stock_name_index() -> None:
    global _stock_name_detection_index, _stock_reference_names, _stock_short_name_index, _stock_pinyin_index
    if _stock_name_detection_index is not None:
        return
    snapshot = _coerce_cached_snapshot(_STOCK_NAME_MAP_SERVICE.get_cached())
    if snapshot is None:
        snapshot = _load_local_stock_name_map()
    if snapshot is None:
        _stock_name_detection_index = ()
        _stock_reference_names = ()
        return
    _stock_reference_names = tuple(str(name) for name in snapshot.mapping.values())
    _stock_name_detection_index = _build_stock_name_detection_index(snapshot)


def _ensure_short_name_index() -> frozenset[str]:
    global _stock_short_name_index
    if _stock_short_name_index is None:
        _ensure_stock_name_index()
        _stock_short_name_index = build_short_name_index(_stock_reference_names or ())
    return _stock_short_name_index


def _ensure_pinyin_index() -> frozenset[str]:
    global _stock_pinyin_index
    if _stock_pinyin_index is None:
        _ensure_stock_name_index()
        _stock_pinyin_index = build_pinyin_index(_stock_reference_names or ())
    return _stock_pinyin_index


def _contains_pinyin_reference(message: str) -> bool:
    tokens = extract_pinyin_tokens(message)
    if not tokens:
        return False
    index = _ensure_pinyin_index()
    return any(token in index for token in tokens)


def contains_known_stock_name(message: str) -> bool:
    """是否包含完整股票名、A/B 归一形式或拼音首字母。"""
    _ensure_stock_name_index()
    normalized = normalize_name(message)
    if len(normalized) >= 2 and _stock_name_detection_index:
        if any(name in normalized for name in _stock_name_detection_index):
            return True
    return _contains_pinyin_reference(message)


def contains_short_stock_name(message: str) -> bool:
    """是否包含自动派生的股票简称（不含语境门控）。"""
    normalized = normalize_name(message)
    if len(normalized) < 2:
        return False
    index = _ensure_short_name_index()
    return any(alias in normalized for alias in index)


def mentions_stock_target(message: str) -> bool:
    """是否应当视为股票标的：高置信引用，或“简称 + 股票语境词”。"""
    if contains_known_stock_name(message):
        return True
    # “这只/该股/买入”这类指向具体标的的措辞同样构成语境；
    # 只看泛化词会把“这只茅台还能拿吗”漏成未识别标的。
    if not (has_stock_context(message) or has_specific_stock_context(message)):
        return False
    return contains_short_stock_name(message)


def _normalize_source_id(source_id: object) -> str:
    known_source_ids = KNOWN_STOCK_NAME_SOURCE_IDS | KNOWN_SPOT_SOURCE_IDS
    return str(source_id) if source_id in known_source_ids else LEGACY_STOCK_NAMES_SOURCE_ID


_STOCK_NAME_MAP_SERVICE = BaseFileSnapshotService[StockNameMapSnapshot](
    cache_key="stock_name_map",
    ttl=86400,
    file_path=_STOCK_NAME_FILE,
)
_STOCK_NAME_FILE_MAX_AGE_SECONDS = 24 * 60 * 60
_stock_name_map_singleflight: AsyncSingleFlight[StockNameMapSnapshot] = AsyncSingleFlight()
_stock_name_detection_index: tuple[str, ...] | None = None
_stock_reference_names: tuple[str, ...] | None = None
_stock_short_name_index: frozenset[str] | None = None
_stock_pinyin_index: frozenset[str] | None = None


def _get_cninfo_provider():
    """Lazily resolve the Cninfo provider singleton."""
    return get_provider("cninfo")


def _get_baidu_provider():
    """Lazily resolve the Baidu provider singleton."""
    return get_provider("baidu")


def _get_eastmoney_provider():
    """Lazily resolve the EastMoney provider singleton."""
    return get_provider("eastmoney")


def _get_sina_provider():
    """Lazily resolve the Sina provider singleton."""
    return get_provider("sina")


def _get_tdxhub_provider():
    """Lazily resolve the TDX provider singleton."""
    return get_provider("tdxhub")


def _load_stock_name_file() -> StockNameMapSnapshot | None:
    """从本地 JSON 文件加载股票名称映射。

    Param:
        无
    Return:
        股票代码到名称的字典，数据量不足或异常时返回 None
    """
    try:
        if _STOCK_NAME_FILE.exists():
            with open(_STOCK_NAME_FILE, "r", encoding="utf-8") as f:
                payload = json.load(f)
            if isinstance(payload, dict) and isinstance(payload.get("mapping"), dict):
                mapping = payload["mapping"]
                source_id = _normalize_source_id(payload.get("source_id"))
                raw_overrides = payload.get("source_overrides")
                source_overrides = (
                    {
                        str(code): _normalize_source_id(source)
                        for code, source in raw_overrides.items()
                    }
                    if isinstance(raw_overrides, dict)
                    else {}
                )
            else:
                mapping = payload
                source_id = LEGACY_STOCK_NAMES_SOURCE_ID
                source_overrides = {}
            if isinstance(mapping, dict) and len(mapping) >= _STOCK_NAME_MAP_MIN_SIZE:
                logger.info(f"从本地文件加载股票名称映射: {len(mapping)} 只")
                return StockNameMapSnapshot(
                    mapping={str(code): str(name) for code, name in mapping.items()},
                    default_source_id=source_id,
                    source_overrides=source_overrides,
                )
            logger.info(f"本地文件映射不足({len(mapping) if isinstance(mapping, dict) else 0}只)，需重新获取")
    except Exception as e:
        logger.warning(f"读取本地股票名称文件失败: {e}")
    return None


def _load_stock_name_map_from_spot_snapshot() -> StockNameMapSnapshot | None:
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
            return StockNameMapSnapshot.from_source(mapping, get_spot_source(df))
    except Exception as e:
        logger.warning(f"从本地快照文件加载股票名称映射失败: {e}")
    return None


def _save_stock_name_file(snapshot: StockNameMapSnapshot) -> None:
    """将股票名称映射保存到本地 JSON 文件。

    Param:
        snapshot: 带来源信息的股票名称映射
    Return:
        无
    """
    try:
        payload = {
            "source_id": snapshot.default_source_id,
            "source_overrides": snapshot.source_overrides,
            "mapping": snapshot.mapping,
        }
        atomic_write_text(
            _STOCK_NAME_FILE,
            json.dumps(payload, ensure_ascii=False, indent=2),
        )
        logger.info(f"股票名称映射已保存到本地文件: {len(snapshot.mapping)} 只")
    except Exception as e:
        logger.warning(f"保存本地股票名称文件失败: {e}")


def _load_local_stock_name_map() -> StockNameMapSnapshot | None:
    """Load the standalone name file, falling back to the local market snapshot.

    A complete name file is authoritative and avoids reading the full market
    snapshot on every cold start; the snapshot is only a fallback (and may be
    stale/rejected as realtime data).
    """
    file_snapshot = _load_stock_name_file()
    if file_snapshot is not None:
        return file_snapshot
    return _load_stock_name_map_from_spot_snapshot()


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
        return bool(time() - _STOCK_NAME_FILE.stat().st_mtime > _STOCK_NAME_FILE_MAX_AGE_SECONDS)
    except OSError as e:
        logger.warning(f"检查本地股票名称文件新鲜度失败: {e}")
        return True


def _snapshot_from_exchange_master(master: ExchangeStockMaster) -> StockNameMapSnapshot | None:
    if not master.complete or len(master.records) < _STOCK_NAME_MAP_MIN_SIZE:
        return None
    default_source = SSE_STOCK_NAMES_SOURCE_ID
    return StockNameMapSnapshot(
        mapping=master.name_map,
        default_source_id=default_source,
        source_overrides={
            record.code: record.source
            for record in master.records
            if record.source != default_source
        },
    )


async def _fetch_stock_name_map_remote() -> StockNameMapSnapshot | None:
    """优先合并三大交易所官方名录，再回退到聚合股票名称来源。

    Param:
        无
    Return:
        股票代码到名称的字典，全部失败时返回空字典
    """
    try:
        master = await get_exchange_stock_master()
        official_snapshot = _snapshot_from_exchange_master(master)
        if official_snapshot is not None:
            logger.info("三大交易所官方股票名称映射: %s 只", len(master.records))
            return official_snapshot
        logger.info(
            "交易所统一股票主表不完整，回退聚合名称来源: count=%s failed=%s",
            len(master.records),
            sorted(master.failed_exchanges),
        )
    except Exception as error:
        logger.info("交易所统一股票主表不可用，回退聚合名称来源: %s", error)

    attempts = [
        StockNameSourceAttempt(
            source=TDXHUB_STOCK_NAMES,
            display_name="TDX",
            fetcher_factory=lambda: _get_tdxhub_provider().fetch_stock_names,
            semaphore=tdx_semaphore,
        )
    ]
    attempts.extend(
        [
            StockNameSourceAttempt(
                source=CNINFO_STOCK_NAMES,
                display_name="巨潮",
                fetcher_factory=lambda: _get_cninfo_provider().fetch_stock_names,
                semaphore=misc_semaphore,
            ),
            StockNameSourceAttempt(
                source=BAIDU_STOCK_NAMES,
                display_name="百度",
                fetcher_factory=lambda: _get_baidu_provider().fetch_stock_names,
                semaphore=baidu_semaphore,
            ),
            StockNameSourceAttempt(
                source=EASTMONEY_STOCK_NAMES,
                display_name="东方财富",
                fetcher_factory=lambda: _get_eastmoney_provider().fetch_stock_names,
                semaphore=eastmoney_semaphore,
            ),
            StockNameSourceAttempt(
                source=SINA_STOCK_NAMES,
                display_name="新浪",
                fetcher_factory=lambda: _get_sina_provider().fetch_stock_names,
                semaphore=sina_semaphore,
            ),
        ]
    )

    for index, attempt in enumerate(attempts):
        try:
            stocks = await provider_gateway.call(
                attempt.source.provider,
                attempt.source.operation,
                lambda: call_blocking(
                    attempt.fetcher_factory(),
                    semaphore=attempt.semaphore,
                ),
            )
            mapping = _mapping_from_stocks(stocks, attempt.display_name)
            if mapping:
                return StockNameMapSnapshot.from_source(mapping, attempt.source.id)
        except Exception as error:
            if index + 1 < len(attempts):
                logger.info(
                    "%s股票列表获取失败: %s，尝试%s",
                    attempt.display_name,
                    error,
                    attempts[index + 1].display_name,
                )
            else:
                logger.error("%s股票列表获取失败: %s", attempt.display_name, error)
    return None


async def _cache_and_persist_stock_name_map(snapshot: StockNameMapSnapshot) -> StockNameMapSnapshot:
    global _stock_name_detection_index, _stock_reference_names, _stock_short_name_index, _stock_pinyin_index
    _STOCK_NAME_MAP_SERVICE.set_cached(snapshot)
    _stock_reference_names = tuple(str(name) for name in snapshot.mapping.values())
    _stock_name_detection_index = _build_stock_name_detection_index(snapshot)
    _stock_short_name_index = None
    _stock_pinyin_index = None
    await call_blocking(
        _save_stock_name_file,
        snapshot,
        semaphore=misc_semaphore,
    )
    return snapshot


def _coerce_cached_snapshot(cached: object) -> StockNameMapSnapshot | None:
    if isinstance(cached, StockNameMapSnapshot):
        return cached
    if isinstance(cached, dict):
        return StockNameMapSnapshot.from_source(cached, LEGACY_STOCK_NAMES_SOURCE_ID)
    return None


async def _load_stock_name_map() -> StockNameMapSnapshot:
    cached = _coerce_cached_snapshot(_STOCK_NAME_MAP_SERVICE.get_cached())
    if cached is not None:
        return cached

    local_snapshot = await call_blocking(
        _load_local_stock_name_map,
        semaphore=misc_semaphore,
    )
    if local_snapshot is not None and local_snapshot.mapping:
        _STOCK_NAME_MAP_SERVICE.set_cached(local_snapshot)
        return cast(StockNameMapSnapshot, local_snapshot)

    remote_snapshot = await _fetch_stock_name_map_remote()
    if remote_snapshot is not None and remote_snapshot.mapping:
        return await _cache_and_persist_stock_name_map(remote_snapshot)
    return StockNameMapSnapshot.empty()


async def get_stock_name_map_snapshot() -> StockNameMapSnapshot:
    """获取带实际来源的股票名称映射快照。

    Param:
        无
    Return:
        股票名称映射及按股票记录的来源
    """
    cached = _coerce_cached_snapshot(_STOCK_NAME_MAP_SERVICE.get_cached())
    if cached is not None:
        return cached

    return cast(StockNameMapSnapshot, await _stock_name_map_singleflight.do(
        _STOCK_NAME_MAP_SERVICE.cache_key,
        _load_stock_name_map,
    ))


async def get_stock_name_map() -> dict[str, str]:
    """获取股票名称映射，保持原有字典接口兼容。"""
    return (await get_stock_name_map_snapshot()).mapping


async def _refresh_stock_name_map() -> None:
    """后台刷新股票名称映射并落地缓存与文件。

    Param:
        无
    Return:
        无
    """
    snapshot = await _fetch_stock_name_map_remote()
    if snapshot is None or not snapshot.mapping:
        raise RuntimeError("远程股票名称映射为空")
    await _cache_and_persist_stock_name_map(snapshot)
    logger.info(f"股票名称映射后台刷新完成: {len(snapshot.mapping)} 只")


async def build_stock_name_map() -> None:
    """预热股票名称映射；当本地文件超过 24 小时则触发后台刷新。

    Param:
        无
    Return:
        无
    """
    master = await get_exchange_stock_master()
    official_snapshot = _snapshot_from_exchange_master(master)
    if official_snapshot is not None:
        await _cache_and_persist_stock_name_map(official_snapshot)
        mapping = official_snapshot.mapping
    else:
        mapping = await get_stock_name_map()
    if not mapping:
        raise RuntimeError("股票名称映射预热结果为空")
    needs_refresh = await call_blocking(
        _stock_name_file_needs_refresh,
        semaphore=misc_semaphore,
    )
    if needs_refresh:
        await _refresh_stock_name_map()
