"""实时行情清洗：上游把"当日无成交"返回成 price=0 时不能当成行情透传。

早期实现是 ``_normalize_quote()``——把 price=0 的停牌行情改写成昨收并清空涨跌幅。
该函数已随行情源重构移除，停牌过滤改由 ``_has_usable_price()`` 在
``_load_quote_source()`` 汇总阶段统一完成（无可用价格的条目直接丢弃，
不进入下游）。这里锁定该过滤契约。
"""

from __future__ import annotations

import pytest

from app.financial_data.stock.quotes.realtime import _has_usable_price


def test_accepts_a_normal_quote() -> None:
    quote = {
        "code": "600519",
        "price": 1258.62,
        "last_close": 1235.58,
        "change_amt": 23.04,
        "change_pct": 1.8647,
        "amplitude_pct": 2.5858,
    }
    assert _has_usable_price(quote) is True


def test_rejects_zero_price_without_last_close() -> None:
    """TDX 对当日无成交的股票返回 price=0 + change_pct=-100。

    实测 002813 路畅科技 price=0、change_amt=-26.38、change_pct=-100，
    没有昨收可兜底时必须整条丢弃，否则全站显示"0.00 / -100.00%"。
    """
    assert _has_usable_price({
        "code": "002813",
        "price": 0.0,
        "last_close": 0.0,
        "change_amt": -26.38,
        "change_pct": -100.0,
    }) is False


def test_keeps_suspended_quote_when_last_close_is_available() -> None:
    """停牌但有昨收时保留条目：昨收仍是有信息量的展示价。"""
    assert _has_usable_price({"code": "002813", "price": 0.0, "last_close": 26.38}) is True


def test_falls_back_to_last_close_when_price_key_is_missing() -> None:
    assert _has_usable_price({"code": "600519", "last_close": 12.5}) is True


def test_rejects_quote_without_any_price() -> None:
    assert _has_usable_price({"price": None, "last_close": None}) is False


def test_rejects_negative_price() -> None:
    assert _has_usable_price({"price": -1.0, "last_close": None}) is False


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), "abc", ""])
def test_rejects_non_numeric_price(bad: object) -> None:
    assert _has_usable_price({"price": bad, "last_close": None}) is False
