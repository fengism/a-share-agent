"""策略信号聚合、技术质量与风险画像。"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from app.modules.potential import constants
from app.modules.potential.common import _float_or_none, _limit_ratio
from app.modules.potential.themes import _theme_score
from app.modules.quant.engine import build_target_positions
from app.modules.quant.public import mining_weight

logger = logging.getLogger(__name__)

_MAX_SIGNAL_AGE_DAYS = constants._MAX_SIGNAL_AGE_DAYS
_FRESH_SIGNAL_BONUS = constants._FRESH_SIGNAL_BONUS
_STRATEGY_FAMILIES = constants._STRATEGY_FAMILIES
_FAMILY_CAPS = constants._FAMILY_CAPS
_REGIME_FAMILY_MULTIPLIERS = constants._REGIME_FAMILY_MULTIPLIERS
_AGREEMENT_BONUS_PER_FAMILY = constants._AGREEMENT_BONUS_PER_FAMILY
_MIN_MARKET_CAP_YI = constants._MIN_MARKET_CAP_YI
_MAX_MARKET_CAP_YI = constants._MAX_MARKET_CAP_YI


def _latest_entry_index(positions: Sequence[int | float]) -> int | None:
    for index in range(len(positions) - 1, -1, -1):
        if positions[index] == 1 and (index == 0 or positions[index - 1] != 1):
            return index
    return None

def _signal_decay(age: int) -> float:
    """信号时效衰减：0 日 1.5 倍，5 日线性衰减到 1.0 倍。"""
    if age <= 0:
        return _FRESH_SIGNAL_BONUS
    if age >= _MAX_SIGNAL_AGE_DAYS:
        return 1.0
    return round(
        _FRESH_SIGNAL_BONUS - (age / _MAX_SIGNAL_AGE_DAYS) * (_FRESH_SIGNAL_BONUS - 1.0),
        3,
    )

def _regime_multiplier(regime: str, family: str) -> float:
    """按市场环境调整策略族权重。"""
    multipliers = _REGIME_FAMILY_MULTIPLIERS.get(regime, _REGIME_FAMILY_MULTIPLIERS["neutral"])
    return multipliers.get(family, 1.0)

def _evaluate_strategies(
    bars_items: list,
    strategy_snapshots: dict,
    regime: str = "neutral",
) -> tuple[list[str], str, int | None, float, list[str]]:
    """对单只股票的全部策略求信号，并按策略族聚合、封顶、加一致性奖励。"""
    hits: list[str] = []
    latest_signal_date = ""
    signal_age: int | None = None
    family_scores: dict[str, float] = {}
    for key, snapshot in strategy_snapshots.items():
        try:
            positions = build_target_positions(bars_items, snapshot)
        except Exception as error:  # noqa: BLE001 - 单个策略异常不应中断其余策略
            logger.debug("潜力股策略信号计算失败 key=%s: %s", key, error)
            continue
        if not positions or positions[-1] != 1:
            continue
        entry_index = _latest_entry_index(positions)
        if entry_index is None:
            continue
        age = len(positions) - 1 - entry_index
        if age > _MAX_SIGNAL_AGE_DAYS:
            continue
        family = _STRATEGY_FAMILIES.get(key, "other")
        weighted = mining_weight(key) * _signal_decay(age) * _regime_multiplier(regime, family)
        family_scores[family] = family_scores.get(family, 0.0) + weighted
        hits.append(snapshot.definition.name)
        if signal_age is None or age < signal_age:
            signal_age = age
            latest_signal_date = bars_items[entry_index].date
    if not hits:
        return [], "", None, 0.0, []
    base_score = sum(
        min(score, _FAMILY_CAPS.get(family, _FAMILY_CAPS["other"])) for family, score in family_scores.items()
    )
    agreement_bonus = _AGREEMENT_BONUS_PER_FAMILY * max(0, len(family_scores) - 1)
    return (
        hits,
        latest_signal_date,
        signal_age,
        round(base_score + agreement_bonus, 2),
        sorted(family_scores),
    )

def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None

def _sma(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    return sum(values[-period:]) / period

def _atr_pct(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> float | None:
    if len(closes) < period + 1 or len(highs) != len(closes) or len(lows) != len(closes):
        return None
    true_ranges = []
    for index in range(-period, 0):
        true_range = max(
            highs[index] - lows[index],
            abs(highs[index] - closes[index - 1]),
            abs(lows[index] - closes[index - 1]),
        )
        true_ranges.append(true_range)
    atr = sum(true_ranges) / len(true_ranges)
    return atr / closes[-1] if closes[-1] > 0 else None

def _rsi(closes: list[float], period: int = 14) -> float | None:
    if len(closes) < period + 1:
        return None
    gains = []
    losses = []
    for index in range(-period, 0):
        change = closes[index] - closes[index - 1]
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))
    average_gain = sum(gains) / period
    average_loss = sum(losses) / period
    if average_loss <= 0:
        return 100.0
    relative_strength = average_gain / average_loss
    return 100 - 100 / (1 + relative_strength)

def _consecutive_up_days(closes: list[float]) -> int:
    count = 0
    for index in range(len(closes) - 1, 0, -1):
        if closes[index] > closes[index - 1]:
            count += 1
        else:
            break
    return count

def _technical_profile(bars_items: list, candidate: dict) -> dict:
    """计算技术质量分、风险标记与硬风控结论。"""
    closes = [float(item.close) for item in bars_items if item.close and item.close > 0]
    highs = [float(item.high) for item in bars_items if item.high and item.high > 0]
    lows = [float(item.low) for item in bars_items if item.low and item.low > 0]
    volumes = [float(item.volume) for item in bars_items if item.volume is not None and item.volume >= 0]
    risk_flags: list[str] = []
    if len(closes) < 30 or len(highs) != len(closes) or len(lows) != len(closes):
        return {"quality_score": 0.0, "risk_flags": ["历史数据不足"], "hard_skip": False}

    close = closes[-1]
    ma20 = _sma(closes, 20)
    ma60 = _sma(closes, 60)
    ma20_bias = (close - ma20) / ma20 if ma20 else None
    ret_5d = close / closes[-6] - 1 if len(closes) >= 6 else None
    ret_20d = close / closes[-21] - 1 if len(closes) >= 21 else None
    ret_60d = close / closes[-61] - 1 if len(closes) >= 61 else None
    atr_pct = _atr_pct(highs, lows, closes)
    rsi14 = _rsi(closes)
    consecutive_up = _consecutive_up_days(closes)
    volume_ratio = None
    volume_ma5 = _mean(volumes[-5:]) if len(volumes) >= 5 else None
    volume_ma20 = _mean(volumes[-20:]) if len(volumes) >= 20 else None
    if volume_ma5 is not None and volume_ma20 and volume_ma20 > 0:
        volume_ratio = volume_ma5 / volume_ma20
    high60 = max(highs[-60:]) if len(highs) >= 60 else max(highs)
    drawdown_60 = (high60 - close) / high60 if high60 > 0 else None
    change_pct = candidate.get("change_pct")
    if change_pct is None and bars_items[-1].change_pct is not None:
        change_pct = float(bars_items[-1].change_pct)
    limit_ratio = _limit_ratio(str(candidate.get("code") or ""), candidate.get("board"))
    is_limit_up = change_pct is not None and change_pct >= limit_ratio * 100 - 0.3
    is_one_word_limit = is_limit_up and abs(highs[-1] - lows[-1]) <= 1e-6

    hard_skip = False
    if is_one_word_limit:
        risk_flags.append("一字板")
        hard_skip = True
    if close <= 1.0:
        risk_flags.append("低价股")
        hard_skip = True
    if atr_pct is not None and atr_pct > 0.12:
        risk_flags.append("波动过大")
        hard_skip = True
    if ma20_bias is not None and ma20_bias > 0.25:
        risk_flags.append("偏离MA20过大")
        hard_skip = True
    if ret_5d is not None and ret_5d > 0.30:
        risk_flags.append("5日涨幅过大")
        hard_skip = True
    if consecutive_up >= 7:
        risk_flags.append("连续上涨")
        hard_skip = True

    quality = 0.0
    if ret_20d is not None:
        if 0 < ret_20d <= 0.25:
            quality += 0.35
        elif ret_20d > 0.35:
            quality -= 0.4
            risk_flags.append("20日涨幅过大")
        elif ret_20d < -0.15:
            quality -= 0.2
            risk_flags.append("20日跌幅较大")
    if ret_60d is not None and ret_60d > 0:
        quality += 0.2
    if volume_ratio is not None:
        if volume_ratio >= 1.2:
            quality += 0.25
        elif volume_ratio < 0.7:
            quality -= 0.15
            risk_flags.append("量能不足")
    if ma20_bias is not None:
        if 0 <= ma20_bias <= 0.12:
            quality += 0.25
        elif ma20_bias > 0.18:
            quality -= 0.5
            risk_flags.append("偏离MA20过大")
        elif ma20_bias < -0.08:
            quality -= 0.2
            risk_flags.append("跌破MA20")
    if ma60 is not None and close < ma60:
        quality -= 0.1
        risk_flags.append("跌破MA60")
    if rsi14 is not None:
        if 35 <= rsi14 <= 75:
            quality += 0.15
        elif rsi14 > 82:
            quality -= 0.35
            risk_flags.append("RSI超买")
    if consecutive_up >= 5:
        quality -= 0.4
        risk_flags.append("连续上涨")
    if atr_pct is not None:
        if atr_pct <= 0.06:
            quality += 0.1
        elif atr_pct > 0.09:
            quality -= 0.4
            risk_flags.append("波动过大")
    if drawdown_60 is not None and drawdown_60 > 0.45:
        quality -= 0.2
        risk_flags.append("深度回撤")
    if is_limit_up:
        quality -= 0.2
        risk_flags.append("收盘涨停")
    pe = candidate.get("pe")
    if pe is not None:
        if 0 < pe <= 60:
            quality += 0.15
        elif pe <= 0:
            quality -= 0.4
            risk_flags.append("亏损")
        elif pe > 120:
            quality -= 0.35
            risk_flags.append("估值偏高")
    pb = candidate.get("pb")
    if pb is not None and pb > 10:
        quality -= 0.25
        risk_flags.append("PB偏高")
    market_cap = candidate.get("market_cap")
    if market_cap is not None:
        if market_cap > _MAX_MARKET_CAP_YI:
            quality -= 0.4
            risk_flags.append("市值过大")
            hard_skip = True
        elif market_cap < _MIN_MARKET_CAP_YI:
            quality -= 0.4
            risk_flags.append("市值过小")
            hard_skip = True
        elif 30 <= market_cap <= 800:
            quality += 0.1
        elif market_cap > 1500:
            quality -= 0.15
            risk_flags.append("市值偏大")
    sector_strength = candidate.get("sector_strength")
    if sector_strength is not None:
        if sector_strength >= 1.0:
            quality += 0.25
        elif sector_strength <= -1.0:
            quality -= 0.25
            risk_flags.append("行业弱势")

    # 去重但保持顺序
    deduped_flags = list(dict.fromkeys(risk_flags))
    return {
        "quality_score": round(max(-2.0, min(quality, 2.0)), 2),
        "risk_flags": deduped_flags,
        "hard_skip": hard_skip,
    }

def _build_reason(
    hits: list[str],
    signal_types: list[str],
    industry: str | None,
    sector_strength: float | None,
    risk_flags: list[str],
) -> str:
    parts: list[str] = []
    if hits:
        parts.append("命中" + "、".join(hits[:3]))
    if signal_types:
        parts.append("信号族 " + "/".join(signal_types))
    if industry:
        parts.append(industry)
    if sector_strength is not None:
        parts.append(f"行业中位 {sector_strength:+.1f}%")
    if risk_flags:
        parts.append("风险：" + "、".join(risk_flags[:2]))
    return "；".join(parts)[:160]

def _evaluate_candidate(
    bars_items: list,
    strategy_snapshots: dict,
    candidate: dict,
    regime: str,
) -> dict | None:
    """对单只股票完成信号、技术质量与最终评分（同步，在线程池中执行）。"""
    if len(bars_items) < 2:
        return None
    final_bar = bars_items[-1]
    prev_bar = bars_items[-2]
    prev_close = prev_bar.close if prev_bar.close else final_bar.close
    change_pct = (
        round((final_bar.close - prev_close) / prev_close * 100, 2)
        if prev_close and prev_close > 0
        else _float_or_none(candidate.get("change_pct"))
    )
    if change_pct is not None and change_pct < -3.0:
        return None
    if final_bar.open > 0 and (final_bar.close - final_bar.open) / final_bar.open < -0.035:
        return None

    hits, latest_signal_date, signal_age, signal_score, signal_types = _evaluate_strategies(
        bars_items, strategy_snapshots, regime
    )
    if not hits:
        return None
    profile = _technical_profile(bars_items, candidate)
    if profile["hard_skip"]:
        return None
    quality_score = float(profile["quality_score"])
    theme_score = _theme_score(candidate.get("theme_strength"))
    themes = candidate.get("themes") or []
    final_score = round(max(0.0, signal_score + quality_score + theme_score), 2)
    industry = candidate.get("industry")
    sector_strength = candidate.get("sector_strength")
    reason = _build_reason(hits, signal_types, industry, sector_strength, profile["risk_flags"])
    if themes:
        reason = f"{reason}；题材：{'、'.join(themes[:3])}"[:200]
    return {
        "code": str(candidate["code"]),
        "name": str(candidate["name"]),
        "price": round(final_bar.close, 2) if final_bar.close else _float_or_none(candidate.get("price")),
        "change_pct": change_pct,
        "market_cap": _float_or_none(candidate.get("market_cap")),
        "turnover_pct": _float_or_none(candidate.get("turnover_pct")),
        "amount": _float_or_none(candidate.get("amount")),
        "industry": industry if isinstance(industry, str) else None,
        "strategies": hits,
        "signal_types": signal_types,
        "signal_date": latest_signal_date,
        "signal_age_days": signal_age,
        "score": final_score,
        "signal_score": signal_score,
        "quality_score": quality_score,
        "fundamental_score": 0.0,
        "theme_score": theme_score,
        "themes": themes,
        "sector_strength": _float_or_none(sector_strength),
        "risk_flags": profile["risk_flags"],
        "reason": reason,
    }
