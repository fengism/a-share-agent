from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from app.infrastructure.providers.eastmoney.misc import MiscMixin
from app.infrastructure.providers.exchange_etf import (
    _build_async_client,
    _normalize_fund_code,
    _parse_szse_current_frame,
)


def test_normalize_fund_code():
    assert _normalize_fund_code("510300") == "510300"
    assert _normalize_fund_code("159919.0") == "159919"
    assert _normalize_fund_code("500") == "000500"
    assert _normalize_fund_code(159919) == "159919"


def test_parse_szse_current_frame_with_commas():
    df = pd.DataFrame({
        "基金代码": ["159919", "159845.0", "invalid", "159915"],
        "当前规模(份)": ["7,342,416,640", "2,919,425,600", "not_a_number", 27343454936.0],
    })
    result = _parse_szse_current_frame(
        df,
        code_column="基金代码",
        share_column="当前规模(份)",
    )
    assert len(result) == 3
    assert result["159919"] == 7342416640.0
    assert result["159845"] == 2919425600.0
    assert result["159915"] == 27343454936.0


@pytest.mark.asyncio
async def test_build_async_client_ipv4_transport():
    client = _build_async_client(timeout=10.0)
    try:
        assert client.trust_env is False
        assert client._transport._pool._local_address == "0.0.0.0"
    finally:
        await client.aclose()


def test_eastmoney_fetch_etf_current_shares():
    class DummyEastMoney(MiscMixin):
        def __init__(self):
            self.em_get_response = MagicMock()

    dummy = DummyEastMoney()
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "data": {
            "diff": [
                {"f12": "510300", "f38": 29400787712.0},
                {"f12": "159919", "f38": 7342416640.0},
            ]
        }
    }
    dummy.em_get_response.return_value = mock_resp

    codes = {"510300", "159919"}
    shares = dummy.fetch_etf_current_shares(codes)

    assert dummy.em_get_response.called
    call_args, call_kwargs = dummy.em_get_response.call_args
    assert "push2delay.eastmoney.com" in call_args[0]
    secids = call_kwargs["params"]["secids"].split(",")
    assert "1.510300" in secids
    assert "0.159919" in secids
    assert call_kwargs["params"]["invt"] == "2"

    assert shares["510300"] == 29400787712.0
    assert shares["159919"] == 7342416640.0


@pytest.mark.asyncio
async def test_fetch_szse_current_fallback_to_eastmoney():
    from app.financial_data.market.quotes.national_team import _fetch_szse_current

    with patch("app.financial_data.market.quotes.national_team._fetch_szse_current_direct") as mock_direct, \
         patch("app.financial_data.market.quotes.national_team._fetch_szse_current_eastmoney") as mock_em:
        mock_direct.side_effect = RuntimeError("Direct network down")
        mock_em.return_value = {
            "159919": 7342416640.0,
            "159845": 2919425600.0,
            "159629": 845252663.0,
            "159915": 27343454936.0,
        }

        obs = await _fetch_szse_current()
        assert len(obs) == 4
        for code in ["159919", "159845", "159629", "159915"]:
            assert code in obs
            assert obs[code].source == "eastmoney_current"


@pytest.mark.asyncio
async def test_fetch_sse_current_eastmoney():
    from app.financial_data.market.quotes.national_team import _fetch_sse_current

    with patch("app.financial_data.market.quotes.national_team._fetch_sse_current_eastmoney") as mock_em:
        mock_em.return_value = {
            "510300": 29400787712.0,
            "510050": 11160666880.0,
        }

        obs = await _fetch_sse_current()
        assert "510300" in obs
        assert obs["510300"].source == "eastmoney_current"
        assert obs["510300"].shares_100m == pytest.approx(294.00787712)

