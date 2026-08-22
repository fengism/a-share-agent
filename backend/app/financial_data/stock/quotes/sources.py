"""股票行情快照来源标识。"""

import pandas as pd

SPOT_SOURCE_ATTR = "stock_spot_source_id"
SINA_SPOT_SOURCE_ID = "sina.spot_snapshot"
SINA_CN_RANK_SPOT_SOURCE_ID = "sina.cnrank_spot_snapshot"
EASTMONEY_SPOT_SOURCE_ID = "eastmoney.spot_snapshot"
AKSHARE_SPOT_SOURCE_ID = "akshare.eastmoney_spot_snapshot"
LEGACY_SPOT_SOURCE_ID = "cache.legacy_spot_snapshot"

KNOWN_SPOT_SOURCE_IDS = {
    SINA_SPOT_SOURCE_ID,
    SINA_CN_RANK_SPOT_SOURCE_ID,
    EASTMONEY_SPOT_SOURCE_ID,
    AKSHARE_SPOT_SOURCE_ID,
    LEGACY_SPOT_SOURCE_ID,
}


def mark_spot_source(frame: pd.DataFrame, source_id: str) -> pd.DataFrame:
    """在 DataFrame 元数据中记录快照的实际上游来源。"""
    if source_id not in KNOWN_SPOT_SOURCE_IDS:
        raise ValueError(f"未知行情快照来源: {source_id}")
    frame.attrs[SPOT_SOURCE_ATTR] = source_id
    return frame


def get_spot_source(frame: pd.DataFrame | None) -> str:
    """读取快照来源；旧缓存或缺失元数据时返回兼容来源。"""
    if frame is None:
        return LEGACY_SPOT_SOURCE_ID
    source_id = frame.attrs.get(SPOT_SOURCE_ATTR)
    if source_id in KNOWN_SPOT_SOURCE_IDS:
        return str(source_id)
    return LEGACY_SPOT_SOURCE_ID
