"""百度股市通 HTTP 传输实现。"""

import logging
from collections.abc import Callable

import requests

from app.constants.http import BD_HEADERS_WITH_COOKIE

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://finance.pae.baidu.com"
DEFAULT_TIMEOUT = 10


class BaiduTransport:
    def __init__(
        self,
        *,
        credentials_provider: Callable[[], tuple[str, str]],
        session: requests.Session | None = None,
    ) -> None:
        self.default_headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Referer": "https://gushitong.baidu.com",
            "Accept": "application/json",
            "Origin": "https://gushitong.baidu.com",
            "Host": "finance.pae.baidu.com",
        }
        self._session = session or requests.Session()
        self._session.trust_env = False
        self._credentials_provider = credentials_provider

    def _request_headers(self) -> dict[str, str]:
        headers = dict(self.default_headers)
        _, acs_token = self._credentials_provider()
        if acs_token.strip():
            headers["acs-token"] = acs_token.strip()
        return headers

    def cookie_headers(self) -> dict[str, str]:
        headers = self._request_headers()
        headers.update(BD_HEADERS_WITH_COOKIE)
        cookie, _ = self._credentials_provider()
        if cookie:
            headers["cookie"] = cookie
        return headers

    def get_json(
        self,
        path: str,
        params: dict,
        headers: dict | None = None,
        timeout: int | None = None,
    ) -> dict:
        url = path if path.startswith("http") else f"{DEFAULT_BASE_URL}{path}"
        effective_headers = headers or self._request_headers()
        logger.debug("Baidu request: %s, headers_keys=%s", url, list(effective_headers))
        response = self._session.get(
            url,
            params=params,
            headers=effective_headers,
            timeout=timeout or DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()


def check_result_code(data: dict) -> None:
    if str(data.get("ResultCode", -1)) != "0":
        raise RuntimeError(f"百度PAE错误: {data}")
