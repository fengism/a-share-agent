"""Unit tests for app.utils.symbol_utils (pure functions).

Assertions were validated by executing the functions directly, so they reflect
the code's actual behaviour.
"""
import pytest

from app.utils.symbol_utils import (
    classify_exchange,
    normalize_code,
    normalize_index_symbol,
    normalize_index_symbol_v2,
    normalize_index_code,
    normalize_stock_name,
    contains_stock_reference,
)


class TestClassifyExchange:
    def test_shanghai(self):
        assert classify_exchange("600519") == "SH"
        assert classify_exchange("900901") == "SH"

    def test_shenzhen(self):
        assert classify_exchange("000001") == "SZ"
        assert classify_exchange("300750") == "SZ"

    def test_beijing(self):
        assert classify_exchange("830799") == "BJ"

    def test_invalid(self):
        with pytest.raises(ValueError):
            classify_exchange("100000")
        with pytest.raises(ValueError):
            classify_exchange("")


class TestNormalizeCode:
    def test_plain_code(self):
        r = normalize_code("600519")
        assert (r.raw, r.exchange, r.prefixed_upper, r.prefixed_lower) == (
            "600519", "SH", "SH600519", "sh600519",
        )

    def test_strips_prefix(self):
        assert normalize_code("sz000001").raw == "000001"
        assert normalize_code("SZ000001").exchange == "SZ"
        assert normalize_code("bj830799").exchange == "BJ"

    def test_invalid(self):
        with pytest.raises(ValueError):
            normalize_code("12345")
        with pytest.raises(ValueError):
            normalize_code("abcdef")


class TestIndexSymbols:
    def test_normalize_index_symbol(self):
        assert normalize_index_symbol("000001") == "sh000001"
        assert normalize_index_symbol("sh000001") == "sh000001"
        assert normalize_index_symbol("399001") == "sz399001"

    def test_normalize_index_symbol_v2(self):
        assert normalize_index_symbol_v2("600000") == "sh600000"
        assert normalize_index_symbol_v2("000001") == "sz000001"
        assert normalize_index_symbol_v2("sz000001") == "sz000001"

    def test_normalize_index_code(self):
        assert normalize_index_code("sh000001") == "000001"
        assert normalize_index_code("000001") == "000001"


class TestStockName:
    def test_strip_and_remove_spaces(self):
        assert normalize_stock_name(" 贵州 茅台 ") == "贵州茅台"
        assert normalize_stock_name(None) == ""


class TestContainsStockReference:
    def test_code_in_text(self):
        assert contains_stock_reference("代码600519异动", "600519", "贵州茅台") is True

    def test_absent(self):
        assert contains_stock_reference("大盘走势平稳", "600519", "贵州茅台") is False

    def test_empty_text(self):
        assert contains_stock_reference("", "600519", "贵州茅台") is False
