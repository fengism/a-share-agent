import pandas as pd
import pytest

from app.modules.screener.presets import list_screener_presets
from app.modules.screener.schemas import ScreenerFilter
from app.modules.screener.screening import _screen_dataframe


@pytest.fixture
def mock_spot_df() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "代码": "600001",
            "名称": "破净大盘股",
            "最新价": 10.0,
            "涨跌幅": 1.5,
            "昨收": 10.0,
            "最高": 10.6,
            "最低": 9.8,
            "换手率": 1.2,
            "成交量": 500000,
            "市盈率-动态": 8.0,
            "市净率": 0.85,
            "总市值": 50000000000,
            "成交额": 500000000,
        },
        {
            "代码": "600002",
            "名称": "高估值题材股",
            "最新价": 25.0,
            "涨跌幅": 6.8,
            "昨收": 23.4,
            "最高": 25.5,
            "最低": 23.0,
            "换手率": 8.5,
            "成交量": 1200000,
            "市盈率-动态": 65.0,
            "市净率": 4.5,
            "总市值": 8000000000,
            "成交额": 850000000,
        },
        {
            "代码": "600003",
            "名称": "ST退市风险股",
            "最新价": 2.0,
            "涨跌幅": -5.0,
            "昨收": 2.1,
            "最高": 2.1,
            "最低": 1.95,
            "换手率": 0.5,
            "成交量": 100000,
            "市盈率-动态": -10.0,
            "市净率": 0.7,
            "总市值": 1000000000,
            "成交额": 5000000,
        },
    ])


def test_broken_net_filtering(mock_spot_df: pd.DataFrame):
    # 筛选破净股，且排除 ST
    filters = ScreenerFilter(is_broken_net=True, exclude_st=True)
    result = _screen_dataframe(
        df=mock_spot_df,
        second_industry_map={},
        exchange_master=None,
        filters=filters,
    )
    assert result.total == 1
    assert result.items[0].code == "600001"
    assert result.items[0].is_broken_net is True
    assert result.items[0].pb == 0.85
    # 振幅计算: (10.6 - 9.8) / 10.0 * 100 = 8.0%
    assert result.items[0].amplitude == 8.0


def test_amplitude_filtering_and_sorting(mock_spot_df: pd.DataFrame):
    # 题材股振幅: (25.5 - 23.0) / 23.4 * 100 ≈ 10.68%
    filters = ScreenerFilter(amplitude_min=10.0, exclude_st=True, sort_by="amplitude", sort_order="desc")
    result = _screen_dataframe(
        df=mock_spot_df,
        second_industry_map={},
        exchange_master=None,
        filters=filters,
    )
    assert result.total == 1
    assert result.items[0].code == "600002"
    assert result.items[0].amplitude is not None
    assert result.items[0].amplitude > 10.0


def test_screener_presets_definitions():
    presets = list_screener_presets()
    assert len(presets) >= 4
    keys = {p.key for p in presets}
    assert "deep_broken_net" in keys
    assert "theme_volume_expansion" in keys
    assert "low_pe_growth_cross" in keys
