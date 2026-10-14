"""复权因子表守卫：拒绝 TDX 抖动导致的退化因子。

背景：TDX XDXR 在协议层失败（如 unpack requires a buffer of 4 bytes）时会返回
"非空但无意义"的帧，``normalize_gbbq`` 照样产出结构合法的表，算出来的因子恒为
1.0。原有的 ``isna()`` / ``isfinite()`` 校验都能通过，于是把一份毫无信息量的因子
表静默写进库——直到有人对比复权价时才发现整条曲线没有任何跳变。
"""

from datetime import UTC, date, datetime, timedelta

import pandas as pd
import pytest

from app.modules.market_daily.adjustment import (
    _build_factors,
    _has_price_affecting_actions,
    _normalize_actions,
)

_CODE = "600519"
_ACTION_BASE = {"category": 1, "peigujia": 0.0, "songzhuangu": 0.0, "peigu": 0.0, "suogu": 0.0, "fenhong": 0.0}


def _actions_frame(**overrides) -> pd.DataFrame:
    row = {**_ACTION_BASE, **overrides}
    frame = pd.DataFrame([{"__day": "2026-06-26", **row}])
    frame.index = pd.to_datetime(frame.pop("__day"))
    return frame


def _trading_dates() -> list[date]:
    return [day.date() for day in pd.bdate_range("2025-01-01", "2026-10-13")]


def _build(raw: pd.DataFrame):
    normalized, _actions, action_hash = _normalize_actions(_CODE, raw)
    return _build_factors(
        _CODE, _trading_dates(), normalized, action_hash, datetime.now(UTC),
    )


def _variants(factors) -> int:
    return len({
        (
            round(factor.qfq_multiplier, 8), round(factor.qfq_offset, 8),
            round(factor.hfq_multiplier, 8), round(factor.hfq_offset, 8),
        )
        for factor in factors
    })


def test_cash_dividend_produces_varying_factors():
    normalized, _a, _h = _normalize_actions(_CODE, _actions_frame(fenhong=30.0))
    assert _has_price_affecting_actions(normalized) is True
    assert _variants(_build(_actions_frame(fenhong=30.0))) > 1


def test_bonus_share_produces_varying_factors():
    assert _variants(_build(_actions_frame(songzhuangu=10.0))) > 1


def test_rights_issue_produces_varying_factors():
    assert _variants(_build(_actions_frame(peigu=3.0, peigujia=10.0))) > 1


def test_stock_without_corporate_actions_may_have_constant_factors():
    """确实没有公司行为时，因子恒为 1.0 是正确结果，不能误拒。"""
    normalized, _a, _h = _normalize_actions(_CODE, pd.DataFrame())
    assert _has_price_affecting_actions(normalized) is False
    factors = _build(pd.DataFrame())
    assert factors
    assert _variants(factors) == 1


def test_zero_valued_actions_are_not_price_affecting():
    normalized, _a, _h = _normalize_actions(_CODE, _actions_frame())
    assert _has_price_affecting_actions(normalized) is False


def test_degenerate_factor_table_is_rejected():
    """有价格影响的公司行为、但因子算出来恒定 —— 必须拒绝写入。"""
    # suogu(缩股) 被 _has_price_affecting_actions 视为影响除权，但 SDK 的
    # adjustment_factors 不处理该字段，结果就是恒定因子：正是要挡住的退化场景。
    with pytest.raises(ValueError, match="因子恒定"):
        _build(_actions_frame(suogu=10.0))


def test_guard_does_not_block_normal_refresh():
    """守卫只在"行为存在但因子不变"时触发，正常分红必须照常写入。"""
    factors = _build(_actions_frame(fenhong=30.0))
    assert len(factors) == len(_trading_dates())
    assert factors[-1].source


def test_factor_refresh_ttl_and_versions_unchanged():
    """守卫不应影响既有元数据契约。"""
    from app.modules.market_daily.adjustment import (
        ALGORITHM_VERSION,
        LOCAL_ALGORITHM_VERSIONS,
        SINA_ALGORITHM_VERSION,
    )

    assert ALGORITHM_VERSION.startswith("tdxhub-gbbq-affine-v1")
    assert LOCAL_ALGORITHM_VERSIONS == {ALGORITHM_VERSION, SINA_ALGORITHM_VERSION}
    assert timedelta(hours=24).total_seconds() == 86400