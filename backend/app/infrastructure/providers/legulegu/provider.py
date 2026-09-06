"""乐咕乐股公开市场数据 Provider。"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

import requests

from app.configuration.runtime import get_settings
from app.configuration.schema import Settings

_NORTHBOUND_HISTORY_URL = "https://www.legulegu.com/stockdata/hu-shen-gang-tong-data"
_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://www.legulegu.com/stockdata/hk-to-a",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
    ),
}


class LeguleguDataProvider:
    name = "legulegu"

    def __init__(
        self,
        *,
        settings_provider: Callable[[], Settings] = get_settings,
        session: requests.Session | None = None,
    ) -> None:
        self._settings_provider = settings_provider
        self._session = session or requests.Session()

    def fetch_northbound_history(self) -> Mapping[str, Any]:
        settings = self._settings_provider()
        token = settings.legulegu_token.strip()
        if not token:
            raise ValueError("未配置 LEGULEGU_TOKEN")
        self._session.trust_env = settings.http_trust_env
        response = self._session.get(
            _NORTHBOUND_HISTORY_URL,
            params={"token": token},
            headers=_HEADERS,
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, Mapping):
            raise ValueError("乐咕乐股返回格式无效")
        return payload


legulegu_provider = LeguleguDataProvider()
