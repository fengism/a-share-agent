import pandas as pd
import pytest

from app.services.stock import basic_info


@pytest.mark.asyncio
async def test_get_basic_info_degrades_when_tencent_sources_fail(monkeypatch, capsys):
    async def fake_call_blocking(func, *args, **kwargs):
        name = getattr(func, "__name__", "")
        if name == "fetch_stock_basic_info":
            return {"股票简称": "测试股份", "市盈率": "12.3", "市净率": "1.2"}
        if name == "fetch_stock_concepts":
            return None
        if name == "fetch_stock_quote":
            raise RuntimeError("tencent failed")
        return func(*args, **kwargs)

    monkeypatch.setattr(basic_info, "call_blocking", fake_call_blocking)
    monkeypatch.setattr(basic_info, "_load_basic_info_spot_df", lambda: _empty_spot_df())
    monkeypatch.setattr(basic_info, "_safe_fetch_exchange_basic_row", _empty_exchange_row)
    monkeypatch.setattr(basic_info, "get_stock_name_map", _name_map)
    monkeypatch.setattr(basic_info.cache, "get", lambda key: None)
    monkeypatch.setattr(basic_info.cache, "set", lambda *args, **kwargs: None)

    result = await basic_info.get_basic_info("600519")

    assert result.code == "600519"
    assert result.name == "测试股份"
    assert result.concepts == []
    assert capsys.readouterr().out == ""


async def _empty_exchange_row(code: str):
    return {}


async def _name_map():
    return {"600519": "名称映射"}


async def _empty_spot_df():
    return pd.DataFrame(columns=["代码", "名称", "总市值", "流通市值", "最新价"])
