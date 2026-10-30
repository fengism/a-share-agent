"""全市场成交量/成交额量纲契约（2026-10-13 收盘实测锚定）。

house 契约：
- 成交量 = **股**（A 股 / 港股均是「股」，不是「手」）
- 成交额 = **元**（A 股 CNY，港股 HKD）

各上游原始量纲并不一致，且同一接口的兜底链可能来自不同源，一旦漏乘系数就会
出现 100 倍偏差。用 ``amount / volume`` 反推的隐含均价来判定，而不是硬编码
供应商数值——量纲再错会直接炸，而不是悄悄改掉数字。
"""

import json
from unittest.mock import patch

import pandas as pd
import pytest

from app.infrastructure.providers.akshare import indices as ak_indices
from app.infrastructure.providers.registry import get_provider
from app.infrastructure.providers.tdxhub import tdxhub_provider
from app.infrastructure.providers.tencent import TencentDataProvider, _volume_to_shares

_TRADING_DAY = "2026-10-13"


# ── 腾讯个股：按板块量纲不同 ────────────────────────────────────────────────
@pytest.mark.parametrize(
    ("code", "raw_volume", "expected_shares"),
    [
        ("600519", 26_573.0, 2_657_300.0),      # 沪主板：原始为手，×100
        ("000001", 994_937.0, 99_493_700.0),    # 深主板：原始为手，×100
        ("300750", 408_835.0, 40_883_500.0),    # 创业板：原始为手，×100
        ("920002", 7_306.0, 730_600.0),         # 北交所：原始为手，×100
        ("688981", 30_272_877.0, 30_272_877.0),  # 科创板：原始已是股，不乘
        ("688111", 5_005_151.0, 5_005_151.0),    # 科创板：原始已是股，不乘
        ("689009", 6_806_587.0, 6_806_587.0),    # 科创 CDR：原始已是股，不乘
    ],
)
def test_tencent_stock_volume_factor_per_board(code: str, raw_volume: float, expected_shares: float):
    assert _volume_to_shares(code) == (1 if expected_shares == raw_volume else 100)


def _tencent_stock_response(code: str, raw_volume: float, raw_amount_wan: float) -> str:
    from app.core.market import normalize_code

    sym = normalize_code(code).prefixed_lower
    payload = {
        "data": {
            sym: {
                "qfqday": [
                    [
                        _TRADING_DAY, "100.0", "104.75", "106.0", "99.0",
                        f"{raw_volume:.2f}", {}, "3.5", f"{raw_amount_wan:.2f}", "0",
                    ]
                ]
            }
        }
    }
    return f"kline_dayqfq2026={json.dumps(payload, ensure_ascii=False)}"


def _fetch_tencent_stock(code: str, raw_volume: float, raw_amount_wan: float) -> pd.DataFrame:
    with patch("app.infrastructure.providers.tencent._get_session") as session:
        session.return_value.get.return_value.text = _tencent_stock_response(
            code, raw_volume, raw_amount_wan,
        )
        return TencentDataProvider().fetch_stock_kline(code, "20260101", "20261231", adjust="qfq")


@pytest.mark.parametrize(
    ("code", "raw_volume", "raw_amount_wan"),
    [
        ("600519", 26_573.0, 339_331.56),
        ("300750", 408_835.0, 1_190_724.12),
        ("688981", 30_272_877.0, 317_102.65),   # 科创：错乘 100 会让均价变 1.05
        ("689009", 6_806_587.0, 25_326.59),    # 科创 CDR：同上
    ],
)
def test_tencent_stock_volume_implied_price_is_sane(code, raw_volume, raw_amount_wan):
    frame = _fetch_tencent_stock(code, raw_volume, raw_amount_wan)
    volume = float(frame.iloc[-1]["成交量"])
    amount = float(frame.iloc[-1]["成交额"])
    assert amount == pytest.approx(raw_amount_wan * 10000)
    assert volume == pytest.approx(raw_volume * _volume_to_shares(code))
    # 茅台 1277 元、金山 229 元、中芯 104 元、九号 37 元
    implied = amount / volume
    assert 1.0 <= implied <= 2000.0, f"{code} 量纲错误: volume={volume:,.0f} 均价={implied:,.2f}"


def test_tencent_keeps_amount_in_yuan():
    """腾讯原始成交额是万元，任何分支都必须是元。"""
    frame = _fetch_tencent_stock("688981", 30_272_877.0, 317_102.65)
    assert float(frame.iloc[-1]["成交额"]) == pytest.approx(3_171_026_500.0)


# ── akshare 指数：index_zh_a_hist 原始为手 ──────────────────────────────────
@pytest.mark.parametrize(
    "symbol", ["000001", "399001", "399006", "000688", "000300", "899050"],
)
def test_akshare_index_volume_is_normalized_to_shares(symbol: str):
    payload = pd.DataFrame(
        [{
            "日期": _TRADING_DAY, "开盘": 2899.15, "收盘": 2958.34, "最高": 2999.76,
            "最低": 2860.80, "成交量": 182_678_834.0, "成交额": 452_004_282_368.0,
        }]
    )
    with patch.object(ak_indices.ak, "index_zh_a_hist", return_value=payload):
        frame = ak_indices.fetch_index_kline(symbol, "daily", "20260101", "20261231")

    volume = float(frame.iloc[-1]["成交量"])
    amount = float(frame.iloc[-1]["成交额"])
    assert volume == pytest.approx(18_267_883_400.0)
    assert amount == pytest.approx(452_004_282_368.0)
    # 指数成分股均价 10~100 元；漏乘 100 会得到 2474 元
    assert 10.0 <= amount / volume <= 100.0


@pytest.mark.parametrize(
    ("symbol", "raw_amount_wan", "expected_yuan"),
    [
        ("sh000001", 77_930_228.80, 779_302_288_000.0),   # 上证，与 TDX/东财 7,793.02 亿一致
        ("sh000688", 7_698_032.06, 76_980_320_600.0),      # 科创50，与 TDX/东财 769.80 亿一致
        ("sh000300", 44_203_772.15, 442_037_721_500.0),    # 沪深300，与 TDX/东财 4,420.38 亿一致
    ],
)
def test_tencent_index_amount_is_converted_from_wan_yuan(symbol, raw_amount_wan, expected_yuan):
    """腾讯指数成交额在 index 8、单位万元；必须 ×10000，且不能被前 6 列截断丢弃。"""
    payload = {
        "data": {
            symbol: {
                "day": [
                    [
                        _TRADING_DAY, "2899.15", "2958.34", "2999.76", "2860.80",
                        "177_673_105.00", {}, "3.24", f"{raw_amount_wan:.2f}", "0", "0",
                    ]
                ]
            }
        }
    }
    with patch("app.infrastructure.providers.tencent._get_session") as session:
        session.return_value.get.return_value.text = (
            f"kline_day_2026={json.dumps(payload, ensure_ascii=False)}"
        )
        frame = TencentDataProvider().fetch_index_kline(symbol, "20260101", "20261231")

    assert "成交额" in frame.columns, "成交额列丢失（iloc[:, :6] 截断）"
    assert float(frame.iloc[-1]["成交额"]) == pytest.approx(expected_yuan)


def test_akshare_index_matches_stock_normalization():
    """指数与个股同源(东财)，成交量系数必须一致，避免只修一半。"""
    import inspect

    index_src = inspect.getsource(ak_indices.fetch_index_kline)
    from app.infrastructure.providers.akshare import stock as ak_stock

    stock_src = inspect.getsource(ak_stock.fetch_stock_kline)
    assert 'frame["成交量"] = pd.to_numeric(frame["成交量"], errors="coerce") * 100' in index_src
    assert 'frame["成交量"] = pd.to_numeric(frame["成交量"], errors="coerce") * 100' in stock_src


# ── TDX 指数：bars 返回「手」，系数与个股一致 ───────────────────────────────
def test_tdx_index_volume_uses_shou_factor():
    raw = pd.DataFrame([{
        "open": 2899.15, "close": 2958.34, "high": 2999.76, "low": 2860.80,
        "vol": 182_678_834.0, "volume": 182_678_834.0,
        "amount": 452_004_282_368.0, "datetime": f"{_TRADING_DAY} 15:00",
    }])
    frame = tdxhub_provider._format_index_kline_df(
        raw, start_date=_TRADING_DAY, end_date=_TRADING_DAY, volume_multiplier=100,
    )
    row = frame.iloc[-1]
    assert float(row["volume"]) == pytest.approx(18_267_880_000.0)
    assert 10.0 <= float(row["amount"]) / float(row["volume"]) <= 100.0


# ── 港股：新浪已是「股」+「元」，不得再乘 ────────────────────────────────────
@pytest.mark.parametrize(
    ("volume", "amount", "close", "note"),
    [
        (14_011_738.0, 5_984_000_000.0, 425.80, "腾讯控股"),
        (46_617_409.0, 5_074_000_000.0, 108.20, "阿里巴巴"),
        (182_805_610.0, 4_542_000_000.0, 24.52, "小米集团"),
    ],
)
def test_hk_volume_implied_price_matches_close(volume, amount, close, note):
    """港股链不得引入换算：隐含均价必须贴近收盘价（港元）。"""
    implied = amount / volume
    assert abs(implied / close - 1) < 0.05, f"{note} 港股量纲异常: 均价={implied:.2f} 收盘={close:.2f}"


def test_hk_normalizer_does_not_rescale_units():
    import inspect

    from app.financial_data.hk.service import _normalize_history_frame

    src = inspect.getsource(_normalize_history_frame)
    assert "* 100" not in src, "港股成交量/成交额已是股/元，不得再乘 100"


# ── 东财指数与个股：同源同系数 ───────────────────────────────────────────────
def test_eastmoney_index_volume_factor_matches_stock():
    import inspect

    index_src = inspect.getsource(get_provider("eastmoney").fetch_index_kline)
    stock_src = inspect.getsource(get_provider("eastmoney").fetch_kline)
    assert 'df["volume"] = pd.to_numeric(df["volume"], errors="coerce") * 100' in index_src
    assert 'df["成交量"] = pd.to_numeric(df["成交量"], errors="coerce") * 100' in stock_src