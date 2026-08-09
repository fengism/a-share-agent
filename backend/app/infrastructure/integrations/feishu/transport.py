"""飞书开放平台认证 HTTP 传输。"""

from collections.abc import Callable
from typing import Any

from app.infrastructure.integrations.feishu.auth import FeishuAuth


class FeishuTransport:
    def __init__(
        self,
        auth: FeishuAuth,
        session_provider: Callable[[], Any],
    ) -> None:
        self.auth = auth
        self._session_provider = session_provider

    @staticmethod
    def parse_response(response, error_prefix: str) -> dict:
        if response.status_code >= 400:
            raise RuntimeError(f"{error_prefix}: {response.text[:300]}")
        data = response.json()
        if data.get("code", -1) != 0:
            raise RuntimeError(f"{error_prefix}: {data.get('msg', 'unknown error')}")
        return data

    def post_json(
        self,
        url: str,
        body: dict,
        error_prefix: str,
        *,
        timeout: int = 10,
        params: dict | None = None,
    ) -> dict:
        response = self._session_provider().post(
            url,
            headers=self.auth.headers(),
            params=params,
            json=body,
            timeout=timeout,
        )
        return self.parse_response(response, error_prefix)

    def post(self, url: str, **kwargs):
        return self._session_provider().post(
            url,
            headers=self.auth.headers(),
            **kwargs,
        )

    def delete(self, url: str, **kwargs):
        return self._session_provider().delete(
            url,
            headers=self.auth.headers(),
            **kwargs,
        )
