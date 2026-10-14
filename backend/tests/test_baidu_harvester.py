"""Unit tests for Baidu headless credential harvester and provider integration."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.configuration.schema import Settings
from app.infrastructure.providers.baidu.harvester import BaiduCredentialHarvester
from app.infrastructure.providers.baidu.provider import BaiduDataProvider
from app.infrastructure.providers.baidu.transport import BaiduTransport, check_result_code


@pytest.mark.asyncio
async def test_harvester_caching_and_invalidation() -> None:
    harvester = BaiduCredentialHarvester(ttl_seconds=10.0)
    assert not harvester.is_valid()
    assert harvester.get_credentials() == ("", "")

    harvester.update("cookie_a=1", "token_123")
    assert harvester.is_valid()
    assert harvester.get_credentials() == ("cookie_a=1", "token_123")

    # Invalidation resets valid state
    harvester.invalidate()
    assert not harvester.is_valid()
    assert harvester.get_credentials() == ("", "")


@pytest.mark.asyncio
async def test_ensure_credentials_deduplication() -> None:
    harvester = BaiduCredentialHarvester(ttl_seconds=60.0)

    mock_harvest = AsyncMock(return_value=("captured_cookie=val", "acs_token_xyz"))
    with patch("app.infrastructure.providers.baidu.harvester.harvest_baidu_credentials", mock_harvest):
        # Concurrent calls should only trigger harvest once
        res1, res2 = await asyncio.gather(
            harvester.ensure_credentials(),
            harvester.ensure_credentials(),
        )

        assert res1 == ("captured_cookie=val", "acs_token_xyz")
        assert res2 == ("captured_cookie=val", "acs_token_xyz")
        assert mock_harvest.await_count == 1


def test_provider_credentials_prefers_harvester() -> None:
    harvester = BaiduCredentialHarvester(ttl_seconds=60.0)
    harvester.update("dynamic_cookie=1", "dynamic_token_abc")

    settings = Settings(baidu_cookie="static_cookie", baidu_acs_token="static_token")
    provider = BaiduDataProvider(lambda: settings, harvester=harvester)

    cookie, token = provider._credentials()
    assert cookie == "dynamic_cookie=1"
    assert token == "dynamic_token_abc"


def test_provider_credentials_falls_back_to_settings() -> None:
    harvester = BaiduCredentialHarvester(ttl_seconds=60.0)
    settings = Settings(baidu_cookie="static_cookie", baidu_acs_token="static_token")
    provider = BaiduDataProvider(lambda: settings, harvester=harvester)

    cookie, token = provider._credentials()
    assert cookie == "static_cookie"
    assert token == "static_token"


def test_transport_invalidates_harvester_on_403() -> None:
    harvester = MagicMock()
    transport = BaiduTransport(
        credentials_provider=lambda: ("cookie", "token"),
        on_risk_detected=harvester.invalidate,
    )

    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_response.json.return_value = {"Result": {"code": 403, "msg": "hit risk"}}

    with patch.object(transport._session, "get", return_value=mock_response):
        with pytest.raises(ConnectionError, match="百度风控拦截"):
            transport.get_json("/vapi/v1/fundsortlist", params={})

    harvester.invalidate.assert_called_once()


def test_check_result_code_detects_risk_control() -> None:
    risk_data = {"ResultCode": 0, "Result": {"code": 403, "isCaptchaEnabled": True, "msg": "hit risk"}}
    with pytest.raises(ConnectionError, match="百度风控拦截"):
        check_result_code(risk_data)
