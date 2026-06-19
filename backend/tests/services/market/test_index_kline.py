"""单元测试：指数 K 线服务内部函数测试。"""
import pytest
import pandas as pd

from app.services.market.index_kline import _to_kline_data


class TestToKlineData:
    """_to_kline_data DataFrame → KlineData 转换测试"""

    def test_basic_conversion(self):
        df = pd.DataFrame({
            "日期": ["2026-01-02", "2026-01-03"],
            "开盘": [3000.0, 3010.0],
            "收盘": [3010.0, 3020.0],
            "最高": [3020.0, 3030.0],
            "最低": [2990.0, 3000.0],
            "成交量": [1000000.0, 1200000.0],
            "成交额": [3e9, 3.6e9],
            "振幅": [1.0, 1.0],
            "涨跌幅": [0.5, 0.33],
        })
        result = _to_kline_data("000001", "daily", df)
        assert result.code == "000001"
        assert result.period == "daily"
        assert len(result.items) == 2
        assert result.items[0].date == "20260102"
        assert result.items[0].open == 3000.0
        assert result.items[0].close == 3010.0
        assert result.items[1].date == "20260103"

    def test_empty_dataframe(self):
        df = pd.DataFrame()
        result = _to_kline_data("399001", "daily", df)
        assert result.code == "399001"
        assert len(result.items) == 0

    def test_english_column_names(self):
        df = pd.DataFrame({
            "date": ["2026-01-02"],
            "open": [3000.0],
            "close": [3010.0],
            "high": [3020.0],
            "low": [2990.0],
            "volume": [1000000.0],
            "amount": [3e9],
        })
        result = _to_kline_data("000001", "daily", df)
        assert len(result.items) == 1
        assert result.items[0].date == "20260102"

    def test_missing_columns(self):
        """缺少可选列时不应崩溃。"""
        df = pd.DataFrame({
            "日期": ["2026-01-02"],
            "开盘": [3000.0],
            "收盘": [3010.0],
            "最高": [3020.0],
            "最低": [2990.0],
        })
        # _to_kline_data 中 close/open 等用 float(xxx or 0) 保证不为 None，
        # 而 volume 用 safe_float(...) or 0 也保证不为 None。
        result = _to_kline_data("000001", "daily", df)
        assert len(result.items) == 1
