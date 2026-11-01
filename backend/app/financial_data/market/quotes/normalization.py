from enum import Enum
import logging
import pandas as pd

from app.constants.market import INDEX_FALLBACKS
from app.core.market import normalize_index_code, safe_float
from app.domain.market import IndexItem, MarketIndices

logger = logging.getLogger(__name__)


class VolumeUnit(str, Enum):
    SHARES = "shares"  # 股
    LOTS = "lots"      # 手


def resolve_adaptive_volume(
    raw_volume: float | None,
    *,
    amount: float | None = None,
    price: float | None = None,
    target_unit: VolumeUnit = VolumeUnit.LOTS,
    is_index: bool = False,
    symbol: str = "",
) -> float | None:
    """自适应探测并归一化成交量量纲（手 vs 股），防止上游口径变化或错误处理导致相差 100 倍。

    利用金融市场成交额、成交量与价格的三元物理自洽性推导当前原始值的量纲：
    1. 个股场景：
       implied_unit_price = amount / raw_volume
       ratio = implied_unit_price / price
       - 若 ratio 落在 [0.2, 5.0]，说明 raw_volume 原始量纲为【股】（Shares）；
       - 若 ratio 落在 [20.0, 500.0]，说明 raw_volume 原始量纲为【手】（Lots）；
    2. 指数场景：
       A 股宽基指数所有成分股的加权平均股价长期在 [5, 60] 元/股（每手约 [500, 6000] 元/手）。
       implied_unit_amount = amount / raw_volume
       - 若 implied_unit_amount 落在 [1.0, 150.0]，说明 raw_volume 原始量纲为【股】（Shares）；
       - 若 implied_unit_amount 落在 [200.0, 15000.0]，说明 raw_volume 原始量纲为【手】（Lots）；
       - 若 implied_unit_amount 落在 [20000.0, 2000000.0]，说明 raw_volume 原始量纲为【百手】（被错误除以100）；
    3. 兜底策略：
       若缺少有效 price 或 amount（如集合竞价无成交/停牌），退化到基于市场代码前缀规则兜底。
    """
    if raw_volume is None or raw_volume <= 0:
        return raw_volume

    detected_unit: VolumeUnit | str | None = None

    if amount is not None and amount > 0:
        if is_index:
            implied_unit_amount = amount / raw_volume
            if 1.0 <= implied_unit_amount <= 150.0:
                detected_unit = VolumeUnit.SHARES
            elif 200.0 <= implied_unit_amount <= 15000.0:
                detected_unit = VolumeUnit.LOTS
            elif 20000.0 <= implied_unit_amount <= 2000000.0:
                detected_unit = "hundred_lots"
        elif price is not None and price > 0:
            implied_unit_price = amount / raw_volume
            ratio = implied_unit_price / price
            if 0.2 <= ratio <= 5.0:
                detected_unit = VolumeUnit.SHARES
            elif 20.0 <= ratio <= 500.0:
                detected_unit = VolumeUnit.LOTS

    # 兜底：根据代码前缀推断
    if detected_unit is None:
        sym = symbol.strip().lower()
        if is_index:
            # 新浪/通用接口中，沪市指数（sh/000/000001/000300）多为手，深市/北证为股
            if sym.startswith("sh") or sym in ("000001", "000300", "000016", "000905", "000688"):
                detected_unit = VolumeUnit.LOTS
            elif sym.startswith(("sz", "bj")) or sym in ("399001", "399006", "899050"):
                detected_unit = VolumeUnit.SHARES
            else:
                detected_unit = VolumeUnit.LOTS
        else:
            # 个股科创板（688/689）在腾讯等接口中多为股，其他为主板手
            raw_code = sym.replace("sh", "").replace("sz", "").replace("bj", "")
            if raw_code.startswith(("688", "689")):
                detected_unit = VolumeUnit.SHARES
            else:
                detected_unit = VolumeUnit.LOTS

    # 转换为目标单位
    if target_unit == VolumeUnit.LOTS:
        if detected_unit == VolumeUnit.SHARES:
            return raw_volume / 100.0
        if detected_unit == "hundred_lots":
            return raw_volume * 100.0
        return raw_volume
    else:  # target_unit == VolumeUnit.SHARES
        if detected_unit == VolumeUnit.LOTS:
            return raw_volume * 100.0
        if detected_unit == "hundred_lots":
            return raw_volume * 10000.0
        return raw_volume


def normalize_indices(indices: list[IndexItem]) -> list[IndexItem]:
    """Filter and order index items to match the canonical INDEX_FALLBACKS order.

    Param:
        indices: list of IndexItem to normalize
    Return:
        filtered list of IndexItem, sorted by INDEX_FALLBACKS order
    """
    fallback_map = {code: (name, idx) for idx, (code, name, _secid) in enumerate(INDEX_FALLBACKS)}
    normalized: list[IndexItem] = []
    for item in indices:
        code = normalize_index_code(item.code)
        fallback = fallback_map.get(code)
        if fallback is None:
            continue
        fallback_name, _order = fallback
        normalized.append(
            IndexItem(
                code=code,
                name=item.name or fallback_name,
                price=item.price,
                change_pct=item.change_pct,
                volume=item.volume,
                amount=item.amount,
                open=item.open,
                high=item.high,
                low=item.low,
                amplitude=item.amplitude,
                pre_close=item.pre_close,
            )
        )

    normalized.sort(key=lambda item: fallback_map[item.code][1])
    return normalized


def build_indices_from_sina(df: pd.DataFrame) -> MarketIndices:
    """Build a MarketIndices object from a Sina quote DataFrame.

    Param:
        df: DataFrame with Sina-formatted index columns
    Return:
        MarketIndices containing normalized index items
    """
    indices: list[IndexItem] = []
    for _, row in df.iterrows():
        raw_code = str(row.get("代码", ""))
        price = safe_float(row.get("最新价"))
        raw_volume = safe_float(row.get("成交量"))
        amount = safe_float(row.get("成交额"))
        # 新浪接口沪市指数原始多为手、深市/北证多为股；通过自适应量纲解析归一为「手」
        volume = resolve_adaptive_volume(
            raw_volume,
            amount=amount,
            price=price,
            target_unit=VolumeUnit.LOTS,
            is_index=True,
            symbol=raw_code,
        )
        indices.append(
            IndexItem(
                code=normalize_index_code(raw_code),
                name=str(row.get("名称", "")),
                price=price,
                change_pct=safe_float(row.get("涨跌幅")),
                volume=volume,
                amount=amount,
                open=safe_float(row.get("今开")),
                high=safe_float(row.get("最高")),
                low=safe_float(row.get("最低")),
                amplitude=safe_float(row.get("振幅")),
                pre_close=safe_float(row.get("昨收")),
            )
        )

    return MarketIndices(indices=normalize_indices(indices))


def filter_index_hist_range(df: pd.DataFrame, start_date: str, end_date: str) -> pd.DataFrame:
    """Filter an index history DataFrame to the given date range.

    Param:
        df: DataFrame with a "date" column
        start_date: inclusive start date string (YYYY-MM-DD), or empty for no lower bound
        end_date: inclusive end date string (YYYY-MM-DD), or empty for no upper bound
    Return:
        filtered DataFrame with reset index and "date" column formatted as "YYYY-MM-DD"
    """
    if df.empty:
        return df
    result = df.copy()
    result["date"] = pd.to_datetime(result["date"], errors="coerce")
    result = result.dropna(subset=["date"])
    if start_date:
        result = result[result["date"] >= pd.to_datetime(start_date)]
    if end_date:
        result = result[result["date"] <= pd.to_datetime(end_date)]
    result["date"] = result["date"].dt.strftime("%Y-%m-%d")
    return result.reset_index(drop=True)
