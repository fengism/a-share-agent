"""A 股公司行为与仿射复权因子的持久化和应用。"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
import time
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

import pandas as pd
from tdxhub import __version__ as tdxhub_version
from tdxhub.gbbq import CATEGORY_NAMES, adjustment_factors, normalize_gbbq

from app.core.concurrency.rate_limiter import call_blocking, sina_semaphore, tdx_semaphore
from app.domain.market import KlineData, KlineItem
from app.infrastructure.providers.registry import get_provider
from app.modules.market_daily.models import (
    MarketAdjustmentFactorStatus,
    MarketCorporateAction,
    MarketDailyAdjustmentFactor,
    MarketDailyBar,
)
from app.modules.market_daily.paths import MARKET_DAILY_DATABASE_PATH
from app.modules.market_daily.repository import MarketDailyBarRepository

logger = logging.getLogger(__name__)

ALGORITHM_VERSION = f"tdxhub-gbbq-affine-v1-sdk-{tdxhub_version}"
SINA_ALGORITHM_VERSION = "sina-multiplicative-v1"
LOCAL_ALGORITHM_VERSIONS = frozenset({ALGORITHM_VERSION, SINA_ALGORITHM_VERSION})
HK_FACTOR_ALGORITHM_VERSIONS = frozenset({"hk-csv-qfq-affine-v1"})
ALL_FACTOR_ALGORITHM_VERSIONS = LOCAL_ALGORITHM_VERSIONS | HK_FACTOR_ALGORITHM_VERSIONS
FACTOR_REFRESH_TTL = timedelta(hours=24)
FACTOR_FAILURE_RETRY_TTL = timedelta(minutes=5)
# 读本地复权 K 线时，向 start_date 之前多取的自然日数，仅用于拿到"前一根"做
# 前收/涨跌幅衔接；14 天足以跨过春节/国庆等最长连续休市。
_ADJUSTMENT_ANCHOR_LOOKBACK_DAYS = 14
_FACTOR_SOURCE = "tdxhub.gbbq.adjustment_factors"
_SINA_FACTOR_SOURCE = "sina.qfq_hfq"
_ACTION_SOURCE = "tdxhub.xdxr"
_CANONICAL_ANCHOR = date(1990, 1, 1)
_OHLC = ("open", "high", "low", "close")
# 会引起除权参考价变化的公司行为字段：任一非零即意味着该股确实有过除权除息。
_PRICE_AFFECTING_ACTION_COLUMNS = ("fenhong", "songzhuangu", "peigu", "suogu")

_repository = MarketDailyBarRepository(MARKET_DAILY_DATABASE_PATH)
_code_locks: dict[str, asyncio.Lock] = {}
_code_locks_guard = asyncio.Lock()


def _number(value: object) -> float:
    if value is None or pd.isna(value):
        return 0.0
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return 0.0


def _json_value(value: object) -> object:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "item"):
        value = value.item()
    return value


def _normalize_actions(code: str, raw: pd.DataFrame) -> tuple[pd.DataFrame, list[MarketCorporateAction], str]:
    normalized = normalize_gbbq(raw)
    serializable: list[dict[str, object]] = []
    actions: list[MarketCorporateAction] = []
    date_sequences: dict[str, int] = {}
    for action_date, row in normalized.iterrows():
        action_text = pd.Timestamp(action_date).date().isoformat()
        sequence = date_sequences.get(action_text, 0)
        date_sequences[action_text] = sequence + 1
        payload = {
            key: _json_value(value)
            for key, value in sorted(row.to_dict().items())
            if key != "category_name"
        }
        canonical = {
            "date": action_text,
            "sequence": sequence,
            **payload,
        }
        serializable.append(canonical)
        category = int(row["category"])
        actions.append(MarketCorporateAction(
            code=code,
            action_date=pd.Timestamp(action_date).date(),
            sequence=sequence,
            category=category,
            category_name=str(row.get("category_name") or CATEGORY_NAMES.get(category, category)),
            cash_dividend=_number(row.get("fenhong")),
            rights_shares=_number(row.get("peigu")),
            rights_price=_number(row.get("peigujia")),
            bonus_shares=_number(row.get("songzhuangu")),
            split_ratio=_number(row.get("suogu")),
            raw_json=json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            source=_ACTION_SOURCE,
        ))
    encoded = json.dumps(serializable, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return normalized, actions, hashlib.sha256(encoded.encode()).hexdigest()


def _has_price_affecting_actions(
    actions: pd.DataFrame | None,
    trading_dates: list[date] | None = None,
) -> bool:
    """该股是否存在会引起除权参考价变化的公司行为。

    区分"本来就没有公司行为"（因子恒为 1.0 是正确结果）与"上游返回了退化数据"
    （有公司行为却算出恒定因子）是关键：两者在因子表里长得一模一样。
    """
    if actions is None or len(actions) == 0:
        return False
    frame = actions
    if trading_dates:
        first_day = min(trading_dates)
        try:
            frame = actions[actions.index >= pd.Timestamp(first_day)]
        except Exception:
            frame = actions
    if len(frame) == 0:
        return False
    for column in _PRICE_AFFECTING_ACTION_COLUMNS:
        if column not in frame.columns:
            continue
        values = pd.to_numeric(frame[column], errors="coerce").fillna(0.0)
        if bool(values.abs().gt(0).any()):
            return True
    return False


def _build_factors(
    code: str,
    trading_dates: list[date],
    actions: pd.DataFrame,
    action_hash: str,
    calculated_at: datetime,
) -> list[MarketDailyAdjustmentFactor]:
    if not trading_dates:
        return []
    # HFQ 的基准必须早于上市与公司行为；否则仅用本地数据起点会改变后复权锚点。
    dates = [_CANONICAL_ANCHOR, *trading_dates]
    frame = adjustment_factors(dates, actions).iloc[1:]
    factor_columns = ["qfq_mul", "qfq_add", "hfq_mul", "hfq_add"]
    if frame[factor_columns].isna().any().any():
        raise ValueError(f"{code} 复权因子包含空值")
    if not all(math.isfinite(float(value)) for value in frame[factor_columns].to_numpy().flat):
        raise ValueError(f"{code} 复权因子包含非有限值")
    # TDX 抖动时会返回"非空但无意义"的 XDXR 帧（协议层 unpack 失败等），规范化后
    # 仍是一张结构合法的表，算出来的因子恒为 1.0。上面两条校验都能通过，于是
    # 静默把一份毫无信息量的因子表写进库——直到有人对比复权价时才发现整条曲线
    # 没有任何跳变。这里用"有公司行为 ⇒ 因子必须变化"把它挡在写库之前。
    if _has_price_affecting_actions(actions, trading_dates):
        distinct = {
            (round(float(row["qfq_mul"]), 8), round(float(row["qfq_add"]), 8),
             round(float(row["hfq_mul"]), 8), round(float(row["hfq_add"]), 8))
            for _, row in frame.iterrows()
        }
        if len(distinct) < 2:
            raise ValueError(f"{code} 存在除权除息行为但复权因子恒定，拒绝写入退化因子表")
    return [
        MarketDailyAdjustmentFactor(
            code=code,
            trade_date=trading_day,
            qfq_multiplier=float(row["qfq_mul"]),
            qfq_offset=float(row["qfq_add"]),
            hfq_multiplier=float(row["hfq_mul"]),
            hfq_offset=float(row["hfq_add"]),
            action_hash=action_hash,
            algorithm_version=ALGORITHM_VERSION,
            source=_FACTOR_SOURCE,
            calculated_at=calculated_at,
        )
        for trading_day, (_, row) in zip(trading_dates, frame.iterrows(), strict=True)
    ]


def _build_sina_factors(
    code: str,
    trading_dates: list[date],
    raw_factors: dict[str, pd.DataFrame],
    calculated_at: datetime,
) -> tuple[list[MarketDailyAdjustmentFactor], str]:
    """将新浪除权日因子对齐到本地交易日。

    新浪定义为 qfq_price = raw_price / qfq_factor、
    hfq_price = raw_price * hfq_factor，只能表达乘法复权，不能替代 TDX 的仿射公司行为。
    """
    if not trading_dates:
        return [], hashlib.sha256(b"[]").hexdigest()

    canonical: dict[str, list[dict[str, object]]] = {}
    aligned: dict[str, pd.Series] = {}
    target_index = pd.DatetimeIndex(pd.to_datetime(trading_dates), name="date")
    for method in ("qfq", "hfq"):
        frame = raw_factors.get(method)
        if frame is None or not {"date", "factor"}.issubset(frame.columns):
            raise ValueError(f"{code} 新浪 {method} 复权因子缺失")
        normalized = frame.loc[:, ["date", "factor"]].copy()
        normalized["date"] = pd.to_datetime(normalized["date"], errors="coerce").dt.normalize()
        normalized["factor"] = pd.to_numeric(normalized["factor"], errors="coerce")
        normalized = (
            normalized.dropna(subset=["date", "factor"])
            .sort_values("date")
            .drop_duplicates("date", keep="last")
        )
        if normalized.empty:
            raise ValueError(f"{code} 新浪 {method} 复权因子为空")
        values = normalized["factor"].astype(float)
        if (values <= 0).any() or not all(math.isfinite(value) for value in values):
            raise ValueError(f"{code} 新浪 {method} 复权因子包含非正或非有限值")
        canonical[method] = [
            {"date": timestamp.date().isoformat(), "factor": float(factor)}
            for timestamp, factor in zip(normalized["date"], values, strict=True)
        ]
        series = pd.Series(values.to_numpy(), index=pd.DatetimeIndex(normalized["date"]), dtype=float)
        expanded_index = series.index.union(target_index).sort_values()
        aligned_values = series.reindex(expanded_index).ffill().bfill().reindex(target_index)
        if aligned_values.isna().any():
            raise ValueError(f"{code} 新浪 {method} 复权因子无法覆盖本地交易日")
        aligned[method] = aligned_values

    encoded = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    factor_hash = hashlib.sha256(encoded.encode()).hexdigest()
    factors: list[MarketDailyAdjustmentFactor] = []
    for index, trading_day in enumerate(trading_dates):
        qfq_factor = float(aligned["qfq"].iloc[index])
        hfq_factor = float(aligned["hfq"].iloc[index])
        qfq_multiplier = 1.0 / qfq_factor
        if not math.isfinite(qfq_multiplier):
            raise ValueError(f"{code} 新浪 qfq 复权乘数无效")
        factors.append(MarketDailyAdjustmentFactor(
            code=code,
            trade_date=trading_day,
            qfq_multiplier=qfq_multiplier,
            qfq_offset=0.0,
            hfq_multiplier=hfq_factor,
            hfq_offset=0.0,
            action_hash=factor_hash,
            algorithm_version=SINA_ALGORITHM_VERSION,
            source=_SINA_FACTOR_SOURCE,
            calculated_at=calculated_at,
        ))
    return factors, factor_hash


def _state_is_fresh(
    state: dict[str, object] | None,
    expected_count: int,
    now: datetime,
    allowed_versions: frozenset[str] | None = None,
) -> bool:
    if allowed_versions is None:
        allowed_versions = LOCAL_ALGORITHM_VERSIONS
    if state is None or bool(state.get("using_last_good")) or bool(state.get("last_error")):
        return False
    factor_count = state.get("factor_count")
    try:
        normalized_count = int(str(factor_count))
    except (TypeError, ValueError):
        return False
    if state.get("algorithm_version") not in allowed_versions or normalized_count != expected_count:
        return False
    try:
        checked_at = datetime.fromisoformat(
            str(state.get("last_checked_at") or state["calculated_at"])
        )
    except (KeyError, ValueError):
        return False
    if checked_at.tzinfo is None:
        checked_at = checked_at.replace(tzinfo=UTC)
    return now.astimezone(UTC) - checked_at.astimezone(UTC) < FACTOR_REFRESH_TTL


_HEALTHY_CONFIRMATION_TTL_SECONDS = 5 * 60
_HEALTHY_CACHE_MAXSIZE = 4096
# code -> 到期单调时刻。命中即代表 DB 中因子覆盖完整且新鲜，可跳过 4 次点查。
_healthy_cache: dict[str, float] = {}


def _healthy_cache_get(code: str, now_monotonic: float) -> bool:
    expires_at = _healthy_cache.get(code)
    if expires_at is None:
        return False
    if expires_at <= now_monotonic:
        _healthy_cache.pop(code, None)
        return False
    return True


def _healthy_cache_set(code: str, now_monotonic: float) -> None:
    if len(_healthy_cache) >= _HEALTHY_CACHE_MAXSIZE:
        _healthy_cache.clear()
    _healthy_cache[code] = now_monotonic + _HEALTHY_CONFIRMATION_TTL_SECONDS


def _healthy_cache_clear(code: str) -> None:
    _healthy_cache.pop(code, None)


def clear_adjustment_health_cache() -> None:
    """清空因子健康缓存。

    库结构修复（如日行情库 v2 迁移）会重写复权因子，此时必须丢弃「已确认健康」的
    判定，否则后续读取会跳过点查而直接吃旧结论。原先由 ``app.core.cache`` 反向
    import 本模块的私有字典实现，现改为由本模块对外暴露清理入口。
    """
    _healthy_cache.clear()


def canonical_adjustment_anchor() -> date:
    """返回复权因子的基准锚点日期（早于上市日与所有公司行为）。"""
    return _CANONICAL_ANCHOR


def _last_good_failure_is_cooling_down(
    state: dict[str, object] | None,
    now: datetime,
) -> bool:
    if state is None or not state.get("last_error") or not bool(state.get("using_last_good")):
        return False
    try:
        checked_at = datetime.fromisoformat(str(state["last_checked_at"]))
    except (KeyError, ValueError):
        return False
    if checked_at.tzinfo is None:
        checked_at = checked_at.replace(tzinfo=UTC)
    return now.astimezone(UTC) - checked_at.astimezone(UTC) < FACTOR_FAILURE_RETRY_TTL


async def _lock_for(code: str) -> asyncio.Lock:
    async with _code_locks_guard:
        return _code_locks.setdefault(code, asyncio.Lock())


async def ensure_adjustment_factors(code: str, *, force: bool = False) -> bool:
    """确保 A 股本地交易日有可用复权系数；TDX 仿射优先，新浪乘法兜底。"""
    lock = await _lock_for(code)
    async with lock:
        # 已确认健康则直接返回，跳过 3 次点查 + 1 次 DDL 检查；盘中高频读取的主要开销在此。
        now_monotonic = time.monotonic()
        if not force and _healthy_cache_get(code, now_monotonic):
            return True
        await asyncio.to_thread(_repository.initialize)
        trading_dates = await asyncio.to_thread(_repository.list_stock_dates, code)
        if not trading_dates:
            return False
        now = datetime.now(UTC)
        state = await asyncio.to_thread(_repository.get_factor_state, code)
        factor_dates = await asyncio.to_thread(_repository.list_adjustment_factor_dates, code)
        last_good_complete = (
            state is not None
            and state.get("algorithm_version") in LOCAL_ALGORITHM_VERSIONS
            and factor_dates == trading_dates
        )
        if not force and last_good_complete and _state_is_fresh(state, len(trading_dates), now):
            _healthy_cache_set(code, now_monotonic)
            return True
        if not force and last_good_complete and _last_good_failure_is_cooling_down(state, now):
            _healthy_cache_set(code, now_monotonic)
            return True
        _healthy_cache_clear(code)
        try:
            raw = await call_blocking(
                get_provider("tdxhub").fetch_stock_xdxr,
                code,
                semaphore=tdx_semaphore,
            )
            normalized, actions, action_hash = await asyncio.to_thread(_normalize_actions, code, raw)
            existing_action_count = await asyncio.to_thread(
                _repository.count_corporate_actions, code
            )
            if normalized.empty and (
                existing_action_count > 0
                or (state is not None and state.get("algorithm_version") == SINA_ALGORITHM_VERSION)
            ):
                raise RuntimeError("TDX XDXR 临时返回空数据，拒绝覆盖已有复权依据")
            if (
                last_good_complete
                and state is not None
                and state.get("algorithm_version") == ALGORITHM_VERSION
                and state.get("action_hash") == action_hash
            ):
                await asyncio.to_thread(_repository.mark_factor_check, code, now)
                return True
            factors = await asyncio.to_thread(
                _build_factors,
                code,
                trading_dates,
                normalized,
                action_hash,
                now,
            )
            await asyncio.to_thread(
                _repository.replace_adjustment_data,
                code,
                actions=actions,
                factors=factors,
                action_hash=action_hash,
                algorithm_version=ALGORITHM_VERSION,
                source=_FACTOR_SOURCE,
                calculated_at=now,
            )
            return True
        except Exception as tdx_error:
            has_complete_tdx_last_good = (
                last_good_complete
                and state is not None
                and state.get("algorithm_version") == ALGORITHM_VERSION
            )
            if has_complete_tdx_last_good:
                await asyncio.to_thread(
                    _repository.mark_factor_check,
                    code,
                    now,
                    error=f"{type(tdx_error).__name__}: {tdx_error}",
                    using_last_good=True,
                )
                logger.warning(
                    "TDX 复权因子刷新失败，继续使用覆盖完整的 TDX last-good: code=%s",
                    code,
                    exc_info=True,
                )
                return True
            logger.warning("TDX 复权因子刷新失败，尝试新浪乘法因子: code=%s", code, exc_info=True)
            try:
                raw_sina_factors = await call_blocking(
                    get_provider("sina").fetch_adjustment_factors,
                    code,
                    semaphore=sina_semaphore,
                )
                sina_factors, factor_hash = await asyncio.to_thread(
                    _build_sina_factors,
                    code,
                    trading_dates,
                    raw_sina_factors,
                    now,
                )
                await asyncio.to_thread(
                    _repository.replace_adjustment_factors,
                    code,
                    factors=sina_factors,
                    factor_hash=factor_hash,
                    algorithm_version=SINA_ALGORITHM_VERSION,
                    source=_SINA_FACTOR_SOURCE,
                    calculated_at=now,
                )
                return True
            except Exception as sina_error:
                if last_good_complete:
                    combined_error = (
                        f"TDX {type(tdx_error).__name__}: {tdx_error}; "
                        f"Sina {type(sina_error).__name__}: {sina_error}"
                    )
                    await asyncio.to_thread(
                        _repository.mark_factor_check,
                        code,
                        now,
                        error=combined_error,
                        using_last_good=True,
                    )
                    logger.warning(
                        "TDX 与新浪因子刷新均失败，继续使用覆盖完整的 last-good: code=%s",
                        code,
                        exc_info=True,
                    )
                    return True
                logger.warning(
                    "新浪乘法复权因子也不可用，回退既有 K 线上游: code=%s tdx_error=%s sina_error=%s",
                    code,
                    tdx_error,
                    sina_error,
                    exc_info=True,
                )
                return False


def _parse_optional_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _parse_optional_date(value: object) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _safe_int(value: object) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0


async def get_adjustment_factor_status(code: str, market: str = "cn") -> MarketAdjustmentFactorStatus:
    await asyncio.to_thread(_repository.initialize)
    summary = await asyncio.to_thread(_repository.get_adjustment_summary, code, market=market)
    state = summary.get("state")
    state_dict = state if isinstance(state, dict) else {}
    bar_count = _safe_int(summary.get("bar_count"))
    factor_count = _safe_int(summary.get("factor_count"))
    coverage_complete = bar_count > 0 and factor_count == bar_count
    using_last_good = bool(state_dict.get("using_last_good"))
    allowed_versions = HK_FACTOR_ALGORITHM_VERSIONS if market == "hk" else LOCAL_ALGORITHM_VERSIONS
    if bar_count == 0 or not state_dict:
        status = "missing"
    elif not coverage_complete:
        status = "incomplete"
    elif using_last_good or state_dict.get("last_error"):
        status = "degraded"
    elif state_dict.get("algorithm_version") not in allowed_versions:
        status = "degraded"
    elif _state_is_fresh(state_dict, bar_count, datetime.now(UTC), allowed_versions):
        status = "healthy"
    else:
        status = "stale"
    return MarketAdjustmentFactorStatus(
        code=code,
        status=status,
        bar_count=bar_count,
        factor_count=factor_count,
        action_count=_safe_int(summary.get("action_count")),
        first_bar_date=_parse_optional_date(summary.get("first_bar_date")),
        last_bar_date=_parse_optional_date(summary.get("last_bar_date")),
        first_factor_date=_parse_optional_date(summary.get("first_factor_date")),
        last_factor_date=_parse_optional_date(summary.get("last_factor_date")),
        action_hash=str(state_dict.get("action_hash")) if state_dict.get("action_hash") else None,
        algorithm_version=(
            str(state_dict.get("algorithm_version")) if state_dict.get("algorithm_version") else None
        ),
        source=str(state_dict.get("source")) if state_dict.get("source") else None,
        calculated_at=_parse_optional_datetime(state_dict.get("calculated_at")),
        last_checked_at=_parse_optional_datetime(state_dict.get("last_checked_at")),
        last_error=str(state_dict.get("last_error")) if state_dict.get("last_error") else None,
        using_last_good=using_last_good,
        coverage_complete=coverage_complete,
    )


async def refresh_adjustment_factors(code: str, *, force: bool = True) -> MarketAdjustmentFactorStatus:
    await ensure_adjustment_factors(code, force=force)
    return await get_adjustment_factor_status(code)


async def invalidate_adjustment_factors(code: str, market: str = "cn") -> MarketAdjustmentFactorStatus:
    _healthy_cache_clear(code)
    await asyncio.to_thread(_repository.initialize)
    await asyncio.to_thread(_repository.invalidate_adjustment_factors, code, market=market)
    return await get_adjustment_factor_status(code, market=market)


def _adjust_price(value: float | None, multiplier: float, offset: float) -> float | None:
    if value is None:
        return None
    adjusted = Decimal(str(value)) * Decimal(str(multiplier)) + Decimal(str(offset))
    return float(adjusted.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def apply_adjustment(
    bars: list[MarketDailyBar],
    factors: list[MarketDailyAdjustmentFactor],
    method: str,
) -> KlineData | None:
    """按日期应用本地仿射因子；因子不完整时返回 None 触发上游回退。"""
    if method not in {"qfq", "hfq"} or not bars:
        return None
    factor_by_date = {factor.trade_date: factor for factor in factors}
    if any(bar.trade_date not in factor_by_date for bar in bars):
        return None
    items: list[KlineItem] = []
    previous_adjusted_close: float | None = None
    for bar in sorted(bars, key=lambda item: item.trade_date):
        factor = factor_by_date[bar.trade_date]
        multiplier = factor.qfq_multiplier if method == "qfq" else factor.hfq_multiplier
        offset = factor.qfq_offset if method == "qfq" else factor.hfq_offset
        if multiplier is None or offset is None:
            return None
        adjusted = {field: _adjust_price(getattr(bar, field), multiplier, offset) for field in _OHLC}
        fallback_pre_close = _adjust_price(bar.pre_close, multiplier, offset)
        pre_close = previous_adjusted_close if previous_adjusted_close is not None else fallback_pre_close
        close = adjusted["close"]
        open_price = adjusted["open"] if adjusted["open"] is not None else close
        high_price = adjusted["high"] if adjusted["high"] is not None else close
        low_price = adjusted["low"] if adjusted["low"] is not None else close
        if (
            close is None
            or open_price is None
            or high_price is None
            or low_price is None
            or min(open_price, high_price, low_price, close) <= 0
            or high_price < max(open_price, close)
            or low_price > min(open_price, close)
        ):
            logger.warning(
                "本地复权 OHLC 校验失败，回退上游: code=%s date=%s method=%s",
                bar.code,
                bar.trade_date,
                method,
            )
            return None
        change_pct = None
        if pre_close is not None and pre_close != 0:
            change_pct = (close - pre_close) / pre_close * 100
        amplitude = None
        if pre_close is not None and pre_close > 0 and adjusted["high"] is not None and adjusted["low"] is not None:
            amplitude = (adjusted["high"] - adjusted["low"]) / pre_close * 100
        items.append(KlineItem(
            code=bar.code,
            date=bar.trade_date.isoformat(),
            open=open_price,
            high=high_price,
            low=low_price,
            close=close,
            pre_close=pre_close,
            change_pct=change_pct,
            amplitude=amplitude,
            volume=bar.volume or 0,
            amount=bar.amount or 0,
        ))
        previous_adjusted_close = close
    statuses = sorted({bar.verification_status for bar in bars})
    return KlineData(
        code=bars[0].code,
        period="daily",
        adjust=method,
        source=(
            f"market_daily:{method}:"
            f"{'sina_factor' if all(factor.source == _SINA_FACTOR_SOURCE for factor in factors) else 'tdxhub_xdxr'}:"
            f"{'+'.join(statuses)}"
        ),
        adjustment_verified=True,
        items=items,
    )


async def load_local_adjusted_daily_kline(
    code: str,
    start_date: date,
    end_date: date,
    method: str,
    *,
    market: str = "cn",
) -> KlineData | None:
    if method not in {"qfq", "hfq"}:
        return None
    try:
        await asyncio.to_thread(_repository.initialize)
        # 只读区间 + 之前一个自然日窗口作为锚点：复制 apply_adjustment 全量读取时
        # 首根 bar 的前收衔接语义（依赖紧随其前的那一根），无需扫描全部历史。
        read_start = max(date.min, start_date - timedelta(days=_ADJUSTMENT_ANCHOR_LOOKBACK_DAYS))
        bars = await asyncio.to_thread(
            _repository.list_bars,
            market=market,
            instrument_type="stock",
            code=code,
            start_date=read_start,
            end_date=end_date,
        )
        # 区间内没有真实 bar 时不再取锚点，交由调用方回退上游（与全量读取一致）。
        if not any(start_date <= bar.trade_date <= end_date for bar in bars):
            return None
        if market == "cn":
            if not await ensure_adjustment_factors(code):
                return None
        factors = await asyncio.to_thread(
            _repository.list_adjustment_factors,
            code,
            read_start,
            end_date,
            market=market,
        )
        if not factors:
            return None
        adjusted = apply_adjustment(bars, factors, method)
        if adjusted is None:
            return None
        filtered = [item for item in adjusted.items if start_date.isoformat() <= item.date <= end_date.isoformat()]
        if not filtered:
            return None
        return adjusted.model_copy(update={"items": filtered})
    except Exception:
        logger.warning("本地复权行情读取失败，回退既有 K 线上游: market=%s code=%s", market, code, exc_info=True)
        return None
