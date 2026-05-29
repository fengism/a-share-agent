import logging

import pytest

from app.services.base.provider_chain import BaseProviderChain, ProviderAttempt


@pytest.mark.asyncio
async def test_provider_chain_returns_first_success_without_calling_later_loader():
    calls: list[str] = []

    async def first_loader():
        calls.append("first")
        return "ok"

    async def second_loader():
        calls.append("second")
        return "fallback"

    result = await BaseProviderChain([
        ProviderAttempt(label="first", loader=first_loader),
        ProviderAttempt(label="second", loader=second_loader),
    ]).run()

    assert result == "ok"
    assert calls == ["first"]


@pytest.mark.asyncio
async def test_provider_chain_falls_back_after_failure(caplog):
    async def first_loader():
        raise ValueError("bad data")

    async def second_loader():
        return {"source": "fallback"}

    with caplog.at_level(logging.INFO, logger="app.services.base.provider_chain"):
        result, report = await BaseProviderChain([
            ProviderAttempt(label="primary", loader=first_loader, on_error="primary unavailable"),
            ProviderAttempt(label="fallback", loader=second_loader),
        ]).run_with_report()

    assert result == {"source": "fallback"}
    assert report.selected_label == "fallback"
    assert [attempt.label for attempt in report.attempts] == ["primary", "fallback"]
    assert report.attempts[0].success is False
    assert report.attempts[0].error_type == "ValueError"
    assert report.attempts[1].success is True
    assert "label=primary" in caplog.text
    assert "error_type=ValueError" in caplog.text
    assert "primary unavailable" in caplog.text


@pytest.mark.asyncio
async def test_provider_chain_raises_last_error_when_all_attempts_fail():
    async def first_loader():
        raise ValueError("first failed")

    async def second_loader():
        raise RuntimeError("second failed")

    with pytest.raises(RuntimeError, match="second failed"):
        await BaseProviderChain([
            ProviderAttempt(label="first", loader=first_loader),
            ProviderAttempt(label="second", loader=second_loader),
        ]).run()


@pytest.mark.asyncio
async def test_provider_chain_empty_attempts_raise_runtime_error():
    with pytest.raises(RuntimeError, match="provider chain is empty"):
        await BaseProviderChain([]).run()


@pytest.mark.asyncio
async def test_provider_chain_success_log_and_report_selected_provider(caplog):
    async def loader():
        return [1, 2, 3]

    with caplog.at_level(logging.DEBUG, logger="app.services.base.provider_chain"):
        result, report = await BaseProviderChain([
            ProviderAttempt(label="provider-a", loader=loader),
        ]).run_with_report()

    assert result == [1, 2, 3]
    assert report.selected_label == "provider-a"
    assert len(report.attempts) == 1
    assert report.attempts[0].success is True
    assert report.attempts[0].elapsed_ms >= 0
    assert "provider attempt succeeded" in caplog.text
    assert "label=provider-a" in caplog.text
