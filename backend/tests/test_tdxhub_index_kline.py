"""tdxhub 指数 K 线的取数路径：走 bars(index=True)（0.5.1 起的显式指数开关）。"""

import pandas as pd
import pytest

from app.infrastructure.providers.tdxhub import TdxhubDataProvider

_COLUMNS = [
    "datetime",
    "open",
    "close",
    "high",
    "low",
    "vol",
    "volume",
    "amount",
    "up_count",
    "down_count",
]


def _frame(close: float = 3600.0) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "datetime": "2026-10-29 15:00",
                "open": close - 10,
                "close": close,
                "high": close + 5,
                "low": close - 15,
                # SDK 对指数返回的 vol 是「手」，上层统一 ×100 得到股
                "vol": 1_000.0,
                "volume": 1_000.0,
                "amount": 360_000_000.0,
                "up_count": 1200,
                "down_count": 900,
            }
        ],
        columns=_COLUMNS,
    )


class _StubShared:
    def __init__(self, result):
        self.result = result
        self.calls: list[tuple[str, dict]] = []

    def call(self, method, *args, **kwargs):
        self.calls.append((method, kwargs))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result

    def reset(self):
        pass


def _provider(shared: _StubShared) -> TdxhubDataProvider:
    return TdxhubDataProvider(quotes=shared, raise_quotes=shared)


def test_index_kline_uses_bars_with_index_flag():
    shared = _StubShared(_frame())
    provider = _provider(shared)

    result = provider.fetch_index_kline("sh000001")

    assert [method for method, _ in shared.calls] == ["bars"]
    assert shared.calls[0][1]["symbol"] == "sh000001"
    # 0.5.1 的 bars 默认按代码段猜指数；显式传 index=True 不依赖猜测
    assert shared.calls[0][1]["index"] is True
    assert len(result) == 1
    # vol 单位是「手」，统一 ×100 得到股
    assert result["volume"].iloc[0] == pytest.approx(100_000.0)


def test_stock_bars_never_claims_index():
    """个股 K 线不能带 index=True，否则会被按指数记录结构解析。"""
    shared = _StubShared(_frame())
    provider = _provider(shared)

    provider.fetch_stock_bars("600519")

    assert [method for method, _ in shared.calls] == ["bars"]
    assert "index" not in shared.calls[0][1]


def test_stock_bars_volume_matches_stock_kline_contract():
    """fetch_stock_bars 与 fetch_stock_kline 必须同为「股」：bars 原始 vol 是手。"""
    shared = _StubShared(_frame())
    provider = _provider(shared)

    result = provider.fetch_stock_bars("600519")

    assert result["volume"].iloc[0] == pytest.approx(100_000.0)


def test_index_kline_adds_market_prefix():
    """裸 000001 必须补成 sh000001，否则会被当成平安银行（深市个股）。"""
    shared = _StubShared(_frame())
    provider = _provider(shared)

    provider.fetch_index_kline("000001")

    assert shared.calls[0][1]["symbol"] == "sh000001"


def test_index_kline_keeps_market_prefix_for_sz_index():
    shared = _StubShared(_frame())
    provider = _provider(shared)

    provider.fetch_index_kline("sz399001")

    assert shared.calls[0][1]["symbol"] == "sz399001"


def test_index_kline_returns_standard_columns_when_empty():
    shared = _StubShared(pd.DataFrame())
    provider = _provider(shared)

    result = provider.fetch_index_kline("sh000001")

    assert result.empty
    assert list(result.columns) == provider.INDEX_KLINE_COLUMNS
