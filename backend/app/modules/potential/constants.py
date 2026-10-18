"""潜力股挖掘的可调参数（单一事实来源）。"""

from __future__ import annotations

from datetime import time

_MAX_CANDIDATES = 300

_MIN_AMOUNT_YI = 0.8

_MIN_MARKET_CAP_YI = 20.0

_MAX_MARKET_CAP_YI = 3000.0

_MIN_LISTING_DAYS = 365

_MAX_SIGNAL_AGE_DAYS = 5

_MAX_OUTPUT = 50

_MAX_CONCURRENCY = 6

_HISTORY_DAYS = 420

_TRADING_CALENDAR_LOOKBACK_DAYS = 370

_DAILY_MINING_CUTOFF = time(15, 10)

_BAR_FETCH_TIMEOUT_SECONDS = 25.0

_FUNDAMENTAL_CANDIDATE_LIMIT = 60

_FUNDAMENTAL_MIN_SCORE = 1.0

_FUNDAMENTAL_CONCURRENCY = 6

_FUNDAMENTAL_TIMEOUT_SECONDS = 20.0

_HEAD_CANDIDATE_LIMIT = 120

_MID_CANDIDATE_LIMIT = 120

_QUALITY_CANDIDATE_LIMIT = 60

_MID_MAX_AMOUNT_YI = 15.0

_MID_MIN_TURNOVER_PCT = 2.0

_MID_MAX_TURNOVER_PCT = 18.0

_QUALITY_MIN_MARKET_CAP_YI = 30.0

_QUALITY_MAX_MARKET_CAP_YI = 800.0

_QUALITY_MAX_PE = 60.0

_QUALITY_MAX_PB = 8.0

_QUALITY_MIN_AMOUNT_YI = 1.0

_QUALITY_MAX_AMOUNT_YI = 30.0

_QUALITY_MIN_TURNOVER_PCT = 1.0

_QUALITY_MAX_TURNOVER_PCT = 15.0

_FRESH_SIGNAL_BONUS = 1.5

_STRATEGY_FAMILIES: dict[str, str] = {
    "bull_trend": "trend",
    "ma_golden_cross": "trend",
    "volume_breakout": "breakout",
    "shrink_pullback": "pullback",
    "bottom_volume": "reversal",
    "one_yang_three_yin": "reversal",
    "box_oscillation": "range",
}

_FAMILY_CAPS: dict[str, float] = {
    "trend": 2.0,
    "breakout": 1.5,
    "pullback": 1.5,
    "reversal": 2.0,
    "range": 1.2,
    "other": 1.2,
}

_REGIME_FAMILY_MULTIPLIERS: dict[str, dict[str, float]] = {
    "bull": {"trend": 1.15, "breakout": 1.15, "pullback": 1.0, "reversal": 0.9, "range": 0.95},
    "bear": {"trend": 0.85, "breakout": 0.85, "pullback": 0.95, "reversal": 1.15, "range": 1.05},
    "neutral": {"trend": 1.0, "breakout": 1.0, "pullback": 1.0, "reversal": 1.0, "range": 1.0},
}

_AGREEMENT_BONUS_PER_FAMILY = 0.35

_MAX_PER_INDUSTRY = 4

_MAX_PER_UNCLASSIFIED = 6

_INDEX_SYMBOL = "000300"

_THEME_CONCEPT_LIMIT = 8

_THEME_INDUSTRY_LIMIT = 5

_THEME_STRENGTH_CAP = 0.6
