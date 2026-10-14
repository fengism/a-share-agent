"""上游返回「成功但内容不可用」时的熔断行为。

腾讯等接口按 IP 限流时返回 HTTP 200、body 却是 ``v_sh600519="";``。这类失败原先
以 ValueError 落到 ``classify_provider_error`` 的兜底分支 → PERMANENT，而
``ProviderCircuitBreaker.record_failure`` 对非 retryable 错误直接
``circuits[key] = CircuitState()``，于是连续失败计数被反复清零、熔断器永远打不开，
上游持续空返回时每个请求都要白跑一遍完整降级链。
"""

import asyncio
import logging

import pytest

from app.configuration import get_settings
from app.core.exceptions import UpstreamEmptyResponseError
from app.infrastructure.providers.provider_chain import BaseProviderChain, ProviderAttempt
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.provider_policy import (
    ProviderErrorCategory,
    classify_provider_error,
    is_retryable,
)


@pytest.fixture(autouse=True)
def _reset_circuit():
    provider_gateway.reset()
    yield
    provider_gateway.reset()


@pytest.fixture(autouse=True)
def _quiet_warnings(caplog):
    caplog.set_level(logging.CRITICAL)


def test_empty_response_is_transient_and_retryable():
    category = classify_provider_error(UpstreamEmptyResponseError("空体"))
    assert category == ProviderErrorCategory.TRANSIENT
    assert is_retryable(category) is True


def test_caller_error_stays_permanent():
    """请求参数非法是调用方 bug，不能算瞬时故障，否则会误开熔断。"""
    assert classify_provider_error(ValueError("请求日期非法")) == ProviderErrorCategory.PERMANENT


async def _drain(label: str, error: Exception, times: int) -> list[str]:
    """主源每次都失败、由兜底源兜住，只观察主源的熔断状态演进。"""

    async def failing():
        raise error

    async def working():
        return {"600519": {"code": "600519", "price": 1400.0}}

    states = []
    for _ in range(times):
        chain = BaseProviderChain(
            [
                ProviderAttempt(label=label, loader=failing, on_error="主源不可用"),
                ProviderAttempt(label="tdxhub", loader=working, on_error="兜底不可用"),
            ],
            operation="stock_quotes",
        )
        result, _ = await chain.run_with_report()
        assert result["600519"]["price"] == 1400.0, "兜底源应始终可用"
        states.append(provider_gateway.snapshot()[f"{label}:stock_quotes"]["status"])
    return states


async def test_circuit_opens_after_repeated_empty_responses():
    threshold = get_settings().provider_failure_threshold
    states = await _drain("tencent", UpstreamEmptyResponseError("未返回有效实时行情"), threshold + 2)
    assert states[: threshold - 1].count("closed") == threshold - 1
    assert states[-1] == "open", f"空返回应触发熔断，实际状态序列={states}"


async def test_circuit_never_opens_for_permanent_errors():
    """回归守卫：ValueError 仍走永久失败，不会误开熔断。"""
    threshold = get_settings().provider_failure_threshold
    states = await _drain("tencent", ValueError("不支持的证券代码"), threshold + 3)
    assert set(states) == {"closed"}


async def test_open_circuit_short_circuits_further_calls():
    threshold = get_settings().provider_failure_threshold
    calls = {"tencent": 0}

    async def failing():
        calls["tencent"] += 1
        raise UpstreamEmptyResponseError("未返回有效实时行情")

    async def working():
        return {"600519": {"code": "600519", "price": 1400.0}}

    def build() -> BaseProviderChain:
        return BaseProviderChain(
            [
                ProviderAttempt(label="tencent", loader=failing, on_error="主源不可用"),
                ProviderAttempt(label="tdxhub", loader=working, on_error="兜底不可用"),
            ],
            operation="stock_quotes",
        )

    for _ in range(threshold):
        await build().run()

    assert provider_gateway.snapshot()["tencent:stock_quotes"]["status"] == "open"
    calls_before = calls["tencent"]

    await build().run()

    assert calls["tencent"] == calls_before, "熔断打开后不应再调用上游"
    assert calls["tencent"] > 0, "熔断前确实调用过上游，测试才有意义"


def test_realtime_empty_quotes_raise_empty_response_error():
    from app.financial_data.stock.quotes.realtime import _load_quote_source

    def empty(_codes):
        return {}

    with pytest.raises(UpstreamEmptyResponseError):
        asyncio.run(_load_quote_source("tencent", empty, ["600519"], semaphore=None))


def test_kline_content_failures_are_empty_response_errors():
    import pandas as pd

    from app.financial_data.kline_quality import validate_kline_frame

    with pytest.raises(UpstreamEmptyResponseError):
        validate_kline_frame(
            "腾讯财经指数K线", pd.DataFrame(), start_date="2025-10-13", end_date="2026-10-13",
            period="daily",
        )

    truncated = pd.DataFrame([{
        "date": "2026-10-13", "open": 3000.0, "close": 3010.0, "high": 3020.0,
        "low": 2990.0, "volume": 1e8, "amount": 1e10,
    }])
    with pytest.raises(UpstreamEmptyResponseError, match="覆盖度不足"):
        validate_kline_frame(
            "腾讯财经指数K线", truncated, start_date="2025-10-13", end_date="2026-10-13",
            period="daily", require_coverage=True,
        )


def test_kline_invalid_request_date_stays_permanent():
    import pandas as pd

    from app.financial_data.kline_quality import validate_kline_frame

    frame = pd.DataFrame([{
        "date": "2026-10-13", "open": 3000.0, "close": 3010.0, "high": 3020.0,
        "low": 2990.0, "volume": 1e8, "amount": 1e10,
    }])
    with pytest.raises(ValueError, match="请求日期无效"):
        validate_kline_frame(
            "腾讯财经指数K线", frame, start_date="bad", end_date="2026-10-13", period="daily",
        )