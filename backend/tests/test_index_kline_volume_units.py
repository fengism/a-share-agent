"""指数 K 线成交量单位契约：各数据源都必须统一为「股」。

个股路径用 600519 锚定过 house 单位是「股」（2,657,300 股 × ~1,277 元 = 33.9 亿）。
指数链路里腾讯 / TDX / 东财 的原始量纲各不相同，一旦漏乘系数，同一个接口就会因
命中不同数据源而返回相差 100 倍的成交量。
"""

import inspect
import json
from unittest.mock import patch

import pandas as pd
import pytest

from app.infrastructure.providers.registry import get_provider
from app.infrastructure.providers.tdxhub import tdxhub_provider
from app.infrastructure.providers.tencent import TencentDataProvider

# 2026-10-13 收盘，399006 创业板指，三源一致的成交额与合理成分股均价区间
_AMOUNT_YUAN = 452_004_282_368.0
_PLAUSIBLE_PRICE_RANGE = (10.0, 200.0)

# bars 已把指数原始 vol 归一到「手」（与东财手数一致），故 TDX 系数与个股同为 100
_TDX_INDEX_RAW_VOLUME = 182_678_834.0  # 手
_TENCENT_INDEX_RAW_VOLUME = 182_678_834.0  # 手（腾讯原始 vol 亦为手）
_EASTMONEY_INDEX_RAW_VOLUME = 182_678_834.0  # 手
_TRADING_DAY = "2026-10-13"


def _assert_contract(volume: float, amount: float, label: str) -> None:
    # 指数成分股均价约 10~100 元；个股（茅台）在千元级，故按标签区分区间。
    price_range = (100.0, 2000.0) if "个股" in label else _PLAUSIBLE_PRICE_RANGE
    implied_price = amount / volume
    assert price_range[0] <= implied_price <= price_range[1], (
        f"{label} 成交量量纲错误: volume={volume:,.0f} "
        f"隐含均价={implied_price:,.2f} 元（应落在 {price_range}）"
    )


def _tdx_index_frame() -> pd.DataFrame:
    """模拟 tdxhub index bars 的返回：vol 与 volume 同值，另有 datetime。"""
    row = {
        "open": 2899.15, "close": 2958.34, "high": 2999.76, "low": 2860.80,
        "vol": _TDX_INDEX_RAW_VOLUME, "volume": _TDX_INDEX_RAW_VOLUME,
        "amount": _AMOUNT_YUAN, "datetime": f"{_TRADING_DAY} 15:00",
    }
    return pd.DataFrame([row])


def test_tdx_index_volume_is_normalized_to_shares():
    frame = tdxhub_provider._format_index_kline_df(
        _tdx_index_frame(),
        start_date=_TRADING_DAY,
        end_date=_TRADING_DAY,
        volume_multiplier=100,
    )
    row = frame.iloc[-1]
    _assert_contract(float(row["volume"]), float(row["amount"]), "TDX 指数")


def test_tdx_index_uses_bars_with_index_flag():
    """指数走 bars(index=True)（0.5.1 起显式指数开关），系数与个股同为 100。"""
    index_src = inspect.getsource(tdxhub_provider.fetch_index_kline)
    assert '"bars"' in index_src
    assert "index=True" in index_src
    assert "volume_multiplier=100" in index_src
    assert "value * 100" in inspect.getsource(tdxhub_provider.fetch_stock_kline)


def test_tdx_index_kline_requests_prefixed_symbol():
    """指数必须带市场前缀：裸 000001 会被当成平安银行（深市个股）。"""
    captured = {}

    def fake_call(method, **kwargs):
        captured.update(method=method, **kwargs)
        return _tdx_index_frame()

    with patch.object(tdxhub_provider._quotes, "call", side_effect=fake_call):
        frame = tdxhub_provider.fetch_index_kline("000001", _TRADING_DAY, _TRADING_DAY)

    assert captured["method"] == "bars"
    assert captured["index"] is True
    assert captured["symbol"] == "sh000001"
    assert not frame.empty


def test_tdx_stock_volume_stays_in_shares():
    """个股契约回归：raw vol(手) x 100 == 股。"""
    raw = pd.DataFrame(
        [{
            "open": 1400.0, "close": 1410.0, "high": 1420.0, "low": 1390.0,
            "vol": 26_573.0, "volume": 26_573.0, "amount": 3_393_315_840.0,
            "datetime": f"{_TRADING_DAY} 15:00",
        }]
    )
    with patch.object(tdxhub_provider, "_call", return_value=raw):
        frame = tdxhub_provider.fetch_stock_kline("600519", "20261013", "20261013")
    volume, amount = float(frame.iloc[-1]["volume"]), float(frame.iloc[-1]["amount"])
    assert volume == 2_657_300.0
    _assert_contract(volume, amount, "TDX 个股")


def _fake_eastmoney_response():
    payload = {
        "data": {
            "code": "399006",
            "klines": [
                "2026-10-13,2899.15,2958.34,2999.76,2860.80,"
                f"{_EASTMONEY_INDEX_RAW_VOLUME:.0f},{_AMOUNT_YUAN:.2f},4.69,-0.18,-5.48,3.21"
            ],
        }
    }

    class _Response:
        @staticmethod
        def json():
            return payload

    return _Response()


def _eastmoney_index_frame() -> pd.DataFrame:
    provider = get_provider("eastmoney")
    with patch.object(provider, "em_get_response", return_value=_fake_eastmoney_response()):
        return provider.fetch_index_kline("399006", "daily", "20261001", "20261013")


def test_eastmoney_index_volume_is_normalized_to_shares():
    row = _eastmoney_index_frame().iloc[-1]
    _assert_contract(float(row["volume"]), float(row["amount"]), "东财指数")


def test_eastmoney_index_volume_factor_matches_stock_kline():
    """指数与个股同源，成交量换算系数必须一致（同为手 -> 股）。"""
    assert float(_eastmoney_index_frame().iloc[-1]["volume"]) == _EASTMONEY_INDEX_RAW_VOLUME * 100
    assert "df[\"成交量\"] = pd.to_numeric(df[\"成交量\"], errors=\"coerce\") * 100" in inspect.getsource(
        get_provider("eastmoney").fetch_kline
    )


@pytest.mark.parametrize("symbol", ["sz399006", "sh000300", "sh000001"])
def test_tencent_index_volume_and_amount_units(symbol: str):
    """腾讯原始 vol 是手（provider 内乘 100）、amount 是万元（乘 10000），输出须为股/元。"""
    raw_volume = _TENCENT_INDEX_RAW_VOLUME
    raw_amount_wan = _AMOUNT_YUAN / 10000.0
    payload = {
        "data": {
            symbol: {
                "day": [
                    [
                        _TRADING_DAY, "2899.15", "2958.34", "2999.76", "2860.80",
                        f"{raw_volume:.2f}", {}, "3.24", f"{raw_amount_wan:.2f}", "0", "0",
                    ]
                ]
            }
        }
    }
    text = f"kline_day_2026={json.dumps(payload, ensure_ascii=False)}"
    with patch("app.infrastructure.providers.tencent._get_session") as session:
        session.return_value.get.return_value.text = text
        frame = TencentDataProvider().fetch_index_kline(symbol, "20251013", "20261013")

    assert not frame.empty
    volume = float(frame.iloc[-1]["成交量"])
    amount = float(frame.iloc[-1]["成交额"])
    assert volume == pytest.approx(raw_volume * 100)
    assert amount == pytest.approx(_AMOUNT_YUAN)
    # 指数成分股均价 10~100 元；量纲任一错都会偏出三个数量级
    assert 10.0 <= amount / volume <= 100.0


def test_tencent_index_amount_is_not_dropped():
    """回归守卫：腾讯指数行 index 8 是成交额（万元），早期 iloc[:, :6] 把它丢掉了。"""
    import inspect

    src = inspect.getsource(TencentDataProvider.fetch_index_kline)
    assert '"amount": "成交额"' in src
    assert 'iloc[:, :6]' not in src, "只取前 6 列会丢掉成交额"
    assert '"amount": "成交额"' in src