from types import SimpleNamespace

import pandas as pd
import pytest

from app.financial_data.stock.quotes.historical import _historical_source_attempts
from app.infrastructure.providers import cls as cls_module
from app.infrastructure.providers.akshare import stock as ak_stock
from app.infrastructure.providers.eastmoney.kline import KlineMixin
from app.infrastructure.providers.sina.provider import SinaDataProvider
from app.infrastructure.providers.tdxhub import TdxhubDataProvider
from app.infrastructure.providers.tencent import TencentDataProvider


def test_unadjusted_daily_source_order(monkeypatch: pytest.MonkeyPatch) -> None:
    providers = {
        name: SimpleNamespace(
            fetch_stock_kline=lambda *args: pd.DataFrame(),
            fetch_stock_kline_sina=lambda *args: pd.DataFrame(),
            fetch_kline=lambda *args: pd.DataFrame(),
        )
        for name in ("tdxhub", "tencent", "akshare", "eastmoney", "sina", "cls")
    }
    monkeypatch.setattr(
        "app.financial_data.stock.quotes.historical.get_provider",
        lambda name: providers[name],
    )
    attempts = _historical_source_attempts("600519", "daily", "20260901", "20260930", "")
    assert [attempt.label for attempt in attempts] == [
        "TDX 复权K线",
        "腾讯财经复权K线",
        "AkShare 新浪复权K线",
        "东方财富不复权K线直连（fallback）",
        "新浪历史K线直连（fallback）",
        "财联社不复权K线（last-resort）",
    ]


def test_tdx_history_volume_is_normalized_to_shares() -> None:
    class Quotes:
        def call(self, operation, *args, **kwargs):
            assert operation == "bars_all"
            return pd.DataFrame([
                {"datetime": "2026-09-30", "open": 10, "close": 10.5, "high": 11, "low": 9, "vol": 123, "amount": 129150},
            ])

    frame = TdxhubDataProvider(Quotes()).fetch_stock_kline("600519", "20260930", "20260930", "")
    assert frame.iloc[0]["volume"] == 12_300


def test_tencent_history_volume_is_normalized_to_shares(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = 'x={"data":{"sh600519":{"day":[["2026-09-30","10","10.5","11","9","123","x","1.2","12.915","x"]]}}}'
    monkeypatch.setattr(
        "app.infrastructure.providers.tencent._get_session",
        lambda: SimpleNamespace(get=lambda *args, **kwargs: SimpleNamespace(text=payload)),
    )
    frame = TencentDataProvider().fetch_stock_kline("600519", "20260930", "20260930", "")
    assert frame.iloc[0]["成交量"] == 12_300
    assert frame.iloc[0]["成交额"] == pytest.approx(129_150)


def test_akshare_history_volume_units(monkeypatch: pytest.MonkeyPatch) -> None:
    eastmoney = pd.DataFrame({"成交量": [123], "开盘": [10], "收盘": [10.5], "最高": [11], "最低": [9]})
    monkeypatch.setattr(ak_stock.ak, "stock_zh_a_hist", lambda **kwargs: eastmoney)
    frame = ak_stock.fetch_stock_kline("600519", "daily", "20260930", "20260930", "")
    assert frame.iloc[0]["成交量"] == 12_300

    sina = pd.DataFrame({
        "date": ["2026-09-30"], "open": [10], "high": [11], "low": [9], "close": [10.5],
        "volume": [12_300], "amount": [129_150], "turnover": [0.012], "outstanding_share": [1_000_000],
    })
    monkeypatch.setattr(ak_stock.ak, "stock_zh_a_daily", lambda **kwargs: sina)
    frame = ak_stock.fetch_stock_kline_sina("600519", "20260930", "20260930", "")
    assert frame.iloc[0]["成交量"] == 12_300


def test_cls_history_volume_is_normalized_to_shares() -> None:
    frame = cls_module._normalize_kline_rows(
        [{
            "date": "20260930", "open_px": 10, "close_px": 10.5, "high_px": 11, "low_px": 9,
            "business_amount": 12_300, "business_balance": 129_150, "amp": 0.2,
            "tr": 0.01, "change": 0.05, "preclose_px": 10,
        }],
        pd.Timestamp("2026-09-30").date(),
        pd.Timestamp("2026-09-30").date(),
    )
    assert frame.iloc[0]["成交量"] == 12_300


def test_eastmoney_direct_history_volume_is_normalized_to_shares(monkeypatch: pytest.MonkeyPatch) -> None:
    class Provider(KlineMixin):
        eastmoney_headers = {}

        def em_get_response(self, *args, **kwargs):
            return SimpleNamespace(json=lambda: {"data": {"klines": ["2026-09-30,10,10.5,11,9,123,129150,20,5,0.5,1.2"]}})

    frame = Provider().fetch_kline("600519", "daily", "20260930", "20260930", "")
    assert frame.iloc[0]["成交量"] == 12_300


def test_sina_direct_history_volume_stays_in_shares(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = SinaDataProvider()
    monkeypatch.setattr(
        provider._session,
        "get",
        lambda *args, **kwargs: SimpleNamespace(text='[{"day":"2026-09-30","open":"10","high":"11","low":"9","close":"10.5","volume":"12300"}]'),
    )
    frame = provider.fetch_kline("600519", "daily", "20260930", "20260930")
    assert frame.iloc[0]["成交量"] == 12_300
