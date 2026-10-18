"""同花顺 HTTP 传输与动态配置。"""

from collections.abc import Callable
from typing import cast

import requests

from app.configuration.runtime import get_settings
from app.configuration.schema import Settings
from app.constants.http import THS_HEADERS


class ThsTransport:
    def __init__(
        self,
        *,
        settings_provider: Callable[[], Settings] = get_settings,
        session: requests.Session | None = None,
    ) -> None:
        self._settings_provider = settings_provider
        self._session = session or requests.Session()
        self._session.trust_env = settings_provider().http_trust_env

    def headers(self) -> dict[str, str]:
        headers = dict(THS_HEADERS)
        cookie = self._settings_provider().ths_cookie
        if cookie:
            headers["cookie"] = cookie
        return headers

    def session(self) -> requests.Session:
        trust_env = self._settings_provider().http_trust_env
        if self._session.trust_env != trust_env:
            self._session.trust_env = trust_env
        return self._session

    def request(
        self,
        method: str,
        url: str,
        *,
        params: dict | None = None,
        data=None,
        json_body=None,
        headers: dict | None = None,
        timeout: int | float = 10,
    ) -> requests.Response:
        response = self.session().request(
            method,
            url,
            params=params,
            data=data,
            json=json_body,
            headers=headers,
            timeout=timeout,
        )
        response.raise_for_status()
        return response

    def request_json(self, method: str, url: str, **kwargs) -> dict:
        return cast(dict, self.request(method, url, **kwargs).json())
