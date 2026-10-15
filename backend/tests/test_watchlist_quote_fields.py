"""自选股行情字段归一：A 股行情用 ``mcap``，港股行情（HKStockQuote）用 ``market_cap``。

回归：港股自选此前读 ``quote["mcap"]``，而港股行情字典只有 ``market_cap``，
导致港股自选的总市值恒为 None。
"""

from __future__ import annotations

from app.modules.watchlist.service import _watchlist_item_from_quote


def _row() -> dict:
    return {
        "id": 1,
        "stock_name": "腾讯控股",
        "note": "",
        "created_at": "2026-08-20T10:00:00",
    }


def test_hk_quote_uses_market_cap_field() -> None:
    item = _watchlist_item_from_quote(
        _row(),
        market="hk",
        public_code="00700",
        quote={"name": "腾讯控股", "price": 380.0, "market_cap": 3_600_000_000_000.0},
        quote_source="tencent",
        concepts=[],
    )
    assert item.market == "hk"
    assert item.market_cap == 3_600_000_000_000.0


def test_a_share_quote_uses_mcap_field() -> None:
    item = _watchlist_item_from_quote(
        _row(),
        market="cn",
        public_code="600519",
        quote={"name": "贵州茅台", "price": 1500.0, "mcap": 1_905_000_000_000.0},
        quote_source="tencent",
        concepts=[],
    )
    assert item.market == "cn"
    assert item.market_cap == 1_905_000_000_000.0


def test_missing_market_cap_stays_none() -> None:
    item = _watchlist_item_from_quote(
        _row(),
        market="hk",
        public_code="00700",
        quote={"name": "腾讯控股", "price": 380.0},
        quote_source="tencent",
        concepts=[],
    )
    assert item.market_cap is None
