import json

import pytest

from app.utils import http_client


class DummyResponse:
    def __init__(self, payload=None, text="", raise_error: Exception | None = None):
        self._payload = payload or {}
        self.text = text
        self.raise_error = raise_error
        self.raise_called = False

    def raise_for_status(self):
        self.raise_called = True
        if self.raise_error is not None:
            raise self.raise_error

    def json(self):
        return self._payload


def test_get_passes_request_options_and_raises_for_status(monkeypatch):
    captured = {}
    response = DummyResponse(payload={"ok": True})

    def fake_request(method, url, params=None, data=None, json=None, headers=None, timeout=None):
        captured.update({"method": method, "url": url, "params": params, "data": data, "json": json, "headers": headers, "timeout": timeout})
        return response

    monkeypatch.setattr(http_client.requests, "request", fake_request)

    result = http_client.get("https://example.com/api", params={"q": "x"}, headers={"A": "B"}, timeout=3)

    assert result is response
    assert response.raise_called is True
    assert captured == {
        "method": "GET",
        "url": "https://example.com/api",
        "params": {"q": "x"},
        "data": None,
        "json": None,
        "headers": {"A": "B"},
        "timeout": 3,
    }


def test_post_maps_json_body_to_requests_json(monkeypatch):
    captured = {}
    response = DummyResponse(payload={"ok": True})

    def fake_request(method, url, params=None, data=None, json=None, headers=None, timeout=None):
        captured.update({"method": method, "url": url, "json": json, "timeout": timeout})
        return response

    monkeypatch.setattr(http_client.requests, "request", fake_request)

    http_client.post("https://example.com/api", json_body={"name": "test"}, timeout=5)

    assert captured == {
        "method": "POST",
        "url": "https://example.com/api",
        "json": {"name": "test"},
        "timeout": 5,
    }


def test_request_propagates_raise_for_status_error(monkeypatch):
    def fake_request(*args, **kwargs):
        return DummyResponse(raise_error=RuntimeError("http failed"))

    monkeypatch.setattr(http_client.requests, "request", fake_request)

    with pytest.raises(RuntimeError, match="http failed"):
        http_client.get("https://example.com/api")


def test_parse_text_json_strips_response_text():
    response = DummyResponse(text='  {"ok": true}  ')

    assert http_client.parse_text_json(response) == {"ok": True}


def test_parse_text_json_keeps_invalid_json_error():
    response = DummyResponse(text="not json")

    with pytest.raises(json.JSONDecodeError):
        http_client.parse_text_json(response)
