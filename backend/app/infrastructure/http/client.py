import json
import threading
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.configuration import get_settings

_session: requests.Session | None = None
_session_lock = threading.Lock()


def _get_session() -> requests.Session:
    """Get or lazily create a shared requests.Session respecting http_trust_env setting.

    Param:
        None
    Return:
        the shared requests.Session instance
    """
    global _session
    if _session is not None:
        return _session
    with _session_lock:
        if _session is None:
            session = requests.Session()
            session.trust_env = get_settings().http_trust_env
            retry = Retry(
                total=2,
                connect=2,
                read=2,
                backoff_factor=0.3,
                status_forcelist=(429, 500, 502, 503, 504),
                allowed_methods=frozenset({"GET", "HEAD", "OPTIONS"}),
                raise_on_status=False,
            )
            adapter = HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=50)
            session.mount("http://", adapter)
            session.mount("https://", adapter)
            _session = session
    return _session


get_session = _get_session
"""Public alias for _get_session."""


def _reset_session() -> None:
    """Reset the cached session; call after http_trust_env is changed at runtime."""
    close_session()


def close_session() -> None:
    """关闭共享 HTTP 会话并释放连接池。"""
    global _session
    with _session_lock:
        session = _session
        _session = None
    if session is not None:
        session.close()


def request(
    method: str,
    url: str,
    *,
    params: dict | None = None,
    data: Any = None,
    json_body: Any = None,
    headers: dict | None = None,
    timeout: int | float = 10,
    allow_redirects: bool = True,
) -> requests.Response:
    """Send an HTTP request and raise on non-2xx status.

    Param:
        method: HTTP method (e.g. "GET", "POST")
        url: request URL
        params: optional query parameters
        data: optional request body data
        json_body: optional JSON-serializable body
        headers: optional request headers
        timeout: request timeout in seconds (default 10)
    Return:
        the requests.Response object with a successful status
    """
    request_options = {
        "params": params,
        "data": data,
        "json": json_body,
        "headers": headers,
        "timeout": timeout,
    }
    if not allow_redirects:
        request_options["allow_redirects"] = False
    response = _get_session().request(method, url, **request_options)
    response.raise_for_status()
    return response


def get(url: str, **kwargs) -> requests.Response:
    """Send an HTTP GET request via the shared session.

    Param:
        url: request URL
        **kwargs: forwarded to request()
    Return:
        the requests.Response object
    """
    return request("GET", url, **kwargs)


def post(url: str, **kwargs) -> requests.Response:
    """Send an HTTP POST request via the shared session.

    Param:
        url: request URL
        **kwargs: forwarded to request()
    Return:
        the requests.Response object
    """
    return request("POST", url, **kwargs)


def parse_text_json(response: requests.Response) -> Any:
    """Parse the response text as JSON after stripping whitespace.

    Param:
        response: requests.Response with JSON text body
    Return:
        parsed JSON value
    """
    return json.loads(response.text.strip())
