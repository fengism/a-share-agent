"""tdxhub 实时行情取数的分块、缺失代码剔除与负缓存回归测试。

SDK 的 ``quotes()`` 已内建 round2 快照（经典命令返回空时自动降级），本层只负责
分块与“批内有退市/改代码股票”时的容错。
"""

import pandas as pd
import pytest
from tdxhub.tdx.errors import ProtocolError, ResponseHeaderRecvFails

from app.infrastructure.providers import tdxhub as tdxhub_module
from app.infrastructure.providers.tdxhub import TdxhubDataProvider


class _StubQuotes:
    """按代码集合模拟服务端：只返回有效代码的记录，条数不符时抛 ProtocolError。"""

    def __init__(self, available: set[str] | None = None, error: Exception | None = None):
        self.available = available
        self.error = error
        self.requests: list[list[str]] = []

    def call(self, method, *args, **kwargs):
        assert method == "quotes"
        codes = list(args[0])
        self.requests.append(codes)
        if self.error is not None:
            raise self.error
        if self.available is not None:
            missing = [code for code in codes if code not in self.available]
            if missing:
                raise ProtocolError(f"快照记录 marker 未找到: {missing[0]}")
        return pd.DataFrame(
            [
                {
                    "code": code[2:],
                    "price": 10.0,
                    "last_close": 9.0,
                    "open": 9.5,
                    "high": 10.5,
                    "low": 9.4,
                    "vol": 1234.0,
                    "amount": 1_234_000.0,
                }
                for code in codes
            ]
        )


@pytest.fixture(autouse=True)
def clear_negative_cache():
    # 负缓存是模块级状态，必须逐用例清理，否则缺失代码会泄露到后续用例
    tdxhub_module._quotes_missing_codes.clear()
    yield
    tdxhub_module._quotes_missing_codes.clear()


def _provider(quotes: _StubQuotes) -> TdxhubDataProvider:
    return TdxhubDataProvider(quotes=quotes, raise_quotes=quotes)


def test_single_request_for_valid_batch():
    quotes = _StubQuotes(available={"sh600000", "sz000001"})
    provider = _provider(quotes)

    result = provider.fetch_stock_quotes(["600000", "000001"])

    assert sorted(result) == ["000001", "600000"]
    assert quotes.requests == [["sh600000", "sz000001"]]
    assert result["600000"]["last_close"] == 9.0
    assert result["600000"]["volume"] == 1234.0


def test_batches_are_limited_to_80_codes():
    codes = [f"sh6{index:05d}" for index in range(81)]
    quotes = _StubQuotes()
    provider = _provider(quotes)

    provider.fetch_stock_quotes(codes)

    assert [len(request) for request in quotes.requests] == [80, 1]


def test_missing_code_is_dropped_by_bisection():
    """一只退市股不应让整批实时行情失败。"""
    quotes = _StubQuotes(available={"sh600000", "sz000001", "sh601318"})
    provider = _provider(quotes)

    result = provider.fetch_stock_quotes(["600000", "600001", "000001", "601318"])

    assert list(result) == ["600000", "000001", "601318"]
    assert tdxhub_module._quotes_missing_codes.get("sh600001") is not None


def test_missing_code_is_not_requested_again():
    quotes = _StubQuotes(available={"sh600000"})
    provider = _provider(quotes)

    provider.fetch_stock_quotes(["600000", "600001"])
    requests_after_first = len(quotes.requests)

    provider.fetch_stock_quotes(["600000", "600001"])

    assert len(quotes.requests) == requests_after_first + 1
    assert quotes.requests[-1] == ["sh600000"]


def test_single_code_failure_without_prior_success_is_not_cached():
    """整批都失败时无法区分“代码无效”与“链路异常”，不能污染负缓存。"""
    quotes = _StubQuotes(error=ProtocolError("快照响应数量不匹配"))
    provider = _provider(quotes)

    assert provider.fetch_stock_quotes(["600000"]) == {}
    assert tdxhub_module._quotes_missing_codes.get("sh600000") is None


def test_bisect_budget_bounds_request_count():
    """大量缺失代码时二分必须被预算截断，不能退化成上百次往返。"""
    quotes = _StubQuotes(available={"sh600000"})
    provider = _provider(quotes)
    codes = [f"sh6{index:05d}" for index in range(80)]

    result = provider.fetch_stock_quotes(codes)

    assert len(quotes.requests) <= tdxhub_module._QUOTES_MAX_REQUESTS_PER_BATCH + 1
    assert len(result) <= 1


def test_empty_snapshot_returns_empty_dict():
    quotes = _StubQuotes()
    provider = _provider(quotes)

    assert provider.fetch_stock_quotes([]) == {}
    assert quotes.requests == []


def test_parse_row_accepts_classic_and_round2_field_names():
    """经典命令用 last_close，round2 用 pre_close，两者都要能归一。"""
    quotes = _StubQuotes()
    quotes.call = lambda *args, **kwargs: pd.DataFrame(
        [
            {
                "code": "600000",
                "price": 10.0,
                "pre_close": 9.0,
                "open": 9.5,
                "high": 10.5,
                "low": 9.4,
                "vol": 100.0,
                "amount": 1000.0,
            }
        ]
    )
    provider = _provider(quotes)

    quote = provider.fetch_stock_quotes(["600000"])["600000"]

    assert quote["last_close"] == 9.0
    assert quote["change_pct"] == pytest.approx(100 / 9)


def test_transport_error_is_not_treated_as_missing_code():
    """读超时/EOF 是传输故障，不能当成"代码没有快照"去二分，更不能写负缓存。"""
    quotes = _StubQuotes(error=ResponseHeaderRecvFails("round2 响应头接收 0/16 字节失败"))
    provider = _provider(quotes)

    with pytest.raises(ResponseHeaderRecvFails):
        provider.fetch_stock_quotes(["600000", "000001"])

    assert len(quotes.requests) == 1
    assert tdxhub_module._quotes_missing_codes.get("sh600000") is None
