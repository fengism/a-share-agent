"""财报数据源标注的回归护栏。

旧实现用 ``"sina_error" in locals()`` 判断是否走了 AkShare 兜底，但 PEP 3110 会在
except 块结束时删掉异常名，该判断恒为 False——兜底结果被标成 ``source=sina``，
故障溯源时这条日志会直接把人带偏。
"""
import logging

import pandas as pd
import pytest

from app.financial_data.stock.fundamentals import financials


class _Sym:
    raw = "600519"
    prefixed_upper = "SH600519"


def _install_providers(monkeypatch, sina_impl, akshare_impl):
    monkeypatch.setattr(
        financials,
        "_get_sina_provider",
        lambda: type("P", (), {"fetch_stock_financials": staticmethod(sina_impl)})(),
    )
    monkeypatch.setattr(
        financials,
        "_get_akshare_provider",
        lambda: type("P", (), {"fetch_stock_financials": staticmethod(akshare_impl)})(),
    )
    monkeypatch.setattr(financials.cache, "set", lambda *a, **k: None)


def _frame() -> pd.DataFrame:
    return pd.DataFrame([{"REPORT_DATE": "2025-12-31", "NET_PROFIT": 1}])


def _capture_source(caplog: pytest.LogCaptureFixture) -> str:
    for record in caplog.records:
        if "financial statement loaded" in record.getMessage():
            return record.getMessage()
    raise AssertionError("未捕获到 financial statement loaded 日志")


class TestFinancialStatementSource:
    async def test_labels_sina_on_primary_path(self, monkeypatch, caplog):
        _install_providers(monkeypatch, lambda *a, **k: _frame(), lambda *a, **k: _frame())
        with caplog.at_level(logging.INFO, logger=financials.__name__):
            await financials._load_financial_statement(_Sym(), "income", "k")
        assert "source=sina" in _capture_source(caplog)

    async def test_labels_akshare_on_fallback_path(self, monkeypatch, caplog):
        def _sina_down(*_args, **_kwargs):
            raise RuntimeError("新浪不可用")

        _install_providers(monkeypatch, _sina_down, lambda *a, **k: _frame())
        with caplog.at_level(logging.INFO, logger=financials.__name__):
            await financials._load_financial_statement(_Sym(), "income", "k")
        assert "source=akshare" in _capture_source(caplog)
