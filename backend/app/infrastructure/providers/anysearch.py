"""AnySearch unified search API adapter."""

from __future__ import annotations

import json
import re
import threading
import time
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import requests

from app.configuration import get_settings
from app.core.timezones import SHANGHAI_TIMEZONE
from app.infrastructure.http.client import provider_post

ANYSEARCH_SEARCH_URL = "https://api.anysearch.com/v1/search"
_TIME_RANGE_DAYS = {"day": 1, "week": 7, "month": 30, "half_year": 183}
_DEFAULT_QUOTA_COOLDOWN_SECONDS = 300.0
_DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS = 60.0
_KEY_SCOPED_HTTP_STATUSES = frozenset({401, 402, 403, 429})
_PERMANENT_KEY_HTTP_STATUSES = frozenset({401, 403})


class AnySearchResponseError(RuntimeError):
    """Raised when AnySearch returns a malformed or unsuccessful JSON envelope."""


class AnySearchKeysUnavailableError(RuntimeError):
    """Raised when configured keys are disabled or cooling down."""


def _shanghai_today() -> date:
    return datetime.now(SHANGHAI_TIMEZONE).date()


def _query_with_time_range(query: str, time_range: str, today: date) -> str:
    """Add an explicit Beijing-time date window because AnySearch has no native time filter."""
    days = _TIME_RANGE_DAYS.get(time_range)
    if days is None:
        return query
    start_date = today - timedelta(days=days)
    return (
        f"{query} 时间范围：{start_date.isoformat()} 至 {today.isoformat()}（北京时间），"
        "仅返回该时间范围内发布或更新的资料"
    )


def _retry_after_seconds(response: requests.Response) -> float | None:
    raw_value = (response.headers.get("Retry-After") or "").strip()
    if not raw_value:
        return None
    try:
        return max(0.0, float(raw_value))
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(raw_value)
        except (TypeError, ValueError, OverflowError):
            return None
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)
        return max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())


def _parse_api_keys(value: str) -> tuple[str, ...]:
    """Parse a single key, comma/newline-separated keys, or a JSON string array."""
    normalized = value.strip()
    if not normalized:
        return ()

    candidates: list[Any]
    if normalized.startswith("["):
        try:
            decoded = json.loads(normalized)
        except (TypeError, ValueError):
            decoded = None
        candidates = decoded if isinstance(decoded, list) else re.split(r"[,\r\n]+", normalized)
    else:
        candidates = re.split(r"[,\r\n]+", normalized)

    # Preserve configured order while preventing duplicate keys from receiving extra traffic.
    return tuple(
        dict.fromkeys(
            normalized_candidate
            for candidate in candidates
            if (normalized_candidate := str(candidate).strip()) and "***" not in normalized_candidate
        )
    )


class AnySearchProvider:
    name = "anysearch"

    def __init__(
        self,
        *,
        transport: Callable[..., requests.Response] = provider_post,
        settings_provider: Callable[[], Any] = get_settings,
        today_provider: Callable[[], date] = _shanghai_today,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._transport = transport
        self._settings_provider = settings_provider
        self._today_provider = today_provider
        self._clock = clock
        self._key_lock = threading.Lock()
        self._key_cursor = 0
        self._configured_keys: tuple[str, ...] = ()
        self._disabled_keys: set[str] = set()
        self._cooldown_until_by_key: dict[str, float] = {}

    def _candidate_api_keys(self) -> tuple[str, ...]:
        configured = str(getattr(self._settings_provider(), "anysearch_api_key", "") or "")
        keys = _parse_api_keys(configured)
        if not keys:
            return ("",)
        with self._key_lock:
            if keys != self._configured_keys:
                self._configured_keys = keys
                self._disabled_keys.clear()
                self._cooldown_until_by_key.clear()
                self._key_cursor = 0
            now = self._clock()
            start = self._key_cursor % len(keys)
            self._key_cursor += 1
            ordered = keys[start:] + keys[:start]
            available = tuple(
                key
                for key in ordered
                if key not in self._disabled_keys and self._cooldown_until_by_key.get(key, 0.0) <= now
            )
        if not available:
            raise AnySearchKeysUnavailableError("AnySearch configured keys are unavailable")
        return available

    def _record_key_http_failure(self, api_key: str, status_code: int, response: requests.Response) -> None:
        if not api_key:
            return
        with self._key_lock:
            if status_code in _PERMANENT_KEY_HTTP_STATUSES:
                self._disabled_keys.add(api_key)
                self._cooldown_until_by_key.pop(api_key, None)
                return
            retry_after = _retry_after_seconds(response)
            default_cooldown = (
                _DEFAULT_QUOTA_COOLDOWN_SECONDS if status_code == 402 else _DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS
            )
            cooldown_seconds = max(default_cooldown, retry_after or 0.0)
            self._cooldown_until_by_key[api_key] = max(
                self._cooldown_until_by_key.get(api_key, 0.0),
                self._clock() + cooldown_seconds,
            )

    def search(
        self,
        query: str,
        max_results: int = 10,
        timeout: int = 15,
        *,
        time_range: str = "any",
        language: str = "zh",
        tag: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Search AnySearch and adapt its result envelope to the common web-search shape."""
        constrained_query = _query_with_time_range(query, time_range, self._today_provider())

        payload: dict[str, Any] = {
            "query": constrained_query,
            "max_results": max(1, min(max_results, 10)),
        }
        normalized_tag = (tag or "").strip()
        if normalized_tag:
            payload["tag"] = normalized_tag
        if params:
            payload["params"] = params
        if language == "zh":
            payload["language"] = "zh-CN"

        response: requests.Response | None = None
        last_key_error: requests.HTTPError | None = None
        for api_key in self._candidate_api_keys():
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            try:
                response = self._transport(
                    ANYSEARCH_SEARCH_URL,
                    json_body=payload,
                    headers=headers,
                    timeout=timeout,
                )
                break
            except requests.HTTPError as exc:
                status_code = exc.response.status_code if exc.response is not None else None
                if not api_key or status_code not in _KEY_SCOPED_HTTP_STATUSES or exc.response is None:
                    raise
                self._record_key_http_failure(api_key, status_code, exc.response)
                last_key_error = exc
        if response is None:
            raise AnySearchKeysUnavailableError("AnySearch configured keys are unavailable") from last_key_error
        try:
            body = response.json()
        except ValueError as exc:
            raise AnySearchResponseError("AnySearch returned invalid JSON") from exc
        if not isinstance(body, dict) or body.get("code") != 0:
            raise AnySearchResponseError("AnySearch returned an unsuccessful response")

        data = body.get("data")
        raw_results = data.get("results") if isinstance(data, dict) else None
        if not isinstance(raw_results, list):
            raise AnySearchResponseError("AnySearch response is missing data.results")

        results: list[dict[str, Any]] = []
        for item in raw_results:
            if not isinstance(item, dict):
                continue
            url = item.get("url") or ""
            snippet = item.get("snippet") or item.get("content") or ""
            normalized = {
                # 官方允许 title 为空；公共归一化层要求非空，使用 URL 避免丢失有效结果。
                "title": item.get("title") or url,
                "href": url,
                "body": snippet,
                "engine": self.name,
            }
            published_at = next(
                (
                    item.get(key)
                    for key in (
                        "published_at",
                        "publish_time",
                        "published_time",
                        "pub_date",
                        "date_published",
                        "date",
                    )
                    if item.get(key) not in (None, "")
                ),
                None,
            )
            if published_at is not None:
                normalized["published_at"] = published_at
            results.append(normalized)
        return results[: payload["max_results"]]


anysearch_provider = AnySearchProvider()
