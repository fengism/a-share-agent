"""市场环境与情绪（指数趋势 + 涨跌家数/涨停板）。"""

from __future__ import annotations

import logging
from datetime import date, timedelta

import pandas as pd

from app.financial_data.market.public import get_index_kline
from app.modules.potential.common import _limit_ratio, _normalize_code
from app.modules.potential.constants import _INDEX_SYMBOL

logger = logging.getLogger(__name__)


def _market_emotion(df: pd.DataFrame | None, master_records: list) -> dict:
    """从全市场快照计算涨跌家数、涨停/跌停与情绪分。"""
    neutral = {
        "label": "neutral",
        "emotion_score": 0.0,
        "advance_ratio": None,
        "limit_up_count": 0,
        "limit_down_count": 0,
        "median_change_pct": None,
    }
    if df is None or df.empty:
        return neutral
    frame = pd.DataFrame(
        {
            "code": df.get("代码", pd.Series(dtype=object)).map(_normalize_code),
            "change": pd.to_numeric(df.get("涨跌幅"), errors="coerce"),
        }
    ).dropna(subset=["change"])
    if frame.empty:
        return neutral
    board_by_code = {record.code: record.board for record in master_records}
    up_count = int((frame["change"] > 0).sum())
    down_count = int((frame["change"] < 0).sum())
    limit_up = 0
    limit_down = 0
    for change, code in zip(frame["change"], frame["code"]):
        ratio = _limit_ratio(str(code), board_by_code.get(str(code))) * 100
        if change >= ratio - 0.3:
            limit_up += 1
        elif change <= -ratio + 0.3:
            limit_down += 1
    total_directional = up_count + down_count
    advance_ratio = up_count / total_directional if total_directional else 0.5
    median_change = float(frame["change"].median())
    breadth = (advance_ratio - 0.5) * 2
    limit_balance = min(1.0, limit_up / 80.0) - min(1.0, limit_down / 40.0)
    median_component = max(-1.0, min(1.0, median_change / 2.0))
    score = max(-1.0, min(1.0, 0.5 * breadth + 0.3 * limit_balance + 0.2 * median_component))
    return {
        "label": "strong" if score >= 0.3 else "weak" if score <= -0.3 else "neutral",
        "emotion_score": round(score, 3),
        "advance_ratio": round(advance_ratio, 4),
        "limit_up_count": limit_up,
        "limit_down_count": limit_down,
        "median_change_pct": round(median_change, 2),
    }

def _combine_regime(index_regime: str, emotion_label: str) -> str:
    """把指数趋势与市场情绪合成有效环境，避免单一指数信号误判。"""
    if index_regime == "bull":
        return "bull" if emotion_label in {"strong", "neutral"} else "neutral"
    if index_regime == "bear":
        return "bear" if emotion_label in {"weak", "neutral"} else "neutral"
    if emotion_label == "strong":
        return "bull"
    if emotion_label == "weak":
        return "bear"
    return "neutral"

async def _resolve_market_regime(market_date: date) -> tuple[str, str]:
    """用沪深300 均线与 20 日动量判断市场环境。"""
    start_date = market_date - timedelta(days=140)
    try:
        bars = await get_index_kline(
            _INDEX_SYMBOL,
            period="daily",
            start_date=start_date.isoformat(),
            end_date=market_date.isoformat(),
        )
    except Exception as error:
        logger.warning("潜力股市场环境获取失败: %s", error)
        return "neutral", "指数数据不可用，按中性环境处理"
    closes = [float(item.close) for item in bars.items if item.close and item.close > 0]
    if len(closes) < 60:
        return "neutral", "指数历史不足 60 日，按中性环境处理"
    ma20 = sum(closes[-20:]) / 20
    ma60 = sum(closes[-60:]) / 60
    ret20 = closes[-1] / closes[-21] - 1 if len(closes) >= 21 else 0.0
    if closes[-1] > ma20 > ma60 and ret20 > 0:
        regime = "bull"
    elif closes[-1] < ma20 < ma60 and ret20 < 0:
        regime = "bear"
    else:
        regime = "neutral"
    note = (
        f"沪深300近20日 {ret20 * 100:+.1f}%，"
        f"{'站上' if closes[-1] >= ma20 else '跌破'}MA20，"
        f"{'站上' if closes[-1] >= ma60 else '跌破'}MA60"
    )
    return regime, note
